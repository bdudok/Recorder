@echo off
rem Starts the vEEG recorder GUI. Arguments are passed on, e.g. "vEEG.bat --cam 1".
rem Edit CONDA_ROOT if Miniforge/Anaconda is installed elsewhere.
set CONDA_ROOT=%USERPROFILE%\miniforge3
call "%CONDA_ROOT%\Scripts\activate.bat" veeg
cd /d "%~dp0.."
start "" pythonw -m VideoEEG.gui %*
