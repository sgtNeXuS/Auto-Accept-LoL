import os
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

def compile_to_exe():
    png_source = "NeXusMagic.png"
    final_ico = "NeXusMagic.ico"
    script_name = "nexus_magic.py"
    exe_name = "NeXuS_Auto_Accept"
    
    try:
        # 1. Translate the PNG into the permanent NeXusMagic.ico file
        convert_png_to_ico(png_source, final_ico)
        
        # 2. Structure compiler variables
        command = [
            "pyinstaller",
            "--onefile",
            f"--icon={final_ico}",
            f"--name={exe_name}",
            script_name
        ]
        
        # 3. Compile the payload
        print(f"[*] Initializing compiler tracking for {script_name}...")
        subprocess.run(command, check=True)
        print(f"\n{'-'*60}\n[✓] SUCCESS! Standalone console application compiled with custom branding.")
        print(f"File path: dist/{exe_name}.exe")
        print(f"[✓] Note: Your permanent icon file is available at: ./{final_ico}")
        
    except FileNotFoundError as e:
        print(e)
    except subprocess.CalledProcessError:
        print("\n[-] Error: PyInstaller build routine halted.")

if __name__ == "__main__":
    compile_to_exe()