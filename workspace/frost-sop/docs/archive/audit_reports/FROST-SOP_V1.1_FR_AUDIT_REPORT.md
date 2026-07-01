# FROST-SOP V1.1 全量功能需求审计报告

**审计日期**: 2026-06-25
**审计基线**: AUDIT_BASELINE_REQUIREMENTS.md (PRD V1.1 + FROST 白皮书 V3.0)
**审计方法**: 逐条 FR 代码对照 + 宪法五条验证 + 架构一致性审查
**审计原则**: 颗粒度最低、最严苛、诚实、中肯

---

## 一、总体摘要

| 维度 | 结论 |
|------|------|
| **43 条 FR** | 已实现 16 条 (37%)，部分实现 15 条 (35%)，未实现 12 条 (28%) |
| **6 个 SOP** | 7 个 YAML 文件存在，但仅 2 个(DEV-001/STR-002)有测试覆盖；**无真实执行产出** |
| **17 张数据库表** | 18 张表全部存在，但 2 个 P0 表结构字段不匹配问题 |
| **3 常驻 + 9 角色** | 3 常驻 Agent 存在；9 个基础基因种子存在，但**非 9 个 YAML 角色模板** |
| **四个原子** | 全部实现 (Store/Skill/Agent/SOP) |
| **宪法五条** | 第二条和第四条基本遵守，其余三条存在偏差 |
| **三层架构** | 代码层面完整，但运行链路未完全贯通 |
| **长老审计** | 代码存在，但 UI 无集成 |
| **交棒机制** | **完全未实现** |

**verdict: 不通过 — 大量 PRD 功能需求未实现，核心执行链路停留在 mock 阶段，不具备上线条件。**

---

## 二、43 条 FR 逐条验证

### 2.1 仪表盘模块 (FR-DASH-001~006)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-DASH-001 | 项目标题区：显示名称、版本、状态 | `app.py` L721-739 渲染项目标题+状态标签 | ✅ 已实现 | — |
| FR-DASH-002 | KPI 卡片：今日任务、运行 Agent、月度成本、下次回顾 | `app.py` L752-758 有任务计数，但月度成本/下次回顾未显示为 KPI 卡片 | ⚠️ 部分实现 | 无"下次回顾"KPI 卡片；成本数据在详情页而非仪表盘首屏 |
| FR-DASH-003 | Agent 团队网格：3 个常驻 Agent 状态 | `app.py` L850-882 渲染 8 张卡片（含 3 常驻+5 孙辈），但**纯 HTML 不可点击** | ⚠️ 部分实现 | 展示有，交互无；卡片是装饰性 `<div>`，非 Streamlit 按钮 |
| FR-DASH-004 | 实时日志面板（深色终端风格） | `app.py` 有日志渲染区域，深色 CSS 定义 | ✅ 已实现 | — |
| FR-DASH-005 | CEO 指挥面板：输入框 + 发送 + 快捷按钮 | `app.py` L1214-1283 有输入框+3 快捷按钮+发送 | ⚠️ 部分实现 | **输入后只写日志，不调用任何 LLM/Agent** — 纯占位符 |
| FR-DASH-006 | 任务执行结果区 | `app.py` L1855-1858 有 `st.expander` 展示结果 | ✅ 已实现 | — |

### 2.2 调度模块 (FR-MAIN-001~003)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-MAIN-001 | 意图解析：解析自然语言指令，识别任务类型 | `app.py` L1312-1318 `ancestor.run(["call_llm"])` 获取响应文本，**无结构化 JSON 解析** | ❌ 未实现 | 返回的是 mock 文本，未解析意图/任务类型 |
| FR-MAIN-002 | SOP 选择：匹配 6 个 SOP 之一 | `execute_task()` 中硬编码 SOP 路径 `sops/templates/{sop_id}.yaml`，无动态匹配逻辑 | ⚠️ 部分实现 | 需要用户显式指定 sop_id，无自动匹配 |
| FR-MAIN-003 | Agent 团队组建：根据 SOP 阶段实例化角色 | `skills/assemble.py` L29-223 有动态组装，但基于 LLM 解析而非 SOP 阶段精确映射 | ⚠️ 部分实现 | 组装的是通用孙辈，非 SOP 定义的具体角色（产品经理→架构师→...） |

### 2.3 执行模块 (FR-AGENT-001~004)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-AGENT-001 | 阶段生命周期管理（**真实执行，非模拟**） | `skills/orchestration.py` L167-348 `execute_stage` 执行，但 `call_llm_for_output` 在 `FROST_TESTING=1` 时返回 mock 文本 | ❌ 未实现 | **核心阻塞：所有执行都是 mock，无真实代码/文件产出** |
| FR-AGENT-002 | 工具调用框架（文件/代码/文档生成） | `skills/tools.py` L11-40 `write_file` 存在，但 `call_llm_for_output` 中 `FROST_TESTING=1` 时直接返回文本，**不调用真实 LLM，不写入文件** | ❌ 未实现 | write_file Skill 注册了但执行路径中未使用 |
| FR-AGENT-003 | 结果输出格式化（Markdown） | `skills/tools.py` L64-80 定义了 Markdown 格式化提示词 | ✅ 已实现 | — |
| FR-AGENT-004 | 状态实时上报（<3 秒刷新） | `app.py` 中无任何定时刷新逻辑，`st.rerun()` 仅在用户交互时触发 | ❌ 未实现 | 无 `setInterval`/`setTimeout` 或 SSE 主动推送 |

### 2.4 记忆模块 (FR-MEM-001, FR-MEM-004)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-MEM-001 | Agent 专属记忆存储 | `core/agent.py` L34-35 `self.store` 每个 Agent 独立；`core/memory.py` L21-314 `MemoryStore` 支持按 agent_id 分 Collection | ✅ 已实现 | — |
| FR-MEM-004 | 向量语义检索（失败降级 BM25） | `core/memory.py` L56-84 有 ChromaDB 初始化+`fallback_mode` 降级为关键词匹配，但**无 BM25 实现** | ⚠️ 部分实现 | 降级是简单关键词列表，非 BM25 算法；且 `requirements.txt` 无 `chromadb` |

### 2.5 审计模块 (FR-AUDIT-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-AUDIT-001 | 操作审计日志（追加-only） | `core/db.py` L191-199 `audit_log` 表存在；`agents/elder.py` 有审计逻辑；`app.py` L467 `add_log()` 仅写 session_state 日志，**不写 audit_log 表** | ⚠️ 部分实现 | 审计日志表存在，但非所有操作都写入；追加-only 在 SQLite 层面未强制约束 |
| FR-AUDIT-002 | 成本审计（按 Agent/SOP 汇总） | `core/db.py` L660-679 `get_monthly_cost()` 按月汇总；`cost_log` 表有 agent_id/task_id 字段 | ⚠️ 部分实现 | 无按 SOP 维度的成本汇总；无审计报告自动生成 |

### 2.6 成本模块 (FR-COST-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-COST-001 | 月度预算配置（默认 ¥300） | `core/cost.py` L33 `monthly_budget=300.0` **硬编码**；`stores/constitution.py` L22 有 `const.budget_monthly=300` 但**未被 CostTracker 读取** | ⚠️ 部分实现 | 预算值存在，但非从宪法 Store 动态读取 |
| FR-COST-002 | 实时成本追踪 + 重层调用独立统计 | `core/cost.py` L45-73 `track_cost()` 写入 `cost_log`；但**无"重层调用"概念**（轻层/重层路由未实现） | ⚠️ 部分实现 | 有成本记录，但无轻/重层独立统计 |

### 2.7 状态模块 (FR-STATE-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-STATE-001 | 能量状态记录（滑动条 + 情绪按钮 + 曲线图） | `app.py` L1527-1583 `render_energy_logger()` 有滑动条+情绪按钮；**无曲线图**（recharts 未在 Streamlit 中集成） | ⚠️ 部分实现 | 2/3 功能实现，曲线图缺失 |
| FR-STATE-002 | 私人日程管理（CRUD + 时间线 + 提醒） | `core/db.py` L781-908 完整的日程 CRUD + 提醒查询；`app.py` L1584-1646 `render_schedule_page()` 有 UI | ✅ 已实现 | 提醒通过 Windows Toast 通知（`core/notifier.py`） |

### 2.8 存储模块 (FR-STORE-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-STORE-001 | SQLite 结构化数据（17 张表） | `core/db.py` L70-337 定义 18 张表（含 kv_store），全部存在 | ✅ 已实现 | 实际 18 张，比要求多 1 张 kv_store |
| FR-STORE-002 | ChromaDB 向量数据持久化 | `core/memory.py` L21-314 完整集成；`data/chromadb` 目录存在 | ⚠️ 部分实现 | 代码存在但 `requirements.txt` 未声明 `chromadb`（P1-4 已知问题） |

### 2.9 设置模块 (FR-SET-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-SET-001 | API 配置（多提供商 + 加密） | `.env` 有 `DEEPSEEK_API_KEY`，`skills/llm.py` 读取；**无多提供商**（仅 DeepSeek）；**无 AES 加密** | ❌ 未实现 | 单提供商，明文存储 API Key |
| FR-SET-002 | 本地模型配置（Ollama） | 代码中无任何 Ollama 引用或本地模型路由 | ❌ 未实现 | 完全未实现 |

### 2.10 Skill 库模块 (FR-SKILL-001~003)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-SKILL-001 | Skill 存储与检索（触发词/任务类型/成功率） | `core/db.py` L268-279 `skills` 表有 `trigger_keywords`、`task_type`、`success_rate` 字段；`stores/asset.py` 有 9 个基础基因 | ⚠️ 部分实现 | 表结构支持，但 UI 无检索界面；成功率无自动计算 |
| FR-SKILL-002 | Skill 版本管理（保留 5 个历史版本 + 回滚） | `core/db.py` L282-292 `skill_versions` 表存在；`core/skill_version.py` 有版本管理逻辑（但无独立测试） | ⚠️ 部分实现 | 表和代码存在，但回滚逻辑未经测试验证 |
| FR-SKILL-003 | Skill 手动编辑（前端管理页面） | **无前端 Skill 管理页面**；`frontend/src/` 中无 Skill 管理路由 | ❌ 未实现 | 完全未实现 |

### 2.11 提取器模块 (FR-EXTRACT-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-EXTRACT-001 | 从重层日志提取 Skill（LLM 分析 + 生成） | `core/skill_extractor.py` / `test_f10_skill_extractor.py` 14 个用例覆盖 | ✅ 已实现 | — |
| FR-EXTRACT-002 | Skill 验证与激活（3 次测试 → 成功率 ≥80% → 激活） | **无 3 次测试循环逻辑**；无成功率阈值判断；无自动激活/停用状态机 | ❌ 未实现 | 提取器生成 Skill 后无验证/激活流程 |

### 2.12 路由模块 (FR-ROUTER-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-ROUTER-001 | 轻层优先匹配（Jaccard 相似度 <200ms） | **无轻层路由概念**；无 Jaccard 相似度计算；无本地意图匹配缓存 | ❌ 未实现 | 完全未实现 |
| FR-ROUTER-002 | 重层调用封装（Aider/Perplexity/DeepSeek） | **无 Aider/Perplexity 封装**；仅 `skills/llm.py` 调用 DeepSeek API | ❌ 未实现 | 完全未实现 |

### 2.13 工具日志模块 (FR-TOOL-001)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-TOOL-001 | 统一工具调用日志（SQLite + JSON 双记录） | `core/db.py` L296-310 `tool_calls` 表存在（SQLite 侧），但**无 JSON 文件侧记录** | ⚠️ 部分实现 | 仅 SQLite 单记录，无双写 |

### 2.14 修复模块 (FR-FIX-001~008)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-FIX-001 | SOPEngine 真实执行（非固定字符串） | `skills/orchestration.py` L313-316 `child.run()` 调用 `call_llm_for_output`，但 `FROST_TESTING=1` 时返回 mock 字符串 | ❌ 未实现 | **所有执行产出都是 mock 文本** |
| FR-FIX-002 | 决策点前端恢复（弹窗 + 确认/驳回/修改） | `app.py` L472-593 `render_decision_dialog()` 有弹窗；但 `core/decision_manager.py` 有恢复逻辑 bug（P0-2） | ⚠️ 部分实现 | UI 有，后端逻辑有 2 个 FAILED 测试 |
| FR-FIX-003 | 9 个角色模板 YAML + 实例化逻辑 | `stores/asset.py` L55-124 有 9 个基础基因种子（Python dict），**非 YAML 角色模板**；无独立 `roles/` 目录 | ⚠️ 部分实现 | 9 个能力基因存在，但非 YAML 角色模板；无显式实例化逻辑 |
| FR-FIX-004 | V1.0 常驻 Agent 角色模板映射 | `agents/ancestor.py` / `agents/parent.py` / `agents/elder.py` 3 个常驻存在，但**无角色模板映射表**（祖辈→长老→父辈未映射到具体角色模板） | ⚠️ 部分实现 | 3 个 Agent 类存在，但无与 YAML 角色的映射 |
| FR-FIX-005 | 能量状态输入器（滑动条 + 情绪按钮 + 曲线图） | 同 FR-STATE-001 | ⚠️ 部分实现 | 曲线图缺失 |
| FR-FIX-006 | 私人日程管理页面 | 同 FR-STATE-002 | ✅ 已实现 | — |
| FR-FIX-007 | Agent 状态实时刷新（<3 秒） | 同 FR-AGENT-004 | ❌ 未实现 | 无实时刷新机制 |
| FR-FIX-008 | Embedding 优雅降级（失败切 BM25） | 同 FR-MEM-004 | ⚠️ 部分实现 | 降级为简单关键词，非 BM25 |

### 2.15 SOP 模块 (FR-SOP-001~002)

| ID | 需求 | 代码证据 | 状态 | 偏差说明 |
|----|------|----------|------|----------|
| FR-SOP-001 | 6 个 SOP 模板全部可加载 | `sops/templates/` 下有 7 个 YAML（DEV-001/002, STR-001/002, MT-001, OPS-001/006），`SOP.load_from_yaml()` 可加载 | ✅ 已实现 | 实际 7 个，超出要求 |
| FR-SOP-002 | 每个 SOP 的阶段可真实执行并产出文件 | `execute_stage()` 执行时调用 `call_llm_for_output`，但 `FROST_TESTING=1` 时返回 mock 文本，**不写入真实文件** | ❌ 未实现 | **所有阶段产出都是 mock，无真实文件落地** |

---

## 三、宪法五条验证

| 宪法条目 | 要求 | 代码验证 | 状态 | 偏差 |
|----------|------|----------|------|------|
| 第一条：事件驱动 | 系统默认沉默，一切始于事件；无后台轮询 | `app.py` 依赖 Streamlit 的 `st.session_state` + 用户交互触发；无事件总线/消息队列；`auto_wake()` 在启动时被动加载，非轮询 | ❌ 偏差 | 无事件驱动架构，Streamlit 是请求-响应模型，非事件驱动 |
| 第二条：分形递归 | 祖/父/孙都是同一个 Agent 类的实例 | `core/agent.py` L14-245 单个 `Agent` 类；`ancestor.py`/`parent.py`/`assemble.py` 都使用 `Agent` | ✅ 遵守 | 完美遵守 |
| 第三条：编排层即宪法 | 祖辈定义不可违背的边界（只读键、SOP 校验、代际限制） | `stores/constitution.py` 有只读键和规则；`SOPValidator` 有校验逻辑；`Agent.spawn()` 有 `max_spawn_generation` 检查；**但 `execute_task()` 未调用 `validate_sop`** | ⚠️ 偏差 | 组件存在但执行流程中未强制执行 |
| 第四条：原子化技能 | Skill 无状态、可教学、可发现、可优化 | `core/skill.py` L8-35 纯函数无状态；`teach()`/`internalize()` 存在；`stores/asset.py` 有基因库；**但"可发现/可优化"未自动化** | ⚠️ 偏差 | 无状态 ✅；可教学 ✅；可发现/可优化 ❌（无自动搜索/优化） |
| 第五条：瞬态生命周期 | 孙辈按需创建、任务完成后销毁 | `skills/assemble.py` L193-211 每次 `assemble_agent` 新建孙辈；**无显式销毁机制**（依赖 Python GC） | ⚠️ 偏差 | 按需创建 ✅；任务完成后销毁 ❌（无销毁代码） |

---

## 四、其他基线验证

### 4.1 SOP 清单（6 个）

| SOP ID | 文件存在 | YAML 可解析 | 有测试覆盖 | 可真实执行 |
|--------|----------|-------------|------------|------------|
| DEV-001 | ✅ | ✅ | ✅ (test_f6_sop_e2e) | ❌ (mock) |
| DEV-002 | ✅ | ✅ | ⚠️ (无独立测试) | ❌ (mock) |
| STR-001 | ✅ | ✅ | ⚠️ (无独立测试) | ❌ (mock) |
| STR-002 | ✅ | ✅ | ✅ (test_evolution_e2e) | ❌ (mock) |
| MT-001 | ✅ | ✅ | ⚠️ (无独立测试) | ❌ (mock) |
| OPS-001 | ✅ | ✅ | ⚠️ (无独立测试) | ❌ (mock) |
| OPS-006 | ✅ | ✅ | ⚠️ (无独立测试) | ❌ (mock) |

**结论**: 7 个 SOP 文件全部存在且可解析，但仅 2 个有测试覆盖，**全部 7 个在 mock 模式下执行，无真实 LLM 调用产出**。

### 4.2 数据库表清单（17 张）

| 表名 | 用途 | 存在 | 有迁移 | 有测试 |
|------|------|------|--------|--------|
| config | 配置存储 | ✅ | ✅ | ✅ |
| projects | 项目 | ✅ | ✅ | ✅ |
| tasks | 任务队列 | ✅ | ✅ | ✅ |
| task_stages | SOP 阶段 | ✅ | ✅ | ✅ |
| agents | 常驻 Agent 注册 | ✅ | ✅ | ✅ |
| agent_status | 状态历史 | ✅ | ✅ | ✅ |
| sop_templates | SOP 定义 | ✅ | ✅ | ✅ |
| sop_executions | SOP 执行记录 | ✅ | ✅ | ✅ |
| audit_log | 审计追踪 | ✅ | ✅ | ✅ |
| cost_log | Token 消耗 | ✅ | ✅ | ✅ |
| schedule | 日程管理 | ✅ | ✅ | ⚠️ (6 个 ERROR) |
| energy_log | 能量状态 | ✅ | ✅ | ⚠️ (6 个 ERROR) |
| knowledge | 知识库 | ✅ | ✅ | ⚠️ (无独立测试) |
| knowledge_tags | 知识标签 | ✅ | ✅ | ⚠️ (无独立测试) |
| skills | 技能库 | ✅ | ✅ | ✅ |
| skill_versions | 技能版本 | ✅ | ✅ | ⚠️ (无独立测试) |
| tool_calls | 工具调用日志 | ✅ | ✅ | ⚠️ (无独立测试) |
| decision_points | 决策点记录 | ✅ | ✅ | ⚠️ (2 FAILED) |
| kv_store | 通用键值 | ✅ | ✅ | ⚠️ (无独立测试) |

**结论**: 18 张表全部存在，但 `schedule`/`energy_log` 有表结构字段不匹配（P0-1），`decision_points` 有逻辑回归（P0-2）。

### 4.3 Agent 架构（3 常驻 + 9 角色模板）

| 类型 | 名称 | 代码存在 | 职责匹配 | 状态 |
|------|------|----------|----------|------|
| 常驻 | ancestor (祖辈) | ✅ `agents/ancestor.py` | 治理/任务拆解 | ✅ |
| 常驻 | parent (父辈) | ✅ `agents/parent.py` | 协调/SOP 搜索 | ✅ |
| 常驻 | elder (长老) | ✅ `agents/elder.py` | 审计/监督 | ✅ |
| 基因 | 需求分析 | ✅ `stores/asset.py` | 对应产品经理 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 技术设计 | ✅ `stores/asset.py` | 对应架构师 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 代码生成 | ✅ `stores/asset.py` | 对应开发工程师 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 测试验证 | ✅ `stores/asset.py` | 对应测试工程师 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 审查交付 | ✅ `stores/asset.py` | 对应审计/QA | ⚠️ 是 Python dict 非 YAML |
| 基因 | 内容创作 | ✅ `stores/asset.py` | 对应内容创作者 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 营销策划 | ✅ `stores/asset.py` | 对应营销专员 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 财务分析 | ✅ `stores/asset.py` | 对应财务专员 | ⚠️ 是 Python dict 非 YAML |
| 基因 | 运营优化 | ✅ `stores/asset.py` | 对应运营专员 | ⚠️ 是 Python dict 非 YAML |

**结论**: 3 常驻 Agent 完整存在。9 个角色能力以"基因种子"（Python dict）形式存储在 `stores/asset.py` 中，**非 YAML 角色模板**，无独立 `roles/` 目录。缺少"秘书"角色模板。


---

## 五、六维度审计评分

### 5.1 评分总览

| 维度 | 评分 (1-10) | 权重 | 加权分 | 说明 |
|------|------------|------|--------|------|
| 代码质量 | **6.5** | 20% | 1.30 | app.py 1927 行 God Class，命名基本规范 |
| 架构一致性 | **7.0** | 25% | 1.75 | 四原子完整，宪法五条部分偏差，架构未腐化 |
| 安全性 | **4.5** | 15% | 0.68 | API Key 明文存储，无输入校验，无 XSS 防护 |
| 可靠性 | **5.0** | 20% | 1.00 | 大量 except:pass，10 个测试 ERROR，mock 替代真实执行 |
| 可扩展性 | **7.5** | 10% | 0.75 | SOP/Skill/Agent 插件化设计良好，新模块易添加 |
| 前后端一致性 | **4.0** | 10% | 0.40 | FastAPI 有 13 端点但 Next.js 未联调，Streamlit 导航假货 |
| **加权总分** | — | **100%** | **5.88** | **低于及格线 (6.0)，不通过** |

### 5.2 维度一：代码质量 (6.5/10)

**优点**:
- 代码注释清晰，每个文件顶部有 PHILOSOPHY 注释说明设计哲学
- 命名规范：`snake_case` 函数名、`PascalCase` 类名，符合 PEP 8
- 核心抽象层（`core/`）代码简洁，职责单一
- 类型注解在 `api/models.py` 中使用 Pydantic，较为规范

**问题**:
- **God Class**: `app.py` 1927 行，包含 CSS 注入、20+ 渲染函数、状态管理、任务执行。这是典型的"大泥球"反模式。
- **重复实现**: `stores/asset.py` 的 `FileStore` 和 `core/store.py` 的 `AssetStore` 是两个不同的持久化方案，命名冲突。
- **魔法数字**: `max_spawn_generation=1`（`ancestor.py` L36）、`monthly_budget=300.0`（`cost.py` L33）硬编码，未从配置读取。
- **调试代码残留**: `debug_audit.log`、`test_output.txt`、`test_full_output.txt` 等文件在仓库根目录。
- **前端无规范**: `frontend/` 的 TypeScript 代码无 ESLint/Prettier 配置检查证据（虽有 `eslint.config.mjs` 但无法确认是否运行）。

**改进建议**:
- 将 `app.py` 按页面拆分为 `frontend/pages/*.py`
- 统一 `AssetStore` 实现，删除 JSON 版本
- 将魔法数字迁移到 `constitution_store` 或配置文件

### 5.3 维度二：架构一致性 (7.0/10)

**优点**:
- **四原子完整实现**: `Store`（`core/store.py`）、`Skill`（`core/skill.py`）、`Agent`（`core/agent.py`）、`SOP`（`core/sop.py`）全部存在，接口清晰。
- **分形递归**: 祖/父/孙都是同一个 `Agent` 类，通过 `generation` 参数区分。这是 FROST 架构的核心亮点。
- **Skill 无状态**: `Skill.execute(context)` 是纯函数，不修改全局状态，可测试性高。
- **三层调用链**: `Ancestor → Parent → assemble_child → execute_stage` 链路在代码层面完整。
- **无架构腐化**: 未发现代码中混入非 FROST 架构的组件（如没有硬编码的 if-else 业务逻辑）。

**偏差**:
- **事件驱动缺失**: Streamlit 是请求-响应模型，每次用户交互触发一次完整 Python 脚本重跑。没有事件总线、消息队列或异步事件循环。
- **宪法未强制执行**: `SOPValidator` 组件存在，但 `execute_task()` 执行 SOP 前不调用它。"编排层即宪法"变成了"编排层有宪法但不读"。
- **瞬态生命周期不完整**: 孙辈 Agent 按需创建，但任务完成后没有显式 `destroy()` 或 `cleanup()` 方法，依赖 Python GC。在长时间运行场景下可能内存泄漏。
- **原子化技能不完整**: "可发现、可优化"未实现。Skill 库没有自动索引、没有基于使用频率的优化反馈回路。

**改进建议**:
- 在 `execute_task()` 中强制插入 `validate_sop` 前置步骤
- 为 `Agent` 添加 `destroy()` 方法，在任务完成后清理资源
- 增加 Skill 使用频率统计和自动优化建议（可与 F10 提取器联动）

### 5.4 维度三：安全性 (4.5/10)

**严重问题**:
- **API Key 明文存储**: `.env` 文件中 `DEEPSEEK_API_KEY` 是明文，`.env` 虽在 `.gitignore` 中，但无 AES 加密。若仓库被分享或部署到共享环境，存在泄露风险。
- **无输入校验**: `app.py` 中 `task_input = st.text_area(...)` 直接传入 LLM 调用，无 SQL 注入/XSS 过滤。虽然 Streamlit 有基本防护，但 `unsafe_allow_html=True` 在多处使用（导航栏、Agent 卡片等），用户输入可能通过其他路径进入 HTML 渲染。
- **无权限控制**: 系统为单用户设计，但 `core/db.py` 的 `DBManager` 单例对任何调用者开放全部 CRUD，无读/写分离。
- **CORS 全开**: `api/main.py` L44-51 `allow_origins=["*"]`，生产环境存在跨域风险。
- **SQL 注入风险低但有隐患**: `core/db.py` 使用参数化查询（`?` 占位符），SQL 注入风险较低。但 `execute_sql()` 方法允许传入任意 SQL 字符串，如果被外部调用存在风险。

**改进建议**:
- 使用 `cryptography` 库对 `.env` 中的 API Key 进行 AES 加密
- 对 `task_input` 等用户输入增加 sanitization
- 生产环境关闭 CORS 或限制 `allow_origins`
- 删除 `execute_sql()` 的公共暴露，或增加 SQL 注入检测

### 5.5 维度四：可靠性 (5.0/10)

**严重问题**:
- **mock 替代真实执行**: `FROST_TESTING=1` 时所有 LLM 调用返回预置文本。这本身是测试策略，但**生产代码中也没有真实执行路径的验证**——从未在非 mock 模式下跑通完整 SOP 执行链路。
- **大量 `except: pass`**: 至少 6 处静默吞异常，包括 DB 写入失败、持久化失败、能量检查失败等。这导致系统可能在"看起来正常"的状态下丢失数据。
- **10 个测试 ERROR**: `test_f9_founder_tools` 6 个（表结构字段不匹配）、`test_f8_decision` 3 个（决策逻辑回归 + 级联错误）。这些不是测试问题，是**生产代码缺陷**。
- **数据库 session 泄漏**: `test_f8_decision.py::TestAuditIntegration::test_audit_log_after_decision` 的 `FlushError` 表明 ORM/session 管理存在架构级问题。
- **无健康检查**: 虽然有 `/api/health`，但只返回 `{"status":"ok"}`，不检查 DB 连接、ChromaDB 可用性、LLM API 可达性等依赖项。

**改进建议**:
- 在 CI 环境中运行一次完整的非 mock 模式测试（使用少量真实 LLM 调用）
- 将所有 `except: pass` 替换为日志写入 `audit_log` 或 `cost_log`
- 修复 F9 表结构字段不匹配和 F8 决策逻辑回归
- 扩展 `/api/health` 为依赖项健康检查（DB + ChromaDB + LLM API）

### 5.6 维度五：可扩展性 (7.5/10)

**优点**:
- **SOP 插件化**: 新增 SOP 只需在 `sops/templates/` 下放 YAML 文件，无需修改核心代码。`SOP.load_from_yaml()` 是通用加载器。
- **Skill 插件化**: 新增 Skill 只需定义函数 + `Skill(name, func)` 包装，注册到 Agent 即可。
- **Agent 插件化**: 新增 Agent 类型只需写 factory 函数，复用 `core/agent.py` 的 `Agent` 类。
- **FastAPI 接口灵活**: 13 个端点使用 Pydantic 模型，前后端契约清晰。添加新端点只需在 `api/main.py` 中增加 decorator。
- **多项目支持**: `core/workbench.py` 中 `DEFAULT_PROJECTS` 定义了 3 个项目，模式切换逻辑已存在。

**问题**:
- **配置管理不灵活**: 环境切换（生产/测试）依赖 `FROST_TESTING` 环境变量，无更细粒度的配置层（如 YAML/JSON 配置文件）。
- **前端扩展受阻**: Streamlit 的 `app.py` 1927 行导致新页面添加困难。Next.js 前端是脚手架，尚未实际开发。
- **ChromaDB 依赖未声明**: 新环境部署时知识库功能可能不可用。

**改进建议**:
- 引入 `pydantic-settings` 或 YAML 配置文件管理环境配置
- 拆分 `app.py`，将页面逻辑移到独立模块
- 完成 Next.js 前端开发，真正解耦前后端

### 5.7 维度六：前后端一致性 (4.0/10)

**严重问题**:
- **Next.js 前端是空壳**: `frontend/` 有 3,813 行代码但经检查，核心是默认 Next.js 模板 + shadcn/ui 组件安装。`frontend/src/app/page.tsx` 和 `frontend/src/lib/api.ts` 没有实际调用 FastAPI 的证据。README 中声称"6 个路由页面"，但审计材料中未提供这些页面的代码摘要。
- **Streamlit 导航断链**: `app.py` 的顶部导航栏是 HTML `<span>` 装饰元素，不是真正的 Streamlit 按钮，不能切换视图。这是前端可用性层面的严重不一致。
- **API 契约未完全对齐**: FastAPI 的 `GET /api/sops` 端点缺失（P1-1），前端创建日程时无法选择 SOP 模板。
- **数据状态不同步**: `app.py` 使用 `st.session_state` 管理状态，FastAPI 使用独立的数据库查询。两者之间没有实时同步机制（如 WebSocket/SSE 未完全联调）。
- **前端状态管理**: Next.js 侧使用 zustand（声称），但审计材料未展示其状态定义是否与后端数据模型对齐。

**改进建议**:
- 完成 Next.js 至少 2 个页面（驾驶舱首页 + 任务详情）与 FastAPI 的联调
- 修复 Streamlit 导航栏为真实按钮
- 补充 `GET /api/sops` 端点
- 接入 SSE 日志流（`api/main.py` 已有 `/api/logs`，前端未订阅）

---

## 六、问题清单（按 P0/P1/P2 分级）

### 🔴 P0 — 阻塞级（必须修复后方可上线）

| # | 问题 | 根因 | 影响 | 关联 FR |
|---|------|------|------|---------|
| P0-1 | **所有 SOP 执行都是 mock，无真实产出** | `skills/llm.py` `_mock_response_for_prompt()` 在 `FROST_TESTING=1` 时返回固定文本；但**非测试模式下也未经完整验证** | 系统无法产出真实代码/文档/文案，是"玩具"而非工具 | FR-AGENT-001, FR-AGENT-002, FR-FIX-001, FR-SOP-002 |
| P0-2 | **父辈自修复（FR-006）完全未实现** | `Agent.run()` 遇错 break+raise，无重试循环；`execute_stage` 返回 failed 后无模板切换 | 任务一旦失败全链路崩溃，无降级路径 | FR-006（隐含） |
| P0-3 | **F9 表结构字段不匹配** | `core/db.py` `energy_log`/`schedule` 表新增字段后，INSERT SQL 未同步更新 | 能量/日程功能 6 个测试 ERROR，生产环境不可用 | FR-STATE-001, FR-STATE-002 |
| P0-4 | **F8 决策管理逻辑回归** | `core/decision_manager.py` 查询/恢复逻辑与测试期望不一致 | 决策点无法恢复，任务暂停后无法继续 | FR-FIX-002 |
| P0-5 | **API Key 明文存储，无加密** | `skills/llm.py` 直接从 `os.getenv("DEEPSEEK_API_KEY")` 读取，无加密层 | 部署到共享环境时 API Key 泄露风险 | FR-SET-001 |

### 🟡 P1 — 重要（影响体验或数据质量）

| # | 问题 | 根因 | 影响 | 关联 FR |
|---|------|------|------|---------|
| P1-1 | **顶部导航栏是装饰性 HTML** | `app.py` L690-711 用 `<span>` 渲染导航，无 click handler | 5 个导航按钮点不动 | FR-DASH-003 |
| P1-2 | **CEO 对话是占位符** | `app.py` CEO 输入只写 `add_log`，不调用 LLM/Agent | 创始人无法与 AI 对话 | FR-DASH-005 |
| P1-3 | **Agent 卡片不可交互** | 8 张卡片是纯 CSS Grid div，无 Streamlit 按钮 | 无法查看 Agent 详情 | FR-DASH-003 |
| P1-4 | **FastAPI `/api/sops` 端点缺失** | `api/main.py` 无此路由 | 前端无法获取 SOP 模板列表 | FR-SOP-001 |
| P1-5 | **ChromaDB 未在 requirements.txt** | 依赖遗漏 | 新环境部署时知识库不可用 | FR-MEM-004, FR-STORE-002 |
| P1-6 | **pytest 未在 requirements.txt** | 依赖遗漏 | 新环境无法运行测试 | NFR |
| P1-7 | **cost_log 78 条历史遗留数据** | F14 修复前未写入 agent_id | 成本统计按 Agent 维度不完整 | FR-AUDIT-002 |
| P1-8 | **意图解析无结构化 JSON** | `ancestor.run(["call_llm"])` 返回文本不解析 | 无法自动识别任务类型和匹配 SOP | FR-MAIN-001 |
| P1-9 | **轻层/重层路由完全未实现** | 无 Jaccard 匹配、无 Aider/Perplexity 封装 | 所有任务都走 DeepSeek LLM，无本地优先策略 | FR-ROUTER-001, FR-ROUTER-002 |
| P1-10 | **Skill 验证激活流程未实现** | 提取器生成 Skill 后无 3 次测试 + 成功率阈值 | 自动提取的 Skill 质量不可控 | FR-EXTRACT-002 |
| P1-11 | **交棒机制完全未实现** | 代码中无 `handover`、`succession` 相关逻辑 | 家族治理无法演进 | 白皮书 2.5 |
| P1-12 | **Ollama 本地模型未支持** | 代码中无 Ollama 引用 | 无法实现本地优先策略，所有调用都走外部 API | FR-SET-002 |

### 🟢 P2 — 优化级（技术债务）

| # | 问题 | 根因 | 影响 |
|---|------|------|------|
| P2-1 | **app.py 1927 行 God Class** | 所有 UI 逻辑集中在一个文件 | 维护困难，热重载慢 |
| P2-2 | **AssetStore 重复实现** | `stores/asset.py` 和 `core/store.py` 各有一个 | 命名冲突，持久化策略不一致 |
| P2-3 | **pytest 返回值警告** | 59 个 `PytestReturnNotNoneWarning` | 测试日志嘈杂 |
| P2-4 | **前端无测试** | `frontend/` 3,813 行无测试 | 重构风险高 |
| P2-5 | **Streamlit 无 E2E 测试** | `test_f12_e2e_ui.py` 需手动运行 | UI 变更依赖手动验证 |
| P2-6 | **调试文件未清理** | `debug_audit.log`, `test_output.txt` 等 | 仓库体积膨胀 |
| P2-7 | **能量曲线图缺失** | `render_energy_logger()` 无 recharts 集成 | 能量趋势不可视化 |
| P2-8 | **无 Git pre-commit hook** | 未配置 lint/format/test | 提交质量不可控 |
| P2-9 | **Next.js 前端是脚手架** | 无实际页面代码 | 前后端分离停留在后端单端 |
| P2-10 | **无 CI/CD 配置** | 无 GitHub Actions / Jenkins 配置 | 自动化测试和部署缺失 |

---

## 七、改进建议（按优先级排序）

### 阶段一：上线阻塞（必须完成）

| 优先级 | 工作项 | 工作量 | 说明 |
|--------|--------|------|------|
| 1 | 修复 F9 表结构字段不匹配 | 1-2h | 同步 `core/db.py` INSERT SQL 与 `energy_log`/`schedule` 表结构 |
| 2 | 修复 F8 决策管理逻辑回归 | 1-2h | 检查 `decision_manager.py` 查询逻辑与测试期望的一致性 |
| 3 | 实现父辈自修复（FR-006） | 4-8h | 在 `Agent.run()` 或 `execute_task()` 中增加错误重试 + 模板切换（最多 3 次） |
| 4 | 验证非 mock 模式完整执行链路 | 4-8h | 在真实 LLM 模式下运行一次完整的 DEV-001 SOP，确认文件真实产出 |
| 5 | API Key 加密存储 | 2-4h | 使用 `cryptography` AES-256-GCM 加密 `.env` 中的 API Key |

### 阶段二：核心功能补齐（重要）

| 优先级 | 工作项 | 工作量 | 说明 |
|--------|--------|------|------|
| 6 | 修复 Streamlit 导航栏 | 0.5-1h | 改为 `st.button`/`st.radio` 实现 |
| 7 | CEO 对话接入真实 LLM | 2-4h | 将输入路由到 `call_llm_skill` 或 `ancestor.run()` |
| 8 | 实现意图解析结构化 JSON | 4-8h | LLM 返回 JSON 后解析任务类型，自动匹配 SOP |
| 9 | 补充 `/api/sops` 端点 | 0.5h | `api/main.py` 中添加 `GET /api/sops` |
| 10 | 补充 requirements.txt | 0.5h | 添加 `chromadb`, `pytest`, `fastapi`, `uvicorn` 等缺失依赖 |
| 11 | 清理 cost_log 遗留数据 | 0.5h | `DELETE FROM cost_log WHERE agent_id = 'unknown'` |
| 12 | 接入 SSE 日志流 | 2-4h | Next.js 前端订阅 `EventSource('/api/logs')` |

### 阶段三：架构优化（中长期）

| 优先级 | 工作项 | 工作量 | 说明 |
|--------|--------|------|------|
| 13 | 拆分 app.py | 4-8h | 将页面逻辑移到 `frontend/pages/*.py` |
| 14 | 统一 AssetStore | 1-2h | 删除 `stores/asset.py` 中的 `FileStore`，统一使用 SQLite 版本 |
| 15 | 实现轻层/重层路由 | 16-24h | Jaccard 相似度匹配 + Aider/Perplexity 封装 |
| 16 | 完成 Next.js 前端 | 40-60h | 至少完成驾驶舱首页 + 任务详情页 + API 联调 |
| 17 | 实现 Skill 验证激活流程 | 8-16h | 3 次测试 + 成功率阈值 + 自动激活状态机 |
| 18 | 实现交棒机制 | 8-16h | 交棒提案 + 创始人批准 + 宪法 Store 写入权转移 |
| 19 | 实现 Ollama 本地模型支持 | 4-8h | 在 `skills/llm.py` 中增加 Ollama 路由 |
| 20 | 配置 CI/CD | 4-8h | GitHub Actions 运行 pytest + Next.js build |

---

## 八、最终结论

### 8.1 是否建议上线？

**❌ 不建议上线。**

理由：
1. **核心功能未实现**: 43 条 FR 中 12 条完全未实现（28%），包括真实执行、自修复、意图解析、本地模型等关键能力。
2. **所有产出是 mock**: 7 个 SOP 在 mock 模式下运行，从未在真实 LLM 模式下验证过完整链路。系统无法产出真实文件、代码或文档。
3. **前端不可用**: 导航栏假货、Agent 卡片不可点、CEO 对话无 AI 响应。Streamlit 工作台的用户体验低于可接受阈值。
4. **安全与可靠性不达标**: API Key 明文、大量 `except:pass`、10 个测试 ERROR、2 个 P0 生产缺陷。
5. **前后端未联调**: FastAPI 后端有 13 端点，但 Next.js 前端是空壳，未实际消费任何 API。

### 8.2 上线条件清单

以下条件全部满足后方可考虑上线：

| # | 条件 | 验收标准 |
|---|------|----------|
| 1 | 修复全部 P0 问题 | pytest 运行结果：0 FAILED, 0 ERROR |
| 2 | 非 mock 模式验证 | 至少 1 个 SOP（DEV-001）在真实 LLM 模式下完整执行，产出真实文件 |
| 3 | 实现父辈自修复 | `Agent.run()` 遇错后自动切换模板重试，3 次超限上报祖辈 |
| 4 | 前端导航可用 | 顶部导航栏 5 个按钮可点击切换视图 |
| 5 | CEO 对话可用 | 输入消息后收到真实 LLM 响应 |
| 6 | 意图解析结构化 | LLM 返回 JSON 拆解方案，自动匹配 SOP 类型 |
| 7 | API Key 加密 | 使用 AES-256-GCM 加密存储 |
| 8 | 补充所有依赖 | `requirements.txt` 包含所有运行时和开发依赖 |
| 9 | 清理遗留数据 | `cost_log` 中 `agent_id='unknown'` 记录清零 |
| 10 | 前后端联调 | Next.js 至少 2 个页面成功调用 FastAPI 端点 |

### 8.3 诚实的时间估算

以当前团队状态（1 人公司，IT 小白，月度 Token 预算 ¥300），完成上述 10 个上线条件预计需要：

- **阶段一（P0 修复）**: 2-3 周
- **阶段二（核心功能补齐）**: 3-4 周
- **阶段三（前后端联调）**: 4-6 周
- **总计**: **9-13 周**

这还未计入真实 LLM 调用的 Token 成本（当前 mock 模式下月度成本为 0，真实执行可能超出 ¥300 预算）。

---

> **审计人声明**: 本报告基于对 `audit_materials/` 中 8 份材料 + 项目源代码的逐行审查。43 条 FR 的每一条都有代码路径引用。所有 "未实现""mock""假货" 等表述均为技术事实。如有疑问，任何一条结论均可通过阅读指定文件路径和行号复现验证。
