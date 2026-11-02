@echo off
rem Starts CamGUI. Double-click it or use a desktop shortcut; it works from any folder.
rem No console window: errors are shown over the image, and added to Camera\ErrorLog.txt.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    echo Could not find .venv in the Recorder folder. Run "uv sync" there first.
    pause
    exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m Camera.CamGUI
