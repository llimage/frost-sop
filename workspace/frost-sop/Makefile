# FROST-SOP Makefile
# 全量测试运行入口
#
# 注意：由于 SQLite 不支持并发写入，所有包含数据库操作的测试
# 默认使用串行模式。纯计算/无状态单元测试可使用 test-parallel。

PYTHON := python -X utf8
PYTEST := $(PYTHON) -m pytest
TESTS_DIR := tests

.PHONY: help
help: ## 显示帮助信息
	@echo "FROST-SOP 全量测试命令"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: install
install: ## 安装所有依赖（含测试工具）
	pip install -r requirements.txt
	pip install bandit==1.8.3

.PHONY: test
test: ## 运行所有测试（串行 — SQLite 安全）
	$(PYTEST) $(TESTS_DIR)/ --timeout 60 -s -q

.PHONY: test-parallel
test-parallel: ## 运行无状态测试（并行，⚠️ 仅限非数据库测试）
	$(PYTEST) $(TESTS_DIR)/ -m "not db" -n auto --timeout 60 -s -q

.PHONY: test-verbose
test-verbose: ## 运行所有测试（串行，完整输出）
	$(PYTEST) $(TESTS_DIR)/ -v --tb=short -s

.PHONY: test-unit
test-unit: ## 仅运行单元测试（串行）
	$(PYTEST) $(TESTS_DIR)/ -m "unit" --timeout 60 -s -q

.PHONY: test-integration
test-integration: ## 仅运行集成测试
	$(PYTEST) $(TESTS_DIR)/ -m "integration" --timeout 120 -s -q

.PHONY: test-e2e
test-e2e: ## 仅运行端到端测试
	$(PYTEST) $(TESTS_DIR)/ -m "e2e" --timeout 180 -s -q

.PHONY: test-property
test-property: ## 仅运行属性测试 (Hypothesis)
	$(PYTEST) $(TESTS_DIR)/ -m "property" --hypothesis-show-statistics -s -q

.PHONY: test-benchmark
test-benchmark: ## 仅运行性能基准测试
	$(PYTEST) $(TESTS_DIR)/ -m "benchmark" --benchmark-only -s -q

.PHONY: cov
cov: ## 运行测试 + 覆盖率报告（串行）
	$(PYTEST) $(TESTS_DIR)/ \
		--cov \
		--cov-report=html \
		--cov-report=term-missing \
		--timeout 60 \
		-s -q

.PHONY: cov-open
cov-open: cov ## 运行测试并打开覆盖率 HTML 报告
	@echo "Coverage report: htmlcov/index.html"

.PHONY: mutation
mutation: ## 运行变异测试 (mutmut)
	@echo "Running mutation tests on core/ ..."
	mutmut run --paths-to-mutate "agents/ api/ core/ skills/ stores/" \
		--runner "$(PYTHON) -m pytest -x --tb=no -s -m 'unit'" || true
	mutmut results

.PHONY: lint
lint: ## 代码检查 (ruff + mypy + bandit)
	ruff check .
	$(PYTHON) -m mypy agents/ api/ core/ skills/ stores/ --ignore-missing-imports
	bandit -r agents/ api/ core/ skills/ stores/ -ll

.PHONY: security
security: ## 仅安全扫描
	bandit -r agents/ api/ core/ skills/ stores/ -ll

.PHONY: all
all: lint test cov ## 全量检查：lint + 测试 + 覆盖率

.PHONY: ci
ci: ## CI 模式：全量检查（严格失败，串行）
	$(PYTEST) $(TESTS_DIR)/ \
		-m "not load and not benchmark" \
		--timeout 60 \
		--cov \
		--cov-report=xml \
		--cov-report=term \
		--cov-fail-under=55 \
		-s -q

.PHONY: load-test
load-test: ## 启动 Locust 负载测试 Web UI
	@echo "Starting Locust at http://localhost:8089"
	locust -f tests/load/locustfile.py --host=http://localhost:8000

.PHONY: load-test-headless
load-test-headless: ## 无头负载测试 (10用户, 60秒)
	locust -f tests/load/locustfile.py \
		--host=http://localhost:8000 \
		--headless \
		--users 10 \
		--spawn-rate 2 \
		--run-time 60s \
		--html=locust_report.html

.PHONY: clean
clean: ## 清理测试产物
	rm -rf htmlcov/ .coverage .mutmut-cache .benchmarks
	rm -f coverage.xml locust_report.html benchmark_results.json
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

.PHONY: quick
quick: ## 快速冒烟测试（仅核心单元测试，串行）
	$(PYTEST) $(TESTS_DIR)/test_store.py $(TESTS_DIR)/test_encryption.py \
		$(TESTS_DIR)/test_agent.py $(TESTS_DIR)/test_sop_*.py \
		--timeout 30 -s -q
