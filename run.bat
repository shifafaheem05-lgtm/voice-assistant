
@echo off
rem Starts the assistant. Say "Jarvis, ..." before each command. Falls back to text mode if the microphone is not available.
cd /d "%~dp0"
title Voice Assistant
if exist venv\Scripts\python.exe (set PY=venv\Scripts\python.exe) else (set PY=python)
%PY% -m assistant --voice --wake-word jarvis
if errorlevel 1 (
  echo.
  echo Voice mode could not start. Starting text mode instead ^(type your commands^)...
  echo.
  %PY% -m assistant
)
pause
