"""
FROST V5.0 Panel 核心数据类测试

测试目标：core/panel.py 中的所有数据类
"""

from datetime import datetime

from core.panel import (
    ComponentType,
    Layout,
    LayoutType,
    PanelComponent,
    PanelDefinition,
    PanelSnapshot,
    PanelState,
    PanelType,
    Region,
    Theme,
)


class TestPanelType:
    """测试 PanelType 枚举"""

    def test_cockpit_value(self):
        assert PanelType.COCKPIT.value == "cockpit"

    def test_task_value(self):
        assert PanelType.TASK.value == "task"

    def test_all_types_have_values(self):
        for pt in PanelType:
            assert pt.value is not None
            assert isinstance(pt.value, str)


class TestLayoutType:
    """测试 LayoutType 枚举"""

    def test_single_value(self):
        assert LayoutType.SINGLE.value == "single"

    def test_all_types_have_values(self):
        for lt in LayoutType:
            assert lt.value is not None


class TestRegion:
    """测试 Region 数据类"""

    def test_default_creation(self):
        r = Region(name="content")
        assert r.name == "content"
        assert r.ratio == 1.0
        assert r.content_type == ""
        assert r.components == []

    def test_custom_creation(self):
        r = Region(
            name="input",
            ratio=0.7,
            content_type="stage_input",
            components=["comp:input_1", "comp:input_2"],
        )
        assert r.ratio == 0.7
        assert len(r.components) == 2


class TestLayout:
    """测试 Layout 数据类"""

    def test_default_creation(self):
        layout = Layout()
        assert layout.type == LayoutType.SINGLE
        assert layout.regions == []

    def test_with_regions(self):
        layout = Layout(
            type=LayoutType.SPLIT,
            regions=[
                Region(name="left", ratio=0.7),
                Region(name="right", ratio=0.3),
            ],
        )
        assert len(layout.regions) == 2
        assert layout.regions[0].ratio == 0.7


class TestTheme:
    """测试 Theme 数据类"""

    def test_default_creation(self):
        theme = Theme()
        assert theme.name == "default"
        assert theme.primary_color == "#2c3e50"
        assert theme.dark_mode == {}

    def test_custom_theme(self):
        theme = Theme(name="dark", primary_color="#e74c3c", dark_mode={"background": "#0F172A"})
        assert theme.primary_color == "#e74c3c"
        assert theme.dark_mode["background"] == "#0F172A"


class TestPanelComponent:
    """测试 PanelComponent 数据类"""

    def test_minimal_creation(self):
        comp = PanelComponent(id="comp:test", type=ComponentType.TEXT_INPUT)
        assert comp.id == "comp:test"
        assert comp.type == ComponentType.TEXT_INPUT
        assert comp.label == ""
        assert comp.editable == False
        assert comp.properties == {}

    def test_full_creation(self):
        comp = PanelComponent(
            id="comp:code",
            type=ComponentType.CODE_EDITOR,
            label="代码编辑器",
            data_source="task.code",
            editable=True,
            properties={"language": "python", "theme": "dark"},
        )
        assert comp.label == "代码编辑器"
        assert comp.properties["language"] == "python"

    def test_properties_extensibility(self):
        """测试 properties 字段的扩展性"""
        comp = PanelComponent(
            id="comp:custom",
            type=ComponentType.TEXT_DISPLAY,
            properties={
                "custom_field_1": "value1",
                "custom_field_2": 42,
                "custom_field_3": {"nested": "data"},
            },
        )
        assert len(comp.properties) == 3


class TestPanelDefinition:
    """测试 PanelDefinition 核心数据类"""

    def test_minimal_creation(self):
        panel = PanelDefinition(panel_id="panel:test_001", panel_type=PanelType.TASK)
        assert panel.panel_id == "panel:test_001"
        assert panel.panel_type == PanelType.TASK
        assert panel.title == ""
        assert panel.components == []
        assert panel.version == "1.0"

    def test_full_creation(self):
        panel = PanelDefinition(
            panel_id="panel:cockpit_001",
            panel_type=PanelType.COCKPIT,
            title="家族驾驶舱",
            subtitle="概览页面",
            task_id="task:auth_001",
            layout=Layout(type=LayoutType.TABS),
            components=[
                PanelComponent(id="comp:health", type=ComponentType.HEALTH_GAUGE),
                PanelComponent(id="comp:tasks", type=ComponentType.TASK_LIST),
            ],
            theme=Theme(primary_color="#3498db"),
            actions={"on_load": "emit:panel_loaded"},
        )
        assert panel.title == "家族驾驶舱"
        assert len(panel.components) == 2
        assert panel.theme.primary_color == "#3498db"

    def test_to_dict(self):
        """测试序列化为字典"""
        panel = PanelDefinition(panel_id="panel:test", panel_type=PanelType.TASK, title="测试面板")
        d = panel.to_dict()
        assert isinstance(d, dict)
        assert d["panel_id"] == "panel:test"
        assert d["panel_type"] == PanelType.TASK  # dataclasses.asdict 会保留枚举

    def test_from_dict(self):
        """测试从字典反序列化"""
        data = {
            "panel_id": "panel:test",
            "panel_type": PanelType.TASK,
            "title": "测试面板",
        }
        panel = PanelDefinition.from_dict(data)
        assert panel.panel_id == "panel:test"
        assert panel.title == "测试面板"


class TestPanelState:
    """测试 PanelState 运行时状态"""

    def test_default_creation(self):
        state = PanelState(panel_id="panel:test")
        assert state.panel_id == "panel:test"
        assert state.values == {}
        assert state.expanded == {}
        assert state.interaction_log == []

    def test_value_recording(self):
        state = PanelState(panel_id="panel:test")
        state.values["comp:input_1"] = "用户输入"
        state.values["comp:rating"] = 4
        assert len(state.values) == 2

    def test_interaction_log(self):
        state = PanelState(panel_id="panel:test")
        state.interaction_log.append(
            {
                "timestamp": "2026-06-28T10:00:00",
                "component_id": "comp:btn_approve",
                "action": "click",
                "value": "确认",
            }
        )
        assert len(state.interaction_log) == 1
        assert state.interaction_log[0]["action"] == "click"


class TestPanelSnapshot:
    """测试 PanelSnapshot 历史记录"""

    def test_creation(self):
        panel = PanelDefinition(panel_id="panel:test", panel_type=PanelType.TASK)
        state = PanelState(panel_id="panel:test")
        snapshot = PanelSnapshot(
            snapshot_id="snap:001",
            panel_id="panel:test",
            task_id="task:001",
            panel_definition=panel,
            panel_state=state,
            task_status="completed",
            captured_at=datetime.now().isoformat(),
        )
        assert snapshot.snapshot_id == "snap:001"
        assert snapshot.task_status == "completed"
