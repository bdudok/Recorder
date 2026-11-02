@echo off
rem Starts RecorderGUI_CL. Double-click it or use a desktop shortcut; it works from any folder.
rem The console stays open and shows what the Recorder prints. Closing it stops the Recorder.
rem LNCM-lib must be checked out next to this repo (for BaserowAPI).
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Could not find .venv in the Recorder folder. Run "uv sync" there first.
    pause
    exit /b 1
)
set "PYTHONPATH=%~dp0..\LNCM-lib"
".venv\Scripts\python.exe" -m Recorder.RecorderGUI_CL
if errorlevel 1 pause
