@echo off
cd /d "C:\New Projet\SMART-MEGA"
call "C:\New Projet\SMART-MEGA\smart_python.cmd" "C:\New Projet\SMART-MEGA\smart_regression_runner.py" > "C:\New Projet\SMART-MEGA\runtime\full_regression_20260906.log" 2>&1
> "C:\New Projet\SMART-MEGA\runtime\full_regression_20260906.exit" echo %ERRORLEVEL%
