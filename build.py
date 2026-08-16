import glob
import os
import sys
import subprocess
from PIL import Image

# Windows consoles default to a legacy codepage (e.g. cp1252) that can't
# encode the checkmarks below, which crashed this script instantly on every
# Windows run (local and CI). Force UTF-8 so the box-drawing/status glyphs
# always work.
sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

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

def write_version_file():
    """Stamp version.py with the tag being built (CI sets GITHUB_REF_NAME to
    e.g. "v1.0.5" on a tag push). Local/manual builds keep whatever version
    is already checked in, so they're distinguishable from a real release."""
    ref = os.environ.get("GITHUB_REF_NAME", "")
    if ref.startswith("v"):
        version = ref[1:]
        with open("version.py", "w", encoding="utf-8") as f:
            f.write(f'VERSION = "{version}"\n')
        print(f"[*] Baked version {version} into version.py")


def find_signtool():
    """Locate signtool.exe: PATH first, then the newest Windows Kits install."""
    from shutil import which
    found = which("signtool")
    if found:
        return found
    candidates = glob.glob(
        r"C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe"
    )
    return max(candidates) if candidates else None


def sign_exe(exe_path):
    """Best-effort Authenticode signing with whatever code-signing cert is
    installed in the current user's certificate store. Never fails the
    build: CI machines and fresh checkouts have no such cert, and that's
    fine, they just end up with an unsigned exe like before."""
    signtool = find_signtool()
    if not signtool:
        print("[*] signtool.exe not found; skipping signing.")
        return
    try:
        subprocess.run(
            [
                signtool, "sign",
                "/fd", "SHA256",
                "/a",
                "/t", "http://timestamp.digicert.com",
                exe_path,
            ],
            check=True,
        )
        print(f"[✓] Signed {exe_path}")
    except subprocess.CalledProcessError:
        print("[*] No usable code-signing certificate found; left unsigned.")


def compile_to_exe(gui=True):
    png_source = "NeXusMagic.png"
    final_ico = "NeXusMagic.ico"
    script_name = "nexus_gui.py" if gui else "nexus_magic.py"
    exe_name = "NeXuS_Auto_Accept"

    try:
        # 1. Translate the PNG into the permanent NeXusMagic.ico file
        convert_png_to_ico(png_source, final_ico)
        write_version_file()

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
                f"--add-data={final_ico}{data_sep}.",
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

        # 4. Sign the binary, if a code-signing cert is available locally.
        sign_exe(os.path.join("dist", f"{exe_name}.exe"))

    except FileNotFoundError as e:
        print(e)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"\n[-] Error: PyInstaller build routine halted (exit code {e.returncode}).")
        sys.exit(1)

if __name__ == "__main__":
    compile_to_exe(gui="--console" not in sys.argv)