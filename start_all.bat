@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   S-O-P V3.0 一键启动
echo   三个服务：
echo     NiceGUI 驾驶舱  →  http://localhost:8080
echo     FROST-SOP API   →  http://localhost:8000/docs
echo     Next.js 前端    →  http://localhost:3000
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 启动 NiceGUI 驾驶舱 (端口 8080)...
start "SOP-NiceGUI-8080" cmd /k "cd /d %~dp0 && python -X utf8 start_nicegui.py"

echo [2/3] 启动 FROST-SOP FastAPI (端口 8000)...
start "SOP-FastAPI-8000" cmd /k "cd /d %~dp0\workspace\frost-sop && python -X utf8 -m uvicorn api.main:app --port 8000 --reload"

echo [3/3] 启动 Next.js 前端 (端口 3000)...
start "SOP-NextJS-3000" cmd /k "cd /d %~dp0\workspace\frost-sop\frontend && npm run dev"

echo.
echo ============================================================
echo   全部启动完毕！等待约 10 秒后打开浏览器：
echo.
echo   驾驶舱:  http://localhost:8080
echo   API文档: http://localhost:8000/docs
echo   前端:    http://localhost:3000
echo            (如3000被占会自动用3001)
echo.
echo   关闭：直接关掉三个弹出的黑色窗口即可
echo   或双击 stop_all.bat 一键关闭
echo ============================================================
echo.
echo 正在打开浏览器...
timeout /t 8 /nobreak >nul
start http://localhost:8080
start http://localhost:3000

pause
