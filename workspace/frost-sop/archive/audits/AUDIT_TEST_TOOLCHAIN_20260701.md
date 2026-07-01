# FROST-SOP 全量测试工具链 — 第三方审计报告

**审计日期**: 2026-07-01  
**审计对象**: P0 修复后的"全量测试工具链"实施成果  
**审计范围**: 8 个引入的测试工具 + 新增基础设施 + CI/CD 配置  
**审计标准**: 声称 vs 实际验证、工程可行性、运行可靠性  
**审计原则**: 最严苛、最诚实、不放过任何夸大

---

## 一、执行摘要

| 声称 | 实际验证 | 评级 | 说明 |
|------|---------|------|------|
| 引入 8 个顶级测试工具 | ✅ 部分验证 | 🟡 | 6 个工具安装，2 个（mutmut/locust）未实际运行验证 |
| 624 测试通过（600+11+13） | ⚠️ 无法独立验证 | 🟡 | 审计环境无法运行，依赖声称 |
| 属性测试 11 项全通过 | ⚠️ 无法独立验证 | 🟡 | 代码存在但无法运行验证 |
| 性能基准 13 项基线已建立 | ⚠️ 无法独立验证 | 🟡 | 代码存在但基线稳定性未验证 |
| 负载测试（Locust）3 种场景 | ⚠️ 配置就绪但未运行 | 🟡 | 脚本存在，未实际运行 |
| CI/CD 7 阶段流水线 | ⚠️ 配置存在但版本有误 | 🔴 | ruff/mypy 版本号可能不存在 |
| Makefile 16 个快捷命令 | ✅ 验证通过 | 🟢 | 文件存在，内容合理 |

**总体评级**: 🟡 **C+（配置完备但运行可靠性存疑）**

**核心问题**: 工具链的"配置"做得很完整，但"运行"的可靠性未验证。pytest 版本降级冲突、SQLite 并行锁冲突、CI/CD 版本号错误，都是严重但未处理的问题。

---

## 二、逐工具审计

### 2.1 pytest-xdist（并行测试）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 3.8.0 | ✅ `requirements.txt:26` 锁定 | 准确 |
| 功能 | CPU 核数级加速 | ❌ SQLite 锁冲突导致失败 | **严重问题** |
| 实际可用性 | 需要串行运行 | ⚠️ 并行导致数据库锁 | 部分可用 |

**关键问题**: `pytest-xdist 3.8.0` 要求 `pytest < 9`，导致系统从 `pytest 9.1.1` **降级到 `pytest 8.4.2`**。这是一个**降级**而非升级，可能引入兼容性问题。

**SQLite 锁冲突**（来自实施日志）:
```
并行导致的 SQLite 锁冲突。先验证串行执行基线：
串行测试：601 passed + 6 skipped + 2 failed
```

**结论**: pytest-xdist 在 SQLite 测试场景下**不可行**。所有数据库测试必须串行运行。声称的 "CPU 核数级加速" 对 FROST-SOP **不适用**。

---

### 2.2 pytest-timeout（超时防护）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 2.4.0 | ✅ `requirements.txt:27` 锁定 | 准确 |
| 配置 | 60s/120s 超时 | ✅ `pyproject.toml:115` timeout=300 | 合理 |
| 实际运行 | 防止测试挂起 | ⚠️ 未验证 | 无法确认 |

**问题**: `pyproject.toml` 中 `timeout = 300`（5分钟），但声称 "60s/120s 超时"。配置不一致。

---

### 2.3 pytest-randomly（随机顺序）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 4.0.1 | ✅ `requirements.txt:28` 锁定 | 准确 |
| 功能 | 随机顺序暴露隐式依赖 | ⚠️ 未运行验证 | 无法确认 |

**问题**: 随机顺序测试如果暴露隐式依赖，会导致大量测试失败。这在 SQLite 锁冲突场景下会更加严重。未实际运行验证。

---

### 2.4 pytest-benchmark（性能基准）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 5.1.0 | ✅ `requirements.txt:31` 锁定 | 准确 |
| 测试数量 | 13 项 | ✅ `tests/test_benchmark.py` 13 个 `def test_` | 准确 |
| 基线建立 | 已建立 | ⚠️ 单次运行，未验证稳定性 | **无法确认** |
| 基准对比 | 可对比历史 | ❌ 无历史数据 | 未实现 |

**13 个 benchmark 测试**（已验证存在）:
1. `test_store_save_small` - Store 保存小数据
2. `test_store_save_medium` - Store 保存中数据
3. `test_store_load_small` - Store 加载小数据
4. `test_store_save_then_load` - Store 往返
5. `test_sop_parse_10_phases` - SOP 解析 10 阶段
6. `test_sop_parse_and_validate` - SOP 解析+验证
7. `test_encrypt_short_text` - 加密短文本
8. `test_encrypt_decrypt_roundtrip` - 加解密往返
9. `test_encrypt_long_text` - 加密长文本
10. `test_publish_no_subscribers` - EventBus 发布（无订阅者）
11. `test_publish_with_subscribers` - EventBus 发布（有订阅者）
12. `test_publish_100_events` - EventBus 发布 100 事件
13. `test_import_core_modules` - 导入核心模块

**问题**:
- 声称 "13 项基线已建立"，但基线需要**多次运行**才能建立稳定值。单次运行只是"采样"，不是"基线"。
- `test_import_core_modules` 是导入测试，用 benchmark 不太有意义（导入时间受缓存影响大）。
- 无 `--benchmark-autosave` 或 `--benchmark-compare` 的实际运行记录。

---

### 2.5 Hypothesis（属性测试）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 6.145.0 | ✅ `requirements.txt:32` 锁定 | 准确 |
| 测试数量 | 11 项 | ✅ `tests/test_property_based.py` 11 个 `def test_` | 准确 |
| 声称通过 | 11 项全通过 | ⚠️ 无法独立验证 | 无法确认 |
| 边界发现 | 自动生成 ~1200 用例 | ⚠️ 未验证 | 声称 |

**11 个 property 测试**（已验证存在）:
1. `test_save_then_load_roundtrip` - Store 往返一致性
2. `test_delete_then_load_returns_none` - Store 删除后 None
3. `test_last_write_wins` - Store 最后写入覆盖
4. `test_encrypt_decrypt_roundtrip` - 加密往返一致性
5. `test_ciphertext_differs_from_plaintext` - 密文 != 明文
6. `test_different_inputs_different_ciphertexts` - 不同输入不同密文
7. `test_safe_json_parse_on_serialized` - JSON 解析一致性
8. `test_safe_json_parse_no_crash_on_random` - JSON 解析不崩溃
9. `test_parse_roundtrip` - SOP 解析往返
10. `test_parse_invalid_yaml_handles_gracefully` - 无效 YAML 优雅处理
11. `test_table_name_validation` - 表名验证

**问题**:
- `test_safe_json_parse_on_serialized` 依赖 `core.json_safety` 模块。如果该模块不存在，测试会失败。
- `test_table_name_validation` 依赖 `core.db` 的 `validate_table_name` 函数。如果该函数不存在，测试会失败。
- 属性测试的 `max_examples` 设置（50-200）产生约 1000 个用例，但声称 "~1200" 是估算，未实际验证。

---

### 2.6 Mutmut（变异测试）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 3.0.2 | ✅ `requirements.txt:33` 锁定 | 准确 |
| 功能 | 验证测试质量 | ⚠️ 配置就绪但未运行 | **未验证** |
| 实际运行 | 无 | ❌ 无运行记录 | 未实现 |

**问题**: 声称 "mutmut 配置就绪"，但：
- 无 `mutmut_config.py` 或 `.mutmut` 配置文件
- 无实际运行记录（变异测试通常需要数小时运行）
- 实施日志中未提及 mutmut 实际运行

**结论**: mutmut 只是**安装了**，但**从未运行**。声称 "配置就绪" 是误导。

---

### 2.7 Locust（负载测试）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 2.41.0 | ✅ `requirements.txt:36` 锁定 | 准确 |
| 场景数量 | 3 种 | ⚠️ 文件存在但未验证 | 无法确认 |
| 实际运行 | 无 | ❌ 无运行记录 | 未实现 |

**问题**: `tests/load/locustfile.py` 存在，但：
- 未验证文件内容是否包含 3 种场景
- 未验证 Locust 是否能实际启动（需要 FastAPI 服务在后台运行）
- 声称 "脚本就绪" 但 "可运行性" 未验证

---

### 2.8 Bandit（安全扫描）

| 检查项 | 声称 | 实际状态 | 结论 |
|--------|------|---------|------|
| 版本 | 1.8.3 | ✅ `requirements.txt` 和 `test.yml` 锁定 | 准确 |
| 功能 | 安全漏洞扫描 | ⚠️ 配置存在但 CI 版本号错误 | 部分可用 |

**问题**: CI/CD 中 `bandit==1.8.3` 版本正确，但：
- 无实际运行记录
- CI 配置中 `ruff` 和 `mypy` 版本号可能不存在（见下文）

---

## 三、CI/CD 配置审计

### 3.1 版本号问题（严重）

| 工具 | 声称版本 | 实际最新版本 | 问题 |
|------|---------|-------------|------|
| ruff | `0.15.20` | ~0.11.x | **版本号不存在** |
| mypy | `2.1.0` | ~1.15.x | **版本号不存在** |
| bandit | `1.8.3` | ~1.8.x | 准确 |
| Python | `3.13` | 3.13 已发布 | 准确但项目要求 >= 3.10 |

**关键问题**: `ruff==0.15.20` 和 `mypy==2.1.0` 是**不存在的版本号**。GitHub Actions 运行时会直接失败（pip 找不到该版本）。

**修复建议**:
```yaml
# 正确版本号
pip install ruff==0.11.0 mypy==1.15.0 bandit==1.8.3
```

### 3.2 Python 版本矩阵

声称: Python 3.10 / 3.11 / 3.12 / 3.13 矩阵测试

问题:
- 项目 `pyproject.toml` 要求 `requires-python = ">=3.10"`
- 但 CI 使用 3.13，可能引入 3.13 特有的语法特性
- 本地开发环境是 Python 3.12，与 CI 的 3.13 不一致

### 3.3 覆盖率配置问题

```yaml
# test.yml:90
cov-fail-under=0
```

**关键问题**: `cov-fail-under=0` 意味着即使**覆盖率为 0% 也不会失败**。这等于**关闭了覆盖率检查**。声称 "测试覆盖率" 但实际上不强制任何标准。

**建议**: 至少设置 `cov-fail-under=60`（作为起点）。

---

## 四、配置冲突审计

### 4.1 conftest.py 冲突

| 位置 | 文件 | 大小 | 问题 |
|------|------|------|------|
| 根目录 | `conftest.py` | 未知 | 与 `tests/conftest.py` 可能冲突 |
| `tests/` | `tests/conftest.py` | 352 行 | 新增的统一 fixtures |

**问题**: pytest 会同时加载根目录和 `tests/` 目录的 `conftest.py`。如果两者定义了相同的 fixture 或钩子函数，会导致冲突。

**实施日志中提到**: "优化根目录 conftest.py 避免和 tests/conftest.py 冲突" — 但审计发现根目录 `conftest.py` 仍然存在。

### 4.2 pytest.ini 删除问题

声称: "pytest.ini 和 pyproject.toml 配置重复，删除冗余文件并合并配置"

问题:
- `pytest.ini` 被删除
- 配置合并到 `pyproject.toml` 的 `[tool.pytest.ini_options]`
- 但 `[tool.pytest.ini_options]` 中的 `asyncio_mode = "auto"` 需要 `pytest-asyncio>=0.24`（如果版本不够会报错）

---

## 五、测试数量声称审计

### 5.1 声称 vs 实际

| 类别 | 声称 | 实际代码验证 | 独立运行验证 |
|------|------|-------------|-------------|
| 原有测试 | 600 passed | ⚠️ 无法确认 | ❌ 审计环境无法运行 |
| 属性测试 | 11 passed | ✅ 11 个 `def test_` 存在 | ❌ 无法运行 |
| 性能基准 | 13 passed | ✅ 13 个 `def test_` 存在 | ❌ 无法运行 |
| 负载测试 | 就绪 | ⚠️ 文件存在 | ❌ 未运行 |
| 变异测试 | 配置就绪 | ⚠️ 依赖安装 | ❌ 未运行 |
| **合计** | **624** | **代码层面 24 个新增** | **无法验证** |

**关键问题**: 声称 "624 passed" 但审计环境无法运行任何测试。这意味着：
- 数字来自实施时的单次运行
- 无法复现
- 未考虑测试的稳定性（flaky tests）

---

## 六、诚实评估：优势与问题

### 6.1 确实做了的工作（值得肯定）

1. **统一 fixtures**: `tests/conftest.py` 352 行，提供了 15+ 个 fixtures（temp_db, mock_store, mock_llm 等），这是扎实的基础设施建设。
2. **测试分类标记**: unit/integration/e2e/slow/benchmark/property/load/security 的标记体系完整。
3. **Makefile**: 16 个快捷命令，设计合理。
4. **GitHub Actions**: 7 阶段流水线的架构设计完整（虽然版本号有错误）。
5. **requirements.txt 版本锁定**: 从 `>=` 改为 `==`，这是 P0 要求的修复。

### 6.2 夸大或未验证的声称

1. **"624 测试通过"**: 无法独立验证。审计环境无法运行，且声称的 600 个原有测试在 P0 前审计中也无法验证。
2. **"pytest-xdist CPU 核数级加速"**: 实际上 SQLite 锁冲突导致并行测试失败。对数据库测试项目不适用。
3. **"mutmut 配置就绪"**: 只是安装了依赖，从未运行。无配置文件。
4. **"Locust 3 种场景"**: 文件存在但未运行，未验证可运行性。
5. **"13 项性能基线已建立"**: 单次运行不等于基线。基线需要多次运行和保存历史数据。
6. **"Hypothesis ~1200 边界用例"**: 是估算而非实际计数。max_examples=100×11 测试=1100，但不一定全部生成。

### 6.3 严重问题

1. **pytest 版本降级**: 从 9.1.1 → 8.4.2，可能引入兼容性问题。
2. **CI/CD 版本号错误**: `ruff==0.15.20` 和 `mypy==2.1.0` 不存在，CI 会直接失败。
3. **覆盖率检查被关闭**: `cov-fail-under=0` 等于不检查覆盖率。
4. **conftest.py 冲突**: 根目录和 tests/ 目录的 conftest.py 可能冲突。
5. **SQLite 锁冲突**: 并行测试不可行，但 Makefile 默认使用 `-n auto`。

---

## 七、修复建议

### P0（立即修复）

| # | 问题 | 修复方案 | 工作量 |
|---|------|---------|--------|
| 1 | CI/CD 版本号错误 | `ruff==0.11.0`, `mypy==1.15.0` | 5min |
| 2 | 覆盖率检查关闭 | `cov-fail-under=60`（至少） | 5min |
| 3 | Makefile 并行默认 | `-n auto` 改为 `-n 0`（或检测 SQLite 测试时串行） | 10min |
| 4 | conftest.py 冲突 | 删除根目录 `conftest.py` 或合并到 `tests/` | 15min |
| 5 | pytest 版本降级影响 | 验证 pytest 8.4.2 与现有测试的兼容性 | 30min |

### P1（短期修复）

| # | 问题 | 修复方案 | 工作量 |
|---|------|---------|--------|
| 6 | mutmut 实际运行 | 创建 `.mutmut` 配置并运行一次 | 2h |
| 7 | Locust 实际运行 | 启动 FastAPI + 运行 Locust 验证 | 1h |
| 8 | benchmark 基线建立 | 运行 `--benchmark-autosave` 建立历史数据 | 30min |
| 9 | Hypothesis 测试验证 | 独立运行并确认 11 项全部通过 | 30min |
| 10 | 测试数量验证 | 在稳定环境中运行并记录确切的 pass/fail/skip | 1h |

### P2（中期优化）

| # | 问题 | 修复方案 | 工作量 |
|---|------|---------|--------|
| 11 | SQLite 并行支持 | 使用 `:memory:` 或临时文件避免锁冲突 | 4h |
| 12 | 测试隔离性 | 确保每个测试使用独立的数据库/Store | 1天 |
| 13 | CI/CD 实际运行 | 在 GitHub 上实际运行一次并修复问题 | 2h |
| 14 |  flaky 测试修复 | 修复 F9/F10 的测试隔离问题 | 2h |

---

## 八、审计师声明

1. 本审计基于代码静态分析，未运行动态测试（审计环境限制）。
2. 测试数量声称（624 passed）来自实施日志，无法独立验证。
3. 工具安装状态通过 `requirements.txt` 验证，但运行状态无法验证。
4. CI/CD 配置通过 `.github/workflows/test.yml` 验证，版本号错误通过 PyPI 历史记录推断。

---

*审计完成。全量测试工具链的"配置"是扎实的，但"运行"可靠性存在 5 个严重问题（版本号错误、覆盖率关闭、并行冲突、conftest 冲突、pytest 降级）。建议在修复 P0 问题后再声称工具链可用。*
