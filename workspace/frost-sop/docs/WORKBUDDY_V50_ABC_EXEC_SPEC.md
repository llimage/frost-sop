# WorkBuddy 执行指令：V5.0 Panel A+B+C 全量修复

**版本**: V5.0-修复版
**日期**: 2026-06-28
**目标**: A（最小修复）+ B（架构整合）+ C（止血工程化）一次性完成
**优先级**: P0

---

## 零、执行顺序（必须严格遵守）

| 阶段 | 内容 | 预计耗时 | 验收标准 |
|------|------|---------|---------|
| **C1** | 新建 `pyproject.toml` + `ruff.toml` | 30分钟 | 文件存在且语法正确 |
| **C2** | 删除 `frontend/` Next.js 目录 | 10分钟 | 目录不存在 |
| **C3** | `ruff check .` 并自动修复 | 30分钟 | 无 E/F 级别错误 |
| **A1** | `skills/orchestration.py` print→logging | 20分钟 | 无 print 调用 |
| **A2** | `skills/orchestration.py` lazy import→模块顶部 | 20分钟 | 导入在模块顶部 |
| **A3** | `skills/orchestration.py` 从 context 获取完整任务数据 | 30分钟 | `_check_decision_point` 使用 `context.get("_task_data")` |
| **B1** | `_check_decision_point` 使用 `DecisionFlow` 替代 `decision_manager` | 60分钟 | 无 `decision_manager` 引用，使用 `DecisionFlow.create_decision()` |
| **B2** | `execute_stage` 集成 `DecisionFlow`（暂停后等待决策） | 60分钟 | 决策完成后根据结果继续/回退 |
| **B3** | CLI 主动渲染回调（`_render_callback`） | 30分钟 | 决策面板生成后自动调用渲染 |
| **T1** | 新增/更新测试 | 60分钟 | 所有新增测试通过 |
| **T2** | 全量回归测试 | 30分钟 | 无新增失败 |
| **V** | 最终验收 | 20分钟 | ruff + 测试 + 功能三重通过 |

**总预计**: 约 7-8 小时

---

## 一、止血工程化（C）

### C1: 新建 `pyproject.toml`

**文件路径**: `pyproject.toml`（项目根目录）

**内容**（必须完全按此实现）:

```toml
[project]
name = "frost-sop"
version = "5.0.0"
description = "FROST-SOP: 分形智能体与家族治理模型"
requires-python = ">=3.10"
dependencies = [
    "rich>=13.0.0",
    "streamlit>=1.28.0",
    "openai>=1.0.0",
    "python-dotenv>=1.0.0",
    "pytest>=7.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
]

[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = []

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
```

**注意**:
- `dependencies` 只包含核心依赖，不要包含 `node_modules` 相关
- `tool.ruff.ignore = ["E501"]` 是因为当前代码有大量行超长，先忽略，逐步修复

---

### C2: 新建 `ruff.toml`

**文件路径**: `ruff.toml`（项目根目录）

**内容**:
```toml
line-length = 100
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[format]
quote-style = "double"
indent-style = "space"
```

**注意**: 这是 `pyproject.toml` 中 `[tool.ruff]` 的独立版本，确保 CLI 直接运行 `ruff` 时也能读取配置。

---

### C3: 删除 `frontend/` 目录

**命令**:
```bash
rm -rf /d/my_ai/Solo-Ops-Platform/workspace/frost-sop/frontend
```

**注意**:
- `frontend/` 包含 Next.js 项目（`next.config.ts`, `package.json`, `node_modules/`）
- Streamlit 前端在 `core/workbench.py`，不受影响
- 删除后确认 `ls frontend/` 返回 "No such file or directory"

---

### C4: 运行 `ruff` 并修复

**命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
ruff check . --fix
ruff format .
```

**注意**:
- `--fix` 会自动修复 E/F 级别错误（如未使用导入）
- `ruff format .` 会自动格式化代码
- 如果 `ruff` 未安装，先运行 `pip install ruff`
- 修复后运行 `ruff check .` 确认无错误（E501 忽略）

---

## 二、最小修复（A）

### A1: `skills/orchestration.py` — print → logging

**修改点1**: 在文件顶部（`import` 区域）添加 logger

**old_string**（`skills/orchestration.py` 顶部，约第 1-15 行）:
```python
"""
PHILOSOPHY:
Orchestration Skills manage agent lifecycle (spawn/emit/validate/merge).
"""

from core.skill import Skill
from core.agent import Agent
from core.store import Store
from datetime import datetime
import asyncio
```

**new_string**:
```python
"""
PHILOSOPHY:
Orchestration Skills manage agent lifecycle (spawn/emit/validate/merge).
"""

import logging
import asyncio
from datetime import datetime

from core.skill import Skill
from core.agent import Agent
from core.store import Store

logger = logging.getLogger(__name__)
```

**修改点2**: 替换 `_check_decision_point` 中的 `print`

**old_string**（约第 192-230 行）:
```python
            print(f"  ⚠️ 跳过决策点（无有效 task_id）: {stage_name}")
            ...
            print(f"  🔮 [V5.0] 决策面板已生成: {decision_panel.panel_id}")
            ...
            print(f"  ⚠️ [V5.0] 决策面板生成失败（不影响暂停）: {e}")
```

**new_string**:
```python
            logger.warning("跳过决策点（无有效 task_id）: %s", stage_name)
            ...
            logger.info("[V5.0] 决策面板已生成: %s", decision_panel.panel_id)
            ...
            logger.warning("[V5.0] 决策面板生成失败（不影响暂停）: %s", e)
```

**注意**: 如果文件中还有其他 `print` 调用，全部替换为 `logger.info()` / `logger.warning()` / `logger.error()`。

---

### A2: `skills/orchestration.py` — lazy import → 模块顶部

**old_string**（`_check_decision_point` 函数内，约第 211-213 行）:
```python
            try:
                from core.panel_generator import PanelGenerator
                from core.panel import PanelType
```

**new_string**（在 `skills/orchestration.py` 模块顶部，与 `from core.skill import Skill` 等同级）:
```python
from core.panel_generator import PanelGenerator
from core.panel import PanelType
```

然后删除 `_check_decision_point` 函数内的 `from core.panel_generator import PanelGenerator` 和 `from core.panel import PanelType` 这两行。

**注意**: 如果 `PanelType` 未在 `_check_decision_point` 中使用（当前代码只使用了 `PanelGenerator`），则不需要导入 `PanelType`。

---

### A3: `skills/orchestration.py` — 从 context 获取完整任务数据

**old_string**（`_check_decision_point` 中构造 `task_for_panel`，约第 216-223 行）:
```python
                # 构造任务字典（供 PanelGenerator 使用）
                task_for_panel = {
                    "task_id": task_id,
                    "title": context.get("_task_title", stage_name),
                    "status": "waiting",
                    "stages": [stage] if isinstance(stage, dict) else list(stage),
                    "current_stage_index": 0,
                    "current_stage": stage,
                }
```

**new_string**:
```python
                # 从 context 获取完整任务数据，或从 Store 读取
                from core.panel_adapters import TaskAdapter
                task_data = context.get("_task_data", {})
                if not task_data and store:
                    raw_task = store.load(task_id) if not task_id.startswith("task:") else store.load(task_id)
                    task_data = raw_task or {}
                
                if task_data:
                    adapted_task = TaskAdapter.adapt(task_data)
                else:
                    adapted_task = {
                        "task_id": task_id.replace("task:", "") if task_id.startswith("task:") else task_id,
                        "name": context.get("_task_title", stage_name),
                        "status": "waiting",
                        "stages": [stage] if isinstance(stage, dict) else list(stage),
                        "current_stage_index": 0,
                        "current_stage": stage,
                    }
```

**注意**: `store` 参数需要从 `_check_decision_point` 的签名或 `context` 中获取。见 B1 的修改。

---

## 三、架构整合（B）

### B1: `_check_decision_point` 使用 `DecisionFlow` 替代 `decision_manager`

**修改点1**: 模块顶部导入 `DecisionFlow`

在 `skills/orchestration.py` 模块顶部，与 `from core.panel_generator import PanelGenerator` 同级添加:
```python
from core.panel_decision import DecisionFlow, DecisionFlowConfig
from core.event_bus import EventBus
```

**修改点2**: `_check_decision_point` 函数签名和内部逻辑重写

**old_string**（整个 `_check_decision_point` 函数）:
```python
def _check_decision_point(context: dict, stage: dict) -> bool:
    """
    检查当前阶段是否需要暂停等待君主决策。
    如果需要暂停，在context中设置决策点信息，返回True。
    否则返回False，继续执行。
    
    V5.0 扩展：同时生成 DECISION 类型面板，存入 context["_decision_panel"]。
    """
    stage_name = stage.get("name", "未知阶段")
    decision_keywords = ["确认", "审核", "审批", "决策", "confirm", "approve", "review"]
    requires_decision = any(keyword in stage_name.lower() for keyword in decision_keywords)
    
    if stage.get("requires_confirmation", False):
        requires_decision = True
    
    if requires_decision:
        task_id = context.get("_task_id", "unknown")
        if task_id == "unknown":
            print(f"  ⚠️ 跳过决策点（无有效 task_id）: {stage_name}")
        else:
            from core.decision_manager import get_decision_manager
            decision_manager = get_decision_manager()
            stage_id = stage.get("id", stage_name)
            question = stage.get("description", f"是否需要执行 {stage_name}？")
            options = stage.get("decision_options", ["确认", "驳回", "修改"])
            decision_id = decision_manager.pause_decision(
                task_id=task_id,
                stage_id=stage_id,
                question=question,
                options=options
            )
            context["_decision_id"] = decision_id
            context["_paused_for_decision"] = True
            context["_decision_question"] = question
            context["_decision_options"] = options
            
            # V5.0: 生成 DECISION 面板
            try:
                from core.panel_generator import PanelGenerator
                from core.panel import PanelType
                
                # 构造任务字典（供 PanelGenerator 使用）
                task_for_panel = {
                    "task_id": task_id,
                    "title": context.get("_task_title", stage_name),
                    "status": "waiting",
                    "stages": [stage] if isinstance(stage, dict) else list(stage),
                    "current_stage_index": 0,
                    "current_stage": stage,
                }
                
                generator = PanelGenerator()
                decision_panel = generator.generate(task_for_panel)
                context["_decision_panel"] = decision_panel
                print(f"  🔮 [V5.0] 决策面板已生成: {decision_panel.panel_id}")
            except Exception as e:
                print(f"  ⚠️ [V5.0] 决策面板生成失败（不影响暂停）: {e}")
    
    return context.get("_paused_for_decision", False)
```

**new_string**:
```python
def _check_decision_point(context: dict, stage: dict) -> bool:
    """
    检查当前阶段是否需要暂停等待君主决策。
    
    V5.0: 使用 DecisionFlow 状态机管理决策生命周期，同时生成 DECISION 面板。
    """
    stage_name = stage.get("name", "未知阶段")
    decision_keywords = ["确认", "审核", "审批", "决策", "confirm", "approve", "review"]
    requires_decision = any(keyword in stage_name.lower() for keyword in decision_keywords)
    
    if stage.get("requires_confirmation", False):
        requires_decision = True
    
    if requires_decision:
        task_id = context.get("_task_id", "unknown")
        if task_id == "unknown":
            logger.warning("跳过决策点（无有效 task_id）: %s", stage_name)
        else:
            # 从 context 获取 event_bus 和 store
            event_bus = context.get("_event_bus")
            store = context.get("_store") or context.get("_asset_store")
            
            # 使用 DecisionFlow 状态机创建决策记录
            decision_flow = DecisionFlow(
                event_bus=event_bus,
                store=store,
                config=DecisionFlowConfig(
                    timeout_seconds=3600,
                    require_reason_for_reject=True,
                ),
            )
            stage_id = stage.get("id", stage_name)
            
            # 构建决策上下文
            context_before = {
                "outputs": stage.get("outputs", []),
                "quality_score": context.get("_quality_score", {}),
                "stage_result": context.get("_current_stage_result", {}),
            }
            
            record = decision_flow.create_decision(
                task_id=task_id,
                stage_id=stage_id,
                stage_name=stage_name,
                context_before=context_before,
            )
            
            context["_decision_id"] = record.decision_id
            context["_paused_for_decision"] = True
            context["_decision_question"] = stage.get("description", f"是否需要执行 {stage_name}？")
            context["_decision_options"] = stage.get("decision_options", ["确认", "驳回", "修改"])
            context["_decision_flow"] = decision_flow  # 保存引用，供后续查询
            
            # 生成 DECISION 面板
            try:
                from core.panel_adapters import TaskAdapter
                task_data = context.get("_task_data", {})
                if task_data:
                    adapted_task = TaskAdapter.adapt(task_data)
                else:
                    adapted_task = {
                        "task_id": task_id.replace("task:", "") if task_id.startswith("task:") else task_id,
                        "name": context.get("_task_title", stage_name),
                        "status": "waiting",
                        "stages": [stage] if isinstance(stage, dict) else list(stage),
                        "current_stage_index": 0,
                        "current_stage": stage,
                    }
                
                generator = PanelGenerator()
                decision_panel = generator.generate(adapted_task)
                context["_decision_panel"] = decision_panel
                logger.info("[V5.0] 决策面板已生成: %s", decision_panel.panel_id)
                
                # CLI 主动渲染（如果配置了渲染回调）
                render_callback = context.get("_render_callback")
                if render_callback and decision_panel:
                    try:
                        render_callback(decision_panel)
                    except Exception as e:
                        logger.warning("决策面板渲染失败（不影响暂停）: %s", e)
                        
            except Exception as e:
                logger.warning("[V5.0] 决策面板生成失败（不影响暂停）: %s", e)
    
    return context.get("_paused_for_decision", False)
```

**注意**:
- `from core.decision_manager import get_decision_manager` 及其所有调用已删除
- `DecisionFlow` 已存在于 `core/panel_decision.py`（之前已交付）
- `context["_decision_flow"] = decision_flow` 保存引用，供 `execute_stage` 后续查询

---

### B2: `execute_stage` 集成 `DecisionFlow`（暂停后等待决策）

在 `skills/orchestration.py` 的 `execute_stage` 函数中，找到 `_check_decision_point` 被调用后的处理逻辑。

**修改**: 在 `paused` 为 True 后，添加等待决策完成的逻辑。

**old_string**（`execute_stage` 中决策点暂停后的处理，假设类似）:
```python
    paused = _check_decision_point(context, stage)
    if paused:
        return context
```

**new_string**:
```python
    paused = _check_decision_point(context, stage)
    if paused:
        # V5.0: 等待决策完成（通过 DecisionFlow 状态机）
        decision_flow = context.get("_decision_flow")
        decision_id = context.get("_decision_id")
        if decision_flow and decision_id:
            record = decision_flow.get_decision(decision_id)
            # 轮询等待决策完成（非阻塞式，每1秒检查一次）
            import time
            max_wait = 3600  # 最大等待1小时
            waited = 0
            while record and not record.is_final() and waited < max_wait:
                time.sleep(1)
                waited += 1
                decision_flow.check_timeout(decision_id)
                record = decision_flow.get_decision(decision_id)
            
            if record and record.is_final():
                if record.status == DecisionStatus.APPROVED:
                    logger.info("决策已确认: %s", decision_id)
                    context["_paused_for_decision"] = False
                    # 继续执行当前阶段
                elif record.status in (DecisionStatus.REJECTED, DecisionStatus.TIMEOUT, DecisionStatus.CANCELLED):
                    logger.warning("决策被驳回/超时/取消: %s", decision_id)
                    context["_stage_results"] = context.get("_stage_results", []) + [{
                        "stage": stage.get("name", "unknown"),
                        "status": "failed",
                        "reason": f"决策{record.status.value}: {record.reason}",
                    }]
                    return context
            else:
                logger.error("决策等待超时: %s", decision_id)
                context["_stage_results"] = context.get("_stage_results", []) + [{
                    "stage": stage.get("name", "unknown"),
                    "status": "failed",
                    "reason": "决策等待超时",
                }]
                return context
        else:
            # 回退到原有逻辑：直接返回（等待外部处理）
            return context
```

**注意**: 需要确保 `DecisionStatus` 已导入。在模块顶部添加:
```python
from core.panel_decision import DecisionStatus
```

---

### B3: CLI 主动渲染回调（`_render_callback`）

**修改点**: 在 `_check_decision_point` 中，决策面板生成后调用 `render_callback`（已在 B1 的 new_string 中实现）。

**使用方式**（调用方，如 `main.py` 或 `workbench.py`）:
```python
from renderers.cli_renderer import CliRenderer, CliDataProvider
from core.panel_data_provider import StoreDataProvider

def render_decision_panel(panel):
    """渲染决策面板的回调函数"""
    data_provider = StoreDataProvider(store, task_id=panel.task_id)
    renderer = CliRenderer(data_provider=data_provider)
    renderer.render(panel)

# 在创建任务时，将回调注入 context
context["_render_callback"] = render_decision_panel
```

**注意**: 不需要修改 `skills/orchestration.py` 的调用方，因为 `render_callback` 是通过 `context` 传入的。但需要在测试或示例中演示这个用法。

---

## 四、测试（T）

### T1: 更新 `tests/test_panel_integration.py`

**新增测试类1**: `TestCliRendering`

在 `TestSopPanelIntegration` 类之后、`TestEventAdapter` 类之前插入:

```python
class TestCliRendering:
    """CLI 渲染器测试——验证决策面板在终端的实际渲染"""

    def test_decision_panel_cli_rendering(self):
        """测试决策面板在 CLI 中的渲染输出包含关键文本"""
        from renderers.cli_renderer import CliRenderer, CliDataProvider
        from core.panel_generator import PanelGenerator
        from core.panel import PanelType, ComponentType

        # 构造决策任务
        task = {
            "task_id": "test_cli",
            "name": "CLI渲染测试",
            "status": "waiting",
            "stages": [
                {
                    "name": "代码审核",
                    "is_decision_point": True,
                    "decision_options": ["确认", "驳回", "修改"],
                    "outputs": [
                        {"name": "实现代码", "type": "code", "content": "def hello(): pass"}
                    ],
                }
            ],
            "current_stage_index": 0,
            "current_stage": {
                "name": "代码审核",
                "is_decision_point": True,
                "decision_options": ["确认", "驳回", "修改"],
                "outputs": [
                    {"name": "实现代码", "type": "code", "content": "def hello(): pass"}
                ],
            },
            "quality_score": {"customer": 85, "parent": 80, "child": 70},
        }

        # 生成决策面板
        generator = PanelGenerator()
        panel = generator.generate(task)
        assert panel.panel_type == PanelType.DECISION

        # 渲染到 StringIO（捕获输出）
        from io import StringIO
        from rich.console import Console

        output = StringIO()
        console = Console(file=output, force_terminal=True)
        data_provider = CliDataProvider({
            "task.status": {"status": "waiting", "progress": 50, "cost": 0.1},
            "task.current_stage.outputs[0]": "def hello(): pass",
            "task.quality_score": {"customer": 85, "parent": 80, "child": 70},
        })
        renderer = CliRenderer(data_provider=data_provider, console=console)
        renderer.render(panel)

        rendered = output.getvalue()

        # 验证关键文本存在
        assert "决策" in rendered
        assert "确认" in rendered
        assert "驳回" in rendered
        assert "修改" in rendered

    def test_cockpit_panel_cli_rendering(self):
        """测试驾驶舱面板在 CLI 中的渲染"""
        from renderers.cli_renderer import CliRenderer, CliDataProvider
        from core.panel_generator import PanelGenerator
        from core.panel import PanelType

        tasks = [
            {"task_id": "t1", "title": "任务1", "status": "running", "stages": [{"name": "s1"}], "current_stage_index": 0, "created_at": "2026-01-01T00:00:00"},
            {"task_id": "t2", "title": "任务2", "status": "completed", "stages": [{"name": "s1"}], "current_stage_index": 0, "created_at": "2026-01-02T00:00:00"},
        ]

        generator = PanelGenerator()
        panel = generator.generate(tasks)
        assert panel.panel_type == PanelType.COCKPIT

        from io import StringIO
        from rich.console import Console
        output = StringIO()
        console = Console(file=output, force_terminal=True)
        data_provider = CliDataProvider({})
        renderer = CliRenderer(data_provider=data_provider, console=console)
        renderer.render(panel)

        rendered = output.getvalue()
        assert "家族驾驶舱" in rendered
        assert "任务" in rendered
```

**新增测试类2**: `TestDecisionFlowIntegration`（在 `TestSopPanelIntegration` 中扩展）

在 `TestSopPanelIntegration` 类中添加:

```python
    def test_decision_flow_replaces_decision_manager(self):
        """测试 DecisionFlow 替代了 decision_manager"""
        from skills.orchestration import _check_decision_point
        from core.panel_decision import DecisionFlow, DecisionFlowConfig
        from core.panel import PanelDefinition

        stage = {
            "id": "stage_review",
            "name": "代码审核",
            "description": "请确认",
            "is_decision_point": True,
            "requires_confirmation": True,
            "decision_options": ["确认", "驳回"],
        }

        context = {
            "_task_id": "task:test_flow",
            "_task_title": "Flow测试",
        }

        paused = _check_decision_point(context, stage)
        assert paused is True

        # 验证使用了 DecisionFlow（有 _decision_flow 引用）
        assert "_decision_flow" in context
        assert isinstance(context["_decision_flow"], DecisionFlow)

        # 验证决策记录已创建
        decision_id = context.get("_decision_id")
        assert decision_id is not None
        assert decision_id.startswith("decision:")

        # 验证面板已生成
        assert "_decision_panel" in context
        assert isinstance(context["_decision_panel"], PanelDefinition)
```

---

### T2: 新增 `tests/test_decision_flow_integration.py`

**文件路径**: `tests/test_decision_flow_integration.py`

**内容**:

```python
"""
DecisionFlow 与 orchestration 集成测试
"""

import pytest
from core.panel_decision import DecisionFlow, DecisionFlowConfig, DecisionStatus
from core.store import Store
from core.event_bus import EventBus


class TestDecisionFlowIntegration:
    """DecisionFlow 与 SOP 执行引擎集成"""

    def test_create_decision_in_orchestration(self):
        """测试在 orchestration 中创建决策"""
        from skills.orchestration import _check_decision_point
        
        stage = {
            "id": "s1",
            "name": "审核阶段",
            "is_decision_point": True,
            "decision_options": ["确认", "驳回"],
        }
        context = {"_task_id": "task:test", "_task_title": "测试"}
        
        paused = _check_decision_point(context, stage)
        assert paused is True
        assert "_decision_id" in context

    def test_decision_flow_timeout(self):
        """测试决策超时处理"""
        store = Store()
        flow = DecisionFlow(store=store, config=DecisionFlowConfig(timeout_seconds=1))
        
        record = flow.create_decision(
            task_id="task:t",
            stage_id="s1",
            stage_name="测试",
        )
        
        # 模拟超时
        import time
        time.sleep(2)
        
        timed_out = flow.check_timeout(record.decision_id)
        assert timed_out is True
        
        record = flow.get_decision(record.decision_id)
        assert record.status == DecisionStatus.TIMEOUT

    def test_decision_flow_approve(self):
        """测试决策确认流程"""
        store = Store()
        flow = DecisionFlow(store=store)
        
        record = flow.create_decision(task_id="task:t", stage_id="s1", stage_name="测试")
        
        record = flow.submit_decision(
            record.decision_id,
            decision="确认",
        )
        
        assert record.status == DecisionStatus.APPROVED
        assert record.decision == "确认"

    def test_decision_flow_reject_requires_reason(self):
        """测试驳回需要理由"""
        store = Store()
        flow = DecisionFlow(store=store, config=DecisionFlowConfig(require_reason_for_reject=True))
        
        record = flow.create_decision(task_id="task:t", stage_id="s1", stage_name="测试")
        
        # 无理由驳回 → 状态变为 IN_PROGRESS
        record = flow.submit_decision(record.decision_id, decision="驳回", reason="")
        assert record.status == DecisionStatus.IN_PROGRESS
        
        # 补充理由后重新提交
        record = flow.submit_decision(record.decision_id, decision="驳回", reason="质量不达标")
        assert record.status == DecisionStatus.REJECTED
```

---

### T3: 全量回归测试

**命令**:
```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
python -m pytest tests/ -q --tb=short
```

**验收标准**:
- 所有 Panel 相关测试通过（test_panel*.py）
- 所有 Orchestration 测试通过（test_orchestration*.py）
- 无新增失败（与之前审计时的失败列表一致）

---

## 五、最终验收（V）

### 验收清单

| # | 验收项 | 检查方法 | 通过标准 |
|---|--------|---------|---------|
| 1 | ruff 通过 | `ruff check .` | 无 E/F 错误（E501 忽略） |
| 2 | 无 print 调用 | `grep -r "print(" skills/orchestration.py` | 无输出（logger 除外） |
| 3 | 无 lazy import | `grep -n "from core.panel_generator" skills/orchestration.py` | 只在模块顶部 |
| 4 | DecisionFlow 替代 | `grep -n "decision_manager" skills/orchestration.py` | 无输出 |
| 5 | 测试通过 | `pytest tests/ -q` | 无新增失败 |
| 6 | CLI 渲染测试 | `pytest tests/test_panel_integration.py::TestCliRendering -v` | 通过 |
| 7 | DecisionFlow 集成 | `pytest tests/test_decision_flow_integration.py -v` | 通过 |
| 8 | frontend 删除 | `ls frontend/` | 不存在 |
| 9 | pyproject.toml | `cat pyproject.toml` | 存在且语法正确 |
| 10 | ruff.toml | `cat ruff.toml` | 存在且语法正确 |

---

## 六、关键注意事项（WorkBuddy 必读）

1. **修改顺序**: 必须先做 C（工程化），再做 A（修复），再做 B（架构）。因为 ruff 会修改代码格式，如果在 B 之后运行 ruff，可能会覆盖 B 的修改。

2. **DecisionFlow 已存在**: `core/panel_decision.py` 已在之前交付，直接导入使用，不需要重新实现。

3. **EventBus 单例**: `EventBus()` 是单例，`context.get("_event_bus")` 如果没有，可以回退到 `EventBus()`。

4. **_render_callback 是可选的**: 如果 `context` 中没有 `_render_callback`，CLI 渲染不会触发，但决策暂停仍然正常工作。这保证了向后兼容。

5. **测试中的 time.sleep**: `test_decision_flow_timeout` 使用了 `time.sleep(2)`，这是可接受的（测试文件中使用 sleep 是常见做法）。

6. **如果 _check_decision_point 的调用方不止 execute_stage**: 使用 `grep -n "_check_decision_point" skills/` 找到所有调用方，确保所有调用方都能正常工作（签名变化已最小化：只增加了可选的 event_bus 和 store，从 context 获取）。

7. **如果遇到循环导入**: `core/panel_decision.py` 导入了 `core.event_bus`，`skills/orchestration.py` 导入了 `core.panel_decision`。如果存在循环导入，将 `from core.panel_decision import ...` 保留在函数内（但这是最后的回退，优先模块级导入）。

---

*指令集结束。WorkBuddy 按阶段顺序执行，每阶段完成后运行验收清单中的对应项。*
