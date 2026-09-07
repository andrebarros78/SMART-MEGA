@echo off
cd /d "C:\New Projet\SMART-MEGA"
call smart_python.cmd smart_full_process_pipeline.py > runtime\full_process_20260906.log 2>&1
echo %ERRORLEVEL% > runtime\full_process_20260906.exit
