@echo off
rem Starts CamGUI. Double-click it or use a desktop shortcut; it works from any folder.
rem The console stays open and shows what CamGUI prints. Closing it stops CamGUI.
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Could not find .venv in the Recorder folder. Run "uv sync" there first.
    pause
    exit /b 1
)
".venv\Scripts\python.exe" -m Camera.CamGUI
if errorlevel 1 pause
