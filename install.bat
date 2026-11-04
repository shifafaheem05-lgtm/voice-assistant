@echo off
rem First-time setup: creates a virtual environment and installs the voice packages.
cd /d "%~dp0"
title Voice Assistant - setup
echo Creating the virtual environment...
py -3.12 -m venv venv 2>nul || py -3.11 -m venv venv 2>nul || python -m venv venv
if not exist venv\Scripts\python.exe (
  echo Could not find Python. Install Python 3.12 from python.org and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
echo Installing voice packages...
venv\Scripts\python -m pip install -r requirements-voice.txt
if errorlevel 1 (
  echo.
  echo The voice packages could not be installed ^(PyAudio needs Python 3.12 or older^).
  echo The assistant still works in text mode - just double-click run.bat.
) else (
  echo.
  echo Done! Double-click run.bat to start the assistant.
)
pause
