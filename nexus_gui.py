"""NeXuS Auto Accept - GUI

A dark-themed desktop app that watches the League client and auto-accepts
ready checks. Wraps the background polling logic in backend.Engine.
"""

import os
import platform
import queue
import sys
import threading
import time

import customtkinter as ctk

from backend import Engine, play_sound
from fonts import HEADING_FONT, MONO_FONT, register_bundled_fonts
from version import VERSION

APP_NAME = "NeXuS Auto Accept"
# PyInstaller onefile builds unpack bundled data (--add-data) to sys._MEIPASS
# at runtime rather than next to the script, so resolve assets relative to that.
BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ICON_PNG = os.path.join(BASE_DIR, "NeXusMagic.png")
ICON_ICO = os.path.join(BASE_DIR, "NeXusMagic.ico")
HEADER_LOGO_PNG = os.path.join(BASE_DIR, "assets", "icons", "icon-36.png")
TOOL_LOGOS_DIR = os.path.join(BASE_DIR, "assets", "tools")
TOOL_LOGO_FILES = {
    "Blitz App": "blitz.png",
    "Mobalytics": "mobalytics.png",
    "Porofessor": "porofessor.png",
    "U.GG Desktop App": "ugg.png",
}

# League-inspired dark palette
COLOR_BG = "#0A1428"
COLOR_PANEL = "#1E2328"
COLOR_TEXT = "#F0E6D2"
COLOR_MUTED = "#A09B8C"
COLOR_BLUE = "#0AC8B9"
COLOR_GOLD = "#C8AA6E"
COLOR_GREEN = "#2ECC71"
COLOR_RED = "#E84057"

STATUS_COLORS = {
    "info": COLOR_BLUE,
    "gold": COLOR_GOLD,
    "green": COLOR_GREEN,
    "red": COLOR_RED,
}
# Light badge backgrounds read best with dark text; the red "failed" badge
# needs the light text instead.
STATUS_TEXT_COLORS = {
    "info": COLOR_BG,
    "gold": COLOR_BG,
    "green": COLOR_BG,
    "red": COLOR_TEXT,
}
BADGE_CHIP_BG = COLOR_PANEL


def tracked(text, gap=" "):
    """Letter-space a short label, e.g. 'STATUS' -> 'S T A T U S' (thin spaces)."""
    return gap.join(text)


ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")
register_bundled_fonts()


def _apply_window_icon(window, delayed=False):
    """Set the app icon on a Tk/CTk window.

    CTkToplevel resets its icon to Tk's default right after creation, so
    Toplevels need the call deferred a tick (via `after`) or it gets
    clobbered.
    """
    def _set():
        try:
            if platform.system() == "Windows" and os.path.exists(ICON_ICO):
                window.iconbitmap(ICON_ICO)
        except Exception:
            pass
        try:
            if os.path.exists(ICON_PNG):
                from PIL import Image, ImageTk
                img = Image.open(ICON_PNG)
                window._icon_photo = ImageTk.PhotoImage(img)
                window.iconphoto(True, window._icon_photo)
        except Exception:
            pass

    if delayed:
        window.after(250, _set)
    else:
        _set()


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, engine: Engine):
        super().__init__(master)
        self.engine = engine
        self.title("Settings")
        self.geometry("340x350")
        self.resizable(False, False)
        self.configure(fg_color=COLOR_BG)
        self.transient(master)
        _apply_window_icon(self, delayed=True)
        self.grab_set()

        ctk.CTkLabel(
            self, text="Settings", font=ctk.CTkFont(family=HEADING_FONT, size=18, weight="bold"), text_color=COLOR_GOLD
        ).pack(pady=(16, 8))

        self._add_switch("play_sound", "Play sound on match found")
        self._add_volume_slider()
        self._add_switch("show_notification", "Show desktop notification")

        startup_switch = self._add_switch("launch_on_startup", "Launch on Windows startup")
        if platform.system() != "Windows":
            startup_switch.configure(state="disabled")
            ctk.CTkLabel(
                self, text="(Windows only)", font=ctk.CTkFont(size=11), text_color=COLOR_MUTED
            ).pack()

        ctk.CTkButton(self, text="Close", command=self.destroy, fg_color=COLOR_PANEL).pack(pady=(16, 4))
        ctk.CTkLabel(
            self, text=f"v{VERSION}", font=ctk.CTkFont(size=10), text_color=COLOR_MUTED
        ).pack(pady=(0, 8))

    def _add_switch(self, key, label):
        var = ctk.BooleanVar(value=self.engine.config.get(key, True))

        def on_toggle():
            self.engine.update_setting(key, var.get())

        switch = ctk.CTkSwitch(
            self, text=label, variable=var, command=on_toggle,
            progress_color=COLOR_BLUE, text_color=COLOR_TEXT,
        )
        switch.pack(anchor="w", padx=24, pady=6)
        return switch

    def _add_volume_slider(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=(0, 10))

        header = ctk.CTkFrame(row, fg_color="transparent")
        header.pack(fill="x")
        ctk.CTkLabel(header, text="Volume", text_color=COLOR_MUTED, font=ctk.CTkFont(size=12)).pack(side="left")
        value_label = ctk.CTkLabel(
            header, text=f"{int(self.engine.config.get('sound_volume', 0.2) * 100)}%",
            text_color=COLOR_MUTED, font=ctk.CTkFont(size=12),
        )
        value_label.pack(side="right")

        def on_move(value):
            value_label.configure(text=f"{int(float(value) * 100)}%")

        def on_release(_event=None):
            volume = round(slider.get(), 2)
            self.engine.update_setting("sound_volume", volume)
            # Preview so the user can hear the level they just picked.
            threading.Thread(target=play_sound, args=(volume,), daemon=True).start()

        slider = ctk.CTkSlider(
            row, from_=0.0, to=1.0, number_of_steps=20, command=on_move,
            progress_color=COLOR_BLUE, button_color=COLOR_GOLD, button_hover_color="#B0925C",
        )
        slider.set(self.engine.config.get("sound_volume", 0.2))
        slider.pack(fill="x", pady=(6, 0))
        slider.bind("<ButtonRelease-1>", on_release)


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{APP_NAME} v{VERSION}")
        self.geometry("480x580")
        self.minsize(440, 500)
        self.configure(fg_color=COLOR_BG)
        self._set_icon()

        self.events = queue.Queue()
        self.engine = Engine(on_event=self._on_engine_event)

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.engine.start()
        self.after(100, self._poll_events)

    def _set_icon(self):
        _apply_window_icon(self)

    # -- UI construction -------------------------------------------------
    def _build_ui(self):
        header = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=12)
        header.pack(fill="x", padx=16, pady=(16, 8))

        logo_source = HEADER_LOGO_PNG if os.path.exists(HEADER_LOGO_PNG) else ICON_PNG
        if os.path.exists(logo_source):
            from PIL import Image
            logo_img = Image.open(logo_source)
            self.logo_image = ctk.CTkImage(light_image=logo_img, dark_image=logo_img, size=(36, 36))
            ctk.CTkLabel(header, image=self.logo_image, text="").pack(side="left", padx=(16, 10), pady=12)

        ctk.CTkLabel(
            header, text=APP_NAME, font=ctk.CTkFont(family=HEADING_FONT, size=20, weight="bold"), text_color=COLOR_GOLD
        ).pack(side="left", pady=12)

        ctk.CTkButton(
            header, text="⚙", width=32, height=32, fg_color=BADGE_CHIP_BG,
            hover_color="#2A2F36", command=self._open_settings,
        ).pack(side="right", padx=16, pady=12)

        # Companion tools strip - detected app logos, sits right under the header.
        # Packed/unpacked dynamically depending on what's detected.
        self._tool_icon_images = {}
        self.tools_frame = ctk.CTkFrame(self, fg_color="transparent")
        ctk.CTkLabel(
            self.tools_frame, text=tracked("DETECTED"), font=ctk.CTkFont(family=MONO_FONT, size=10, weight="bold"),
            text_color=COLOR_MUTED,
        ).pack(side="left", padx=(0, 10))
        self.tools_icons_row = ctk.CTkFrame(self.tools_frame, fg_color="transparent")
        self.tools_icons_row.pack(side="left")

        # Status badge - two-tone "STATUS | VALUE" pill, matching assets/status-badges.png
        self.status_card = ctk.CTkFrame(self, fg_color="transparent")
        self.status_card.pack(fill="x", padx=16, pady=8)

        self.status_chip = ctk.CTkFrame(self.status_card, fg_color=BADGE_CHIP_BG, corner_radius=8)
        self.status_chip.pack(side="left", fill="y")
        ctk.CTkLabel(
            self.status_chip, text=tracked("STATUS"), font=ctk.CTkFont(family=MONO_FONT, size=13, weight="bold"),
            text_color=COLOR_MUTED,
        ).pack(padx=16, pady=14)

        self.status_value_chip = ctk.CTkFrame(self.status_card, fg_color=COLOR_BLUE, corner_radius=8)
        self.status_value_chip.pack(side="left", padx=(3, 0), fill="both", expand=True)
        self.status_label = ctk.CTkLabel(
            self.status_value_chip, text="STARTING...", font=ctk.CTkFont(family=MONO_FONT, size=13, weight="bold"),
            text_color=COLOR_BG, justify="left",
        )
        self.status_label.pack(padx=16, pady=14, fill="x")
        # Keep the status text wrapped within the chip's actual rendered
        # width (a fixed guess clips or overflows depending on window size).
        self.status_value_chip.bind("<Configure>", self._on_status_chip_resize)

        # Champion select panel - shows teammates' picks, only shown while
        # champ select is active. Kept collapsed the rest of the time so it
        # doesn't reserve dead space in the layout.
        self.champ_frame = ctk.CTkFrame(self, fg_color=COLOR_PANEL, corner_radius=12)
        ctk.CTkLabel(
            self.champ_frame, text=tracked("CHAMPION SELECT"), font=ctk.CTkFont(family=MONO_FONT, size=11, weight="bold"),
            text_color=COLOR_MUTED,
        ).pack(anchor="w", padx=12, pady=(10, 4))
        self.champ_list_frame = ctk.CTkFrame(self.champ_frame, fg_color="transparent")
        self.champ_list_frame.pack(fill="x", padx=12, pady=(0, 10))

        # Activity log
        self._log_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._log_frame.pack(fill="both", expand=True, padx=16, pady=8)

        ctk.CTkLabel(
            self._log_frame, text=tracked("ACTIVITY LOG"),
            font=ctk.CTkFont(family=MONO_FONT, size=11, weight="bold"), text_color=COLOR_MUTED,
        ).pack(anchor="w")

        self.log_box = ctk.CTkTextbox(
            self._log_frame, fg_color=COLOR_PANEL, text_color=COLOR_TEXT, font=ctk.CTkFont(family=MONO_FONT, size=12),
            wrap="word", state="disabled",
        )
        self.log_box.pack(fill="both", expand=True, pady=(4, 0))

        # Footer controls
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=16)

        self.pause_button = ctk.CTkButton(
            footer, text="⏸ Pause Auto-Accept", command=self._toggle_pause,
            fg_color=COLOR_BLUE, hover_color="#089385", text_color="#0A1428",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        self.pause_button.pack(fill="x")
        self._sync_pause_button()

    def _on_status_chip_resize(self, event):
        self.status_label.configure(wraplength=max(event.width - 32, 60))

    def _open_settings(self):
        SettingsWindow(self, self.engine)

    def _toggle_pause(self):
        self.engine.set_paused(not self.engine.is_paused())
        self._sync_pause_button()
        self._append_log(time.strftime("%H:%M:%S"), "Auto-accept paused" if self.engine.is_paused() else "Auto-accept resumed")

    def _sync_pause_button(self):
        if self.engine.is_paused():
            self.pause_button.configure(text="▶ Resume Auto-Accept", fg_color=COLOR_GOLD, hover_color="#B0925C")
        else:
            self.pause_button.configure(text="⏸ Pause Auto-Accept", fg_color=COLOR_BLUE, hover_color="#089385")

    # -- engine event handling -------------------------------------------
    def _on_engine_event(self, kind, payload):
        self.events.put((kind, payload))

    def _poll_events(self):
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "status":
                    self._apply_status(payload["text"], payload["kind"])
                elif kind == "log":
                    self._append_log(payload["time"], payload["text"])
                elif kind == "tools":
                    self._apply_tools(payload["tools"])
                elif kind == "champ_select":
                    self._apply_champ_select(payload["champions"])
        except queue.Empty:
            pass
        self.after(100, self._poll_events)

    def _apply_status(self, text, kind):
        self.status_label.configure(text=text, text_color=STATUS_TEXT_COLORS.get(kind, COLOR_BG))
        self.status_value_chip.configure(fg_color=STATUS_COLORS.get(kind, COLOR_BLUE))

    def _append_log(self, timestamp, text):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"{timestamp}  {text}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _apply_tools(self, tools):
        for child in self.tools_icons_row.winfo_children():
            child.destroy()

        if not tools:
            self.tools_frame.pack_forget()
            return

        for name in tools:
            filename = TOOL_LOGO_FILES.get(name)
            if not filename:
                continue
            path = os.path.join(TOOL_LOGOS_DIR, filename)
            if not os.path.exists(path):
                continue
            if name not in self._tool_icon_images:
                from PIL import Image
                img = Image.open(path)
                self._tool_icon_images[name] = ctk.CTkImage(light_image=img, dark_image=img, size=(28, 28))
            chip = ctk.CTkFrame(self.tools_icons_row, fg_color=BADGE_CHIP_BG, corner_radius=6)
            chip.pack(side="left", padx=(0, 6))
            ctk.CTkLabel(chip, image=self._tool_icon_images[name], text="").pack(padx=5, pady=5)

        self.tools_frame.pack(fill="x", padx=16, pady=(0, 8), before=self.status_card)

    def _apply_champ_select(self, champions):
        for child in self.champ_list_frame.winfo_children():
            child.destroy()

        if not champions:
            self.champ_frame.pack_forget()
            return

        for name in champions:
            chip = ctk.CTkFrame(self.champ_list_frame, fg_color=BADGE_CHIP_BG, corner_radius=6)
            chip.pack(side="left", padx=(0, 6), pady=2)
            ctk.CTkLabel(
                chip, text=name or "—", font=ctk.CTkFont(family=MONO_FONT, size=11), text_color=COLOR_TEXT,
            ).pack(padx=8, pady=4)

        self.champ_frame.pack(fill="x", padx=16, pady=(0, 8), before=self._log_frame)

    def _on_close(self):
        self.engine.stop()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
