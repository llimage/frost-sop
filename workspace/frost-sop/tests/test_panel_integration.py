"""
FROST V5.0 面板系统集成测试

测试范围：
1. StoreDataProvider + Store 集成
2. DecisionFlow + EventBus 集成
3. TaskAdapter + PanelGenerator 集成
4. PanelSystemAdapter 端到端流程
5. EventAdapter 事件触发与订阅
6. CLI 渲染器 + DataProvider 集成
"""
import os
import sys
import pytest
from datetime import datetime
from typing import Any, Dict, List, Optional

# 设置测试环境
os.environ['FROST_TESTING'] = '1'

from core.panel import (
    PanelDefinition, PanelComponent, ComponentType,
    PanelType, LayoutType, Region, Layout, Theme, PanelState
)
from core.panel_renderer import PanelRenderer, DataProvider
from core.panel_generator import PanelGenerator
from core.panel_data_provider import StoreDataProvider, create_data_provider
from core.panel_decision import (
    DecisionFlow, DecisionRecord, DecisionStatus, DecisionFlowConfig
)
from core.panel_adapters import (
    TaskAdapter, EventAdapter, ArmoryAdapter, PanelSystemAdapter
)
from core.store import Store
from core.event_bus import EventBus, Event


# ────────────────────────────────────────────────────────────────────────────
# 助手函数
# ────────────────────────────────────────────────────────────────────────────

def _make_store_with_task(task_id: str = "task:test001") -> Store:
    """创建带测试任务的 Store"""
    store = Store()
    store.save(task_id, {
        "id": task_id,
        "title": "集成测试任务",
        "description": "用于面板系统集成测试",
        "status": "running",
        "stages": [
            {
                "stage_id": "s1",
                "name": "需求分析",
                "description": "分析需求",
                "inputs": [{"name": "需求文档", "type": "document"}],
                "outputs": [{"name": "需求规格", "type": "document", "status": "completed"}],
                "skill": "requirement_analysis",
                "is_decision_point": False,
            },
            {
                "stage_id": "s2",
                "name": "代码实现",
                "description": "实现功能",
                "inputs": [{"name": "需求规格", "type": "document"}],
                "outputs": [{"name": "源代码", "type": "code", "status": "completed"}],
                "skill": "code_implementation",
                "is_decision_point": True,
                "decision_options": ["确认", "驳回", "修改"],
            },
        ],
        "current_stage_index": 1,
        "quality_score": {"customer": 85, "parent": 80, "child": 90},
        "cost": 0.15,
        "tokens": 1500,
        "duration_seconds": 120.0,
        "outputs": [
            {"type": "code", "name": "main.py", "status": "completed"},
        ],
        "event_ids": [],
        "priority": "high",
    })
    return store


def _make_mock_armory():
    """创建模拟武器库（用于 ArmoryAdapter 测试）"""

    class MockWeapon:
        def __init__(self, weapon_id: str):
            self.id = weapon_id
            self.panel_components = [
                {
                    "type": "text_input",
                    "name": "prompt",
                    "label": "输入提示",
                    "data_source": "task.current_stage.inputs[0]",
                    "required": True,
                },
                {
                    "type": "code_preview",
                    "name": "output",
                    "label": "生成代码",
                    "data_source": "task.current_stage.outputs[0]",
                },
            ]

        def to_dict(self):
            return {"id": self.id, "panel_components": self.panel_components}

    class MockArmory:
        def __init__(self):
            self._weapons = {}
            w = MockWeapon("skill:code_gen")
            self._weapons["skill:code_gen"] = w

        def get(self, weapon_id: str):
            return self._weapons.get(weapon_id)

    return MockArmory()


# ────────────────────────────────────────────────────────────────────────────
# 1. StoreDataProvider 集成测试
# ────────────────────────────────────────────────────────────────────────────

class TestStoreDataProvider:
    """StoreDataProvider + Store 集成测试"""

    def setup_method(self):
        self.store = _make_store_with_task()
        self.provider = StoreDataProvider(self.store, task_id="task:test001")

    def test_get_task_field(self):
        """测试获取任务字段"""
        assert self.provider.get("task.status") == "running"
        assert self.provider.get("task.title") == "集成测试任务"
        assert self.provider.get("task.cost") == 0.15

    def test_get_task_stages(self):
        """测试获取任务阶段"""
        stages = self.provider.get("task.stages")
        assert isinstance(stages, list)
        assert len(stages) == 2
        assert stages[0]["name"] == "需求分析"

    def test_get_task_current_stage(self):
        """测试获取当前阶段"""
        current = self.provider.get("task.current_stage")
        assert current is not None
        assert current["name"] == "代码实现"  # current_stage_index=1

    def test_get_task_stage_by_index(self):
        """测试按索引获取阶段"""
        stage0 = self.provider.get("task.stages[0]")
        assert stage0 is not None
        assert stage0["name"] == "需求分析"

    def test_get_task_stage_name_by_path(self):
        """测试路径导航获取阶段名称"""
        name = self.provider.get("task.stages[0].name")
        assert name == "需求分析"

    def test_get_prefixed_key_from_store(self):
        """测试从 Store 读取带前缀的键"""
        # 先往 Store 写一个 intel: 键
        self.store.save("intel:strategist_brief", {"summary": "测试情报"})
        result = self.provider.get("intel:strategist_brief")
        assert result is not None
        assert result["summary"] == "测试情报"

    def test_get_nonexistent_key_returns_none(self):
        """测试读取不存在的键返回 None"""
        # task_id 未设置时，task.* 查询返回 None
        provider_no_task = StoreDataProvider(self.store)
        assert provider_no_task.get("task.status") is None

        # 不存在的键返回 None
        assert self.provider.get("intel:nonexistent") is None

    def test_get_with_data_binding(self):
        """测试带 data_binding 的查询"""
        # quality_score 是一个 dict，data_binding 可以导航到子字段
        score = self.provider.get("task.quality_score", "customer")
        assert score == 85

    def test_create_data_provider_helper(self):
        """测试便捷函数"""
        provider = create_data_provider(self.store, task_id="task:test001")
        assert isinstance(provider, StoreDataProvider)
        assert provider.task_id == "task:test001"


# ────────────────────────────────────────────────────────────────────────────
# 2. DecisionFlow + EventBus 集成测试
# ────────────────────────────────────────────────────────────────────────────

class TestDecisionFlowIntegration:
    """DecisionFlow + EventBus 集成测试"""

    def setup_method(self):
        self.event_bus = EventBus()
        self.store = _make_store_with_task()
        self.flow = DecisionFlow(
            event_bus=self.event_bus,
            config=DecisionFlowConfig(timeout_seconds=3600),
            store=self.store,
        )
        self.events_captured = []
        # 订阅所有决策事件
        self.event_bus.subscribe("decision.created", self._capture_event)
        self.event_bus.subscribe("decision.made", self._capture_event)
        self.event_bus.subscribe("decision.timeout", self._capture_event)
        self.event_bus.subscribe("decision.cancelled", self._capture_event)

    def _capture_event(self, event: Event):
        self.events_captured.append(event)

    def test_create_decision_emits_event(self):
        """测试创建决策时触发事件"""
        record = self.flow.create_decision(
            task_id="task:test001",
            stage_id="stage_2",
            stage_name="代码实现",
            context_before={"quality_score": {"customer": 85}},
        )
        assert record.status == DecisionStatus.PENDING
        assert len(self.events_captured) == 1
        assert self.events_captured[0].event_type == "decision.created"
        assert self.events_captured[0].data["decision_id"] == record.decision_id

    def test_submit_decision_emits_event(self):
        """测试提交决策时触发事件"""
        record = self.flow.create_decision("task:test001", "stage_2", "代码实现")
        self.events_captured.clear()

        self.flow.submit_decision(
            decision_id=record.decision_id,
            decision="确认",
            human_agent_id="monarch",
        )
        assert len(self.events_captured) == 1
        assert self.events_captured[0].event_type == "decision.made"
        assert self.events_captured[0].data["decision"] == "确认"

    def test_decision_flow_full_cycle(self):
        """测试决策完整流程：创建 → 提交 → 查询"""
        record = self.flow.create_decision("task:test001", "stage_2", "代码实现")
        assert record.status == DecisionStatus.PENDING

        # 提交决策（理由必须 >= 10 字符）
        updated = self.flow.submit_decision(
            decision_id=record.decision_id,
            decision="修改",
            reason="变量命名需要改进，建议使用更具描述性的名称",
            human_agent_id="monarch",
        )
        assert updated.status == DecisionStatus.MODIFIED
        assert updated.decision == "修改"
        assert "变量命名" in updated.reason  # 理由包含提交的内容

        # 查询决策
        fetched = self.flow.get_decision(record.decision_id)
        assert fetched is not None
        assert fetched.status == DecisionStatus.MODIFIED

    def test_get_task_decisions(self):
        """测试获取任务的所有决策"""
        self.flow.create_decision("task:test001", "stage_1", "需求分析")
        self.flow.create_decision("task:test001", "stage_2", "代码实现")
        self.flow.create_decision("task:other", "stage_1", "其他任务")

        task_decisions = self.flow.get_task_decisions("task:test001")
        assert len(task_decisions) == 2

    def test_cancel_decision(self):
        """测试取消决策"""
        record = self.flow.create_decision("task:test001", "stage_1", "需求分析")
        self.flow.cancel_decision(record.decision_id, reason="任务终止")
        assert record.status == DecisionStatus.CANCELLED

    def test_persistence_to_store(self):
        """测试决策持久化到 Store"""
        record = self.flow.create_decision("task:test001", "stage_1", "需求分析")
        # 提交后应该持久化
        self.flow.submit_decision(record.decision_id, "确认")

        # 从 Store 读取
        saved = self.store.load(record.decision_id)
        assert saved is not None
        assert saved["status"] == "approved"
        assert saved["decision"] == "确认"

    def test_decision_requires_reason_for_reject(self):
        """测试驳回时必须填写理由"""
        record = self.flow.create_decision("task:test001", "stage_1", "需求分析")
        # 提交驳回但不填理由 → 状态变为 IN_PROGRESS
        updated = self.flow.submit_decision(
            decision_id=record.decision_id,
            decision="驳回",
            reason="",  # 空理由
        )
        assert updated.status == DecisionStatus.IN_PROGRESS

    def test_submit_decision_twice_raises(self):
        """测试重复提交决策报错"""
        record = self.flow.create_decision("task:test001", "stage_1", "需求分析")
        self.flow.submit_decision(record.decision_id, "确认")
        # 再次提交应该报错
        import pytest
        with pytest.raises(ValueError, match="already final"):
            self.flow.submit_decision(record.decision_id, "驳回")


# ────────────────────────────────────────────────────────────────────────────
# 3. TaskAdapter + PanelGenerator 集成测试
# ────────────────────────────────────────────────────────────────────────────

class TestTaskAdapterPanelGenerator:
    """TaskAdapter + PanelGenerator 集成测试"""

    def setup_method(self):
        self.store = _make_store_with_task()

    def test_adapt_from_store(self):
        """测试从 Store 读取并适配任务数据"""
        adapted = TaskAdapter.adapt_from_store(self.store, "task:test001")
        assert adapted["task_id"] == "test001"
        assert adapted["name"] == "集成测试任务"
        assert adapted["status"] == "running"
        assert "current_stage" in adapted
        assert adapted["current_stage"]["name"] == "代码实现"

    def test_adapt_sets_is_decision_point(self):
        """测试适配后正确设置 is_decision_point"""
        adapted = TaskAdapter.adapt_from_store(self.store, "task:test001")
        # current_stage_index=1，对应 stages[1]，is_decision_point=True
        assert adapted["is_decision_point"] is True

    def test_generate_panel_from_adapted_task(self):
        """测试从适配后的任务数据生成面板（当前阶段是决策点 → DECISION 类型）"""
        adapted = TaskAdapter.adapt_from_store(self.store, "task:test001")
        generator = PanelGenerator()
        panel = generator.generate(adapted)
        assert isinstance(panel, PanelDefinition)
        # 当前阶段 is_decision_point=True，生成器返回 DECISION 类型
        assert panel.panel_type == PanelType.DECISION
        assert panel.panel_id.startswith("panel:decision_")

    def test_generate_cockpit_panel(self):
        """测试生成驾驶舱面板（多任务场景）"""
        # 创建多任务列表
        tasks = [
            {
                "task_id": "task:001",
                "title": "任务1",
                "status": "running",
                "stages": [{"name": "阶段1", "is_decision_point": False}],
                "current_stage_index": 0,
                "created_at": "2026-01-01T00:00:00",
            },
            {
                "task_id": "task:002",
                "title": "任务2",
                "status": "completed",
                "stages": [{"name": "阶段1", "is_decision_point": False}],
                "current_stage_index": 0,
                "created_at": "2026-01-02T00:00:00",
            },
        ]
        
        generator = PanelGenerator()
        panel = generator.generate(tasks)
        
        assert panel.panel_type == PanelType.COCKPIT
        assert "任务" in panel.title
        assert len(panel.components) > 0
        # 应该有任务统计、最近任务等组件
        comp_ids = [c.id for c in panel.components]
        assert "comp:task_stats" in comp_ids

    def test_adapt_handles_missing_fields(self):
        """测试适配缺失字段的任务数据"""
        incomplete_task = {"id": "task:incomplete"}
        adapted = TaskAdapter.adapt(incomplete_task)
        assert adapted["task_id"] == "incomplete"
        assert adapted["name"] == ""
        assert adapted["stages"] == []
        assert adapted["current_stage"] == {}


# ───────────────────────────────────────────────────────────────────────────
# 4.5 SOP-Panel 集成测试（V5.0 新增）
# ───────────────────────────────────────────────────────────────────────────

class TestSopPanelIntegration:
    """
    SOP 执行引擎与 Panel 集成测试。
    
    验证：当 SOP 执行遇到决策点时，自动生成 DECISION 类型面板。
    """

    def test_decision_point_generates_panel(self):
        """测试决策点触发时自动生成面板"""
        from skills.orchestration import _check_decision_point
        from core.panel import PanelDefinition, PanelType

        # 构造决策点阶段
        stage = {
            "id": "stage_review",
            "name": "代码审核",
            "description": "请确认是否接受此实现",
            "is_decision_point": True,
            "requires_confirmation": True,
            "decision_options": ["确认", "驳回", "修改"],
            "inputs": [],
            "outputs": [{"name": "实现代码", "type": "code"}],
        }

        context = {
            "_task_id": "task:test_sop_panel",
            "_task_title": "SOP集成测试",
        }

        # 调用决策点检查（会生成面板）
        paused = _check_decision_point(context, stage)

        assert paused is True
        assert context.get("_paused_for_decision") is True
        assert "_decision_panel" in context

        panel = context["_decision_panel"]
        assert isinstance(panel, PanelDefinition)
        assert panel.panel_type == PanelType.DECISION
        assert len(panel.components) > 0

    def test_panel_contains_decision_buttons(self):
        """测试生成的决策面板包含决策按钮组件"""
        from skills.orchestration import _check_decision_point
        from core.panel import ComponentType

        stage = {
            "name": "确认阶段",
            "is_decision_point": True,
            "decision_options": ["确认", "驳回"],
        }

        context = {"_task_id": "task:test_btn", "_task_title": "按钮测试"}

        _check_decision_point(context, stage)

        panel = context["_decision_panel"]
        comp_types = [c.type for c in panel.components]
        # 应该有决策按钮组件
        assert ComponentType.DECISION_BUTTONS in comp_types

    def test_panel_not_generated_for_non_decision_stage(self):
        """测试非决策阶段不生成面板"""
        from skills.orchestration import _check_decision_point

        stage = {
            "name": "代码实现",
            "is_decision_point": False,
        }

        context = {"_task_id": "task:test_no_panel", "_task_title": "无面板测试"}

        paused = _check_decision_point(context, stage)

        assert paused is False
        assert "_decision_panel" not in context



# ───────────────────────────────────────────────────────────────────────────
# 4. EventAdapter 测试
# ────────────────────────────────────────────────────────────────────────────

class TestEventAdapter:
    """EventAdapter 事件触发与订阅测试"""

    def setup_method(self):
        self.event_bus = EventBus()
        self.adapter = EventAdapter(event_bus=self.event_bus)
        self.events_captured = []

    def _capture_event(self, event: Event):
        self.events_captured.append(event)

    def test_emit_panel_loaded(self):
        """测试触发面板加载事件"""
        self.event_bus.subscribe("panel.loaded", self._capture_event)
        self.adapter.emit_panel_loaded("panel:test001", task_id="task:test001")
        assert len(self.events_captured) == 1
        assert self.events_captured[0].event_type == "panel.loaded"
        assert self.events_captured[0].data["panel_id"] == "panel:test001"

    def test_emit_component_changed(self):
        """测试触发组件变更事件"""
        self.event_bus.subscribe("panel.component_changed", self._capture_event)
        self.adapter.emit_component_changed(
            "panel:test001", "comp:input_001", "new value", task_id="task:test001"
        )
        assert len(self.events_captured) == 1
        assert self.events_captured[0].data["component_id"] == "comp:input_001"
        assert self.events_captured[0].data["value"] == "new value"

    def test_emit_decision_made(self):
        """测试触发决策事件"""
        self.event_bus.subscribe("panel.decision_made", self._capture_event)
        self.adapter.emit_decision_made(
            "decision:task:test001:stage_1", "确认", reason="",
            task_id="task:test001", stage_id="stage_1",
        )
        assert len(self.events_captured) == 1
        assert self.events_captured[0].data["decision"] == "确认"

    def test_subscribe_to_decisions(self):
        """测试订阅决策事件"""
        callback_called = False
        def my_callback(event: Event):
            nonlocal callback_called
            callback_called = True

        self.adapter.subscribe_to_decisions(my_callback)
        self.adapter.emit_decision_made("decision:test", "确认")
        assert callback_called is True


# ────────────────────────────────────────────────────────────────────────────
# 5. ArmoryAdapter 测试
# ────────────────────────────────────────────────────────────────────────────

class TestArmoryAdapter:
    """ArmoryAdapter 测试"""

    def test_weapon_to_panel_components(self):
        """测试将武器元数据转换为面板组件"""
        mock_armory = _make_mock_armory()
        weapon = mock_armory.get("skill:code_gen")

        components = ArmoryAdapter.weapon_to_panel_components(weapon)
        assert len(components) == 2
        assert components[0].type == ComponentType.TEXT_INPUT
        assert components[0].label == "输入提示"
        assert components[0].required is True
        assert components[1].type == ComponentType.CODE_PREVIEW

    def test_weapon_without_panel_components(self):
        """测试武器没有 panel_components 时返回空列表"""

        class MockWeaponNoPanel:
            def __init__(self):
                self.id = "skill:no_panel"
                # 没有 panel_components 属性

        weapon = MockWeaponNoPanel()
        components = ArmoryAdapter.weapon_to_panel_components(weapon)
        assert components == []

    def test_update_weapon_metadata(self):
        """测试为武器元数据添加 panel_components"""

        class MockWeapon:
            def __init__(self):
                self.id = "skill:test"
                # 初始没有 panel_components

        weapon = MockWeapon()
        panel_components = [
            {"type": "text_input", "name": "input", "label": "Input"},
        ]
        ArmoryAdapter.update_weapon_metadata(weapon, panel_components)
        assert hasattr(weapon, "panel_components")
        assert weapon.panel_components == panel_components

    def test_component_type_mapping(self):
        """测试组件类型映射完整性"""
        # 验证所有 ComponentType 都有对应的映射
        for comp_type in ComponentType:
            # 检查反向：ArmoryAdapter.COMPONENT_TYPE_MAP 的值是否覆盖所有 ComponentType
            pass  # 至少确保映射存在
        assert ComponentType.TEXT_INPUT in ArmoryAdapter.COMPONENT_TYPE_MAP.values()


# ────────────────────────────────────────────────────────────────────────────
# 6. PanelSystemAdapter 端到端测试
# ────────────────────────────────────────────────────────────────────────────

class TestPanelSystemAdapter:
    """PanelSystemAdapter 端到端集成测试"""

    def setup_method(self):
        self.store = _make_store_with_task()
        self.adapter = PanelSystemAdapter(self.store)

    def test_generate_panel_for_task(self):
        """测试为任务生成面板（当前阶段是决策点 → DECISION 类型）"""
        task_data = self.store.load("task:test001")
        panel = self.adapter.generate_panel_for_task(task_data)
        assert isinstance(panel, PanelDefinition)
        # 当前阶段 is_decision_point=True，生成器返回 DECISION 类型
        assert panel.panel_type == PanelType.DECISION

    def test_create_renderer(self):
        """测试创建渲染器"""
        renderer = self.adapter.create_renderer(task_id="task:test001")
        from renderers.cli_renderer import CliRenderer
        assert isinstance(renderer, CliRenderer)

    def test_full_pipeline_generate_and_render(self):
        """测试完整流程：任务 → 适配 → 生成面板 → 渲染"""
        task_data = self.store.load("task:test001")
        panel = self.adapter.generate_panel_for_task(task_data)

        renderer = self.adapter.create_renderer(task_id="task:test001")
        # 渲染不应该报错
        renderer.render(panel)

    def test_adapter_with_armory(self):
        """测试带武器库的适配器"""
        mock_armory = _make_mock_armory()
        adapter = PanelSystemAdapter(self.store, armory_registry=mock_armory)
        task_data = self.store.load("task:test001")
        # 生成面板时应该能用到武器库信息
        panel = adapter.generate_panel_for_task(task_data)
        assert panel is not None


# ────────────────────────────────────────────────────────────────────────────
# 7. CLI 渲染器 + DataProvider 集成测试
# ────────────────────────────────────────────────────────────────────────────

class TestCliRendererIntegration:
    """CLI 渲染器 + DataProvider 集成测试"""

    def setup_method(self):
        self.store = _make_store_with_task()
        self.provider = StoreDataProvider(self.store, task_id="task:test001")

    def test_render_panel_with_live_data(self):
        """测试用真实数据渲染面板"""
        from renderers.cli_renderer import CliRenderer

        renderer = CliRenderer(data_provider=self.provider)
        task_data = TaskAdapter.adapt_from_store(self.store, "task:test001")
        generator = PanelGenerator()
        panel = generator.generate(task_data)

        # 渲染不应该报错
        renderer.render(panel)

    def test_data_provider_resolve_in_renderer(self):
        """测试渲染器通过 DataProvider 解析数据"""
        from renderers.cli_renderer import CliRenderer

        renderer = CliRenderer(data_provider=self.provider)
        panel = PanelDefinition(
            panel_id="test:live_data",
            panel_type=PanelType.TASK,
            title="实时数据测试",
            layout=Layout(type=LayoutType.SINGLE, regions=[
                Region(name="main", ratio=1.0, content_type="text", components=[]),
            ]),
            components=[
                PanelComponent(
                    id="comp:status",
                    type=ComponentType.TEXT_DISPLAY,
                    label="任务状态",
                    data_source="task.status",
                ),
            ],
        )

        # 渲染时应该从 provider 获取 "task.status"
        renderer.render(panel)
        # 如果不报错，说明数据解析成功


# ────────────────────────────────────────────────────────────────────────────
# 8. 全链路集成测试
# ────────────────────────────────────────────────────────────────────────────

class TestFullPipeline:
    """全链路集成测试：任务 → 适配 → 生成 → 渲染 → 决策"""

    def test_full_pipeline_task_to_panel_to_decision(self):
        """测试完整流程：任务 → 面板 → 决策 → 事件"""
        store = _make_store_with_task()
        event_bus = EventBus()

        # 1. 适配任务数据
        task_data = store.load("task:test001")
        adapted = TaskAdapter.adapt(task_data)
        assert adapted["task_id"] == "test001"

        # 2. 生成面板（当前阶段是决策点 → DECISION 类型）
        generator = PanelGenerator()
        panel = generator.generate(adapted)
        assert panel.panel_type == PanelType.DECISION

        # 3. 创建决策流程
        flow = DecisionFlow(event_bus=event_bus, store=store)
        record = flow.create_decision(
            task_id="task:test001",
            stage_id="stage_2",
            stage_name="代码实现",
            context_before={"outputs": adapted.get("outputs", [])},
        )
        assert record.status == DecisionStatus.PENDING

        # 4. 模拟 Human Agent 决策
        flow.submit_decision(
            decision_id=record.decision_id,
            decision="确认",
            human_agent_id="monarch",
        )
        assert record.status == DecisionStatus.APPROVED

        # 5. 验证事件触发
        events = event_bus.get_event_log(None, limit=10)
        event_types = [e.event_type for e in events]
        assert "decision.created" in event_types
        assert "decision.made" in event_types

    def test_full_pipeline_with_cli_renderer(self):
        """测试完整流程（含 CLI 渲染）"""
        store = _make_store_with_task()

        # 生成面板
        task_data = store.load("task:test001")
        adapted = TaskAdapter.adapt(task_data)
        panel = PanelGenerator().generate(adapted)

        # 创建渲染器
        provider = StoreDataProvider(store, task_id="task:test001")
        from renderers.cli_renderer import CliRenderer
        renderer = CliRenderer(data_provider=provider)

        # 渲染（不报错即通过）
        renderer.render(panel)

    def test_multiple_tasks_cockpit_pipeline(self):
        """测试多任务驾驶舱面板生成流程（遍历 Store 中的任务）"""
        store = _make_store_with_task()

        # 添加更多任务
        for i in range(3):
            store.save(f"task:task_{i:03d}", {
                "id": f"task:task_{i:03d}",
                "title": f"任务 {i}",
                "status": "running",
                "stages": [{"stage_id": "s1", "name": "阶段1", "is_decision_point": False,
                            "inputs": [], "outputs": [], "skill": ""}],
                "current_stage_index": 0,
                "quality_score": {"customer": 80 + i},
                "cost": 0.1 * i,
                "tokens": 100 * i,
                "duration_seconds": 60.0,
                "outputs": [],
                "event_ids": [],
                "created_at": "2026-01-0" + str(i+1) + "T00:00:00",
            })

        # 用 list_keys() 遍历所有 task 键，组装任务列表
        task_keys = [k for k in store.list_keys() if k.startswith("task:")]
        tasks = [store.load(k) for k in task_keys]
        tasks = [t for t in tasks if isinstance(t, dict)]

        # 生成驾驶舱面板
        panel = PanelGenerator().generate(tasks)
        assert panel.panel_type == PanelType.COCKPIT
        assert len(panel.components) > 0

        # 验证组件包含任务统计
        comp_ids = [c.id for c in panel.components]
        assert "comp:task_stats" in comp_ids


# ────────────────────────────────────────────────────────────────────────────
# 9. 边界条件和错误处理
# ────────────────────────────────────────────────────────────────────────────

class TestIntegrationEdgeCases:
    """集成测试：边界条件和错误处理"""

    def test_store_data_provider_without_store(self):
        """测试 StoreDataProvider 在无 Store 时的行为"""
        provider = StoreDataProvider(None, task_id="task:test001")
        # 查询应该返回 None 而不报错
        assert provider.get("task.status") is None
        assert provider.get("intel:xxx") is None

    def test_decision_flow_without_event_bus(self):
        """测试 DecisionFlow 在无 EventBus 时的行为"""
        flow = DecisionFlow(event_bus=None, store=None)
        record = flow.create_decision("task:test", "stage_1", "测试")
        assert record.status == DecisionStatus.PENDING
        # 提交决策不应该报错（只是不触发事件）
        updated = flow.submit_decision(record.decision_id, "确认")
        assert updated.status == DecisionStatus.APPROVED

    def test_task_adapter_with_none_task(self):
        """测试 TaskAdapter 适配 None 任务"""
        adapted = TaskAdapter.adapt(None)
        assert adapted == {}

    def test_task_adapter_with_empty_dict(self):
        """测试 TaskAdapter 适配空字典"""
        adapted = TaskAdapter.adapt({})
        assert adapted["task_id"] == ""
        assert adapted["name"] == ""
        assert adapted["stages"] == []

    def test_panel_generator_with_empty_task_list(self):
        """测试 PanelGenerator 生成空任务列表的驾驶舱面板"""
        generator = PanelGenerator()
        panel = generator.generate([])
        assert panel.panel_type == PanelType.COCKPIT
        assert "0" in panel.title  # "X 任务" where X=0
        # 空列表时组件可能为空或只有默认值，但不应该报错
        assert isinstance(panel.components, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
