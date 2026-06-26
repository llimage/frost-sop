@echo off
chcp 65001 >nul
echo ====================================================
echo  S-O-P 前端启动脚本
echo ====================================================
echo.

REM 检查 node_modules
if not exist "node_modules\" (
    echo [1/3] 首次运行，安装依赖中...
    call npm install
)

echo [2/3] 启动 Next.js 开发服务器...
echo.
echo   访问地址: <ADDRESS_REDACTED>
echo   按 Ctrl+C 停止服务器
echo.
call npm run dev
