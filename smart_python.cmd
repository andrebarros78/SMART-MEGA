@echo off
setlocal
set "PYTHONPATH="
set "PYTHONHOME="
set "SMART_PROJECT_ROOT=%~dp0"
if not exist "%~dp0.venv\Scripts\python.exe" (
  echo SMART-MEGA portable runtime missing: %~dp0.venv\Scripts\python.exe 1>&2
  exit /b 2
)
"%~dp0.venv\Scripts\python.exe" -E %*
exit /b %ERRORLEVEL%