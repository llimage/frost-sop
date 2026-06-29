"""
FROST V5.0 CLI 渲染引擎测试

测试目标：renderers/cli_renderer.py 中的 CliRenderer
"""
import pytest
from io import StringIO
from contextlib import redirect_stdout

from core.panel import (
    PanelDefinition, PanelType, ComponentType, PanelComponent, LayoutType, Theme
)
from renderers.cli_renderer import CliRenderer, CliDataProvider


class TestCliDataProvider:
    """测试 CliDataProvider"""

    def test_get_existing_key(self):
        """测试获取已存在的数据"""
        provider = CliDataProvider(data={"task.status": "running"})
        result = provider.get("task.status")
        assert result == "running"

    def test_get_missing_key(self):
        """测试获取不存在的数据"""
        provider = CliDataProvider(data={})
        result = provider.get("task.status")
        assert result is None


class TestCliRenderer:
    """测试 CliRenderer"""

    def test_render_simple_panel(self):
        """测试渲染简单面板（不崩溃）"""
        panel = PanelDefinition(
            panel_id="panel:test",
            panel_type=PanelType.TASK,
            title="测试面板",
        )

        renderer = CliRenderer()
        # 捕获输出（不实际打印到终端）
        f = StringIO()
        with redirect_stdout(f):
            renderer.render(panel)
        output = f.getvalue()

        assert "测试面板" in output

    def test_render_component_text_display(self):
        """测试渲染文本展示组件"""
        component = PanelComponent(
            id="comp:test",
            type=ComponentType.TEXT_DISPLAY,
            label="测试标签",
        )

        renderer = CliRenderer()
        f = StringIO()
        with redirect_stdout(f):
            renderer.render_component(component, "测试数据")
        output = f.getvalue()

        assert "测试标签" in output
        assert "测试数据" in output

    def test_render_component_health_gauge(self):
        """测试渲染健康度仪表盘"""
        component = PanelComponent(
            id="comp:health",
            type=ComponentType.HEALTH_GAUGE,
            label="健康度",
        )
        data = {"财务": 85, "运营": 72, "治理": 90, "客户": 68}

        renderer = CliRenderer()
        f = StringIO()
        with redirect_stdout(f):
            renderer.render_component(component, data)
        output = f.getvalue()

        assert "健康度" in output
        assert "财务" in output

    def test_render_component_progress_bar(self):
        """测试渲染进度条"""
        component = PanelComponent(
            id="comp:progress",
            type=ComponentType.PROGRESS_BAR,
            label="进度",
        )

        renderer = CliRenderer()
        f = StringIO()
        with redirect_stdout(f):
            renderer.render_component(component, 50)  # 50% 进度
        output = f.getvalue()

        assert "进度" in output

    def test_empty_data_no_crash(self):
        """测试空数据时不会崩溃"""
        component = PanelComponent(
            id="comp:test",
            type=ComponentType.TEXT_DISPLAY,
        )

        renderer = CliRenderer()
        f = StringIO()
        with redirect_stdout(f):
            renderer.render_component(component, None)  # 空数据
        output = f.getvalue()

        assert "无数据" in output  # 应该显示"（无数据）"

    def test_render_with_data_provider(self):
        """测试使用数据提供者渲染"""
        panel = PanelDefinition(
            panel_id="panel:test",
            panel_type=PanelType.TASK,
            title="数据提供测试",
            components=[
                PanelComponent(
                    id="comp:status",
                    type=ComponentType.TEXT_DISPLAY,
                    data_source="task.status",
                )
            ]
        )

        provider = CliDataProvider(data={"task.status": "running"})
        renderer = CliRenderer(data_provider=provider)

        f = StringIO()
        with redirect_stdout(f):
            renderer.render(panel)
        output = f.getvalue()

        assert "running" in output


class TestCliRendererIntegration:
    """集成测试：完整流程"""

    def test_generate_and_render(self):
        """测试从任务生成面板并渲染（完整流程）"""
        from core.panel_generator import generate_panel

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

        # 1. 生成面板
        panel = generate_panel(task)

        assert panel is not None
        assert panel.panel_type.value == "task"

        # 2. 渲染面板
        renderer = CliRenderer()
        f = StringIO()
        with redirect_stdout(f):
            renderer.render(panel)
        output = f.getvalue()

        assert "任务:" in output
        assert len(output) > 0  # 有输出
