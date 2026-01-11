import os
import sys
import subprocess

PROJECT_NAME = "ArknightsPassMaker"
MAIN_SCRIPT = "main.py"
ICON_FILE = "resources/icons/favicon.ico"

NUITKA_ARGS = [
    sys.executable, "-m", "nuitka",
    "--standalone",
    "--onefile",
    f"--output-filename={PROJECT_NAME}.exe",
    "--windows-console-mode=disable",
    "--enable-plugin=pyqt6",
    "--include-package=config",
    "--include-package=core",
    "--include-package=gui",
    "--include-package=utils",
    "--include-data-dir=resources=resources",
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
    except Exception:
        print("Error: Nuitka not installed, run: pip install nuitka")
        return False

    if not os.path.exists(MAIN_SCRIPT):
        print(f"Error: Main script {MAIN_SCRIPT} not found")
        return False

    if os.path.exists(ICON_FILE):
        print(f"Icon file: {ICON_FILE} found")
        NUITKA_ARGS.insert(-1, f"--windows-icon-from-ico={ICON_FILE}")
    else:
        print(f"Warning: Icon file {ICON_FILE} not found")

    if os.path.exists("ffmpeg.exe"):
        print("ffmpeg.exe: found")
        NUITKA_ARGS.insert(-1, "--include-data-files=ffmpeg.exe=ffmpeg.exe")
    else:
        print("Warning: ffmpeg.exe not found, video export may not work")

    return True


def build():
    print("\n" + "=" * 50)
    print("Starting Nuitka build...")
    print("=" * 50 + "\n")

    print("Command:")
    print(" ".join(NUITKA_ARGS))
    print()

    result = subprocess.run(NUITKA_ARGS)

    if result.returncode == 0:
        print("\n" + "=" * 50)
        print("Build successful!")
        print(f"Output: dist/{PROJECT_NAME}.exe")
        print("=" * 50)
        return True
    else:
        print("\n" + "=" * 50)
        print("Build failed!")
        print("=" * 50)
        return False


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
