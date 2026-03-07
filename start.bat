@echo off
setlocal
cd /d %~dp0

set "PYTHON_CMD="

where py >nul 2>nul
if %errorlevel%==0 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if %errorlevel%==0 (
    set "PYTHON_CMD=python"
  )
)

if "%PYTHON_CMD%"=="" (
  echo Python was not found on this machine.
  echo Install Python 3.11+ and then run start.bat again.
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo Creating local virtual environment...
  %PYTHON_CMD% -m venv .venv
  if errorlevel 1 exit /b 1
)

echo Installing dependencies...
call ".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Starting app on http://127.0.0.1:8876
call ".venv\Scripts\python.exe" backend\server.py
