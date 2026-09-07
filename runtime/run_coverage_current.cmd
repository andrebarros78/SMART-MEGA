@echo off
cd /d "C:\New Projet\SMART-MEGA"
"C:\New Projet\SMART-MEGA\.venv\Scripts\python.exe" -E -m coverage erase
"C:\New Projet\SMART-MEGA\.venv\Scripts\python.exe" -E -m coverage run --branch -m pytest -q > runtime\coverage_run.log 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (echo %RC%>runtime\coverage_run.exit & exit /b %RC%)
"C:\New Projet\SMART-MEGA\.venv\Scripts\python.exe" -E -m coverage json -o SMART_COVERAGE_GLOBAL_CURRENT.json >> runtime\coverage_run.log 2>&1
set RC=%ERRORLEVEL%
echo %RC%>runtime\coverage_run.exit
exit /b %RC%

