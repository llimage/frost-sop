# V5.0 Panel 开发代码审计报告

**审计日期**: 2026-06-28  
**审计范围**: `core/panel_generator.py`、`skills/orchestration.py`、V5.0 相关测试  
**审计原则**: 颗粒度最低、最严苛、诚实、中肯  

---

## 一、总体结论

**评级**: ⚠️ **有条件通过（Conditional Pass）**

两个核心任务已完成：
- ✅ 任务1：PanelGenerator 支持 cockpit 面板生成（多任务列表）
- ✅ 任务2：SOP 执行引擎在决策点自动生成 DECISION 面板

但存在**代码质量不一致**（`print` vs `logging`）、**架构冗余**（`decision_manager` + `panel_generator` 双轨并存）、**测试深度不足**（未验证面板实际渲染）等问题。

---

## 二、严重问题（无阻塞级，但需立即修复）

### 🔴 S-001: `_check_decision_point` 使用 `print` 而非 `logging`

**位置**: `skills/orchestration.py:192, 228, 230`

**代码**:
```python
print(f"  ⚠️ 跳过决策点（无有效 task_id）: {stage_name}")
print(f"  🔮 [V5.0] 决策面板已生成: {decision_panel.panel_id}")
print(f"  ⚠️ [V5.0] 决策面板生成失败（不影响暂停）: {e}")
```

**问题**:
- FROST 所有模块使用 `logging.getLogger(__name__)`，但此处使用 `print`
- `print` 输出不可控（无法通过日志级别过滤），不可重定向，不可持久化
- 在 CLI 渲染场景中，`print` 会与面板渲染输出混杂，干扰用户体验

**修复**: 替换为 `logger.info()` / `logger.warning()`，或写入 `context["_logs"]` 供面板展示。

---

### 🔴 S-002: `decision_manager` + `panel_generator` 双轨并存——架构冗余

**位置**: `skills/orchestration.py:194-227`

**问题**:
- `_check_decision_point` **同时**调用了 `decision_manager.pause_decision()` **和** `PanelGenerator.generate()`
- 这意味着决策点暂停由**两个系统**处理：`decision_manager`（数据库写入）和 `panel_generator`（面板生成）
- 两套系统没有明确的职责边界：
  - `decision_manager` 负责什么？数据库持久化 + 状态管理？
  - `panel_generator` 负责什么？UI 生成 + 数据展示？
- 如果未来 `decision_manager` 也要生成 UI，会与 `panel_generator` 冲突

**建议**: 明确分工：
- `decision_manager` = 决策记录的持久化和查询（后端）
- `panel_generator` = 决策面板的生成（前端）
- 或者：将 `decision_manager` 的职责合并到 `panel_decision.py` 的 `DecisionFlow` 中，统一由 `DecisionFlow` 管理决策生命周期

---

### 🔴 S-003: `_check_decision_point` 中 lazy import 增加运行时风险

**位置**: `skills/orchestration.py:211-213`

**代码**:
```python
try:
    from core.panel_generator import PanelGenerator
    from core.panel import PanelType
```

**问题**:
- 函数内动态导入会在**每次调用**时执行导入（Python 会缓存，但仍有查找开销）
- 如果 `core.panel_generator` 模块存在循环导入或导入错误，这个问题只在**运行时**遇到决策点时才暴露
- 不符合 FROST 模块级导入的惯例

**修复**: 将导入移到模块顶部，或至少在 `skills/orchestration.py` 顶部导入。如果存在循环导入，说明架构有耦合问题，应解耦而非隐藏。

---

## 三、中等问题

### ⚠️ M-001: `generate()` 类型签名不够精确

**位置**: `core/panel_generator.py:39`

**代码**:
```python
def generate(self, task: Any, sop: Optional[SOP] = None) -> PanelDefinition:
```

**问题**:
- `task: Any` 过于宽泛。实际接受的类型是 `Union[Dict[str, Any], List[Dict[str, Any]]]`
- 当传入列表时，忽略 `sop` 参数（第57行注释说明），但签名中 `sop` 仍然存在——这会导致调用者困惑

**修复**:
```python
from typing import Union

def generate(self, task: Union[Dict[str, Any], List[Dict[str, Any]]], 
             sop: Optional[SOP] = None) -> PanelDefinition:
    """...当 task 是列表时，sop 参数被忽略..."""
```

---

### ⚠️ M-002: `_create_cockpit_components` 的 `properties` 字段不一致

**位置**: `core/panel_generator.py:395-436`

**问题**:
- `comp:pending_decisions` 使用 `properties.data`（表格数据）
- `comp:recent_tasks` 使用 `properties.items`（时间线索引）

但 `CliRenderer._render_table` 期望 `properties.data` 和 `properties.columns`，`CliRenderer._render_timeline` 期望什么？需要检查 CLI 渲染器是否支持 `properties.items`。

**风险**: 如果 CLI 渲染器不支持 `items` 属性，`comp:recent_tasks` 在终端渲染时可能显示异常。

---

### ⚠️ M-003: `_check_decision_point` 的 `task_for_panel` 构造不完整

**位置**: `skills/orchestration.py:216-223`

**代码**:
```python
task_for_panel = {
    "task_id": task_id,
    "title": context.get("_task_title", stage_name),
    "status": "waiting",
    "stages": [stage] if isinstance(stage, dict) else list(stage),
    "current_stage_index": 0,
    "current_stage": stage,
}
```

**问题**:
- `stages` 字段只有 `[stage]`（单个阶段），但真实任务通常有多个阶段
- `current_stage_index` 固定为 0，不反映真实阶段索引
- `PanelGenerator._create_decision_components` 期望 `task.get("current_stage", {})` 来获取产出、决策选项等，但这里的 `current_stage` 就是 `stage`（传入的参数字典）——如果 `stage` 没有 `outputs` 字段，决策面板就不会显示产出

**修复**: 从 `context` 中提取完整的任务数据（`context.get("_task_data")` 或从 Store 读取），而非构造一个简化版本。

---

### ⚠️ M-004: 测试未验证面板在 CLI 中的实际渲染

**位置**: `tests/test_panel_integration.py`

**问题**:
- `TestSopPanelIntegration` 验证了面板**生成**（`panel.panel_type == PanelType.DECISION`）
- 但**没有验证**面板在 CLI 渲染器中的实际渲染输出
- 即：生成了面板，但不知道 CLI 渲染器能否正确展示决策按钮、质量评分、产出预览

**风险**: 面板数据结构和渲染引擎之间的契约未验证。如果 CLI 渲染器期望 `properties.data` 但面板生成器提供了 `properties.items`，测试不会发现。

**修复**: 添加 `test_decision_panel_cli_rendering` 测试，使用 `CliRenderer` 渲染生成的决策面板，验证输出包含关键文本（如"决策:"、"确认"、"驳回"）。

---

### ⚠️ M-005: 测试数量声称存疑

**声称**: "92 个测试全部通过"

**实际验证**:
- `tests/test_panel.py`: 244 行 → 约 15-20 个测试函数
- `tests/test_panel_generator.py`: 196 行 → 约 10-15 个测试函数
- `tests/test_panel_integration.py`: 825 行 → 约 30-40 个测试函数
- 总计：约 55-75 个测试函数，而非 92 个

**说明**: 92 可能包含了其他测试文件（如 `test_cli_renderer.py` 等），但测试总数与声称的差距需要澄清。

---

## 四、轻微问题

### ℹ️ L-001: `PanelGenerator.__init__` 新增 `store` 参数未在文档中强调

**位置**: `core/panel_generator.py:33`

```python
def __init__(self, armory_registry=None, store=None):
```

`store` 参数用于解析 `family:/intel:/immune:` 前缀的数据源，但 docstring 和规格书中未明确说明何时需要传入 `store`。

### ℹ️ L-002: `_generate_cockpit_title` 的统计信息可能重复计算

**位置**: `core/panel_generator.py:126-132`

```python
total = len(tasks)
running = sum(1 for t in tasks if t.get("status") == "running")
completed = sum(1 for t in tasks if t.get("status") == "completed")
waiting = sum(1 for t in tasks if t.get("status") == "waiting")
```

如果任务状态不是这三个（如 "failed"、"created"），则不会被统计，但标题不显示这些状态。这可能导致 `total ≠ running + completed + waiting`，但标题不暴露这一点——不算错误，但可能误导。

---

## 五、诚实的进度重估

| 任务 | 声称 | 实际验证 | 状态 |
|------|------|----------|------|
| PanelGenerator 支持 cockpit | 完成 | ✅ `generate()` 接收列表，生成 COCKPIT 面板 | 完成 |
| SOP 执行引擎集成 | 核心部分完成 | ⚠️ 生成面板并存入 context，但 CLI 不会主动渲染 | 部分完成 |
| 测试通过 | 92 个 | ⚠️ 数量未精确验证，集成测试未验证 CLI 渲染 | 部分完成 |
| 决策状态机 | 未提及 | ❌ `DecisionFlow` 已定义但未在 `_check_decision_point` 中使用 | 未使用 |

**关键缺口**：`core/panel_decision.py` 的 `DecisionFlow` 状态机（20KB 已交付）**尚未**在 `_check_decision_point` 中集成。当前仍使用 `decision_manager.pause_decision()`，而非 `DecisionFlow.create_decision()`。这意味着：
- 决策记录没有统一的状态机管理
- 决策超时、多级审批、修改次数限制等功能未启用
- `DecisionFlow` 的审计可追溯能力未使用

---

## 六、后续计划建议

### 第一优先级（立即修复）

1. **修复 S-001**：`print` → `logging`
2. **修复 S-003**：将 `PanelGenerator` 导入移到模块顶部
3. **修复 M-003**：`_check_decision_point` 从 `context` 获取完整任务数据

### 第二优先级（架构整合）

4. **修复 S-002**：统一决策系统——用 `DecisionFlow` 替代 `decision_manager.pause_decision()`
   - `_check_decision_point` 调用 `DecisionFlow.create_decision()`
   - 面板生成器从 `DecisionFlow` 读取决策记录，而非直接从 `context` 构造
   - 这会将决策状态机真正投入使用

5. **添加 CLI 渲染联动测试**：验证决策面板在终端的实际渲染输出

### 第三优先级（功能完善）

6. **CLI 渲染器主动检测面板**：当前面板生成到 `context["_decision_panel"]`，但 CLI 渲染器不会主动检测。需要：
   - 在 `execute_stage` 中，如果 `context.get("_decision_panel")`，则调用 `CliRenderer.render()`
   - 或：事件驱动模式——`panel.decision_needed` 事件触发 CLI 渲染

7. **删除 Next.js 前端**（止血）：如外部评估报告所指出的，双前端是资源浪费。保留 Streamlit（`core/workbench.py`）即可。

8. **添加 `pyproject.toml` 和 `ruff.toml`**：基础工程化，回应外部评估报告。

---

## 七、审计文件索引

| 文件 | 变更 | 新增行数 | 关键问题 |
|------|------|---------|---------|
| `core/panel_generator.py` | 支持 cockpit 生成 | +60 | M-001, M-002, L-002 |
| `skills/orchestration.py` | 决策点生成面板 | +35 | S-001, S-002, S-003, M-003 |
| `tests/test_panel_integration.py` | SOP-Panel 集成测试 | +80 | M-004 |

---

*审计完成。两个核心任务已落地，但架构整合和工程化仍需推进。*
