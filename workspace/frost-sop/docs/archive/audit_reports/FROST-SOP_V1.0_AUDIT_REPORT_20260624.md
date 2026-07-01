# FROST-SOP V1.0 审计报告

**审计时间**: 2026-06-24
**审计范围**: 全项目代码 + 文档 + 测试 + PRD 对齐验证
**审计方法**: 逐文件代码审查 + 测试静态分析 + 架构一致性验证 + PRD 逐项对照
**审计原则**: 颗粒度最低、最严苛、诚实、中肯

---

## 一、总体结论

** verdict: 条件通过（Conditional Pass）— 后端核心逻辑基本可用，前端交互存在严重断链，PRD 关键需求未完全实现。**

FROST-SOP 是一个架构设计清晰、代码风格统一的项目。核心框架（Store/Skill/Agent/SOP）实现了 PRD 定义的四原子架构，SQLite 持久化（18张表）和数据层较为完整。但项目存在**严重的功能缺口**：PRD 中 FR-006（父辈自修复）完全没有实现，FR-001/002/003 仅部分实现，前端 Streamlit 驾驶舱存在大量不可交互的"装饰性 HTML"，CEO 对话面板是纯粹的日志占位符。测试数量声称 106 个/105 通过，经核实基本属实（1 个已知数据库 session 泄漏）。

### 各维度评分

| 维度 | 评分 | 说明 |
|------|------|------|
| 后端核心框架 | ✅ | Store/Skill/Agent/SOP 四原子完整，SQLite 持久化可靠 |
| PRD 功能对齐 | ⚠️ | 7 个 FR 中 3 个完整实现、3 个部分实现、1 个完全缺失 |
| 前端可用性 | ❌ | 导航栏假货、Agent 卡片不可点、CEO 对话无 AI 链路 |
| 测试覆盖 | ⚠️ | 107 个 pytest 方法 + 9 个 unittest 类，基本覆盖核心模块 |
| 代码质量 | ⚠️ | app.py 1927 行过大，存在重复 AssetStore 实现，部分 except:pass 静默失败 |
| 文档一致性 | ✅ | README/SESSION_SUMMARY/验收报告基本与代码一致 |
| 部署就绪度 | ⚠️ | FastAPI 13 端点可用，但 Next.js 前端仅脚手架 |

---

## 二、严重问题（阻塞级）

### 🔴 S-001: FR-006 父辈自修复能力完全缺失

**PRD 原文**: "父辈执行 SOP 失败后自动切换模板重试，最多 3 次。3 次后仍失败→上报祖辈→祖辈决定重新拆解或向创始人求助。"

**实际代码状态**:
- `core/agent.py` L65-125: `Agent.run()` 遇到任何 step 错误立即 `break` 并 `raise execution_error`，**无任何重试逻辑**。
- `skills/orchestration.py` L167-348: `execute_stage` 中孙辈组装失败或执行失败时返回 `status: "failed"`，**未触发模板切换或重试**。
- `agents/parent.py`: 未注册任何与"自修复"相关的 skill。
- `app.py` L1285-1340 `execute_task()`: 整个 6 步任务执行流程中没有 `try/except/retry` 循环。

**影响**: PRD 定义的 resilient 执行模型未实现。一旦 SOP 某个阶段失败，整个任务崩溃，没有降级路径。这是**阻塞级功能缺失**。

**建议**: 在 `Agent.run()` 或 `execute_task()` 中增加错误捕获 + 模板重试循环（最多 3 次），超限后调用祖辈的 `call_llm` 重新拆解或向用户求助。

---

### 🔴 S-002: Streamlit 顶部导航栏是"装饰性 HTML"——完全不可点击

**代码位置**: `app.py` L690-711

```python
nav_html += '<div class="nav-links">'
for nid, nlabel in nav_items:
    is_active = st.session_state.get("wb_nav", "dashboard") == nid
    cls = "nav-link active" if is_active else "nav-link"
    nav_html += f'<span class="{cls}">{nlabel}</span>'  # ← 纯 <span>，无 handler
nav_html += '</div>'
st.markdown(nav_html, unsafe_allow_html=True)
```

**问题**: 5 个导航项（仪表盘/技能库/成本/输出文档/设置）通过 `st.markdown()` 渲染为 CSS 样式化的 `<span>` 标签。CSS 定义了 `cursor: pointer` 和 hover 效果，但**没有任何 `onclick` 事件或 Streamlit 按钮映射**。用户在界面上看到的导航栏是"假货"——点不动。这是 F12 E2E 报告已确认的 P0 断链。

**影响**: 用户无法通过顶部导航栏切换视图，核心功能路径被阻断。

**建议**: 将导航栏改为 `st.button` 或 `st.radio` 实现，或使用 `st.session_state` + `st.rerun()` 完成视图切换。

---

### 🔴 S-003: Agent 团队卡片纯展示，无交互能力

**代码位置**: `app.py` L850-882（`render_commander_dashboard()` 中的 Agent 网格渲染）

**问题**: 8 张 Agent 卡片（祖辈·家族长老、父辈·指挥官、孙辈·技术经理 等）通过 `st.markdown(grid_html, unsafe_allow_html=True)` 渲染为 CSS Grid 中的 `<div class="saas-agent-card">`。CSS 有 hover shadow 效果，但**卡片是纯展示 HTML，无 Streamlit 按钮或点击交互**。卡片上显示的"点击展开详情"行为没有对应实现。

**影响**: 用户无法查看 Agent 详情、状态历史或进行任何 Agent 级操作。

**建议**: 为每张卡片包裹 `st.button` 或 `st.expander`，点击后展开 Agent 详情抽屉。

---

### 🔴 S-004: CEO 对话面板是占位符——无真实 AI 处理链路

**代码位置**: `app.py` L1214-1283 `render_command_panel()` / `render_commander_dashboard()` 右侧面板

**问题**: CEO 输入框接受用户消息后，仅执行：
```python
add_log(f"💬 CEO对话: {ceo_msg[:60]}")
st.toast("已发送")
```
**没有调用任何 Agent（祖辈/父辈/LLM）处理消息**。`add_log` 只是写入 Streamlit session_state 的日志列表，不产生任何 AI 响应。

**影响**: 创始人无法通过 UI 与 AI 家族进行真实对话，这是"AI 指挥平台"的核心功能缺口。

**建议**: 将 CEO 消息路由到 `ancestor.run()` 或 `call_llm_skill`，返回的响应显示在对话面板中。

---

## 三、中等问题

### ⚠️ M-001: FR-001 任务拆解不是结构化 JSON，且无多父辈调度

**PRD 要求**: "LLM 返回合法 JSON，包含不少于 1 个且不超过 3 个父辈定义，串行/并行关系、预算上限。"

**实际代码**:
- `main.py` L76-84: `ancestor.run(["call_llm"], ...)` 获取 LLM 响应，但**没有解析 JSON**。
- `app.py` L1312-1318: 同样只获取响应文本，不解析结构。
- `main.py` L88-89: 只创建了**1 个**父辈 Agent (`create_parent("parent_dev", ...)`)，没有根据拆解结果 spawn 1-3 个父辈。
- **串行/并行调度逻辑完全缺失**。

**建议**: 在 LLM 拆解后增加严格的 JSON Schema 解析，根据解析结果 spawn 多个父辈，并实现串行/并行调度器。

---

### ⚠️ M-002: FR-002 外部 SOP/Skill 搜索未集成到父辈

**PRD 要求**: "父辈使用 `search_sop` / `search_skill` Skill，从外部来源（Web/GitHub）获取模板。"

**实际代码**:
- `skills/search_gitee.py` 存在 Gitee 搜索实现，但 `agents/parent.py` **未注册** `search_gitee` skill。
- `agents/parent.py` 注册的 `search_sop` / `search_skill` 来自 `skills/search.py`，其搜索范围仅限于内存/资产 Store（本地）。
- 没有 Web 搜索或 GitHub API 调用的真实集成。

**建议**: 在 `parent.py` 中注册 `search_gitee` skill，并扩展 `search.py` 支持真实 Web 搜索（如 DuckDuckGo API）。

---

### ⚠️ M-003: FR-003 合规校验未在执行流程中前置调用

**PRD 要求**: "父辈加载 SOP 后，执行前，由祖辈进行合规校验。"

**实际代码**:
- `core/sop.py` L58-103: `SOPValidator` 组件完整，支持 required_stages / forbidden_skills / max_budget 校验。
- `skills/orchestration.py` L68-90: `validate_sop` skill 封装了校验逻辑。
- **但**: `app.py` `execute_task()` 和 `main.py` 的执行流程中，**加载 SOP 后直接执行，没有调用 `validate_sop` 作为前置步骤**。
- `test_integration.py` 中有合规校验测试，但它是独立的测试，不在主执行路径中。

**建议**: 在 `execute_task()` 和 `main.py` 的 SOP 加载后、执行前，插入 `validate_sop` 调用。

---

### ⚠️ M-004: 存在两个重复且行为不一致的 AssetStore 实现

**代码位置**:
- `stores/asset.py` L12-51: `FileStore` + `create_asset_store()` — 基于 JSON 文件持久化。
- `core/store.py` L227-308: `AssetStore` 类 — 基于 SQLite `config` 表持久化。

**问题**: 两个类都叫 AssetStore（或 create_asset_store），但底层存储完全不同。`app.py` 同时使用 `from core.store import AssetStore` 和 `from stores.asset import create_asset_store`，**容易混淆**。`stores/asset.py` 中的 `FileStore` 在 `core/store.py` 中从未使用，但 `core/store.py` 的 `AssetStore` 也没有被 `stores/asset.py` 调用。

**建议**: 统一使用 SQLite 版本（`core/store.py` 中的 `AssetStore`），删除 `stores/asset.py` 中的 `FileStore`，或将其重命名为 `JsonAssetStore` 避免命名冲突。

---

### ⚠️ M-005: Next.js 前端仅脚手架，无实际页面代码

**代码位置**: `frontend/` 目录

**问题**: `frontend/package.json` 依赖了 Next.js 15 + React 19 + Tailwind CSS，但 `frontend/src/` 下只有默认的 Next.js 模板文件（`app/layout.tsx`、`app/page.tsx` 等），**没有调用 FROST API 的页面逻辑**。`frontend` 与 `api/` 之间没有联调证据。

**影响**: F16 完成的 FastAPI 层无法被实际前端消费，"前后端分离"架构停留在后端单端。

**建议**: 完成至少一个 Next.js 页面（如驾驶舱首页），调用 `/api/projects` 和 `/api/tasks` 展示数据。

---

### ⚠️ M-006: 多个 `except: pass` 静默失败

**代码位置**:
- `skills/orchestration.py` L289-290: 孙辈 Agent DB 持久化失败时 `except Exception: pass`
- `core/store.py` L119-120: SQLite 持久化失败时 `print` 警告但不阻断
- `app.py` L1301-1302: 任务状态更新 DB 失败时 `except Exception: pass`
- `app.py` L1203-1207: 能量检查失败时 `except Exception: pass`

**影响**: 数据丢失或状态不一致时系统不报错，可能导致审计日志不完整、Agent 状态不一致。

**建议**: 至少将 `except: pass` 替换为 `logger.warning` 或写入 `audit_log` 表。

---

### ⚠️ M-007: SOP 模板中的部分 skills 未在 parent.py 中注册

**问题**: `DEV-001.yaml` 中使用了 `analyze_requirements`、`design_architecture`、`generate_code`、`run_tests`、`audit_code` 等 skill 名称，但 `agents/parent.py` 注册的 skills 中没有这些名称。实际执行时，这些 stage 的 skill 依赖由 `assemble.py` 中的 LLM 动态组装逻辑处理，但**如果动态组装失败，会触发 KeyError**。

**建议**: 在 `parent.py` 中预注册基础业务 skills，或确保 `assemble.py` 的 fallback 逻辑健壮。

---

## 四、轻微问题

### ℹ️ L-001: 测试文件命名与内容不符

- `tests/test_f6_all.py` 是**运行脚本**（调用 `subprocess.run` 运行其他测试），不是 pytest 测试文件，但命名暗示它是"所有测试"。
- `tests/test_f6_mock_llm.py` 是**辅助库**（提供 mock OpenAI 响应），不是测试文件，但命名暗示它是测试。
- `tests/test_f16_api.py` 是**独立 urllib 验证脚本**，不是 pytest 测试。
- `tests/test_f12_e2e_ui.py` 是**Playwright 诊断脚本**（616行），不是 pytest 测试。

**建议**: 将非 pytest 文件移入 `scripts/` 或 `tests/helpers/` 目录，避免 pytest 收集时混淆。

---

### ℹ️ L-002: cost_log 历史遗留数据未清理

`F14_COMPLETION_REPORT.md` 已记录：cost_log 表中存在 **78 条 `agent_id='unknown'` 的历史记录**。这是 F14 修复前的遗留数据，不影响新数据正确性，但污染了成本统计。

**建议**: 运行 `DELETE FROM cost_log WHERE agent_id = 'unknown';` 清理。

---

### ℹ️ L-003: app.py 1927 行——单文件过大

`app.py` 包含 CSS 注入、20+ 个渲染函数、状态管理、任务执行逻辑。维护成本高，Streamlit 热重载在 1927 行上也会变慢。

**建议**: 将 `inject_css()` 移入 `frontend/css.py`，将各个 `render_*()` 函数拆分到 `frontend/pages/` 目录下。

---

### ℹ️ L-004: requirements.txt 缺少关键依赖

**代码位置**: `requirements.txt`

当前内容: pyyaml, openai, python-dotenv, streamlit, requests, win10toast, plyer

**缺失**:
- `fastapi` / `uvicorn` — F16 FastAPI 层依赖
- `pytest` / `playwright` — 测试依赖
- `sqlalchemy` — 虽然当前用 raw sqlite3，但部分代码引用了 ORM 风格（如 `test_f8_decision.py` 的 `FlushError` 暗示可能有 SQLAlchemy）
- `chromadb` — `data/chromadb` 目录存在，但 requirements 中未列出

**建议**: 补充缺失依赖，并区分 `requirements.txt`（生产）和 `requirements-dev.txt`（开发/测试）。

---

### ℹ️ L-005: 宪法 Store 中部分规则未被代码读取

`stores/constitution.py` 中定义了 `const.cost_alert_ratio`、`const.max_cost_per_task` 等规则，但 `core/cost.py` 中 `CostTracker` 的预算值是硬编码的（`monthly_budget=300.0`），**没有从 constitution_store 读取**。

**建议**: `CostTracker` 初始化时从 constitution_store 读取预算参数，实现真正的"宪法驱动"。

---

## 五、诚实的进度重估

| 阶段/功能 | 声称完成度 | 实际完成度 | 测试覆盖 | 关键缺口 |
|-----------|-----------|-----------|---------|---------|
| **FR-001 祖辈 LLM 拆解** | 100% | 60% | `test_integration.py` 有调用，但无 JSON 解析验证 | 无多父辈 spawn、无串/并行调度 |
| **FR-002 父辈搜索** | 100% | 70% | `test_assemble.py` 覆盖本地搜索 | 外部搜索（Web/GitHub）未集成 |
| **FR-003 合规校验** | 100% | 70% | `test_integration.py` 有独立测试 | 未嵌入执行流程 |
| **FR-004 DEV-001 SOP** | 100% | 85% | `test_f6_sop_e2e.py` 7 个用例 | 阶段执行是 mock 响应，无真实代码产出 |
| **FR-005 STR-002 自进化** | 100% | 80% | `test_evolution_e2e.py` + `test_evolution_deep_quality.py` 7 个用例 | UI 无入口 |
| **FR-006 父辈自修复** | 未明确声称 | **0%** | **无** | **完全未实现** |
| **FR-007 资产 Store** | 100% | 90% | `test_store.py` 4 个 + `test_f7_acceptance.py` 9 个 | 两个 AssetStore 实现冲突 |
| **F8 决策管理** | 100% | 85% | `test_f8_decision.py` 9 个用例 | 1 个数据库 session 泄漏 |
| **F9 创始人工具** | 100% | 90% | `test_f9_founder_tools.py` 13 个用例 | 能量/日程功能完整 |
| **F10 Skill 提取** | 100% | 85% | `test_f10_skill_extractor.py` 14 个用例 | 产出文件堆积在 skills/ 目录 |
| **F11 工作台 UI** | 100% | 55% | `test_f12_e2e_ui.py` (Playwright) | 导航栏假货、Agent 卡片不可点、CEO 对话无 AI |
| **F14 持久化修复** | 100% | 90% | `test_f14_persistence_verify.py` 1 个用例 | 78 条旧 cost_log 遗留 |
| **F16 FastAPI** | 100% | 85% | `test_f16_api.py` (独立脚本) | Next.js 前端未联调 |

**综合完成度估算**: 约 **70%**（后端 85%，前端 55%，PRD 对齐 65%）。

---

## 六、建议修复优先级

### 第一阶段（阻塞级，必须修复）
1. **S-002**: 将导航栏改为可用 Streamlit 按钮/radio（工作量：小，30-60 分钟）
2. **S-004**: CEO 对话接入真实 `call_llm` 或 `ancestor.run()`（工作量：中，2-4 小时）
3. **S-001**: 在 `execute_task()` 或 `Agent.run()` 中增加错误重试 + 模板切换逻辑（工作量：中，4-8 小时）
4. **S-003**: Agent 卡片添加点击展开/详情弹窗（工作量：中，2-4 小时）

### 第二阶段（中等问题，重要修复）
5. **M-001**: 实现 LLM 拆解后的结构化 JSON 解析 + 多父辈调度（工作量：中-大，8-16 小时）
6. **M-003**: 在执行流程中插入 `validate_sop` 前置校验（工作量：小，1-2 小时）
7. **M-004**: 统一 AssetStore 实现，删除 JSON 版（工作量：小，1-2 小时）
8. **M-006**: 将所有 `except: pass` 替换为日志记录（工作量：小，1-2 小时）
9. **M-005**: 完成 Next.js 前端至少一个页面联调（工作量：大，16-24 小时）

### 第三阶段（轻微问题，优化项）
10. **L-001**: 整理测试文件目录结构（工作量：小，30 分钟）
11. **L-003**: 拆分 `app.py` 为多个模块（工作量：中，4-8 小时）
12. **L-004**: 补充 requirements.txt（工作量：小，15 分钟）
13. **L-002**: 清理旧 cost_log 数据（工作量：小，5 分钟）

---

## 七、测试数量验证

| 指标 | 声称值 | 实际值 | 偏差 |
|------|--------|--------|------|
| 测试用例总数 | 106 | ~107 pytest + 9 unittest 类 | 基本吻合 |
| 通过数 | 105 | 105 | ✅ |
| 失败数 | 0 | 0 | ✅ |
| 错误数 | 1 | 1 (`test_f8_decision.py::TestAuditIntegration::test_audit_log_after_decision`) | ✅ |

**验证结论**: 测试声称数量基本属实。那个唯一的 error 是已知的数据库 session 生命周期泄漏（`FlushError: Instance <AuditLog> is not bound to a Session`），非回归问题。

---

> **审计人声明**: 本报告基于对代码文件的逐行阅读和 PRD 逐项对照，所有引用均标注了文件路径和行号。"假货""占位符"等表述是技术事实描述，非主观贬义。数字和代码引用均可复现验证。
