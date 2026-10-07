@echo off
rem Starts the vEEG recorder GUI. Double-click it, or pass arguments, e.g. "vEEG.bat --cam 1".
rem Works from any folder and without activating conda: it finds the "veeg" environment and
rem puts its folders on PATH (needed for ffmpeg and Qt).
setlocal
set VEEG_ENV=
for %%D in ("%USERPROFILE%\.conda\envs\veeg" "%USERPROFILE%\miniforge3\envs\veeg" "%USERPROFILE%\anaconda3\envs\veeg" "%USERPROFILE%\miniconda3\envs\veeg" "C:\ProgramData\anaconda3\envs\veeg" "C:\ProgramData\miniforge3\envs\veeg") do (
    if not defined VEEG_ENV if exist "%%~D\pythonw.exe" set "VEEG_ENV=%%~D"
)
if not defined VEEG_ENV (
    echo Could not find the conda environment "veeg". Create it with:
    echo     conda env create -f VideoEEG\environment.yml
    echo or add its folder to the list in %~f0
    pause
    exit /b 1
)
set "PATH=%VEEG_ENV%;%VEEG_ENV%\Library\mingw-w64\bin;%VEEG_ENV%\Library\usr\bin;%VEEG_ENV%\Library\bin;%VEEG_ENV%\Scripts;%PATH%"
cd /d "%~dp0.."
start "" "%VEEG_ENV%\pythonw.exe" -m VideoEEG.gui %*
