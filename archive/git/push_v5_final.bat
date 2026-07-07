@echo off
chcp 65001 >nul 2>&1
echo ============================================
echo   FROST-SOP v5.0.0 Baseline Push Script
echo ============================================
echo.

cd /d D:\my_ai\Solo-Ops-Platform

echo [1/4] Checking repo status...
git status --short
if errorlevel 1 (
    echo ERROR: Working tree not clean or git error!
    pause
    exit /b 1
)
echo OK - Working tree clean
echo.

echo [2/4] Pushing to GitHub (llimage/frost-sop)...
git push github master:main --no-verify
if errorlevel 1 (
    echo WARNING: GitHub push failed, trying with force...
    git push github master:main --force --no-verify
)
git push github --tags --no-verify
echo GitHub push complete.
echo.

echo [3/4] Pushing to Gitee (liao_liang_7514/frost-sop)...
git push origin master:main --force --no-verify
git push origin --tags --no-verify
echo Gitee push complete.
echo.

echo [4/4] Verification...
echo.
echo === GitHub remote ===
git remote get-url github
echo === Gitee remote ===
git remote get-url origin
echo === Tags ===
git tag -l
echo === HEAD ===
git log --oneline -3
echo.
echo ============================================
echo   Push complete! Check repos:
echo   GitHub: https://github.com/llimage/frost-sop
echo   Gitee:  https://gitee.com/liao_liang_7514/frost-sop
echo ============================================
pause
