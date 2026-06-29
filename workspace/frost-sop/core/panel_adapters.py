"""
FROST V5.0 面板适配器——与现有代码的整合接口

PHILOSOPHY: 面板系统不是独立王国，它是FROST现有代码的延伸。
通过适配器模式，面板系统与任务、事件、武器库无缝集成，不破坏现有代码。
"""

from typing import Any, Dict, Optional
from datetime import datetime

from core.panel import PanelDefinition, PanelComponent, ComponentType
from core.panel_renderer import DataProvider
from core.panel_data_provider import StoreDataProvider
from core.event_bus import EventBus, Event


# ────────────────────────────────────────────────────────────────────────────
# 1. 任务数据适配器（TaskAdapter）
# ────────────────────────────────────────────────────────────────────────────

class TaskAdapter:
    """
    任务数据适配器——将 FROST 现有任务格式适配为面板生成器期望的格式。

    FROST 现有任务格式（从 Store 读取，key 前缀 "task:"）：
    {
        "id": "task:auth_feature_001",
        "title": "Add user authentication",
        "description": "...",
        "status": "running",
        "stages": [...],
        "current_stage_index": 0,
        "quality_score": {"customer": 85, "parent": 80, "child": 70},
        "cost": 0.15,
        "outputs": [...],
    }

    面板生成器期望的格式（PanelGenerator.generate() 的 task 参数）：
    {
        "task_id": "auth_feature_001",
        "name": "Add user authentication",
        "description": "...",
        "status": "running",
        "stages": [...],
        "current_stage_index": 0,
        "current_stage": {...},  # 需要计算
        "quality_score": {...},
        "cost": 0.15,
        "outputs": [...],
    }
    """

    @staticmethod
    def adapt(task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 FROST 任务数据适配为面板生成器期望的格式。

        Args:
            task_data: 从 Store 读取的任务字典（key 前缀 "task:"）

        Returns:
            面板生成器期望的任务字典
        """
        if not isinstance(task_data, dict):
            return {}

        # 基础字段映射
        adapted = {
            "task_id": task_data.get("id", "").replace("task:", ""),
            "name": task_data.get("title", ""),
            "description": task_data.get("description", ""),
            "status": task_data.get("status", "created"),
            "stages": task_data.get("stages", []),
            "current_stage_index": task_data.get("current_stage_index", 0),
            "quality_score": task_data.get("quality_score", {}),
            "cost": task_data.get("cost", 0.0),
            "tokens": task_data.get("tokens", 0),
            "duration_seconds": task_data.get("duration_seconds", 0.0),
            "outputs": task_data.get("outputs", []),
            "event_ids": task_data.get("event_ids", []),
        }

        # 计算当前阶段
        stages = adapted["stages"]
        current_idx = adapted["current_stage_index"]
        if 0 <= current_idx < len(stages):
            adapted["current_stage"] = stages[current_idx]
        else:
            adapted["current_stage"] = {}

        # 计算是否处于决策点
        current_stage = adapted["current_stage"]
        adapted["is_decision_point"] = current_stage.get("is_decision_point", False)
        adapted["decision_options"] = current_stage.get("decision_options", ["确认", "驳回", "修改"])

        # 计算是否需要简报
        adapted["requires_briefing"] = adapted["status"] in ("completed", "failed")

        # 计算优先级
        adapted["priority"] = task_data.get("priority", "normal")

        return adapted

    @staticmethod
    def adapt_from_store(store, task_id: str) -> Dict[str, Any]:
        """从 Store 读取任务并适配"""
        task_data = store.load(f"task:{task_id}") if not task_id.startswith("task:") else store.load(task_id)
        return TaskAdapter.adapt(task_data)


# ────────────────────────────────────────────────────────────────────────────
# 2. 事件系统适配器（EventAdapter）
# ────────────────────────────────────────────────────────────────────────────

class EventAdapter:
    """
    事件系统适配器——面板交互与 FROST V2.0 EventBus 的整合。

    V2.0 EventBus 接口：
    - EventBus() — 单例获取
    - event_bus.subscribe(event_type, callback) — callback(event: Event) -> None
    - event_bus.publish(event) — Event(event_type, source, data)
    - event_bus.get_event_log(event_type, limit)

    面板系统新增事件类型：
    - "panel.loaded" — 面板加载完成
    - "panel.component_changed" — 面板组件值变更
    - "panel.decision_made" — Human Agent 做出决策
    - "panel.closed" — 面板关闭
    """

    # 面板系统事件类型常量
    PANEL_LOADED = "panel.loaded"
    PANEL_COMPONENT_CHANGED = "panel.component_changed"
    PANEL_DECISION_MADE = "panel.decision_made"
    PANEL_CLOSED = "panel.closed"

    def __init__(self, event_bus: Optional[EventBus] = None):
        self.event_bus = event_bus or EventBus()

    def emit_panel_loaded(self, panel_id: str, task_id: Optional[str] = None):
        """触发面板加载事件"""
        event = Event(
            event_type=self.PANEL_LOADED,
            source="panel_system",
            data={"panel_id": panel_id, "task_id": task_id},
        )
        self.event_bus.publish(event)

    def emit_component_changed(self, panel_id: str, component_id: str, value: Any,
                                task_id: Optional[str] = None):
        """触发面板组件变更事件"""
        event = Event(
            event_type=self.PANEL_COMPONENT_CHANGED,
            source="panel_system",
            data={
                "panel_id": panel_id,
                "component_id": component_id,
                "value": value,
                "task_id": task_id,
                "timestamp": datetime.now().isoformat(),
            },
        )
        self.event_bus.publish(event)

    def emit_decision_made(self, decision_id: str, decision: str, reason: str = "",
                           task_id: Optional[str] = None, stage_id: Optional[str] = None):
        """触发 Human Agent 决策事件"""
        event = Event(
            event_type=self.PANEL_DECISION_MADE,
            source="human_agent",
            data={
                "decision_id": decision_id,
                "task_id": task_id,
                "stage_id": stage_id,
                "decision": decision,
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
            },
        )
        self.event_bus.publish(event)

    def emit_panel_closed(self, panel_id: str, task_id: Optional[str] = None):
        """触发面板关闭事件"""
        event = Event(
            event_type=self.PANEL_CLOSED,
            source="panel_system",
            data={"panel_id": panel_id, "task_id": task_id},
        )
        self.event_bus.publish(event)

    def subscribe_to_decisions(self, callback):
        """订阅决策事件（SOP 执行引擎使用）"""
        self.event_bus.subscribe(self.PANEL_DECISION_MADE, callback)

    def get_panel_events(self, panel_id: str, limit: int = 100) -> list:
        """获取面板相关的所有事件"""
        all_events = self.event_bus.get_event_log(None, limit=limit)
        return [e for e in all_events if e.data.get("panel_id") == panel_id]


# ────────────────────────────────────────────────────────────────────────────
# 3. 武器库适配器（ArmoryAdapter）
# ────────────────────────────────────────────────────────────────────────────

class ArmoryAdapter:
    """
    武器库适配器——扩展 WeaponMetadata 以支持面板组件声明。

    在 core/armory.py 的 WeaponMetadata 中增加 panel_components 字段后，
    此适配器负责根据武器的面板组件声明，生成对应的 PanelComponent。
    """

    # 组件类型映射：武器声明的组件类型 → PanelComponent 类型
    COMPONENT_TYPE_MAP = {
        "text_input": ComponentType.TEXT_INPUT,
        "textarea": ComponentType.TEXTAREA,
        "code_editor": ComponentType.CODE_EDITOR,
        "code_preview": ComponentType.CODE_PREVIEW,
        "text_display": ComponentType.TEXT_DISPLAY,
        "markdown": ComponentType.MARKDOWN,
        "table": ComponentType.TABLE,
        "chart": ComponentType.CHART,
        "decision_buttons": ComponentType.DECISION_BUTTONS,
        "progress_bar": ComponentType.PROGRESS_BAR,
        "health_gauge": ComponentType.HEALTH_GAUGE,
        "alert_banner": ComponentType.ALERT_BANNER,
        "collapsible_card": ComponentType.COLLAPSIBLE_CARD,
        "task_list": ComponentType.TASK_LIST,
        "timeline": ComponentType.TIMELINE,
        "status_bar": ComponentType.STATUS_BAR,
    }

    @staticmethod
    def weapon_to_panel_components(weapon) -> list:
        """
        将武器的 panel_components 声明转换为 PanelComponent 列表。

        Args:
            weapon: WeaponMetadata 实例（需要有 panel_components 字段）

        Returns:
            PanelComponent 列表
        """
        components = []
        panel_components = getattr(weapon, "panel_components", None)
        if not panel_components:
            return components

        for comp_decl in panel_components:
            comp_type = ArmoryAdapter.COMPONENT_TYPE_MAP.get(
                comp_decl.get("type", ""), ComponentType.TEXT_DISPLAY
            )

            component = PanelComponent(
                id=f"comp:{weapon.id}_{comp_decl.get('name', 'unknown')}",
                type=comp_type,
                label=comp_decl.get("label", ""),
                data_source=comp_decl.get("data_source", ""),
                data_binding=comp_decl.get("data_binding", ""),
                required=comp_decl.get("required", False),
                properties=comp_decl.get("properties", {}),
            )
            components.append(component)

        return components

    @staticmethod
    def update_weapon_metadata(weapon, panel_components: list):
        """
        为武器元数据添加 panel_components 字段。

        Args:
            weapon: WeaponMetadata 实例
            panel_components: 面板组件声明列表
            
            示例 panel_components:
            [
                {
                    "type": "text_input",
                    "name": "prompt",
                    "label": "Prompt",
                    "data_source": "task.current_stage.inputs[0]",
                    "required": True,
                },
                {
                    "type": "code_preview",
                    "name": "output",
                    "label": "Generated Code",
                    "data_source": "task.current_stage.outputs[0]",
                },
            ]
        """
        weapon.panel_components = panel_components


# ────────────────────────────────────────────────────────────────────────────
# 4. 综合适配器（PanelSystemAdapter）——一键集成
# ────────────────────────────────────────────────────────────────────────────

class PanelSystemAdapter:
    """
    综合适配器——面板系统与 FROST 现有代码的一键集成。

    使用方式：
        adapter = PanelSystemAdapter(store, armory_registry)
        
        # 为任务生成面板
        task = store.load("task:xxx")
        panel = adapter.generate_panel_for_task(task)
        
        # 渲染面板
        renderer = adapter.create_renderer(task_id="task:xxx")
        renderer.render(panel)
    """

    def __init__(self, store, armory_registry=None, event_bus=None):
        self.store = store
        self.armory = armory_registry
        self.event_bus = event_bus or EventBus()
        self.event_adapter = EventAdapter(self.event_bus)

    def generate_panel_for_task(self, task_data: dict, sop=None) -> PanelDefinition:
        """为任务生成面板"""
        from core.panel_generator import PanelGenerator

        # 适配任务数据
        adapted_task = TaskAdapter.adapt(task_data)

        # 生成面板
        generator = PanelGenerator(self.armory)
        panel = generator.generate(adapted_task, sop)

        return panel

    def create_renderer(self, task_id: str = None, console=None):
        """创建渲染器（自动配置数据提供者）"""
        from core.panel_renderer import PanelRenderer
        from renderers.cli_renderer import CliRenderer, CliDataProvider

        # 创建数据提供者
        data_provider = StoreDataProvider(
            store=self.store,
            task_id=task_id,
            armory_registry=self.armory,
        )

        # 创建渲染器
        return CliRenderer(data_provider=data_provider, console=console)

    def emit_panel_event(self, event_type: str, panel_id: str, data: dict = None):
        """通过事件适配器触发面板事件"""
        method_map = {
            "loaded": self.event_adapter.emit_panel_loaded,
            "component_changed": self.event_adapter.emit_component_changed,
            "decision_made": self.event_adapter.emit_decision_made,
            "closed": self.event_adapter.emit_panel_closed,
        }

        method = method_map.get(event_type)
        if method:
            if event_type == "component_changed":
                method(panel_id, data.get("component_id"), data.get("value"), data.get("task_id"))
            elif event_type == "decision_made":
                method(
                    data.get("decision_id"), data.get("decision"), data.get("reason", ""),
                    data.get("task_id"), data.get("stage_id"),
                )
            else:
                method(panel_id, data.get("task_id"))
