@echo off
chcp 65001 >nul
title FROST-SOP 启动器
cls

echo =========================================
echo   FROST-SOP V7.1 一键启动器
echo =========================================
echo.

REM 检查 .env 文件
if not exist .env (
    echo [警告] 未找到 .env 文件，API 可能无法调用 LLM
    echo          请复制 .env.example 为 .env 并填入 DEEPSEEK_API_KEY
    echo.
    pause
)

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.11+
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

echo [1/4] 环境检查通过
echo.

REM 启动 API 服务（后台）
echo [2/4] 启动 API 服务 (http://localhost:8000) ...
start "FROST-SOP API" cmd /k "python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload"
timeout /t 3 /nobreak >nul
echo         API 已启动
echo.

REM 启动前端服务
echo [3/4] 启动前端服务 (http://localhost:3000) ...
cd frontend
start "FROST-SOP Frontend" cmd /k "npm run dev"
cd ..
timeout /t 5 /nobreak >nul
echo         前端已启动
echo.

echo [4/4] 启动完成！
echo =========================================
echo   访问地址：
echo     前端：http://localhost:3000
echo     API： http://localhost:8000
echo     文档：http://localhost:8000/docs
echo =========================================
echo.
echo 按任意键关闭所有服务...
pause >nul

echo 正在关闭服务...
taskkill /FI "WINDOWTITLE eq FROST-SOP API*" /T /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq FROST-SOP Frontend*" /T /F >nul 2>&1
echo 已关闭。
