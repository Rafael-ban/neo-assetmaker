@echo off
chcp 65001 >nul

echo ================================================
echo   ArknightsPassMaker Build Script
echo ================================================

python --version >nul 2>&1
if errorlevel 1 (
    echo Python not found!
    pause
    exit /b 1
)

if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)

call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Building...
python build.py

call .venv\Scripts\deactivate.bat

echo.
echo Done!
pause
