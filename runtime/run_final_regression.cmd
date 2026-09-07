@echo off
cd /d "C:\New Projet\SMART-MEGA"
del /q runtime\final_regression.exit 2>nul
call smart_python.cmd -E smart_regression_runner.py > runtime\final_regression.log 2>&1
set EC=%ERRORLEVEL%
echo %EC%>runtime\final_regression.exit
exit /b %EC%
