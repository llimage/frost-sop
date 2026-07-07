@echo off
chcp 65001 >nul
cd /d D:\my_ai\Solo-Ops-Platform

echo ============================================
echo   FROST-SOP v6.0.0 双平台推送
echo ============================================
echo.

echo [1/4] 预检...
git branch --show-current
git log --oneline -1
git tag --list "v6*"
echo.

echo [2/4] 推送到 Gitee (origin)...
git push origin master:main
if %errorlevel% neq 0 (
    echo WARNING: Gitee push failed, trying force...
    git push origin master:main --force
)
echo.

echo [3/4] 推送到 GitHub...
git push github master:main
if %errorlevel% neq 0 (
    echo WARNING: GitHub push failed, trying force...
    git push github master:main --force
)
echo.

echo [4/4] 推送标签...
git push origin --tags
git push github --tags
echo.

echo ============================================
echo   推送完成!
echo   Gitee:  https://gitee.com/liao_liang_7514/frost-sop
echo   GitHub: https://github.com/llimage/frost-sop
echo ============================================
pause
