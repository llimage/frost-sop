@echo off
chcp 65001 >nul
setlocal

echo ============================================================
echo   FROST-SOP V5.0.0 推送脚本
echo   仓库: Gitee  liao_liang_7514/solo-ops-platform
echo   分支: master
echo   内容: 4 commits + v5.0.0 tag (force update)
echo ============================================================
echo.

cd /d "%~dp0"

echo [1/3] 推送 master 分支 ...
git push origin master
if errorlevel 1 goto :err

echo.
echo [2/3] 强制推送 v5.0.0 tag (tag 已移动) ...
git push origin v5.0.0 --force
if errorlevel 1 goto :err

echo.
echo [3/3] 验证推送结果 ...
git status
echo.
git ls-remote --tags origin
echo.
echo ============================================================
echo   推送完成
echo   v5.0.0 tag 已更新到最新 commit
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
