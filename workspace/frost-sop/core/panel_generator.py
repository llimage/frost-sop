"""
FROST V5.0 面板生成器——从 SOP/任务/武器自动生成面板。

PHILOSOPHY: 面板不是手动写的，面板是从SOP和任务自动生成的。
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from core.panel import (
    PanelDefinition, PanelType, Layout, LayoutType, Region,
    PanelComponent, ComponentType, Theme, PanelState
)
from core.sop import SOP


class PanelGenerator:
    """
    面板生成器——根据任务和SOP自动生成面板定义。
    
    生成逻辑：
    1. 分析SOP阶段类型 → 确定面板类型
    2. 分析当前阶段输入/输出 → 生成输入/输出组件
    3. 检查是否有决策点 → 生成决策组件
    4. 检查是否需要简报 → 生成简报组件
    5. 分析布局需求 → 生成布局
    
    扩展（V5.0+）：
    - generate() 支持传入任务列表 → 自动生成 COCKPIT 类型面板
    - 需要 store 参数来支持家族级数据源（family:*, intel:*, immune:*）
    """
    
    def __init__(self, armory_registry=None, store=None):
        self.armory = armory_registry
        self.store = store  # 用于解析 family:/intel:/immune: 前缀的数据源
    
    # ── 主入口 ──────────────────────────────────────────────────────────
    
    def generate(self, task: Any, sop: Optional[SOP] = None) -> PanelDefinition:
        """
        根据任务和SOP生成面板。
        
        Args:
            task: 任务字典（包含 task_id, status, stages, current_stage 等）
                  或任务字典列表（多任务 → 自动生成 COCKPIT 类型面板）
            sop: SOP对象（可选，如果任务已关联SOP）
        
        Returns:
            PanelDefinition
        
        Note:
            当 task 是列表时，自动生成驾驶舱（COCKPIT）面板，
            忽略 sop 参数（驾驶舱面板不关联单个 SOP）。
        """
        # 多任务 → 驾驶舱面板
        if isinstance(task, list):
            return self._generate_cockpit_panel(task)
        
        # 单任务 → 正常逻辑
        task_id = task.get("task_id", task.get("id", "unknown"))
        status = task.get("status", "created")
        
        # 1. 确定面板类型
        panel_type = self._determine_panel_type(task, status)
        
        # 2. 生成面板基础信息
        panel = PanelDefinition(
            panel_id=f"panel:{panel_type.value}_{task_id}",
            panel_type=panel_type,
            title=self._generate_title(task, panel_type),
            subtitle=self._generate_subtitle(task),
            task_id=task_id,
            sop_id=sop.sop_id if sop else None,
            created_at=datetime.now().isoformat(),
        )
        
        # 3. 生成布局
        panel.layout = self._generate_layout(panel_type, task)
        
        # 4. 生成组件
        panel.components = self._generate_components(task, sop, panel_type)
        
        # 5. 生成主题
        panel.theme = self._generate_theme(task)
        
        # 6. 生成交互配置
        panel.actions = self._generate_actions(task, panel_type)
        
        return panel
    
    def _generate_cockpit_panel(self, tasks: List[Dict[str, Any]]) -> PanelDefinition:
        """
        根据任务列表生成驾驶舱（COCKPIT）面板。
        
        Args:
            tasks: 任务字典列表
        
        Returns:
            PanelDefinition（panel_type=COCKPIT）
        """
        panel = PanelDefinition(
            panel_id="panel:cockpit_" + datetime.now().strftime("%Y%m%d_%H%M%S"),
            panel_type=PanelType.COCKPIT,
            title=self._generate_cockpit_title(tasks),
            subtitle=f"共 {len(tasks)} 个任务",
            created_at=datetime.now().isoformat(),
        )
        
        # 布局（标签页）
        panel.layout = self._generate_layout(PanelType.COCKPIT, {})
        
        # 组件（从任务列表计算，而非从单个 task）
        panel.components = self._create_cockpit_components(tasks)
        
        # 主题（默认）
        panel.theme = Theme(name="cockpit")
        
        # 交互配置
        panel.actions = {
            "on_load": "emit:cockpit_loaded",
            "on_close": "emit:cockpit_closed",
        }
        
        return panel
    
    def _generate_cockpit_title(self, tasks: List[Dict[str, Any]]) -> str:
        """生成驾驶舱面板标题（含任务统计）"""
        total = len(tasks)
        running = sum(1 for t in tasks if t.get("status") == "running")
        completed = sum(1 for t in tasks if t.get("status") == "completed")
        waiting = sum(1 for t in tasks if t.get("status") == "waiting")
        return f"家族驾驶舱 — {total} 任务（运行中 {running} / 完成 {completed} / 等待 {waiting}）"
    
    # ── 面板类型判定 ──────────────────────────────────────────────────────
    
    def _determine_panel_type(self, task: Dict[str, Any], status: str) -> PanelType:
        """根据任务状态和内容确定面板类型"""
        
        # 检查是否有决策点
        current_stage = task.get("current_stage", {})
        if current_stage and current_stage.get("is_decision_point", False):
            return PanelType.DECISION
        
        # 检查是否是告警任务
        if task.get("priority") == "critical" or task.get("alert_level") == "high":
            return PanelType.ALERT
        
        # 根据状态判定
        if status in ("created", "running"):
            return PanelType.TASK
        elif status == "completed":
            return PanelType.BRIEFING
        elif status == "waiting":
            return PanelType.DECISION
        
        return PanelType.TASK
    
    # ── 标题生成 ──────────────────────────────────────────────────────────
    
    def _generate_title(self, task: Dict[str, Any], panel_type: PanelType) -> str:
        """生成面板标题"""
        task_name = task.get("name", "未命名任务")
        type_names = {
            PanelType.COCKPIT: "家族驾驶舱",
            PanelType.TASK: f"任务: {task_name}",
            PanelType.DECISION: f"决策: {task_name}",
            PanelType.BRIEFING: f"简报: {task_name}",
            PanelType.ALERT: f"⚠️ 告警: {task_name}",
            PanelType.LINEAGE: "家族族谱",
            PanelType.CONFIG: "系统配置",
        }
        return type_names.get(panel_type, task_name)
    
    def _generate_subtitle(self, task: Dict[str, Any]) -> str:
        """生成面板副标题"""
        status = task.get("status", "")
        stage_name = task.get("current_stage", {}).get("name", "")
        if stage_name:
            return f"状态: {status} | 当前阶段: {stage_name}"
        return f"状态: {status}"
    
    # ── 布局生成 ──────────────────────────────────────────────────────────
    
    def _generate_layout(self, panel_type: PanelType, task: Dict[str, Any]) -> Layout:
        """根据面板类型生成布局"""
        
        if panel_type == PanelType.DECISION:
            # 决策面板：左侧输入/输出，右侧决策按钮
            return Layout(
                type=LayoutType.SPLIT,
                regions=[
                    Region(name="content", ratio=0.7, content_type="stage_content"),
                    Region(name="decision", ratio=0.3, content_type="decision_buttons"),
                ]
            )
        elif panel_type == PanelType.TASK:
            # 任务面板：顶部状态栏，中间内容，底部操作
            return Layout(
                type=LayoutType.SINGLE,
                regions=[
                    Region(name="status", content_type="task_status"),
                    Region(name="content", content_type="stage_content"),
                    Region(name="actions", content_type="stage_actions"),
                ]
            )
        elif panel_type == PanelType.COCKPIT:
            # 驾驶舱：标签页布局
            return Layout(
                type=LayoutType.TABS,
                regions=[
                    Region(name="health", content_type="family_health"),
                    Region(name="tasks", content_type="pending_tasks"),
                    Region(name="briefings", content_type="latest_briefings"),
                    Region(name="alerts", content_type="active_alerts"),
                ]
            )
        
        return Layout(type=LayoutType.SINGLE)
    
    # ── 组件生成 ──────────────────────────────────────────────────────────
    
    def _generate_components(self, task: Dict[str, Any], sop: Optional[SOP], 
                              panel_type: PanelType) -> List[PanelComponent]:
        """根据任务和SOP生成组件列表"""
        components = []
        
        # 1. 状态栏（所有面板都有）
        components.append(self._create_status_bar(task))
        
        # 2. 根据面板类型生成特定组件
        if panel_type == PanelType.DECISION:
            components.extend(self._create_decision_components(task))
        elif panel_type == PanelType.TASK:
            components.extend(self._create_task_components(task, sop))
        elif panel_type == PanelType.COCKPIT:
            components.extend(self._create_cockpit_components(task))
        elif panel_type == PanelType.BRIEFING:
            components.extend(self._create_briefing_components(task))
        
        # 3. 简报卡片（如果任务需要简报）
        if task.get("requires_briefing", False):
            components.append(self._create_briefing_card(task))
        
        return components
    
    # ── 组件工厂方法 ────────────────────────────────────────────────────────
    
    def _create_status_bar(self, task: Dict[str, Any]) -> PanelComponent:
        """创建状态栏组件"""
        return PanelComponent(
            id="comp:status_bar",
            type=ComponentType.STATUS_BAR,
            label="任务状态",
            data_source="task.status",
            data_binding="status",
            properties={
                "show_progress": True,
                "show_cost": True,
                "show_time": True,
            }
        )
    
    def _create_decision_components(self, task: Dict[str, Any]) -> List[PanelComponent]:
        """创建决策面板组件"""
        components = []
        current_stage = task.get("current_stage", {})
        
        # 输出展示（决策前需要看到产出）
        outputs = current_stage.get("outputs", [])
        for i, output in enumerate(outputs):
            comp_type = ComponentType.TEXT_DISPLAY
            if output.get("type") == "code":
                comp_type = ComponentType.CODE_PREVIEW
            elif output.get("type") == "document":
                comp_type = ComponentType.MARKDOWN
            
            components.append(PanelComponent(
                id=f"comp:output_{i}",
                type=comp_type,
                label=output.get("name", f"产出 {i+1}"),
                data_source=f"task.current_stage.outputs[{i}]",
                data_binding="content",
                properties={"language": output.get("language", "text")},
            ))
        
        # 质量评分
        quality = task.get("quality_score", {})
        if quality:
            components.append(PanelComponent(
                id="comp:quality_metrics",
                type=ComponentType.TABLE,
                label="质量评分",
                data_source="task.quality_score",
                properties={
                    "columns": ["维度", "评分", "权重"],
                    "data": [
                        ["客户满意度", quality.get("customer", 0), "40%"],
                        ["父辈审核", quality.get("parent", 0), "35%"],
                        ["孙辈自评", quality.get("child", 0), "25%"],
                    ]
                }
            ))
        
        # 决策按钮
        options = current_stage.get("decision_options", ["确认", "驳回", "修改"])
        components.append(PanelComponent(
            id="comp:decision_buttons",
            type=ComponentType.DECISION_BUTTONS,
            label="决策",
            data_source="task.current_stage.decision",
            properties={
                "options": options,
                "requires_comment": True,  # 驳回/修改时需要填写理由
            },
            on_click="emit:decision_made",
        ))
        
        return components
    
    def _create_task_components(self, task: Dict[str, Any], 
                                 sop: Optional[SOP]) -> List[PanelComponent]:
        """创建任务面板组件"""
        components = []
        current_stage = task.get("current_stage", {})
        
        # 输入组件
        inputs = current_stage.get("inputs", [])
        for i, input_field in enumerate(inputs):
            comp_type = ComponentType.TEXT_INPUT
            if input_field.get("type") == "textarea":
                comp_type = ComponentType.TEXTAREA
            elif input_field.get("type") == "code":
                comp_type = ComponentType.CODE_EDITOR
            
            components.append(PanelComponent(
                id=f"comp:input_{i}",
                type=comp_type,
                label=input_field.get("label", f"输入 {i+1}"),
                data_source=f"task.current_stage.inputs[{i}]",
                required=input_field.get("required", False),
                properties={
                    "placeholder": input_field.get("placeholder", ""),
                    "language": input_field.get("language", "text"),
                },
                on_change="emit:stage_input_changed",
            ))
        
        # 输出组件
        outputs = current_stage.get("outputs", [])
        for i, output in enumerate(outputs):
            components.append(PanelComponent(
                id=f"comp:output_{i}",
                type=ComponentType.TEXT_DISPLAY,
                label=output.get("name", f"产出 {i+1}"),
                data_source=f"task.current_stage.outputs[{i}]",
                readonly=True,
            ))
        
        return components
    
    def _create_cockpit_components(self, tasks: List[Dict[str, Any]]) -> List[PanelComponent]:
        """
        创建驾驶舱面板组件（从任务列表计算）。
        
        Args:
            tasks: 任务字典列表（多任务场景）
        """
        components = []
        
        # ── 任务统计概览（预计算，直接存 properties.data）───
        total = len(tasks)
        by_status = {}
        for t in tasks:
            s = t.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        
        components.append(PanelComponent(
            id="comp:task_stats",
            type=ComponentType.TABLE,
            label="任务统计",
            properties={
                "columns": ["状态", "数量"],
                "data": [[s, c] for s, c in by_status.items()],
            },
        ))
        
        # ── 待决策任务列表（预计算）───
        pending = []
        for t in tasks:
            stages = t.get("stages", [])
            current_idx = t.get("current_stage_index", 0)
            if current_idx < len(stages) and stages[current_idx].get("is_decision_point"):
                pending.append(t)
        
        if pending:
            pending_data = []
            for t in pending[:10]:
                task_id = t.get("task_id", t.get("id", "?"))
                title = t.get("title", t.get("name", "?"))
                stages = t.get("stages", [{}])
                idx = t.get("current_stage_index", 0)
                stage_name = stages[idx].get("name", "?") if idx < len(stages) else "?"
                pending_data.append([task_id, title, stage_name])
            
            components.append(PanelComponent(
                id="comp:pending_decisions",
                type=ComponentType.TASK_LIST,
                label="待决策任务",
                properties={
                    "columns": ["任务ID", "标题", "当前阶段"],
                    "data": pending_data,
                },
            ))
        
        # ── 最近任务时间线（预计算）───
        recent = sorted(
            tasks,
            key=lambda t: t.get("created_at", ""),
            reverse=True
        )[:10]
        
        components.append(PanelComponent(
            id="comp:recent_tasks",
            type=ComponentType.TIMELINE,
            label="最近任务",
            properties={
                "items": [
                    {
                        "time": t.get("created_at", ""),
                        "title": t.get("title", t.get("name", "?")),
                        "status": t.get("status", "unknown"),
                    }
                    for t in recent
                ],
            },
        ))
        
        # ── 家族健康度（需要 Store，用 data_source 延迟解析）───
        components.append(PanelComponent(
            id="comp:health_overview",
            type=ComponentType.HEALTH_GAUGE,
            label="家族健康度",
            data_source="family:health_overview",
            properties={
                "dimensions": ["财务", "运营", "治理", "客户"],
            }
        ))
        
        # ── 活跃告警（需要 Store）───
        components.append(PanelComponent(
            id="comp:active_alerts",
            type=ComponentType.ALERT_BANNER,
            label="活跃告警",
            data_source="immune:active_alerts",
            properties={"max_items": 5},
        ))
        
        return components
    
    def _create_briefing_components(self, task: Dict[str, Any]) -> List[PanelComponent]:
        """创建简报面板组件"""
        components = []
        
        # 任务摘要
        components.append(PanelComponent(
            id="comp:task_summary",
            type=ComponentType.MARKDOWN,
            label="任务摘要",
            data_source="task.summary",
        ))
        
        # KPI图表
        components.append(PanelComponent(
            id="comp:kpi_chart",
            type=ComponentType.CHART,
            label="KPI趋势",
            data_source="task.kpi_history",
            properties={"chart_type": "line", "x_axis": "date", "y_axis": "score"},
        ))
        
        # 产出物列表
        components.append(PanelComponent(
            id="comp:outputs",
            type=ComponentType.TABLE,
            label="产出物",
            data_source="task.outputs",
            properties={"columns": ["类型", "路径", "大小", "哈希"]},
        ))
        
        return components
    
    def _create_briefing_card(self, task: Dict[str, Any]) -> PanelComponent:
        """创建简报卡片组件"""
        return PanelComponent(
            id="comp:briefing_card",
            type=ComponentType.COLLAPSIBLE_CARD,
            label="军师简报",
            data_source="intel:strategist_brief",
            properties={"expand_by_default": False},
        )
    
    # ── 主题生成 ──────────────────────────────────────────────────────────
    
    def _generate_theme(self, task: Dict[str, Any]) -> Theme:
        """根据任务属性生成主题"""
        # 默认主题
        theme = Theme(name="default")
        
        # 告警任务使用红色主题
        if task.get("priority") == "critical":
            theme.primary_color = "#e74c3c"
        
        # 决策任务使用蓝色主题
        current_stage = task.get("current_stage", {})
        if current_stage.get("is_decision_point"):
            theme.primary_color = "#3498db"
        
        return theme
    
    # ── 动作生成 ──────────────────────────────────────────────────────────
    
    def _generate_actions(self, task: Dict[str, Any], panel_type: PanelType) -> Dict[str, str]:
        """生成面板级别的事件响应"""
        actions = {}
        
        actions["on_load"] = "emit:panel_loaded"
        actions["on_close"] = "emit:panel_closed"
        
        if panel_type == PanelType.DECISION:
            actions["on_decision"] = "emit:human_decision_made"
        
        return actions


# ────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ────────────────────────────────────────────────────────────────────────────

def generate_panel(task: Dict[str, Any], sop: Optional[SOP] = None,
                   armory_registry=None) -> PanelDefinition:
    """便捷函数：一键生成面板"""
    generator = PanelGenerator(armory_registry=armory_registry)
    return generator.generate(task, sop)
