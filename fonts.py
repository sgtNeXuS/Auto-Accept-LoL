"""Registers the bundled Space Grotesk / JetBrains Mono fonts for private,
in-process use, so the packaged app renders the intended typeface without
requiring the user to have it installed system-wide.

Space Grotesk is SIL OFL 1.1 licensed, JetBrains Mono is Apache 2.0 - both
license texts ship alongside the font files in assets/fonts/.
"""

import ctypes
import os
import platform
import sys

HEADING_FONT = "Space Grotesk"
MONO_FONT = "JetBrains Mono"

_FONT_FILES = [
    "SpaceGrotesk-Regular.otf",
    "SpaceGrotesk-Medium.otf",
    "SpaceGrotesk-Bold.otf",
    "JetBrainsMono-Regular.ttf",
    "JetBrainsMono-Medium.ttf",
    "JetBrainsMono-Bold.ttf",
]


def _font_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "assets", "fonts")


def _register_windows(path):
    FR_PRIVATE = 0x10
    ctypes.windll.gdi32.AddFontResourceExW(path, FR_PRIVATE, 0)


def _register_macos(path):
    import ctypes.util

    core_text = ctypes.CDLL(ctypes.util.find_library("CoreText"))
    core_foundation = ctypes.CDLL(ctypes.util.find_library("CoreFoundation"))

    core_foundation.CFURLCreateFromFileSystemRepresentation.restype = ctypes.c_void_p
    core_foundation.CFURLCreateFromFileSystemRepresentation.argtypes = [
        ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_bool,
    ]
    path_bytes = path.encode("utf-8")
    url = core_foundation.CFURLCreateFromFileSystemRepresentation(None, path_bytes, len(path_bytes), False)
    if not url:
        return

    core_text.CTFontManagerRegisterFontsForURL.restype = ctypes.c_bool
    core_text.CTFontManagerRegisterFontsForURL.argtypes = [
        ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
    ]
    kCTFontManagerScopeProcess = 1
    error = ctypes.c_void_p()
    core_text.CTFontManagerRegisterFontsForURL(url, kCTFontManagerScopeProcess, ctypes.byref(error))


def register_bundled_fonts():
    """Best-effort, in-process font registration. Never raises - if
    registration fails (or the platform isn't supported) Tk silently
    substitutes a default font instead of crashing."""
    font_dir = _font_dir()
    system = platform.system()
    if system not in ("Windows", "Darwin"):
        return
    for filename in _FONT_FILES:
        path = os.path.join(font_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            if system == "Windows":
                _register_windows(path)
            else:
                _register_macos(path)
        except OSError:
            pass
