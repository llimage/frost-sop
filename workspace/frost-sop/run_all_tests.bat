@echo off
chcp 65001 >nul
REM FROST-SOP 全量测试运行脚本 (Windows)

set PYTHON=python -X utf8
set PYTEST=%PYTHON% -m pytest

echo.
echo ============================================
echo   FROST-SOP 全量测试套件
echo ============================================
echo.

:menu
echo 请选择测试模式:
echo   [1] 快速冒烟测试 (核心模块)
echo   [2] 全部单元测试 (并行)
echo   [3] 全部集成测试
echo   [4] 端到端测试
echo   [5] 属性测试 (Hypothesis)
echo   [6] 性能基准测试
echo   [7] 全量测试 + 覆盖率报告
echo   [8] 代码检查 (ruff + mypy + bandit)
echo   [9] 全量 CI 检查
echo   [L] 负载测试 (Locust Web UI)
echo   [S] 安全扫描
echo   [C] 清理测试产物
echo   [Q] 退出
echo.

set /p choice="请输入选项 [1-9/L/S/C/Q]: "

if "%choice%"=="1" goto quick
if "%choice%"=="2" goto unit
if "%choice%"=="3" goto integration
if "%choice%"=="4" goto e2e
if "%choice%"=="5" goto property
if "%choice%"=="6" goto benchmark
if "%choice%"=="7" goto cov
if "%choice%"=="8" goto lint
if "%choice%"=="9" goto ci
if /I "%choice%"=="L" goto load
if /I "%choice%"=="S" goto security
if /I "%choice%"=="C" goto clean
if /I "%choice%"=="Q" goto end
echo 无效选项，请重试.
goto menu

:quick
echo [快速冒烟测试] 正在运行核心模块测试...
%PYTEST% tests/test_store.py tests/test_encryption.py tests/test_agent.py tests/test_sop_*.py -n auto --timeout 30 -s -q
goto end

:unit
echo [单元测试] 正在并行运行...
%PYTEST% tests/ -m "unit" -n auto --timeout 60 -s -q
goto end

:integration
echo [集成测试] 正在运行...
%PYTEST% tests/ -m "integration" --timeout 120 -s -q
goto end

:e2e
echo [端到端测试] 正在运行...
%PYTEST% tests/ -m "e2e" --timeout 180 -s -q
goto end

:property
echo [属性测试] 正在运行 Hypothesis...
%PYTEST% tests/ -m "property" --hypothesis-show-statistics -s -q
goto end

:benchmark
echo [性能基准测试] 正在运行...
%PYTEST% tests/ -m "benchmark" --benchmark-only -s -q
goto end

:cov
echo [全量测试 + 覆盖率] 正在运行...
%PYTEST% tests/ --cov --cov-report=html --cov-report=term-missing -n auto --timeout 60 -s -q
echo.
echo 覆盖率报告已生成: htmlcov/index.html
goto end

:lint
echo [代码检查] 正在运行...
echo --- Ruff ---
ruff check .
echo.
echo --- Mypy ---
%PYTHON% -m mypy agents/ api/ core/ skills/ stores/ --ignore-missing-imports
echo.
echo --- Bandit ---
bandit -r agents/ api/ core/ skills/ stores/ -ll
goto end

:ci
echo [全量 CI 检查] 正在运行...
echo.
echo === Step 1/3: Ruff Lint ===
ruff check .
if errorlevel 1 (
    echo [FAIL] Ruff found issues
    goto end
)
echo [PASS] Ruff
echo.
echo === Step 2/3: Mypy Type Check ===
%PYTHON% -m mypy agents/ api/ core/ skills/ stores/ --ignore-missing-imports
if errorlevel 1 (
    echo [FAIL] Mypy found type errors
    goto end
)
echo [PASS] Mypy
echo.
echo === Step 3/3: Pytest + Coverage ===
%PYTEST% tests/ -m "not load and not benchmark" -n auto --timeout 60 --cov --cov-report=term -s -q
goto end

:load
echo [负载测试] 启动 Locust Web UI...
echo 请在浏览器中打开 http://localhost:8089
locust -f tests/load/locustfile.py --host=http://localhost:8000
goto end

:security
echo [安全扫描] 正在运行 Bandit...
bandit -r agents/ api/ core/ skills/ stores/ -ll
goto end

:clean
echo [清理] 正在清理测试产物...
if exist htmlcov\ rmdir /s /q htmlcov
if exist .coverage del .coverage
if exist .mutmut-cache rmdir /s /q .mutmut-cache
if exist .benchmarks rmdir /s /q .benchmarks
if exist coverage.xml del coverage.xml
if exist locust_report.html del locust_report.html
if exist benchmark_results.json del benchmark_results.json
for /d /r . %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d" 2>nul
echo 清理完成.
goto end

:end
echo.
pause
