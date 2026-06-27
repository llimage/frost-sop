@echo off
chcp 65001 >nul
echo ================================================
echo FROST-SOP V3.0 推送脚本
echo ================================================
echo.

cd /d D:\my_ai\Solo-Ops-Platform

echo [1/3] 检查 git 状态...
git status -b --short
echo.

echo [2/3] 推送到远程仓库...
git push origin master --tags

if %errorlevel% equ 0 (
    echo.
    echo ✅ 推送成功！
    echo.
    echo 验证标签：
    git tag -l "v*"
) else (
    echo.
    echo ❌ 推送失败，请检查网络连接或权限
    echo.
)

echo.
echo 按任意键退出...
pause >nul
