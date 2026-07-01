"""
FROST V5.0 面板生成器测试

测试目标：core/panel_generator.py 中的 PanelGenerator
"""

from core.panel import ComponentType, LayoutType, PanelDefinition, PanelType
from core.panel_generator import PanelGenerator, generate_panel


class TestPanelGenerator:
    """测试 PanelGenerator"""

    def test_generate_task_panel(self):
        """测试从简单任务生成 TASK 面板"""
        task = {
            "task_id": "auth_001",
            "name": "Add user authentication",
            "status": "running",
            "current_stage_index": 0,
            "current_stage": {
                "name": "需求分析",
                "is_decision_point": False,
                "inputs": [{"label": "需求描述", "required": True}],
                "outputs": [{"name": "需求文档", "type": "document"}],
            },
        }

        generator = PanelGenerator()
        panel = generator.generate(task)

        assert isinstance(panel, PanelDefinition)
        assert panel.panel_type == PanelType.TASK
        assert "任务:" in panel.title
        assert panel.layout.type == LayoutType.SINGLE
        assert len(panel.components) > 0  # 至少有状态栏

    def test_generate_decision_panel(self):
        """测试从决策任务生成 DECISION 面板"""
        task = {
            "task_id": "review_001",
            "name": "Code review",
            "status": "waiting",
            "current_stage_index": 1,
            "current_stage": {
                "name": "质量审核",
                "is_decision_point": True,
                "outputs": [{"name": "代码", "type": "code"}],
            },
        }

        generator = PanelGenerator()
        panel = generator.generate(task)

        assert panel.panel_type == PanelType.DECISION
        assert panel.layout.type == LayoutType.SPLIT  # 决策面板使用分栏布局

    def test_generate_cockpit_panel(self):
        """测试生成驾驶舱面板"""
        task = {
            "task_id": "monitor_001",
            "name": "Family monitor",
            "status": "running",
        }

        generator = PanelGenerator()
        panel = generator.generate(task)
        panel.panel_type = PanelType.COCKPIT  # 手动设置为驾驶舱类型
        panel.layout = generator._generate_layout(PanelType.COCKPIT, task)

        assert panel.layout.type == LayoutType.TABS  # 驾驶舱使用标签页布局

    def test_layout_generation_single(self):
        """测试 SINGLE 布局生成"""
        generator = PanelGenerator()
        layout = generator._generate_layout(PanelType.TASK, {})

        assert layout.type == LayoutType.SINGLE
        assert len(layout.regions) == 3  # status, content, actions

    def test_layout_generation_split(self):
        """测试 SPLIT 布局生成"""
        generator = PanelGenerator()
        layout = generator._generate_layout(PanelType.DECISION, {})

        assert layout.type == LayoutType.SPLIT
        assert len(layout.regions) == 2
        assert layout.regions[0].ratio == 0.7
        assert layout.regions[1].ratio == 0.3

    def test_layout_generation_tabs(self):
        """测试 TABS 布局生成"""
        generator = PanelGenerator()
        layout = generator._generate_layout(PanelType.COCKPIT, {})

        assert layout.type == LayoutType.TABS
        assert len(layout.regions) == 4

    def test_component_generation_status_bar(self):
        """测试状态栏组件生成"""
        generator = PanelGenerator()
        task = {"task_id": "test", "status": "running"}

        comp = generator._create_status_bar(task)

        assert comp.id == "comp:status_bar"
        assert comp.type == ComponentType.STATUS_BAR
        assert comp.data_source == "task.status"

    def test_component_generation_decision(self):
        """测试决策组件生成"""
        generator = PanelGenerator()
        task = {
            "current_stage": {
                "outputs": [{"name": "代码", "type": "code"}],
                "decision_options": ["确认", "驳回"],
            }
        }

        components = generator._create_decision_components(task)

        # 应该有：输出展示 + 决策按钮
        assert len(components) >= 2
        # 检查是否有决策按钮
        decision_comps = [c for c in components if c.type == ComponentType.DECISION_BUTTONS]
        assert len(decision_comps) == 1

    def test_theme_generation_default(self):
        """测试默认主题生成"""
        generator = PanelGenerator()
        task = {"task_id": "test", "status": "running"}

        theme = generator._generate_theme(task)

        assert theme.name == "default"
        assert theme.primary_color == "#2c3e50"  # 默认主色

    def test_theme_generation_critical(self):
        """测试告警任务主题（红色）"""
        generator = PanelGenerator()
        task = {"task_id": "test", "status": "running", "priority": "critical"}

        theme = generator._generate_theme(task)

        assert theme.primary_color == "#e74c3c"  # 告警红色

    def test_generate_panel_function(self):
        """测试便捷函数 generate_panel"""
        task = {
            "task_id": "test_001",
            "name": "Test task",
            "status": "created",
        }

        panel = generate_panel(task)

        assert isinstance(panel, PanelDefinition)
        assert panel.task_id == "test_001"


class TestPanelGeneratorEdgeCases:
    """测试边界情况"""

    def test_generate_with_sop_none(self):
        """测试 sop=None 的情况"""
        task = {
            "task_id": "test",
            "status": "created",
        }

        generator = PanelGenerator()
        panel = generator.generate(task, sop=None)  # sop=None 应该不报错

        assert panel is not None

    def test_generate_with_empty_task(self):
        """测试空任务字典"""
        task = {}

        generator = PanelGenerator()
        panel = generator.generate(task)

        assert isinstance(panel, PanelDefinition)

    def test_panel_id_format(self):
        """测试 panel_id 格式"""
        task = {"task_id": "auth_001", "status": "running"}

        generator = PanelGenerator()
        panel = generator.generate(task)

        assert panel.panel_id.startswith("panel:")
        assert "auth_001" in panel.panel_id
