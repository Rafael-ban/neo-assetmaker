import os
import sys
import subprocess
import shutil

PROJECT_NAME = "AssetMaker"
MAIN_SCRIPT = "run.py"
ICON_FILE = "favicon.ico"

NUITKA_ARGS = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    f"--output-filename={PROJECT_NAME}.exe",
    "--windows-console-mode=disable",
    f"--windows-icon-from-ico={ICON_FILE}",
    "--enable-plugin=pyqt6",
    "--include-package=ui",
    "--include-package=core",
    "--include-module=config",
    "--include-data-files=ffmpeg.exe=ffmpeg.exe",
    f"--include-data-files={ICON_FILE}={ICON_FILE}",
    "--assume-yes-for-downloads",
    "--remove-output",
    "--output-dir=dist",
    MAIN_SCRIPT,
]

def check_requirements():
    print("Checking build environment...")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "nuitka", "--version"],
            capture_output=True, text=True
        )
        print(f"Nuitka version: {result.stdout.strip()}")
    except Exception as e:
        print(f"Error: Nuitka not installed, run: pip install nuitka")
        return False

    if not os.path.exists(MAIN_SCRIPT):
        print(f"Error: Main script {MAIN_SCRIPT} not found")
        print("Creating entry script...")
        create_entry_script()

    if os.path.exists("ffmpeg.exe"):
        print("ffmpeg.exe: found")
    else:
        print("Warning: ffmpeg.exe not found, video export may not work")
        for arg in NUITKA_ARGS[:]:
            if "ffmpeg" in arg:
                NUITKA_ARGS.remove(arg)

    return True

def create_entry_script():
    content = '''import sys
import os

if getattr(sys, 'frozen', False):
    app_dir = os.path.dirname(sys.executable)
else:
    app_dir = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, app_dir)

from ui.gui_main import main

if __name__ == "__main__":
    main()
'''
    with open(MAIN_SCRIPT, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Created entry script: {MAIN_SCRIPT}")

def build():
    print("\n" + "=" * 50)
    print("Starting Nuitka build...")
    print("=" * 50 + "\n")

    if ICON_FILE and os.path.exists(ICON_FILE):
        NUITKA_ARGS.insert(-1, f"--windows-icon-from-ico={ICON_FILE}")

    print("Command:")
    print(" ".join(NUITKA_ARGS))
    print()

    result = subprocess.run(NUITKA_ARGS)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("Build successful!")
        print(f"Output: dist/")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print("Build failed!")
        print("=" * 50)
        return False

    return True

def main():
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    print("=" * 50)
    print(f"  {PROJECT_NAME} - Nuitka Build Tool")
    print("=" * 50)

    if not check_requirements():
        sys.exit(1)

    if build():
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
