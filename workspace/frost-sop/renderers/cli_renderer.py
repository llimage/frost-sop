"""
FROST V5.0 CLI 渲染引擎——在终端渲染面板。

依赖: rich (pip install rich)

修正说明：
- 规格中的 Table.grid() 不是有效API，已修正为 Table.add_row()
- 决策按钮在CLI中渲染为选项列表+input提示
- 所有rich用法已按v13.0+正确实现
"""

from typing import Any, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel as RichPanel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.tree import Tree

from core.panel import PanelDefinition, PanelComponent, ComponentType, PanelState
from core.panel_renderer import PanelRenderer


class CliDataProvider:
    """CLI 数据提供者——从内存字典获取数据"""
    
    def __init__(self, data: dict = None):
        self.data = data or {}
    
    def get(self, data_source: str, data_binding: str = "") -> Any:
        """获取数据——简单实现：从字典中查找"""
        if data_source in self.data:
            return self.data[data_source]
        return None


class CliRenderer(PanelRenderer):
    """CLI 渲染引擎——使用 Rich 库在终端渲染面板"""
    
    def __init__(self, data_provider=None, console: Console = None):
        super().__init__(data_provider)
        self.console = console or Console()
    
    def render(self, panel: PanelDefinition, state: Optional[PanelState] = None) -> None:
        """渲染面板到终端"""
        # 1. 渲染标题
        self._render_header(panel)
        
        # 2. 渲染组件
        for component in panel.components:
            data = self.get_component_data(component)
            self.render_component(component, data)
            self.console.print()  # 空行分隔
        
        # 3. 渲染底部
        self._render_footer(panel)
    
    def _render_header(self, panel: PanelDefinition):
        """渲染面板标题"""
        title = f"[bold]{panel.title}[/bold]"
        if panel.subtitle:
            title += f"\n[dim]{panel.subtitle}[/dim]"
        
        self.console.print(RichPanel(title, border_style=panel.theme.primary_color))
    
    def _render_footer(self, panel: PanelDefinition):
        """渲染面板底部"""
        self.console.print(f"[dim]面板 ID: {panel.panel_id} | 版本: {panel.version}[/dim]")
    
    def render_component(self, component: PanelComponent, data: Any = None) -> None:
        """渲染单个组件"""
        self._render_component_by_type(component, data)
    
    # ── 各组件渲染实现 ─────────────────────────────────────────────
    
    def _render_status_bar(self, component: PanelComponent, data: Any) -> None:
        """渲染状态栏"""
        if isinstance(data, dict):
            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            cost = data.get("cost", 0)
            
            # 使用 Table 代替不存在的 Table.grid()
            grid = Table(box=box.SIMPLE)
            grid.add_column("状态", style="bold")
            grid.add_column("进度", style="bold")
            grid.add_column("成本", style="bold")
            grid.add_row(status, f"{progress}%", f"¥{cost:.2f}")
            self.console.print(RichPanel(grid, title="[bold]状态栏[/bold]"))
        else:
            self.console.print(f"[dim]状态: {data or 'unknown'}[/dim]")
    
    def _render_text_input(self, component: PanelComponent, data: Any) -> None:
        """渲染文本输入"""
        label = component.label or "输入"
        value = data or ""
        required = "[red]*[/red]" if component.required else ""
        
        self.console.print(f"[bold]{label}{required}[/bold]")
        self.console.print(f"[dim]当前值: {value}[/dim]")
        self.console.print("[yellow]请输入（按 Enter 确认）:[/yellow] ", end="")
    
    def _render_textarea(self, component: PanelComponent, data: Any) -> None:
        """渲染多行文本输入"""
        label = component.label or "多行输入"
        value = data or ""
        
        self.console.print(f"[bold]{label}[/bold]")
        self.console.print(f"[dim]当前值:[/dim]")
        self.console.print(f"[italic]{value}[/italic]")
        self.console.print("[yellow]请输入多行文本（输入空行结束）:[/yellow]")
    
    def _render_code_editor(self, component: PanelComponent, data: Any) -> None:
        """渲染代码编辑器"""
        label = component.label or "代码"
        language = component.properties.get("language", "python")
        value = data or ""
        
        self.console.print(f"[bold]{label}[/bold] [dim]({language})[/dim]")
        self.console.print(f"[dim]当前值:[/dim]")
        # 使用 Rich 的语法高亮
        if len(str(value)) < 500:
            from rich.syntax import Syntax
            syntax = Syntax(str(value), language, theme="monokai")
            self.console.print(syntax)
        else:
            self.console.print(f"[italic]{str(value)[:200]}...[/italic]")
    
    def _render_code_preview(self, component: PanelComponent, data: Any) -> None:
        """渲染代码预览"""
        self._render_code_editor(component, data)
    
    def _render_text_display(self, component: PanelComponent, data: Any) -> None:
        """渲染文本展示"""
        label = component.label
        if label:
            self.console.print(f"[bold]{label}[/bold]")
        self.console.print(str(data) if data else "[dim]（无数据）[/dim]")
    
    def _render_markdown(self, component: PanelComponent, data: Any) -> None:
        """渲染 Markdown"""
        label = component.label
        if label:
            self.console.print(f"[bold]{label}[/bold]")
        
        from rich.markdown import Markdown
        if data:
            self.console.print(Markdown(str(data)))
        else:
            self.console.print("[dim]（无数据）[/dim]")
    
    def _render_table(self, component: PanelComponent, data: Any) -> None:
        """渲染表格"""
        label = component.label
        columns = component.properties.get("columns", [])
        
        table = Table(title=label, box=box.ROUNDED)
        for col in columns:
            table.add_column(col)
        
        if isinstance(data, list):
            for row in data:
                if isinstance(row, list):
                    table.add_row(*[str(c) for c in row])
                elif isinstance(row, dict):
                    table.add_row(*[str(row.get(c, "")) for c in columns])
        
        self.console.print(table)
    
    def _render_chart(self, component: PanelComponent, data: Any) -> None:
        """渲染图表（CLI 中使用 ASCII 图表）"""
        label = component.label
        chart_type = component.properties.get("chart_type", "bar")
        
        self.console.print(f"[bold]{label}[/bold] [dim]({chart_type} 图表)[/dim]")
        
        if isinstance(data, list) and len(data) > 0:
            max_val = max(data) if all(isinstance(x, (int, float)) for x in data) else 10
            for i, val in enumerate(data):
                bar = "█" * int((val / max_val) * 30) if max_val > 0 else ""
                self.console.print(f"  {i:3d} | {bar} {val}")
        else:
            self.console.print("[dim]（无图表数据）[/dim]")
    
    def _render_decision_buttons(self, component: PanelComponent, data: Any) -> None:
        """渲染决策按钮——CLI中渲染为选项列表"""
        label = component.label or "决策"
        options = component.properties.get("options", ["确认", "驳回", "修改"])
        
        self.console.print(f"[bold]{label}[/bold]")
        self.console.print("[yellow]请选择决策:[/yellow]")
        
        for i, option in enumerate(options):
            self.console.print(f"  [{i+1}] {option}")
        
        self.console.print("[yellow]输入选项编号（1-{}）:[/yellow] ".format(len(options)), end="")
    
    def _render_progress_bar(self, component: PanelComponent, data: Any) -> None:
        """渲染进度条"""
        label = component.label or "进度"
        progress = data if isinstance(data, (int, float)) else 0
        
        with Progress(
            TextColumn(f"[bold]{label}[/bold]"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            console=self.console,
        ) as p:
            p.add_task(label, total=100, completed=progress)
    
    def _render_health_gauge(self, component: PanelComponent, data: Any) -> None:
        """渲染健康度仪表盘——使用ASCII字符兼容Windows"""
        label = component.label or "健康度"
        
        if isinstance(data, dict):
            self.console.print(f"[bold]{label}[/bold]")
            for dim, score in data.items():
                # 使用 # 和 . 代替 █ 和 ░
                bar_len = int(score / 5)  # 0-20
                bar = "#" * bar_len + "." * (20 - bar_len)
                color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
                self.console.print(f"  {dim:10s} | [{color}]{bar}[/{color}] {score}")
        else:
            self.console.print(f"[bold]{label}[/bold]: {data or 0}")
    
    def _render_alert_banner(self, component: PanelComponent, data: Any) -> None:
        """渲染告警横幅——使用ASCII字符兼容Windows"""
        label = component.label or "告警"
        
        if isinstance(data, list):
            for alert in data:
                level = alert.get("level", "info")
                message = alert.get("message", "")
                # 使用 [!] 代替 ⚠️
                marker = {"critical": "[XXX]", "high": "[!!]", "medium": "[!]", "low": "[i]"}.get(level, "[?]")
                color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "green"}.get(level, "white")
                self.console.print(f"[{color}]{marker} [{level.upper()}] {message}[/{color}]")
        else:
            self.console.print(f"[yellow][!] {label}: {data}[/yellow]")
    
    def _render_collapsible_card(self, component: PanelComponent, data: Any) -> None:
        """渲染可折叠卡片——使用ASCII字符兼容Windows"""
        label = component.label or "卡片"
        expand = component.properties.get("expand_by_default", False)
        
        if expand:
            self.console.print(f"[bold][-] {label}[/bold]")
            self.console.print(str(data) if data else "[dim]（无内容）[/dim]")
        else:
            self.console.print(f"[bold][+] {label}[/bold] [dim](点击展开)[/dim]")
    
    def _render_task_list(self, component: PanelComponent, data: Any) -> None:
        """渲染任务列表"""
        label = component.label or "任务列表"
        columns = component.properties.get("columns", ["任务名称", "状态"])
        
        table = Table(title=label, box=box.ROUNDED)
        for col in columns:
            table.add_column(col)
        
        if isinstance(data, list):
            for task in data:
                if isinstance(task, dict):
                    table.add_row(*[str(task.get(c, "")) for c in columns])
        
        self.console.print(table)
    
    def _render_timeline(self, component: PanelComponent, data: Any) -> None:
        """渲染时间线"""
        label = component.label or "时间线"
        
        self.console.print(f"[bold]{label}[/bold]")
        
        if isinstance(data, list):
            tree = Tree("[bold]家族历史[/bold]")
            for item in data:
                if isinstance(item, dict):
                    ts = item.get("timestamp", "")
                    desc = item.get("description", "")
                    tree.add(f"[dim]{ts}[/dim] {desc}")
            self.console.print(tree)
        else:
            self.console.print("[dim]（无时间线数据）[/dim]")
