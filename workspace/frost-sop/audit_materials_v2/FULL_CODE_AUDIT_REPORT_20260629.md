# FROST-SOP 全量代码审计报告

**审计日期**: 2026-06-29  
**审计范围**: `core/` + `skills/` + `renderers/` + `api/` + `tests/` + `app.py` + `frontend/`  
**审计原则**: 颗粒度最低、最严苛、诚实、中肯  
**代码基线**: 137 Python 文件，~17,000 行核心代码，68 个测试文件，15,463 行测试代码

---

## 一、执行摘要

| 评级维度 | 评分（10分） | 说明 |
|----------|-------------|------|
| 架构设计 | 7/10 | 分形治理模型有原创性，但过度抽象 |
| 代码质量 | 5/10 | 风格不一致，大文件问题严重 |
| 安全合规 | 4/10 | **存在SQL注入风险**，无输入验证 |
| 测试覆盖 | 6/10 | 68个测试文件，但质量参差不齐 |
| 工程化 | 3/10 | 无pyproject.toml，无CI/CD，前端目录224MB |
| 文档完整 | 6/10 | 大量审计报告，但README不足 |
| 可维护性 | 4/10 | 大文件、TODO标记、双前端 |

**总体评级**: ⚠️ **C+（条件通过）** — 核心功能可用，但存在**严重安全风险和工程化债务**。

---

## 二、严重问题（S级 — 必须立即修复）

### S-001: core/db.py SQL注入风险（select_all方法）

**位置**: `core/db.py:592-594`  
**风险等级**: 🔴 **高危**

```python
def select_all(self, table: str, where: str = None, params: List[Any] = None):
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"  # ← 直接字符串拼接
```

**问题**: `where` 参数直接拼接到SQL中，如果调用方传入恶意SQL（如 `where="1=1; DROP TABLE tasks; --"`），会导致数据泄露或破坏。

**修复方案**:
```python
def select_all(self, table: str, where: str = None, params: List[Any] = None):
    # 白名单验证表名
    ALLOWED_TABLES = {"tasks", "agents", "skills", ...}
    if table not in ALLOWED_TABLES:
        raise ValueError(f"Invalid table: {table}")
    
    sql = f"SELECT * FROM {table}"
    if where:
        sql += f" WHERE {where}"  # 仍需要调用方确保 where 安全
    # 或者：只接受预定义的 where 条件模板
```

**影响范围**: 所有调用 `select_all` 的地方，包括 `api/main.py`、`app.py` 等。

---

### S-002: core/db.py SQL注入风险（insert/update/delete方法表名）

**位置**: `core/db.py` 多处  
**风险等级**: 🟡 **中危**

```python
# insert, update, delete, select_one 中都有：
sql = f"INSERT INTO {table} (...) VALUES (...)"
sql = f"UPDATE {table} SET ..."
sql = f"DELETE FROM {table} WHERE ..."
sql = f"SELECT * FROM {table} WHERE ..."
```

**问题**: 表名通过 f-string 直接拼接。虽然表名通常来自内部代码，但如果表名从外部输入（如REST API参数），可导致SQL注入。

**修复方案**: 添加表名白名单验证。

---

### S-003: core/db.py SQL注入风险（ALTER TABLE迁移）

**位置**: `core/db.py:410,429,445,476`  
**风险等级**: 🟡 **中危**

```python
cursor.execute(f"ALTER TABLE energy_log ADD COLUMN {col_name} {col_def}")
```

**问题**: `col_name` 和 `col_def` 直接拼接到SQL中。`col_def` 可能包含恶意SQL。

---

### S-004: frontend/ 目录仍然存在（Next.js前端）

**位置**: `frontend/`  
**风险等级**: 🟡 **中危（工程化）**

**问题**:
1. 目录占用 **224MB**（主要是 `node_modules/`）
2. 双前端并存（Streamlit + Next.js），资源浪费
3. `.gitignore` 已排除 `node_modules/` 和 `.next/`，但源码仍在 git 中
4. 与深度调研报告结论一致："双前端资源浪费"

**修复方案**: `rm -rf frontend/`

---

## 三、架构问题（A级 — 应尽快修复）

### A-001: app.py 过大（2,477行，519处Streamlit调用）

**位置**: `app.py`  
**严重程度**: 🔴 **高**

**问题**: 单文件2,477行，包含：
- 页面配置（CSS注入、布局）
- 业务逻辑（任务创建、Agent执行）
- 数据查询（数据库直接查询）
- 成本追踪
- 日终回顾
- 项目切换

这违反了**单一职责原则**。Streamlit 应用应该拆分为：
- `pages/` 目录下的多页面应用
- `components/` 目录下的可复用组件
- `services/` 目录下的业务逻辑

**建议**: 将 `app.py` 拆分为至少 5-8 个文件。

---

### A-002: 缺少 pyproject.toml

**严重程度**: 🔴 **高**

**问题**: 没有现代 Python 项目配置，导致：
- 无法使用 `pip install -e .` 安装
- 没有工具配置（ruff, mypy, pytest）
- 无法发布到 PyPI
- 依赖版本没有锁定

---

### A-003: requirements.txt 格式问题

**严重程度**: 🟡 **中**

**问题**: 文件使用 CRLF 行尾（`\r\n`），在 Unix 环境下可能导致问题。  
**修复**: `dos2unix requirements.txt` 或重新保存为 LF。

---

### A-004: 前端双轨制（Streamlit + Next.js）

**严重程度**: 🔴 **高**

**问题**: 同时维护两套前端：
- Streamlit: `app.py` (2,477行) + `core/workbench.py` (476行) — 22处引用
- Next.js: `frontend/` (224MB) — 已停止维护

资源浪费，维护成本翻倍。

---

### A-005: 6处 TODO/FIXME 标记

**位置**: `core/armory.py:1012`, `core/graph_executor.py:317,354`, `skills/hunt.py:115,259,497`  
**严重程度**: 🟡 **中**

说明这些功能是**未完成的占位符**。

---

## 四、代码质量问题（B级）

### B-001: 类型注解覆盖率低

虽然核心类（`PanelDefinition`, `DecisionRecord`）有类型注解，但大量函数缺少返回类型注解，特别是 `skills/` 目录下的函数。

### B-002: 测试质量参差不齐

68个测试文件，15,463行测试代码，但：
- 测试命名不规范（`test_f6_5_saved_beans.py`, `test_f16_api.py`）
- 测试文件过大（部分超过500行）
- 缺乏测试配置（`pytest.ini`）

### B-003: 缺少 CI/CD 配置

无 `.github/workflows/`, `.gitee-ci.yml` 等。

### B-004: 缺少 pre-commit hooks

无代码提交前检查。

---

## 五、设计亮点（值得保留）

### ✅ D-001: 分形治理架构

`Agent` → `Store` → `Skill` → `SOP` 四原子设计清晰，分形递归（`generation` + `max_spawn_generation`）有原创性。

### ✅ D-002: EventBus 事件系统

`core/event_bus.py` (637行) 完整实现了发布/订阅模式，支持事件持久化，线程安全。

### ✅ D-003: DecisionFlow 状态机

`core/panel_decision.py` (524行) 实现了完整的7态决策流程（PENDING→IN_PROGRESS→APPROVED/REJECTED/MODIFIED/TIMEOUT/CANCELLED），支持多级审批和超时处理。

### ✅ D-004: Panel 系统

- `core/panel_generator.py` (543行): 支持自动生成 COCKPIT/INPUT/REVIEW/DECISION 面板
- `core/panel_data_provider.py` (293行): 支持 `family:`, `intel:`, `task.status` 等数据源前缀
- `core/panel_adapters.py` (370行): 整合适配器，一键集成
- `renderers/cli_renderer.py` (285行): CLI 渲染引擎，支持所有组件类型
- `renderers/streamlit_renderer.py` (442行): Streamlit 渲染引擎

### ✅ D-005: 安全模块

`core/secrets.py` (348行): AES-256-GCM 加密存储 API Key，使用 PBKDF2HMAC 密钥派生，机器绑定。

### ✅ D-006: 成本追踪

`core/cost.py`: LLM 调用成本追踪，支持预算限制。

### ✅ D-007: 数据库层

`core/db.py` (982行): 17张表，SQLite + WAL 模式，支持完整 CRUD。

---

## 六、文件级问题索引

| 文件 | 行数 | 问题 | 严重度 |
|------|------|------|--------|
| `app.py` | 2,477 | 过大，职责混杂，519处Streamlit调用 | A-001 |
| `core/db.py` | 982 | SQL注入风险（3处） | S-001~S-003 |
| `skills/orchestration.py` | 823 | input()调用在测试环境有问题 | B-001 |
| `core/event_bus.py` | 637 | 无 | — |
| `core/agent.py` | 521 | 无 | — |
| `core/panel_generator.py` | 543 | 无 | — |
| `core/panel_decision.py` | 524 | 无 | — |
| `core/memory.py` | 312 | 无 | — |
| `skills/assemble.py` | 357 | 无 | — |
| `skills/llm.py` | 423 | 无 | — |
| `api/main.py` | 563 | 无 | — |
| `renderers/cli_renderer.py` | 285 | 无 | — |
| `renderers/streamlit_renderer.py` | 442 | 无 | — |
| `core/workbench.py` | 476 | 无 | — |
| `frontend/` | 224MB | 应删除 | S-004 |
| `requirements.txt` | 30 | CRLF行尾 | A-003 |

---

## 七、修复优先级清单

### P0（立即 — 本周内）

| # | 问题 | 文件 | 工作量 | 修复方案 |
|---|------|------|--------|---------|
| 1 | SQL注入（select_all where拼接） | `core/db.py:592` | 30分钟 | 添加where条件白名单或仅接受预定义模板 |
| 2 | SQL注入（表名拼接） | `core/db.py` 多处 | 30分钟 | 添加表名白名单常量 |
| 3 | SQL注入（ALTER TABLE） | `core/db.py:410` | 20分钟 | 添加列名/类型白名单 |
| 4 | 删除 frontend/ | `frontend/` | 10分钟 | `rm -rf frontend/` + `git rm -r frontend/` |
| 5 | 添加 pyproject.toml | 根目录 | 30分钟 | 创建项目配置 + ruff配置 |
| 6 | 修复 requirements.txt CRLF | `requirements.txt` | 5分钟 | `dos2unix` 或重新保存 |

### P1（短期 — 2周内）

| # | 问题 | 文件 | 工作量 | 修复方案 |
|---|------|------|--------|---------|
| 7 | 拆分 app.py | `app.py` | 2-3天 | 拆分为 pages/ + components/ + services/ |
| 8 | 添加 CI/CD | `.github/workflows/` | 2小时 | GitHub Actions: ruff + pytest |
| 9 | 添加 pytest.ini | 根目录 | 15分钟 | 配置测试路径和插件 |
| 10 | 处理 TODO/FIXME | 6处 | 1天 | 实现或删除 |

### P2（中期 — 1个月内）

| # | 问题 | 文件 | 工作量 | 修复方案 |
|---|------|------|--------|---------|
| 11 | 类型注解全覆盖 | 所有文件 | 3-5天 | 添加 mypy 检查 |
| 12 | 测试重构 | `tests/` | 1周 | 按模块组织，删除重复 |
| 13 | 添加 pre-commit | `.pre-commit-config.yaml` | 1小时 | ruff + pytest |
| 14 | 安全扫描自动化 | CI/CD | 2小时 | bandit + safety |

---

## 八、与外部调研报告的对照

| 调研报告判断 | 实际代码状态 | 结论 |
|-------------|-------------|------|
| "6-12个月才能做出MVP" | 核心框架已实现（17,000行代码） | **报告过旧** |
| "Panel 渲染引擎是空白" | CLI + Streamlit 渲染器已可用 | **报告过旧** |
| "DecisionFlow 是理论" | 已集成到 SOP 执行引擎 | **报告过旧** |
| "公司指挥平台有需求但目标不清" | 代码支持，但无用户验证 | **报告准确** |
| "双前端资源浪费" | frontend/ 224MB 仍在 | **报告准确** |
| "有机体隐喻两极分化" | 代码中大量使用（君主/军师/长老/府兵） | **报告准确** |
| "社区≠用户" | 0 stars，无 GitHub 仓库 | **报告准确** |
| "Open Core 是现实路径" | 尚未开源 | **报告准确** |

**核心结论**: 技术实现已远超报告假设，但**工程化、安全、用户验证**仍然是严重短板。

---

## 九、最终建议

### 立即执行（本周）

1. **修复 S-001~S-003 SQL注入**（各30分钟）
2. **删除 frontend/ 目录**（10分钟）
3. **添加 pyproject.toml**（30分钟）
4. **修复 requirements.txt CRLF**（5分钟）

### 短期执行（2周）

5. **拆分 app.py**（2-3天）
6. **添加 CI/CD**（2小时）
7. **处理 TODO/FIXME**（1天）

### 中期执行（1个月）

8. **类型注解全覆盖**（3-5天）
9. **测试重构**（1周）
10. **GitHub 发布**（1天）

### 根本问题

FROST-SOP 已经从"白皮书"变成了"可运行的代码库"（17,000行）。最大的风险不是"写不完"，而是：
- **安全风险**：SQL注入可能导致数据泄露
- **维护风险**：2,477行的 app.py 无法长期维护
- **用户风险**：没有真实使用者，代码再完整也是0

**建议优先级**: 安全修复 → 工程化 → 拆分大文件 → 找第一个使用者。

---

*审计完成。共发现 3 个严重问题（S级）、5 个架构问题（A级）、4 个代码质量问题（B级）。*
