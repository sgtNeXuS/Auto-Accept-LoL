import os
import ssl
import time
import base64
import psutil
import requests
import threading
from urllib3.exceptions import InsecureRequestWarning

# Suppress LCU self-signed certificate warning hooks
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Core Color Palette Mapping
BLUE = "\033[94m"
GOLD = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"
CLEAR_SCREEN = "\033[H\033[J"

# Global Interface State Anchors
current_status = "WAITING FOR LEAGUE CLIENT..."
status_color = BLUE
detected_tools = []
exit_flag = False

def get_width():
    """Dynamically monitors active command line rendering bounds."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80

def check_moba_tools():
    """Scans operating tree structures for active target overlay platforms."""
    global detected_tools
    tools_map = {
        "blitz": "Blitz App",
        "mobalytics": "Mobalytics",
        "porofessor": "Porofessor",
        "u.gg": "U.GG Desktop App"
    }
    found = []
    for process in psutil.process_iter(['name']):
        try:
            p_name = process.info['name']
            if p_name:
                p_name_lower = p_name.lower()
                for key, display in tools_map.items():
                    if key in p_name_lower and display not in found:
                        found.append(display)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    detected_tools = found

def draw_interface(scroll_step):
    """Refreshes and draws the entire console interface panel."""
    w = get_width()
    
    # 1. Print Header
    print(f"{BLUE}{BOLD}" + "=" * w + f"{RESET}")
    print(f"{GOLD}{BOLD}{'League of Legends Auto Accept by NeXuS'.center(w)}{RESET}")
    print(f"{BLUE}{BOLD}" + "=" * w + f"{RESET}")

    # 2. Print Context-Aware Tools Panel (Only draws if tools exist)
    if detected_tools:
        tools_str = f"COMPANION PLUGINS DETECTED: {', '.join(detected_tools)}"
        print(f"{GREEN}{BOLD}{tools_str.center(w)}{RESET}")
        print(f"{BLUE}" + "-" * w + f"{RESET}")

    # 3. Handle Text Scroll Engine Logic
    display_text = f"  ::: {current_status} :::  "
    text_len = len(display_text)
    
    # Build a continuous marquee string that fills the console width
    repeated_text = (display_text * ((w // text_len) + 2))
    start_idx = scroll_step % text_len
    marquee_slice = repeated_text[start_idx : start_idx + w]
    
    if len(marquee_slice) < w:
        marquee_slice += " " * (w - len(marquee_slice))

    print(f"{status_color}{BOLD}{marquee_slice}{RESET}")
    print(f"{BLUE}{BOLD}" + "=" * w + f"{RESET}")

def ui_loop():
    """Main UI thread executing frame refresh tracking ticks."""
    global exit_flag
    scroll_step = 0
    while not exit_flag:
        print("\033[H", end="") 
        draw_interface(scroll_step)
        scroll_step += 1
        time.sleep(0.12)

def get_lcu_credentials():
    """Dynamically targets and hooks parameters inside running client stacks."""
    for process in psutil.process_iter(['name', 'cmdline']):
        try:
            if process.info['name'] in ['LeagueClientUx.exe', 'LeagueClientUx']:
                cmdline = process.info['cmdline']
                port, token = None, None
                if not cmdline:
                    continue
                for arg in cmdline:
                    if '--app-port=' in arg:
                        port = arg.split('=')[1]
                    if '--remoting-auth-token=' in arg:
                        token = arg.split('=')[1]
                if port and token:
                    return port, token
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return None, None

def wait_for_game_to_end():
    """Dormant processing engine validation loop."""
    global current_status, status_color
    current_status = "MATCH IN PROGRESS - ENGINE SLEEPING"
    status_color = BLUE
    while True:
        game_running = False
        for process in psutil.process_iter(['name']):
            try:
                if process.info['name'] in ['League of Legends.exe', 'League of Legends']:
                    game_running = True
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        if not game_running:
            break
        time.sleep(5)

def backend_worker():
    """Asynchronous network interceptor monitoring the local API runtime."""
    global current_status, status_color, exit_flag
    
    check_moba_tools()

    while not exit_flag:
        current_status = "WAITING FOR LEAGUE CLIENT TO LAUNCH"
        status_color = BLUE
        port, token = None, None
        
        while not port or not token:
            port, token = get_lcu_credentials()
            if not port:
                time.sleep(2)

        encoded_auth = base64.b64encode(f"riot:{token}".encode('utf-8')).decode('utf-8')
        headers = {
            'Authorization': f'Basic {encoded_auth}',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }
        base_url = f"https://127.0.0.1:{port}"
        client_connected = True

        while client_connected:
            try:
                # Get the core gameflow phase
                phase_resp = requests.get(f"{base_url}/lol-gameflow/v1/gameflow-phase", headers=headers, verify=False)
                
                if phase_resp.status_code == 200:
                    phase = phase_resp.json()
                    
                    if phase in ["Lobby", "None"]:
                        # Check the actual matchmaking search endpoint to distinguish "idle" vs "searching"
                        search_resp = requests.get(f"{base_url}/lol-lobby/v2/lobby/matchmaking/search-state", headers=headers, verify=False)
                        is_searching = False
                        
                        if search_resp.status_code == 200:
                            search_state = search_resp.json().get('searchState', '')
                            if search_state == "Searching":
                                is_searching = True
                        
                        # State 1 vs State 2 Selection
                        if is_searching:
                            current_status = "IN QUEUE - SEARCHING FOR MATCH"
                            status_color = BLUE
                        else:
                            current_status = "PRESS FIND MATCH TO START SEARCH"
                            status_color = BLUE
                    
                    elif phase == "Matchmaking":
                        current_status = "IN QUEUE - SEARCHING FOR MATCH"
                        status_color = BLUE
                    
                    # State 3: Match Found!
                    elif phase == "ReadyCheck":
                        current_status = "MATCH FOUND! AUTO ACCEPTING..."
                        status_color = GOLD
                        
                        accept_req = requests.post(f"{base_url}/lol-matchmaking/v1/ready-check/accept", headers=headers, verify=False)
                        if accept_req.status_code == 204:
                            current_status = "GAME ACCEPTED!"
                            status_color = GREEN
                        time.sleep(4)
                        
                    elif phase == "ChampSelect":
                        current_status = "CHAMPION SELECT IN PROGRESS"
                        status_color = GREEN
                        
                    elif phase == "InProgress":
                        wait_for_game_to_end()
                        check_moba_tools() 
                        client_connected = False
                        break
                else:
                    client_connected = False
                    break
            except requests.exceptions.RequestException:
                time.sleep(2)
                game_active = False
                for process in psutil.process_iter(['name']):
                    try:
                        if process.info['name'] in ['League of Legends.exe', 'League of Legends']:
                            game_active = True
                            break
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass
                if game_active:
                    wait_for_game_to_end()
                    check_moba_tools()
                client_connected = False
                break
            time.sleep(1)

if __name__ == "__main__":
    os.system("")
    print(CLEAR_SCREEN, end="")
    
    backend_thread = threading.Thread(target=backend_worker, daemon=True)
    backend_thread.start()
    
    try:
        ui_loop()
    except KeyboardInterrupt:
        exit_flag = True
        print(CLEAR_SCREEN, end="")
        print(f"\n{RED}[*] Shutting down NeXuS Auto Accept engine safely.{RESET}")