@echo off
chcp 65001 >nul
echo 正在关闭 S-O-P 三个服务...

REM 按端口杀进程
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8080 " ^| findstr "LISTENING"') do (
    echo 关闭 NiceGUI (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    echo 关闭 FastAPI (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    echo 关闭 Next.js (PID: %%a)
    taskkill /PID %%a /F >nul 2>&1
)

echo.
echo 全部关闭完毕。
pause
