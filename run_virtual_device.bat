@echo off
cd /d "%~dp0"
set "PROJECT_PYTHON=python"
python --version >nul 2>&1
if errorlevel 1 set "PROJECT_PYTHON=%USERPROFILE%\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if not exist "%PROJECT_PYTHON%" if "%PROJECT_PYTHON%" NEQ "python" (
  echo Python 3.10 or newer was not found.
  pause
  exit /b 1
)

"%PROJECT_PYTHON%" virtual_device.py
if errorlevel 1 pause
