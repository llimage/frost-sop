@echo off
title S-O-P Init Test Launcher

echo.
echo  ========================================
echo   S-O-P v6.1 Init Test Environment
echo   Init Questionnaire + Hunt Loop Test
echo  ========================================
echo.

:: 1. Start base services
echo [1/2] Starting base services...
call start_all.bat

:: 2. Wait for services to spin up
echo.
echo [2/2] Services starting, opening test terminal in 5s...
timeout /t 5 /nobreak >nul

:: 3. Open test terminal with init commands
start cmd /k "cd /d D:\my_ai\Solo-Ops-Platform\workspace\frost-sop && title S-O-P Init Test && echo. && echo === S-O-P v6.1 Init Test === && echo. && echo Run these commands in order: && echo. && echo   1) Run init questionnaire: && echo      python -m skills.init.questionnaire && echo. && echo   2) Trigger hunt tasks: && echo      python -m skills.init.task_trigger && echo. && echo   3) Check DB tasks: && echo      python -c \"from core.db import get_db; db=get_db(); print(db.select_all('tasks', where='project_id=?', params=['INIT']))\" && echo."

:: 4. Open service status monitor
start cmd /k "title S-O-P Service Status && echo. && echo S-O-P Service Status && echo. && echo URLs: && echo   NiceGUI: http://localhost:8080 && echo   FastAPI:  http://localhost:8000/docs && echo   Next.js:  http://localhost:3000 && echo. && echo Press Ctrl+C to stop"
