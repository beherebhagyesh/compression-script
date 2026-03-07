@echo off
setlocal
cd /d %~dp0

set "PYTHON_CMD="
set "RUN_PYTHON="

where py >nul 2>nul
if not errorlevel 1 (
  set "PYTHON_CMD=py"
) else (
  where python >nul 2>nul
  if not errorlevel 1 (
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
)

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m pip --version >nul 2>nul
  if not errorlevel 1 (
    set "RUN_PYTHON=.venv\Scripts\python.exe"
  ) else (
    echo Existing virtual environment is incomplete.
    echo Falling back to the system Python installation.
    set "RUN_PYTHON=%PYTHON_CMD%"
  )
) else (
  echo Virtual environment creation failed or is unavailable.
  echo Falling back to the system Python installation.
  set "RUN_PYTHON=%PYTHON_CMD%"
)

echo Installing dependencies...
call "%RUN_PYTHON%" -m pip install --upgrade pip
if errorlevel 1 exit /b 1

call "%RUN_PYTHON%" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

echo Verifying Pillow...
call "%RUN_PYTHON%" -c "from PIL import Image; print(Image.__version__)" >nul 2>nul
if errorlevel 1 (
  echo Pillow import failed. Reinstalling Pillow...
  call "%RUN_PYTHON%" -m pip install --no-cache-dir --force-reinstall Pillow
  if errorlevel 1 exit /b 1
)

echo Starting app on http://127.0.0.1:8876
call "%RUN_PYTHON%" backend\server.py
