# FROST-SOP V3.1 + V4.0 代码级审计报告

**审计日期**: 2026-06-28
**审计范围**: 验收报告声明的 8 项 AC（AC-1 ~ AC-8）
**审计方法**: 逐文件代码审查 + 测试静态分析 + 运行验证 + 架构一致性检查
**审计原则**: 颗粒度最低、最严苛、诚实、中肯
**审计对象**: `workspace/frost-sop/` 目录下全部代码

---

## 一、总体结论

**评级**: ⚠️ 有条件通过（Conditional Pass）

核心功能实现基本到位，但存在**测试数量声称不实**、**全量测试数据夸大**、**代码质量数字模糊**等问题。V4.0 预研产物为纯数据结构，未与现有代码集成，不引入回归风险。

| 维度 | 评分 | 说明 |
|------|------|------|
| 功能实现 | ✅ | 成本追踪、日志、重构子函数、SOP output_type 均已落地 |
| 测试覆盖 | ⚠️ | 新增测试存在，但数量声称与代码实际不符 |
| 代码质量 | ⚠️ | 核心文件 F401 归零，但 E501 计数逻辑不清晰；orchestration.py 仍未拆分 |
| 文档/配置 | ✅ | SOP 模板 7/7 有 output_type；技能卡 YAML 格式正确 |
| 回归安全 | ✅ | V4.0 为独立预研文件，不触及现有执行路径 |

---

## 二、严重问题（阻塞级）

**无阻塞级问题。** 但以下中等问题对工程可信度造成实质影响。

---

## 三、中等问题

### ⚠️ M-001: 测试数量声称与代码实际不符

**声称**: "3个测试文件已创建（12+11+12=35个测试）"、"新测试37/37通过"

**实际**（经 `grep -c "def test_"` 逐文件统计）：

| 文件 | 声称 | 实际 | 偏差 |
|------|------|------|------|
| `tests/test_assemble.py` | 12 | **2** | ❌ -10 |
| `tests/test_assemble_coverage.py` | 未提及 | **13** | 遗漏 |
| `tests/test_evolution_coverage.py` | 11 | **11** | ✅ |
| `tests/test_orchestration_coverage.py` | 12 | **13** | +1 |
| **合计** | **35** | **39** | **+4** |

**验证运行**: `pytest tests/test_assemble.py tests/test_evolution_coverage.py tests/test_orchestration_coverage.py -v` → **26 passed**

若包含 `test_assemble_coverage.py` 则应为 **39** 个测试，但验收报告的数字来源无法从代码中复现。

**影响**: 工程汇报数据失真，可能导致后续阶段对测试覆盖的误判。

**建议**: 修正验收报告数字，统一口径为 4 个新增测试文件 / 39 个新增测试函数。

---

### ⚠️ M-002: 全量测试数量声称（207/210）无法复现

**声称**: "207/210 passed（3个预存V3 async失败）"

**实际**: `pytest --collect-only -q` 全项目仅收集到 **119 个测试**，不是 207/210。

**分析**:
- 119 个测试 vs 声称 210 个，差距约 **76%**
- 即使将 V0.x 测试（`tests/test_v070_full.py` 等）纳入，也不足以达到 210
- 声称的 "3个预存V3 async失败" 在 `tests/test_v3_event_loop_blocking.py` 中确实存在，但 pytest 在完整收集时因 stdout 捕获问题无法稳定运行全量套件

**影响**: 全量回归通过率的声称缺乏可复现的自动化证据。

**建议**: 提供可复现的 pytest 全量运行命令及输出截图，或修正为实际可运行的数字。

---

### ⚠️ M-003: Flake8 数字（91）缺乏清晰边界定义

**声称**: "E501+F401 = 91（249→91）"

**实际**（对 6 个核心文件手动统计）：

| 文件 | E501 (行>79字符) | F401 (未使用导入) |
|------|------------------|-------------------|
| `skills/assemble.py` | 1 | 0 |
| `skills/evolution.py` | 12 | 0 |
| `skills/orchestration.py` | 21 | 0 |
| `core/cost.py` | 7 | 0 |
| `skills/llm.py` | 13 | 0 |
| `main.py` | 16 | 0 |
| **合计** | **70** | **0** |

**问题**:
- 仅 6 个文件就有 70 个 E501，加上其他 30+ 被 autoflake/autopep8 批量修改的文件，91 的数字可能只覆盖了部分文件
- "249→91" 的原始 249 无法从当前代码复现
- 验收报告中没有说明统计范围（是所有 .py 文件还是仅核心文件？）

**建议**: 定义明确的统计范围（如 `flake8 . --select=E501,F401 --count`），并在 CI 中固化。

---

### ⚠️ M-004: orchestration.py 未拆分，复杂度依然过高

**声称**: "AC-3 和 AC-4 重构完成（assemble_agent + audit_family 各拆分为4子函数）"

**实际**:
- `agents/elder.py`（audit_family）确实拆分为 `_scan_store`, `_compute_statistics`, `_generate_report`, `_log_audit_result` → ✅
- `skills/assemble.py`（assemble_agent）确实拆分为 `_collect_templates`, `_semantic_match`, `_keyword_fallback`, `_create_skills_from_genes` → ✅
- **`skills/orchestration.py` 608 行、10 个函数，完全未拆分** → ❌

**orchestration.py 函数清单**:
1. `spawn` (line 13)
2. `emit` (line 54)
3. `validate_sop` (line 69)
4. `merge_from` (line 95)
5. `internalize_sop` (line 130)
6. `execute_stage` (line 169)
7. `_trigger_elder_audit` (line 382)
8. `finalize_task` (line 446)
9. `register_stage_executor` (line 498)

其中 `execute_stage` 从 line 169 到 370（约 201 行），包含决策点检查、Agent 组装、DEFECT-001 修复、F14 持久化、子 Agent 执行、状态更新等复杂逻辑，**认知负荷极高**。

**建议**: 将 `execute_stage` 拆分为 `_check_decision_point`, `_assemble_child`, `_execute_child`, `_persist_result` 等子函数。

---

### ⚠️ M-005: main.py 日志配置仅覆盖 async-mode

**声称**: "AC-2 异步日志可见 — main.py StreamHandler INFO级别"

**实际**（`main.py:489-492`）:
```python
if args.async_mode:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )
```

- 仅在 `--async-mode` 时配置 `StreamHandler`
- 同步模式（默认）**没有配置 StreamHandler**，日志可能不可见或依赖外部配置

**建议**: 将日志配置提取到 main 函数顶部，覆盖两种模式；或确保同步模式入口也有可观测的日志输出。

---

## 四、轻微问题

### ℹ️ L-001: 测试文件命名与数量混淆

`test_assemble.py`（2 个测试）与 `test_assemble_coverage.py`（13 个测试）命名接近，容易混淆。验收报告中的 "12" 可能实际指向 `test_assemble_coverage.py` 的 13 个，但减去了 1 个（或误数）。

**建议**: 合并为单个 `test_assemble.py`，或统一命名规范（如 `test_assemble_unit.py` / `test_assemble_integration.py`）。

---

### ℹ️ L-002: V4.0 技能卡 YAML 与 SkillCard dataclass 未对齐

`core/skill_graph.py` 中定义了 `SkillCard` dataclass（`intent`, `applicable_when`, `not_applicable_when`, `inputs`, `outputs` 等）。

技能卡 YAML（如 `sops/skill_cards/call_llm.yaml`）字段与 dataclass 一致，但**当前没有任何代码加载 YAML 并实例化 SkillCard**。YAML 与 dataclass 之间是"纸面一致"而非"运行时一致"。

**建议**: 在 V4.0 后续阶段提供 `yaml → SkillCard` 的加载器，并编写测试验证字段映射。

---

### ℹ️ L-003: cost.py 预算检查与追踪分离

`track_cost()` 只记录成本，不检查预算；`check_and_throw()` 只检查预算，不记录成本。这种分离设计正确，但存在隐患：

- 如果某处调用 `track_cost()` 后忘记调用 `check_and_throw()`，预算熔断将失效
- `llm.py` 中在线调用路径是 `check_and_throw` → LLM 调用 → `track_cost`，顺序正确

**建议**: 在 `track_cost` 的 docstring 中明确提醒调用方需自行调用 `check_and_throw`。

---

### ℹ️ L-004: `_generate_report` 参数顺序已修正但文档未更新

用户自述中提到 "`_generate_report` 参数顺序有问题，需要修正"。实际代码中参数顺序为 `(stats, tasks, lessons, budget=None)`，逻辑上合理（stats 是核心数据，tasks/lessons 是详情，budget 是可选）。

如果此前存在参数顺序错误（如 `(tasks, stats, lessons)`），当前代码已修正，但建议补充 git diff 或注释说明修正历史。

---

## 五、诚实的进度重估

| AC | 声称 | 实际验证 | 状态 |
|----|------|----------|------|
| AC-1 成本追踪修复 | cost.py + llm.py 写入 cost_log | ✅ 代码确认 `db.insert("cost_log", ...)` 和 `cost_tracker.track_cost()` 均存在 | 完成 |
| AC-2 异步日志可见 | main.py StreamHandler INFO级别 | ⚠️ 仅在 `args.async_mode` 时配置；同步模式未覆盖 | 部分完成 |
| AC-3 assemble_agent 重构 | 4子函数，复杂度<10，18测试全过 | ✅ 4子函数存在；但 "18测试" 无法对应（实际 2+13=15 个 assemble 相关测试） | 完成（数字不精确） |
| AC-4 audit_family 重构 | 4子函数，复杂度<10，18测试全过 | ✅ 4子函数存在；elder.py 测试未在本次新增文件中 | 完成（数字不精确） |
| AC-5 Flake8 ≤200 | E501+F401 = 91（249→91） | ⚠️ 核心文件 E501=70, F401=0；全项目数字未清晰定义 | 数字存疑 |
| AC-6 测试覆盖率 | assemble 84% / evolution 98% / orchestration 71% | ⚠️ 覆盖率未在本次审计中复现（无 pytest-cov 运行证据）；但新增测试确实存在 | 未验证 |
| AC-7 SOP output_type | 7/7 模板全部到位 | ✅ 7个 YAML 均含 `output_type` 字段 | 完成 |
| AC-8 回归测试 | 207/210 passed（3预存失败） | ❌ 全项目仅收集 119 个测试；207/210 无法复现 | 声称不实 |

---

## 六、建议修复优先级

### 第一优先级（下次迭代前）
1. **修正验收报告数字**：测试数量、全量测试通过率、Flake8 计数需与代码实际一致
2. **补充同步模式日志配置**：main.py 默认分支也配置 StreamHandler

### 第二优先级（V3.2 或 V4.0 早期）
3. **拆分 orchestration.py**：尤其是 `execute_stage`（201 行）拆分为子函数
4. **固化 Flake8 统计范围**：在 CI/脚本中定义 `flake8 . --select=E501,F401 --count` 的标准命令

### 第三优先级（V4.0 中期）
5. **YAML → SkillCard 加载器**：将技能卡 YAML 从静态文档转化为可运行时加载的数据结构
6. **合并/规范测试文件命名**：消除 `test_assemble.py` vs `test_assemble_coverage.py` 的混淆

---

## 七、审计文件索引

| 文件路径 | 审计内容 | 行数 |
|----------|----------|------|
| `workspace/frost-sop/core/cost.py` | 成本追踪、预算熔断 | 211 |
| `workspace/frost-sop/skills/llm.py` | LLM 调用、成本集成 | 423 |
| `workspace/frost-sop/main.py` | 入口、日志配置、事件驱动 | 505 |
| `workspace/frost-sop/skills/assemble.py` | Agent 组装、技能合成 | 357 |
| `workspace/frost-sop/skills/evolution.py` | 自进化、趋势分析 | 214 |
| `workspace/frost-sop/skills/orchestration.py` | 生命周期、阶段执行 | 608 |
| `workspace/frost-sop/agents/elder.py` | 长老审计、报告生成 | 218 |
| `workspace/frost-sop/core/skill_graph.py` | V4.0 数据结构 | 102 |
| `workspace/frost-sop/sops/skill_cards/*.yaml` | 5 个技能卡 | 81-111 |
| `workspace/frost-sop/sops/templates/*.yaml` | 7 个 SOP 模板 | — |

---

**审计结论**: V3.1 的功能实现是扎实的，但工程汇报中存在数字放大现象。建议在发布任何验收报告前，使用自动化脚本（如 `pytest --collect-only`、`flake8 --count`）生成数据，避免手动计数误差。V4.0 预研产物为独立文件，风险可控，但需后续投入实现 YAML 到运行时的桥接。
