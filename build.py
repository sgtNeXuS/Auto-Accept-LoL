import os
import sys
import subprocess
from PIL import Image

def convert_png_to_ico(png_path="icon.png", ico_path="NeXusMagic.ico"):
    """Converts a user-provided PNG file into a multi-resolution Windows ICO structure."""
    if not os.path.exists(png_path):
        raise FileNotFoundError(f"[-] Critical: '{png_path}' was not found in this folder. Please place your icon image here.")
        
    print(f"[*] Found source asset '{png_path}'. Translating to Windows layout...")
    img = Image.open(png_path)
    
    # Generate standard Windows desktop scaling profiles for pristine rendering
    sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    img.save(ico_path, format="ICO", sizes=sizes)
    print(f"[✓] Icon successfully compiled and saved to: {ico_path}")

def compile_to_exe(gui=True):
    png_source = "NeXusMagic.png"
    final_ico = "NeXusMagic.ico"
    script_name = "nexus_gui.py" if gui else "nexus_magic.py"
    exe_name = "NeXuS_Auto_Accept"

    try:
        # 1. Translate the PNG into the permanent NeXusMagic.ico file
        convert_png_to_ico(png_source, final_ico)

        # 2. Structure compiler variables
        data_sep = ";" if os.name == "nt" else ":"
        command = [
            "pyinstaller",
            "--onefile",
            f"--icon={final_ico}",
            f"--name={exe_name}",
        ]
        if gui:
            # No console window, and bundle the logo/icon assets the GUI loads at runtime.
            command += [
                "--windowed",
                f"--add-data={png_source}{data_sep}.",
                f"--add-data=assets{data_sep}assets",
            ]
        command.append(script_name)

        # 3. Compile the payload
        print(f"[*] Initializing compiler tracking for {script_name}...")
        subprocess.run(command, check=True)
        kind = "GUI" if gui else "console"
        print(f"\n{'-'*60}\n[✓] SUCCESS! Standalone {kind} application compiled with custom branding.")
        print(f"File path: dist/{exe_name}.exe")
        print(f"[✓] Note: Your permanent icon file is available at: ./{final_ico}")

    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Error: PyInstaller build routine halted (exit code {e.returncode}).")
        sys.exit(1)

if __name__ == "__main__":
    compile_to_exe(gui="--console" not in sys.argv)