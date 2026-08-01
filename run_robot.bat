@echo off
cd /d "%~dp0"
python main.py
if errorlevel 1 (
  echo.
  echo Failed to start. Install Python 3.10 or newer and ensure python is on PATH.
  pause
)
