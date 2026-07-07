@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   FROST-SOP V3.0 一键推送脚本
echo   仓库: Gitee  liao_liang_7514/solo-ops-platform
echo   分支: master
echo   内容: 40 commits + 3 tags (v1.0.0-f10-baseline, v2.0.0, v3.0.0)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 推送 master 分支 ...
git push origin master
if errorlevel 1 goto :err

echo.
echo [2/3] 推送所有 tags ...
git push origin --tags
if errorlevel 1 goto :err

echo.
echo [3/3] 验证推送结果 ...
git status
echo.
git ls-remote --tags origin
echo.
echo ============================================================
echo   推送完成
echo ============================================================
pause
exit /b 0

:err
echo.
echo ============================================================
echo   推送失败！请检查：
echo   1. 网络是否正常（能访问 gitee.com）
echo   2. 远程凭据是否过期（remote URL 内已含 token）
echo   3. Gitee 端 master 分支是否被保护
echo   错误详情见上方 git 输出
echo ============================================================
pause
exit /b 1
