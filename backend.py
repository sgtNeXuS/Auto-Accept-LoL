"""Background engine for NeXuS Auto Accept.

Polls the League client (LCU) API and auto-accepts ready checks. Runs on its
own thread and reports state back to a UI via an ``on_event(kind, payload)``
callback, so it has no direct dependency on any particular UI toolkit.
"""

import os
import sys
import json
import time
import base64
import platform
import threading
import subprocess
from pathlib import Path

import psutil
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# PyInstaller onefile builds unpack bundled data (--add-data) to sys._MEIPASS
# at runtime rather than next to the script, so resolve assets relative to that.
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
READY_SOUND_PATH = os.path.join(BASE_DIR, "assets", "readysound.mp3")

CONFIG_DIR = Path.home() / ".nexus_auto_accept"
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULT_CONFIG = {
    "auto_accept_enabled": True,
    "play_sound": True,
    "show_notification": True,
    "launch_on_startup": False,
}

MOBA_TOOLS_MAP = {
    "blitz": "Blitz App",
    "mobalytics": "Mobalytics",
    "porofessor": "Porofessor",
    "u.gg": "U.GG Desktop App",
}

LEAGUE_CLIENT_NAMES = {"LeagueClientUx.exe", "LeagueClientUx"}
LEAGUE_GAME_NAMES = {"League of Legends.exe", "League of Legends"}

READY_CHECK_TIMEOUT = 12  # safety cap, seconds
READY_CHECK_POLL_INTERVAL = 0.4


def load_config():
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text())
            cfg = DEFAULT_CONFIG.copy()
            cfg.update({k: v for k, v in data.items() if k in DEFAULT_CONFIG})
            return cfg
    except (OSError, json.JSONDecodeError):
        pass
    return DEFAULT_CONFIG.copy()


def save_config(cfg):
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    except OSError:
        pass


def play_sound():
    """Best-effort notification chime. Never raises."""
    try:
        system = platform.system()
        if system == "Windows":
            # winsound only handles uncompressed WAV, so drive the MCI API
            # (stdlib ctypes, no extra dependency) to play the MP3 directly.
            import ctypes
            mci = ctypes.windll.winmm.mciSendStringW
            mci("close readysound", None, 0, None)
            mci(f'open "{READY_SOUND_PATH}" type mpegvideo alias readysound', None, 0, None)
            mci("play readysound", None, 0, None)
        elif system == "Darwin":
            subprocess.run(
                ["afplay", READY_SOUND_PATH],
                check=False, capture_output=True,
            )
        else:
            subprocess.run(
                ["mpg123", "-q", READY_SOUND_PATH],
                check=False, capture_output=True,
            )
    except Exception:
        pass


def show_notification(title, message):
    """Best-effort desktop toast. Never raises."""
    try:
        from plyer import notification
        notification.notify(title=title, message=message, app_name="NeXuS Auto Accept", timeout=5)
    except Exception:
        pass


def set_launch_on_startup(enabled):
    """Windows-only: add/remove a HKCU Run key entry. Returns True on success."""
    if platform.system() != "Windows":
        return False
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Run",
            0, winreg.KEY_SET_VALUE,
        )
        if enabled:
            exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(__file__)
            winreg.SetValueEx(key, "NeXuSAutoAccept", 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, "NeXuSAutoAccept")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError:
        return False


class Engine:
    def __init__(self, on_event):
        """on_event(kind, payload) is called from the background thread and
        must be safe to call from a non-UI thread (e.g. it should push onto
        a queue.Queue rather than touch widgets directly)."""
        self.on_event = on_event
        self.config = load_config()
        self.detected_tools = []
        self._exit = threading.Event()
        self._thread = None

    # -- lifecycle -----------------------------------------------------
    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._exit.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._exit.set()

    # -- settings --------------------------------------------------------
    def is_paused(self):
        return not self.config.get("auto_accept_enabled", True)

    def set_paused(self, paused):
        self.config["auto_accept_enabled"] = not paused
        save_config(self.config)

    def update_setting(self, key, value):
        self.config[key] = value
        save_config(self.config)
        if key == "launch_on_startup":
            set_launch_on_startup(value)

    # -- helpers -----------------------------------------------------------
    def _emit_status(self, text, kind="info"):
        self.on_event("status", {"text": text, "kind": kind})

    def _log(self, text):
        self.on_event("log", {"text": text, "time": time.strftime("%H:%M:%S")})

    def _check_moba_tools(self):
        found = []
        for process in psutil.process_iter(["name"]):
            try:
                p_name = process.info["name"]
                if not p_name:
                    continue
                p_name_lower = p_name.lower()
                for key, display in MOBA_TOOLS_MAP.items():
                    if key in p_name_lower and display not in found:
                        found.append(display)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if found != self.detected_tools:
            self.detected_tools = found
            self.on_event("tools", {"tools": found})

    def _is_game_running(self):
        for process in psutil.process_iter(["name"]):
            try:
                if process.info["name"] in LEAGUE_GAME_NAMES:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def _get_lcu_credentials(self):
        for process in psutil.process_iter(["name", "cmdline"]):
            try:
                if process.info["name"] not in LEAGUE_CLIENT_NAMES:
                    continue
                cmdline = process.info["cmdline"]
                if not cmdline:
                    continue
                port, token = None, None
                for arg in cmdline:
                    if "--app-port=" in arg:
                        port = arg.split("=")[1]
                    if "--remoting-auth-token=" in arg:
                        token = arg.split("=")[1]
                if port and token:
                    return port, token
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return None, None

    def _get_phase(self, base_url, headers):
        try:
            r = requests.get(f"{base_url}/lol-gameflow/v1/gameflow-phase", headers=headers, verify=False, timeout=3)
            if r.status_code == 200:
                return r.json()
        except requests.exceptions.RequestException:
            pass
        return None

    def _notify_match_found(self):
        if self.config.get("play_sound", True):
            threading.Thread(target=play_sound, daemon=True).start()
        if self.config.get("show_notification", True):
            threading.Thread(
                target=show_notification,
                args=("NeXuS Auto Accept", "Ready check! A match has been found."),
                daemon=True,
            ).start()

    def _wait_for_game_to_end(self):
        self._emit_status("MATCH IN PROGRESS - ENGINE SLEEPING", "info")
        while not self._exit.is_set():
            if not self._is_game_running():
                break
            time.sleep(5)

    def _handle_ready_check(self, base_url, headers):
        auto_accept = self.config.get("auto_accept_enabled", True)
        if auto_accept:
            self._emit_status("MATCH FOUND! AUTO ACCEPTING...", "gold")
            self._log("Ready check detected - accepting")
        else:
            self._emit_status("MATCH FOUND! AUTO-ACCEPT PAUSED", "gold")
            self._log("Ready check detected - auto-accept is paused, accept manually")
        self._notify_match_found()

        if not auto_accept:
            while not self._exit.is_set() and self._get_phase(base_url, headers) == "ReadyCheck":
                time.sleep(0.5)
            return

        deadline = time.time() + READY_CHECK_TIMEOUT
        accepted = False
        while not self._exit.is_set() and time.time() < deadline:
            phase = self._get_phase(base_url, headers)
            if phase != "ReadyCheck":
                accepted = True
                break
            try:
                rc = requests.get(f"{base_url}/lol-matchmaking/v1/ready-check", headers=headers, verify=False, timeout=3)
                if rc.status_code == 200 and rc.json().get("playerResponse") == "Accepted":
                    accepted = True
                    break
            except requests.exceptions.RequestException:
                pass
            try:
                requests.post(f"{base_url}/lol-matchmaking/v1/ready-check/accept", headers=headers, verify=False, timeout=3)
            except requests.exceptions.RequestException:
                pass
            time.sleep(READY_CHECK_POLL_INTERVAL)

        if accepted:
            self._emit_status("GAME ACCEPTED!", "green")
            self._log("Accept confirmed")
        else:
            self._emit_status("ACCEPT FAILED - CHECK CLIENT", "red")
            self._log("Could not confirm accept within timeout - check the client")

    # -- main loop -----------------------------------------------------
    def _run(self):
        self._emit_status("WAITING FOR LEAGUE CLIENT...", "info")
        self._check_moba_tools()

        while not self._exit.is_set():
            self._emit_status("WAITING FOR LEAGUE CLIENT TO LAUNCH", "info")
            port, token = None, None
            while not (port and token) and not self._exit.is_set():
                port, token = self._get_lcu_credentials()
                if not port:
                    time.sleep(2)
            if self._exit.is_set():
                break

            self._log("League client detected - connected")
            encoded_auth = base64.b64encode(f"riot:{token}".encode("utf-8")).decode("utf-8")
            headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
            base_url = f"https://127.0.0.1:{port}"
            client_connected = True

            while client_connected and not self._exit.is_set():
                try:
                    phase = self._get_phase(base_url, headers)
                    if phase is None:
                        client_connected = False
                        break

                    if phase in ("Lobby", "None"):
                        is_searching = False
                        try:
                            sr = requests.get(
                                f"{base_url}/lol-lobby/v2/lobby/matchmaking/search-state",
                                headers=headers, verify=False, timeout=3,
                            )
                            if sr.status_code == 200 and sr.json().get("searchState") == "Searching":
                                is_searching = True
                        except requests.exceptions.RequestException:
                            pass
                        if is_searching:
                            self._emit_status("IN QUEUE - SEARCHING FOR MATCH", "info")
                        else:
                            self._emit_status("PRESS FIND MATCH TO START SEARCH", "info")
                    elif phase == "Matchmaking":
                        self._emit_status("IN QUEUE - SEARCHING FOR MATCH", "info")
                    elif phase == "ReadyCheck":
                        self._handle_ready_check(base_url, headers)
                    elif phase == "ChampSelect":
                        self._emit_status("CHAMPION SELECT IN PROGRESS", "green")
                    elif phase == "InProgress":
                        self._wait_for_game_to_end()
                        self._check_moba_tools()
                        client_connected = False
                        break
                    else:
                        self._emit_status(phase.upper() if phase else "UNKNOWN STATE", "info")
                except requests.exceptions.RequestException:
                    time.sleep(2)
                    if self._is_game_running():
                        self._wait_for_game_to_end()
                        self._check_moba_tools()
                    client_connected = False
                    break
                time.sleep(1)

        self._log("Engine stopped")
