@echo off
cd /d "C:\New Projet\SMART-MEGA"
.venv\Scripts\python.exe -E -m coverage erase
.venv\Scripts\python.exe -E -m coverage run --branch -m pytest -q > runtime\live_coverage_tests.log 2>&1
set RC=%ERRORLEVEL%
if not "%RC%"=="0" (echo %RC% > runtime\live_coverage.exit & exit /b %RC%)
.venv\Scripts\python.exe -E -m coverage json -o runtime\SMART_COVERAGE_LIVE_FULL.json > runtime\live_coverage_json.log 2>&1
echo %ERRORLEVEL% > runtime\live_coverage.exit
