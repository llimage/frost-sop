"""
FROST V5.0 面板渲染引擎基类

PHILOSOPHY: 渲染引擎与面板定义解耦。同一份PanelDefinition可在不同引擎上渲染。
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from core.panel import PanelDefinition, PanelComponent, ComponentType, PanelState


class PanelRenderer(ABC):
    """
    面板渲染引擎基类。
    
    所有渲染引擎（CLI、Streamlit、Web）必须继承此类并实现抽象方法。
    """
    
    def __init__(self, data_provider=None):
        """
        Args:
            data_provider: 数据提供者——负责根据 data_source 获取实际数据
        """
        self.data_provider = data_provider
    
    # ── 渲染入口 ──────────────────────────────────────────────────────────
    
    @abstractmethod
    def render(self, panel: PanelDefinition, state: Optional[PanelState] = None) -> Any:
        """
        渲染面板。
        
        Args:
            panel: 面板定义
            state: 面板状态（可选，用于恢复交互状态）
        
        Returns:
            渲染结果（类型取决于渲染引擎）
        """
        pass
    
    @abstractmethod
    def render_component(self, component: PanelComponent, data: Any = None) -> Any:
        """
        渲染单个组件。
        
        Args:
            component: 组件定义
            data: 组件数据（已由数据提供者获取）
        
        Returns:
            渲染结果
        """
        pass
    
    # ── 数据获取 ──────────────────────────────────────────────────────────
    
    def get_component_data(self, component: PanelComponent) -> Any:
        """
        根据组件的 data_source 获取实际数据。
        
        Args:
            component: 组件定义
        
        Returns:
            实际数据
        """
        if not self.data_provider:
            return None
        
        data_source = component.data_source
        if not data_source:
            return None
        
        return self.data_provider.get(data_source, component.data_binding)
    
    # ── 组件分发 ──────────────────────────────────────────────────────────
    
    def _render_component_by_type(self, component: PanelComponent, data: Any) -> Any:
        """根据组件类型分发到具体渲染方法"""
        render_methods = {
            ComponentType.STATUS_BAR: self._render_status_bar,
            ComponentType.TEXT_INPUT: self._render_text_input,
            ComponentType.TEXTAREA: self._render_textarea,
            ComponentType.CODE_EDITOR: self._render_code_editor,
            ComponentType.CODE_PREVIEW: self._render_code_preview,
            ComponentType.TEXT_DISPLAY: self._render_text_display,
            ComponentType.MARKDOWN: self._render_markdown,
            ComponentType.TABLE: self._render_table,
            ComponentType.CHART: self._render_chart,
            ComponentType.DECISION_BUTTONS: self._render_decision_buttons,
            ComponentType.PROGRESS_BAR: self._render_progress_bar,
            ComponentType.HEALTH_GAUGE: self._render_health_gauge,
            ComponentType.ALERT_BANNER: self._render_alert_banner,
            ComponentType.COLLAPSIBLE_CARD: self._render_collapsible_card,
            ComponentType.TASK_LIST: self._render_task_list,
            ComponentType.TIMELINE: self._render_timeline,
        }
        
        method = render_methods.get(component.type)
        if method:
            return method(component, data)
        
        # 默认渲染：文本展示
        return self._render_text_display(component, data)
    
    # ── 各类型组件的抽象渲染方法 ──────────────────────────────────────────
    
    @abstractmethod
    def _render_status_bar(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_text_input(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_textarea(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_code_editor(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_code_preview(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_text_display(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_markdown(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_table(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_chart(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_decision_buttons(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_progress_bar(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_health_gauge(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_alert_banner(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_collapsible_card(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_task_list(self, component: PanelComponent, data: Any) -> Any:
        pass
    
    @abstractmethod
    def _render_timeline(self, component: PanelComponent, data: Any) -> Any:
        pass


# ────────────────────────────────────────────────────────────────────────────
# 数据提供者接口
# ────────────────────────────────────────────────────────────────────────────

class DataProvider(ABC):
    """
    数据提供者——负责根据 data_source 获取实际数据。
    
    渲染引擎不直接访问后端，而是通过数据提供者获取数据。
    这允许在不同环境中使用不同的数据提供者（Mock、API、Store等）。
    """
    
    @abstractmethod
    def get(self, data_source: str, data_binding: str = "") -> Any:
        """
        获取数据。
        
        Args:
            data_source: 数据源标识（如 "task.status", "intel:strategist_brief"）
            data_binding: 数据绑定路径（如 "stages[0].output"）
        
        Returns:
            实际数据
        """
        pass
