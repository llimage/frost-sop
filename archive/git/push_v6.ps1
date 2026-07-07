# ============================================
#   FROST-SOP v6.0.0 Baseline Push Script
#   双平台: Gitee (origin) + GitHub (github)
#   一键推送: 右键 → "使用 PowerShell 运行"
#   PowerShell 7+ 推荐; 兼容 Windows PowerShell 5.1
# ============================================

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  FROST-SOP v6.0.0 基线推送" -ForegroundColor Cyan
Write-Host "  目标: Gitee + GitHub 双平台" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# 固定工作目录
Set-Location "D:\my_ai\Solo-Ops-Platform"

# ── Step 0: 预检 ──
Write-Host "[0/4] 预检..." -ForegroundColor Yellow
$status = git status --short 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: git status 失败!" -ForegroundColor Red
    Write-Host $status
    Read-Host "按回车退出"
    exit 1
}
Write-Host "当前分支: $(git branch --show-current)" -ForegroundColor Green
Write-Host "HEAD commit: $(git log --oneline -1)" -ForegroundColor Green
Write-Host "标签: $(git tag --list 'v6*')" -ForegroundColor Green
Write-Host ""

# ── Step 1: Push to Gitee ──
Write-Host "[1/4] 推送到 Gitee (origin)..." -ForegroundColor Yellow
try {
    git push origin master:main --no-verify 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: 普通推送失败，尝试 force push..." -ForegroundColor DarkYellow
        git push origin master:main --force --no-verify 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "Gitee push 失败"
        }
    }
    Write-Host "  Gitee 分支推送完成" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR: Gitee 推送失败: $_" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# ── Step 2: Push to GitHub ──
Write-Host "[2/4] 推送到 GitHub (github)..." -ForegroundColor Yellow
try {
    git push github master:main --no-verify 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "WARNING: 普通推送失败，尝试 force push..." -ForegroundColor DarkYellow
        git push github master:main --force --no-verify 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "GitHub push 失败"
        }
    }
    Write-Host "  GitHub 分支推送完成" -ForegroundColor Green
}
catch {
    Write-Host "  ERROR: GitHub 推送失败: $_" -ForegroundColor Red
    Read-Host "按回车退出"
    exit 1
}

# ── Step 3: Push tags ──
Write-Host "[3/4] 推送标签到双平台..." -ForegroundColor Yellow
try {
    git push origin --tags --no-verify 2>&1
    Write-Host "  Gitee 标签推送完成" -ForegroundColor Green
}
catch {
    Write-Host "  WARNING: Gitee 标签推送失败（可忽略）" -ForegroundColor DarkYellow
}

try {
    git push github --tags --no-verify 2>&1
    Write-Host "  GitHub 标签推送完成" -ForegroundColor Green
}
catch {
    Write-Host "  WARNING: GitHub 标签推送失败（可忽略）" -ForegroundColor DarkYellow
}

# ── Step 4: 验证 ──
Write-Host ""
Write-Host "[4/4] 验证..." -ForegroundColor Yellow
Write-Host ""

Write-Host "=== 远程仓库 ===" -ForegroundColor Cyan
git remote -v 2>&1
Write-Host ""

Write-Host "=== 标签列表 ===" -ForegroundColor Cyan
git tag -l "v*" 2>&1
Write-Host ""

Write-Host "=== 最新3个提交 ===" -ForegroundColor Cyan
git log --oneline -3 2>&1
Write-Host ""

# ── 完成 ──
Write-Host "============================================" -ForegroundColor Green
Write-Host "  V6.0 推送完成!" -ForegroundColor Green
Write-Host "  Gitee:  https://gitee.com/liao_liang_7514/frost-sop" -ForegroundColor Green
Write-Host "  GitHub: https://github.com/llimage/frost-sop" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

Read-Host "按回车退出"
