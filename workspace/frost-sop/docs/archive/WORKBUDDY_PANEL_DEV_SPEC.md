# FROST V5.0 前端系统（Panel）——WorkBuddy 开发指令集

**版本**: V5.0-设计稿  
**日期**: 2026-06-28  
**目标**: 定义FROST第六个原子——Panel（交互面板），并交付给WorkBuddy执行  
**优先级**: P0（阻塞级——无前端，撒豆成兵不完整）  

---

## 一、设计哲学（WorkBuddy 必须理解）

### 1.1 前端不是"外部包装"

> **Panel 是 FROST 的第六个原子，与 Store/Skill/Agent/SOP 并列。**

- Store = 记忆
- Skill = 能力
- Agent = 执行者
- SOP = 流程
- **Panel = 交互**

没有 Panel，FROST 是一个没有感官的有机体——它能思考、能执行，但无法与人类对话。

### 1.2 面板是数据，不是代码

```
PanelDefinition（数据）→ Renderer（渲染引擎）→ UI（CLI/Streamlit/Web）
```

- **PanelDefinition** 是纯数据（JSON/YAML 可序列化）
- **Renderer** 将数据转化为具体界面
- 同一份 PanelDefinition 可在 CLI、Streamlit、Web 上渲染
- 面板不是 React 组件，不是 Vue 模板，是**元数据驱动的 UI 配置**

### 1.3 面板从任务和 SOP 自动生成

不是手动写 UI，而是：

```
任务需求 → 军师从图谱检索 SOP → 父辈组装 SOP → 面板生成器自动生成 Panel → 渲染引擎渲染
```

**撒豆成兵 = SOP + 武器 + 面板。三者缺一不可。**

---

## 二、核心数据类设计（必须精确实现）

### 2.1 文件：`core/panel.py`

**职责**：定义 Panel 的所有数据类——PanelDefinition、PanelComponent、Layout、Theme。

**代码**（必须完全按此实现）：

```python
"""
FROST V5.0 第六个原子——Panel（交互面板）

PHILOSOPHY: 面板不是UI代码，面板是元数据驱动的UI配置。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Union


# ────────────────────────────────────────────────────────────────────────────
# 面板类型
# ────────────────────────────────────────────────────────────────────────────

class PanelType(Enum):
    """面板类型——根据使用场景定义"""
    COCKPIT = "cockpit"        # 驾驶舱：家族概览（君主日常查看）
    TASK = "task"              # 任务面板：单个任务的驾驶舱（执行中查看）
    DECISION = "decision"      # 决策面板：Human Agent 做决策（审批/驳回/修改）
    BRIEFING = "briefing"      # 简报面板：军师/长老/免疫系统的简报展示
    LINEAGE = "lineage"        # 族谱面板：任务血缘、家族历史可视化
    ALERT = "alert"            # 告警面板：免疫系统告警、紧急通知
    CONFIG = "config"          # 配置面板：宪法规则、平台绑定、武器管理


# ────────────────────────────────────────────────────────────────────────────
# 布局系统
# ────────────────────────────────────────────────────────────────────────────

class LayoutType(Enum):
    """布局类型"""
    SINGLE = "single"          # 单列布局（所有组件垂直排列）
    SPLIT = "split"            # 分栏布局（左右/上下分栏）
    TABS = "tabs"              # 标签页布局（每个标签一个区域）
    GRID = "grid"              # 网格布局（组件按网格排列）
    OVERLAY = "overlay"        # 叠加布局（弹窗/模态框）


@dataclass
class Region:
    """布局区域"""
    name: str                  # 区域名称（如 "input", "output", "decision"）
    ratio: float = 1.0        # 区域占比（0.0-1.0，仅 SPLIT 布局有效）
    content_type: str = ""     # 区域内容类型标识（如 "current_stage_inputs"）
    components: List[str] = field(default_factory=list)  # 组件ID列表


@dataclass
class Layout:
    """面板布局"""
    type: LayoutType = LayoutType.SINGLE
    regions: List[Region] = field(default_factory=list)
    
    # 响应式断点（可选，Web渲染时有效）
    breakpoints: Dict[str, str] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# 组件系统
# ────────────────────────────────────────────────────────────────────────────

class ComponentType(Enum):
    """组件类型——所有UI组件的原子分类"""
    # 输入组件
    TEXT_INPUT = "text_input"          # 单行文本输入
    TEXTAREA = "textarea"              # 多行文本输入
    CODE_EDITOR = "code_editor"        # 代码编辑器（带语法高亮）
    SELECT = "select"                  # 下拉选择
    MULTI_SELECT = "multi_select"      # 多选
    FILE_UPLOAD = "file_upload"        # 文件上传
    
    # 输出组件
    TEXT_DISPLAY = "text_display"      # 纯文本展示
    MARKDOWN = "markdown"              # Markdown 渲染
    CODE_PREVIEW = "code_preview"      # 代码预览（带语法高亮）
    CHART = "chart"                    # 图表（柱状图/折线图/饼图）
    TABLE = "table"                    # 表格
    IMAGE = "image"                    # 图片展示
    PDF = "pdf"                        # PDF 预览
    
    # 决策组件
    DECISION_BUTTONS = "decision_buttons"  # 决策按钮组（确认/驳回/修改）
    CONFIRM_DIALOG = "confirm_dialog"      # 确认对话框
    RATING = "rating"                      # 评分组件（1-5星）
    
    # 状态组件
    STATUS_BAR = "status_bar"          # 状态栏（任务状态、进度）
    PROGRESS_BAR = "progress_bar"      # 进度条
    HEALTH_GAUGE = "health_gauge"      # 健康度仪表盘（0-100）
    ALERT_BANNER = "alert_banner"      # 告警横幅
    
    # 组织组件
    COLLAPSIBLE_CARD = "collapsible_card"  # 可折叠卡片
    TABS = "tabs"                          # 标签页容器
    DIVIDER = "divider"                    # 分割线
    
    # 导航组件
    TASK_LIST = "task_list"            # 任务列表
    BREADCRUMB = "breadcrumb"          # 面包屑导航
    TIMELINE = "timeline"              # 时间线
    
    # 特殊组件
    CHAT = "chat"                      # 聊天界面（与Agent对话）
    GRAPH = "graph"                    # 图谱可视化（节点/边图）
    TERMINAL = "terminal"              # 终端模拟器（日志输出）


@dataclass
class PanelComponent:
    """面板组件——面板的基本构建单元"""
    id: str                        # 组件唯一ID（如 "comp:task_status"）
    type: ComponentType            # 组件类型
    
    # 基础属性
    label: str = ""                # 组件标签/标题
    description: str = ""        # 组件描述/提示文本
    
    # 数据源——组件展示的数据从哪来
    data_source: str = ""         # 数据源标识（如 "task.status", "intel:strategist_brief"）
    data_binding: str = ""         # 数据绑定路径（如 "task.stages[0].output"）
    
    # 交互属性——组件如何响应用户操作
    editable: bool = False         # 是否可编辑
    required: bool = False         # 是否必填（输入组件）
    readonly: bool = False           # 是否只读
    
    # 样式属性
    width: str = "100%"            # 宽度（CSS格式）
    height: str = "auto"           # 高度（CSS格式）
    style: Dict[str, str] = field(default_factory=dict)  # 额外CSS样式
    
    # 类型特定属性（根据 ComponentType 变化）
    properties: Dict[str, Any] = field(default_factory=dict)
    # 例如：CODE_EDITOR 的 properties = {"language": "python", "theme": "dark"}
    # 例如：CHART 的 properties = {"chart_type": "bar", "x_axis": "date", "y_axis": "cost"}
    # 例如：DECISION_BUTTONS 的 properties = {"options": ["确认", "驳回", "修改"]}
    
    # 条件渲染——在什么条件下显示此组件
    show_when: str = ""            # 条件表达式（如 "task.status == 'running'"）
    hide_when: str = ""            # 条件表达式
    
    # 动作——用户交互后触发什么
    on_change: str = ""            # 值变更时触发的动作（如 "emit:stage_input_changed"）
    on_click: str = ""             # 点击时触发的动作（如 "emit:decision_made"）
    on_submit: str = ""            # 提交时触发的动作


# ────────────────────────────────────────────────────────────────────────────
# 主题系统
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class Theme:
    """面板主题——定义视觉风格"""
    name: str = "default"          # 主题名称
    primary_color: str = "#2c3e50" # 主色调
    secondary_color: str = "#3498db"  # 次要色调
    background_color: str = "#ffffff"   # 背景色
    text_color: str = "#333333"    # 文字颜色
    font_family: str = "system"    # 字体
    font_size: str = "14px"        # 字体大小
    border_radius: str = "4px"     # 圆角
    spacing: str = "16px"          # 组件间距
    
    # 暗色模式（可选）
    dark_mode: Dict[str, str] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# 面板定义——核心数据类
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class PanelDefinition:
    """
    面板定义——FROST 第六个原子的核心数据类。
    
    面板不是 UI 代码，面板是元数据驱动的 UI 配置。
    同一份 PanelDefinition 可在 CLI、Streamlit、Web 上渲染。
    """
    # 基础标识
    panel_id: str                  # 唯一ID（如 "panel:task_cockpit_auth_001"）
    panel_type: PanelType          # 面板类型
    title: str = ""                # 面板标题
    subtitle: str = ""             # 面板副标题
    
    # 关联关系
    task_id: Optional[str] = None      # 关联任务ID
    sop_id: Optional[str] = None         # 关联SOP ID
    agent_id: Optional[str] = None       # 关联Agent ID
    
    # 布局
    layout: Layout = field(default_factory=lambda: Layout(type=LayoutType.SINGLE))
    
    # 组件
    components: List[PanelComponent] = field(default_factory=list)
    
    # 主题
    theme: Theme = field(default_factory=Theme)
    
    # 元数据
    version: str = "1.0"           # 面板版本
    created_at: str = ""           # 创建时间（ISO格式）
    updated_at: str = ""           # 更新时间
    
    # 交互配置
    refresh_interval: Optional[int] = None  # 自动刷新间隔（秒），None=不刷新
    auto_close: Optional[int] = None      # 自动关闭时间（秒），None=不关闭
    
    # 权限
    allowed_roles: List[str] = field(default_factory=list)  # 允许查看的角色（如 ["monarch", "strategist"]）
    
    # 动作绑定——面板级别的事件响应
    actions: Dict[str, str] = field(default_factory=dict)  # {"on_load": "emit:panel_loaded", "on_close": "emit:panel_closed"}
    
    # 扩展属性
    meta: Dict[str, Any] = field(default_factory=dict)  # 扩展字段

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        from dataclasses import asdict
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PanelDefinition":
        """从字典反序列化"""
        # 简化实现：直接创建（实际应递归处理嵌套 dataclass）
        return cls(**data)


# ────────────────────────────────────────────────────────────────────────────
# 面板状态——运行时状态
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class PanelState:
    """面板运行时状态——记录当前面板的交互状态"""
    panel_id: str
    
    # 当前值——每个组件的当前值
    values: Dict[str, Any] = field(default_factory=dict)  # {"comp:input_1": "用户输入", "comp:rating": 4}
    
    # 展开/折叠状态
    expanded: Dict[str, bool] = field(default_factory=dict)  # {"comp:briefing": True}
    
    # 当前激活的标签页
    active_tab: str = ""
    
    # 滚动位置
    scroll_position: int = 0
    
    # 最后更新时间
    last_updated: str = ""
    
    # 用户交互记录
    interaction_log: List[Dict[str, Any]] = field(default_factory=list)
    # [{"timestamp": "2026-06-28T10:00:00", "component_id": "comp:btn_approve", "action": "click", "value": "确认"}]


# ────────────────────────────────────────────────────────────────────────────
# 面板快照——历史记录
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class PanelSnapshot:
    """面板快照——任务完成后保存的面板状态"""
    snapshot_id: str
    panel_id: str
    task_id: Optional[str]
    
    # 快照时的面板定义
    panel_definition: PanelDefinition
    
    # 快照时的面板状态
    panel_state: PanelState
    
    # 快照时的任务状态
    task_status: str = ""
    
    # 快照时间
    captured_at: str = ""
```

**WorkBuddy 注意**：
- 所有数据类必须使用 `@dataclass`
- `properties` 字段用于存储类型特定的属性，保持扩展性
- `data_source` 和 `data_binding` 是面板与后端数据连接的关键字段
- 枚举值必须使用 `.value` 序列化

---

## 三、面板生成器（从 SOP/任务自动生成）

### 3.1 文件：`core/panel_generator.py`

**职责**：根据 SOP、任务定义、武器元数据自动生成 PanelDefinition。

**核心逻辑**：

```python
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
    """
    
    def __init__(self, armory_registry=None):
        self.armory = armory_registry
    
    # ── 主入口 ──────────────────────────────────────────────────────────
    
    def generate(self, task: Dict[str, Any], sop: Optional[SOP] = None) -> PanelDefinition:
        """
        根据任务和SOP生成面板。
        
        Args:
            task: 任务字典（包含 task_id, status, stages, current_stage 等）
            sop: SOP对象（可选，如果任务已关联SOP）
        
        Returns:
            PanelDefinition
        """
        task_id = task.get("task_id", "unknown")
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
    
    def _create_cockpit_components(self, task: Dict[str, Any]) -> List[PanelComponent]:
        """创建驾驶舱面板组件"""
        components = []
        
        # 家族健康度仪表盘
        components.append(PanelComponent(
            id="comp:health_overview",
            type=ComponentType.HEALTH_GAUGE,
            label="家族健康度",
            data_source="family:health_overview",
            properties={
                "dimensions": ["财务", "运营", "治理", "客户"],
            }
        ))
        
        # 待审批任务列表
        components.append(PanelComponent(
            id="comp:pending_decisions",
            type=ComponentType.TASK_LIST,
            label="待审批事项",
            data_source="family:pending_decisions",
            properties={
                "columns": ["任务名称", "阶段", "等待时长", "紧急度"],
                "max_items": 10,
            }
        ))
        
        # 军师简报卡片
        components.append(PanelComponent(
            id="comp:strategist_brief",
            type=ComponentType.COLLAPSIBLE_CARD,
            label="军师简报",
            data_source="intel:latest_strategist_brief",
            properties={"expand_by_default": False},
        ))
        
        # 告警列表
        components.append(PanelComponent(
            id="comp:active_alerts",
            type=ComponentType.ALERT_BANNER,
            label="活跃告警",
            data_source="immune:active_alerts",
            properties={"max_items": 5},
        ))
        
        # 最近任务时间线
        components.append(PanelComponent(
            id="comp:recent_tasks",
            type=ComponentType.TIMELINE,
            label="最近任务",
            data_source="family:recent_tasks",
            properties={"limit": 10},
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
```

**WorkBuddy 注意**：
- `PanelGenerator` 必须能处理 `sop=None` 的情况（某些任务可能没有关联SOP）
- `task` 参数是字典，不是 `TaskDefinition` 数据类（因为 `core/task_registry.py` 可能尚未实现）
- 所有 `data_source` 字段是**标识符**，不是实际数据。渲染引擎负责根据标识符从后端获取数据
- 组件工厂方法是可扩展的——未来添加新的面板类型时，只需添加新的 `_create_*_components` 方法

---

## 四、渲染引擎（与面板定义解耦）

### 4.1 文件：`core/panel_renderer.py`

**职责**：定义渲染引擎基类和渲染接口。渲染引擎将 `PanelDefinition` 转化为具体 UI。

**代码**（必须完全按此实现）：

```python
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
```

### 4.2 文件：`renderers/cli_renderer.py`

**职责**：CLI 渲染引擎——使用 `rich` 库在终端渲染面板。

**代码**（必须完全按此实现）：

```python
"""
FROST V5.0 CLI 渲染引擎——在终端渲染面板。

依赖: rich (pip install rich)
"""

from typing import Any, Optional

from rich import box
from rich.align import Align
from rich.console import Console
from rich.layout import Layout as RichLayout
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
        """获取数据"""
        # 简单实现：从字典中查找
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
    
    # ── 各组件渲染实现 ─────────────────────────────────────────────────────
    
    def _render_status_bar(self, component: PanelComponent, data: Any) -> None:
        """渲染状态栏"""
        if isinstance(data, dict):
            status = data.get("status", "unknown")
            progress = data.get("progress", 0)
            cost = data.get("cost", 0)
            
            grid = Table.grid(padding=1)
            grid.add_column()
            grid.add_column()
            grid.add_column()
            grid.add_row(
                f"[bold]状态:[/bold] {status}",
                f"[bold]进度:[/bold] {progress}%",
                f"[bold]成本:[/bold] ¥{cost:.2f}"
            )
            self.console.print(RichPanel(grid, title="状态栏"))
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
        # 使用 Rich 的语法高亮（如果代码较短）
        if len(str(value)) < 500:
            from rich.syntax import Syntax
            syntax = Syntax(str(value), language, theme="monokai")
            self.console.print(syntax)
        else:
            self.console.print(f"[italic]{str(value)[:200]}...[/italic]")
    
    def _render_code_preview(self, component: PanelComponent, data: Any) -> None:
        """渲染代码预览"""
        self._render_code_editor(component, data)  # 代码编辑器相同渲染
    
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
            # 简单的 ASCII 柱状图
            max_val = max(data) if all(isinstance(x, (int, float)) for x in data) else 10
            for i, val in enumerate(data):
                bar = "█" * int((val / max_val) * 30) if max_val > 0 else ""
                self.console.print(f"  {i:3d} | {bar} {val}")
        else:
            self.console.print("[dim]（无图表数据）[/dim]")
    
    def _render_decision_buttons(self, component: PanelComponent, data: Any) -> None:
        """渲染决策按钮"""
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
            task = p.add_task(label, total=100, completed=progress)
    
    def _render_health_gauge(self, component: PanelComponent, data: Any) -> None:
        """渲染健康度仪表盘"""
        label = component.label or "健康度"
        
        if isinstance(data, dict):
            self.console.print(f"[bold]{label}[/bold]")
            for dim, score in data.items():
                bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
                color = "green" if score >= 80 else "yellow" if score >= 50 else "red"
                self.console.print(f"  {dim:10s} | [{color}]{bar}[/{color}] {score}")
        else:
            self.console.print(f"[bold]{label}[/bold]: {data or 0}")
    
    def _render_alert_banner(self, component: PanelComponent, data: Any) -> None:
        """渲染告警横幅"""
        label = component.label or "告警"
        
        if isinstance(data, list):
            for alert in data:
                level = alert.get("level", "info")
                message = alert.get("message", "")
                color = {"critical": "red", "high": "yellow", "medium": "blue", "low": "green"}.get(level, "white")
                self.console.print(f"[{color}]⚠️ [{level.upper()}] {message}[/{color}]")
        else:
            self.console.print(f"[yellow]⚠️ {label}: {data}[/yellow]")
    
    def _render_collapsible_card(self, component: PanelComponent, data: Any) -> None:
        """渲染可折叠卡片"""
        label = component.label or "卡片"
        expand = component.properties.get("expand_by_default", False)
        
        if expand:
            self.console.print(f"[bold]▼ {label}[/bold]")
            self.console.print(str(data) if data else "[dim]（无内容）[/dim]")
        else:
            self.console.print(f"[bold]▶ {label}[/bold] [dim](点击展开)[/dim]")
    
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
```

**WorkBuddy 注意**：
- CLI 渲染引擎依赖 `rich` 库，需要在 `requirements.txt` 中添加 `rich>=13.0.0`
- 所有渲染方法返回 `None`，因为 CLI 渲染是直接输出到终端
- `DataProvider` 使用内存字典，生产环境中应替换为 `StoreDataProvider`（从 Store 读取数据）

---

### 4.3 文件：`renderers/streamlit_renderer.py`（预留）

**职责**：Streamlit 渲染引擎——使用 Streamlit 库在浏览器渲染面板。

**代码框架**（预留，WorkBuddy 后续实现）：

```python
"""
FROST V5.0 Streamlit 渲染引擎——在浏览器渲染面板。

依赖: streamlit (pip install streamlit)

注意：此文件为预留框架，WorkBuddy 在 CLI 渲染引擎稳定后实现。
"""

from typing import Any, Optional

from core.panel import PanelDefinition, PanelComponent, ComponentType, PanelState
from core.panel_renderer import PanelRenderer


class StreamlitRenderer(PanelRenderer):
    """Streamlit 渲染引擎"""
    
    def render(self, panel: PanelDefinition, state: Optional[PanelState] = None) -> Any:
        """渲染面板到 Streamlit"""
        import streamlit as st
        
        # 1. 设置页面标题
        st.set_page_config(page_title=panel.title, layout="wide")
        
        # 2. 渲染标题
        st.title(panel.title)
        if panel.subtitle:
            st.caption(panel.subtitle)
        
        # 3. 渲染组件
        for component in panel.components:
            data = self.get_component_data(component)
            self.render_component(component, data)
        
        # 4. 渲染底部
        st.divider()
        st.caption(f"面板 ID: {panel.panel_id} | 版本: {panel.version}")
    
    def render_component(self, component: PanelComponent, data: Any = None) -> None:
        """渲染单个组件"""
        import streamlit as st
        
        comp_type = component.type
        label = component.label or ""
        
        if comp_type == ComponentType.TEXT_INPUT:
            st.text_input(label, value=str(data) if data else "", key=component.id)
        elif comp_type == ComponentType.TEXTAREA:
            st.text_area(label, value=str(data) if data else "", key=component.id)
        elif comp_type == ComponentType.CODE_PREVIEW:
            st.code(str(data) if data else "", language=component.properties.get("language", "python"))
        elif comp_type == ComponentType.MARKDOWN:
            st.markdown(str(data) if data else "")
        elif comp_type == ComponentType.TABLE:
            import pandas as pd
            if isinstance(data, list):
                df = pd.DataFrame(data)
                st.dataframe(df)
        elif comp_type == ComponentType.DECISION_BUTTONS:
            options = component.properties.get("options", ["确认", "驳回", "修改"])
            st.radio(label, options, key=component.id)
            st.button("提交决策", key=f"{component.id}_submit")
        elif comp_type == ComponentType.PROGRESS_BAR:
            progress = data if isinstance(data, (int, float)) else 0
            st.progress(progress / 100)
        elif comp_type == ComponentType.HEALTH_GAUGE:
            if isinstance(data, dict):
                cols = st.columns(len(data))
                for col, (dim, score) in zip(cols, data.items()):
                    with col:
                        st.metric(dim, f"{score}")
        elif comp_type == ComponentType.ALERT_BANNER:
            if isinstance(data, list):
                for alert in data:
                    level = alert.get("level", "info")
                    message = alert.get("message", "")
                    if level == "critical":
                        st.error(message)
                    elif level == "high":
                        st.warning(message)
                    else:
                        st.info(message)
        elif comp_type == ComponentType.COLLAPSIBLE_CARD:
            with st.expander(label, expanded=component.properties.get("expand_by_default", False)):
                st.write(str(data) if data else "（无内容）")
        elif comp_type == ComponentType.TASK_LIST:
            if isinstance(data, list):
                for task in data:
                    if isinstance(task, dict):
                        name = task.get("任务名称", "")
                        status = task.get("状态", "")
                        st.write(f"- {name} ({status})")
        else:
            st.write(f"[未实现组件] {comp_type.value}: {str(data)}")
    
    # Streamlit 渲染引擎的各组件方法（简化版）
    def _render_status_bar(self, component: PanelComponent, data: Any) -> None:
        import streamlit as st
        if isinstance(data, dict):
            cols = st.columns(3)
            cols[0].metric("状态", data.get("status", "unknown"))
            cols[1].metric("进度", f"{data.get('progress', 0)}%")
            cols[2].metric("成本", f"¥{data.get('cost', 0):.2f}")
    
    # 其他组件方法...
    # （WorkBuddy 在需要时补充）
```

---

## 五、与现有系统的整合

### 5.1 与武器库（Armory）整合

武器元数据扩展：

```python
# 在 core/armory.py 的 WeaponMetadata 中增加字段
panel_components: List[str] = field(default_factory=list)  # 该武器需要的前端组件ID列表
```

面板生成器在生成组件时，检查武器元数据中的 `panel_components`：

```python
# 在 PanelGenerator._generate_components 中
for weapon_id in task.get("weapons", []):
    weapon = self.armory.get(weapon_id) if self.armory else None
    if weapon and weapon.panel_components:
        for comp_id in weapon.panel_components:
            # 根据 comp_id 生成对应的 PanelComponent
            pass
```

**已实现**：`core/panel_adapters.py` 中的 `ArmoryAdapter` 提供了完整的武器-面板组件转换逻辑。

### 5.2 与任务系统（Task）整合

任务创建时自动生成面板：

```python
# 在 core/task_registry.py 的 create_task 中（或 panel_adapters.py 的适配器）
def create_task_with_panel(requirement, parent_id=None):
    # 1. 创建任务（现有逻辑）
    task = TaskDefinition(...)
    
    # 2. 适配任务数据
    from core.panel_adapters import TaskAdapter
    adapted_task = TaskAdapter.adapt(task.to_dict())
    
    # 3. 生成面板
    from core.panel_generator import PanelGenerator
    generator = PanelGenerator(armory_registry)
    panel = generator.generate(adapted_task, sop)
    task.panel_id = panel.panel_id
    
    # 4. 保存面板到 Store
    store.save(f"panel:{task.task_id}", panel.to_dict())
    
    return task
```

**已实现**：`core/panel_adapters.py` 中的 `TaskAdapter` 将现有任务格式适配为面板生成器期望的格式。

### 5.3 与事件系统（Event）整合

面板状态变更触发事件：

```python
# 在 PanelState 更新时
def update_panel_state(panel_id, component_id, value):
    state = load_panel_state(panel_id)
    state.values[component_id] = value
    state.interaction_log.append({
        "timestamp": datetime.now().isoformat(),
        "component_id": component_id,
        "value": value,
    })
    save_panel_state(panel_id, state)
    
    # 触发事件
    event_bus.publish("panel.component_changed", {
        "panel_id": panel_id,
        "component_id": component_id,
        "value": value,
    })
```

### 5.4 与 Human Agent 整合

Human Agent 的决策面板：

```python
# 当 SOP 遇到决策点时
def on_decision_point(task, stage):
    # 1. 生成决策面板
    panel = generate_panel(task.to_dict(), task.sop)
    panel.panel_type = PanelType.DECISION
    
    # 2. 渲染面板
    renderer = CliRenderer(data_provider=StoreDataProvider(store))
    renderer.render(panel)
    
    # 3. 等待 Human Agent 输入
    decision = input("请选择决策: ")
    
    # 4. 记录决策
    record_human_decision(task, stage, decision)
    
    # 5. 触发事件
    event_bus.publish("human.decision_made", {
        "task_id": task.task_id,
        "stage": stage.name,
        "decision": decision,
    })
```

---

## 六、WorkBuddy 执行顺序

### Phase 1: 核心数据类（1天）

1. 创建 `core/panel.py` —— PanelDefinition、PanelComponent、Layout、Theme 等数据类
2. 创建 `tests/test_panel.py` —— 测试数据类的序列化/反序列化
3. 验证：所有数据类可正确导入、可序列化为 dict、可反序列化

### Phase 2: 面板生成器（1天）

4. 创建 `core/panel_generator.py` —— PanelGenerator 类
5. 创建 `tests/test_panel_generator.py` —— 测试从 mock 任务生成面板
6. 验证：给定任务字典，能生成合理的 PanelDefinition

### Phase 3: 渲染引擎基类（0.5天）

7. 创建 `core/panel_renderer.py` —— PanelRenderer 抽象基类 + DataProvider 接口
8. 验证：抽象方法正确定义，无法实例化（除非实现所有抽象方法）

### Phase 4: CLI 渲染引擎（1.5天）

9. 创建 `renderers/cli_renderer.py` —— CliRenderer + CliDataProvider
10. 在 `requirements.txt` 中添加 `rich>=13.0.0`
11. 创建 `tests/test_cli_renderer.py` —— 测试各组件渲染
12. 验证：给定 PanelDefinition，能在终端正确渲染

### Phase 5: 整合验证（1天）

13. 修改 `core/armory.py` —— WeaponMetadata 增加 `panel_components` 字段
14. 创建示例：`examples/panel_demo.py` —— 从 mock 任务生成面板并 CLI 渲染
15. 验证：端到端流程——任务 → 生成面板 → CLI 渲染 → 用户交互

**总计：5 天**

---

## 七、测试规格（WorkBuddy 必须遵守）

### 7.1 `tests/test_panel.py`

- 测试 `PanelDefinition` 序列化/反序列化
- 测试 `PanelComponent` 的 `properties` 字段扩展性
- 测试 `PanelState` 的值记录和交互日志
- 测试 `Layout` 的 `regions` 比例计算

### 7.2 `tests/test_panel_generator.py`

- 测试从简单任务生成 TASK 面板
- 测试从决策任务生成 DECISION 面板
- 测试从告警任务生成 ALERT 面板
- 测试布局生成（SINGLE/SPLIT/TABS）
- 测试组件生成（输入、输出、决策、简报）
- 测试主题生成（根据任务优先级变色）

### 7.3 `tests/test_cli_renderer.py`

- 测试 `CliRenderer` 渲染完整面板
- 测试各组件渲染（status_bar、text_input、code_preview、table、chart、decision_buttons、progress_bar、health_gauge、alert_banner、collapsible_card、task_list、timeline）
- 测试 `CliDataProvider` 数据获取
- 测试空数据时的渲染（不崩溃）

### 7.4 `tests/test_panel_integration.py`（Phase 5）

- 测试端到端：任务 → 生成面板 → 渲染 → 用户输入 → 记录状态
- 测试与事件系统的整合（面板交互触发事件）
- 测试与武器库的整合（武器元数据驱动面板组件）

---

## 八、关键设计决策记录

| 决策 | 理由 |
|------|------|
| 面板是数据，不是代码 | 与 Skill/SOP 保持同构——元数据驱动，可序列化、可传输、可复用 |
| 渲染引擎与面板定义解耦 | 同一份面板可在 CLI/Web/Mobile 渲染，不绑定具体技术栈 |
| 组件类型是枚举，不是类 | 保持极简——新组件只需增加枚举值和渲染方法，不需要新类 |
| data_source 是标识符，不是数据 | 渲染时通过 DataProvider 获取数据，支持动态更新和 Mock 测试 |
| 面板从 SOP/任务自动生成 | 撒豆成兵 = SOP + 武器 + 面板，三者缺一不可 |
| Panel 是第六个原子 | 与 Store/Skill/Agent/SOP 并列，不是附属物 |
| CLI 渲染优先于 Web 渲染 | 先验证数据结构和生成逻辑，再 investment Web 渲染 |
| 决策面板是核心场景 | Human Agent 的交互入口，必须优先实现 |
| 主题根据任务属性动态生成 | 告警任务红色、决策任务蓝色——视觉反馈增强可用性 |
| 面板状态可持久化 | 任务中断后恢复，Human Agent 的决策记录可审计 |

---

## 九、WorkBuddy 交付标准

| 交付物 | 标准 |
|--------|------|
| `core/panel.py` | 所有数据类可导入、可序列化、可反序列化 |
| `core/panel_generator.py` | 给定 mock 任务，能生成合理的 PanelDefinition |
| `core/panel_renderer.py` | 抽象基类正确定义，无法被直接实例化 |
| `renderers/cli_renderer.py` | 给定 PanelDefinition，能在终端正确渲染所有组件类型 |
| `tests/test_*.py` | 所有测试通过，覆盖率 > 80% |
| `examples/panel_demo.py` | 端到端 demo 可运行，展示任务 → 面板 → 渲染 → 交互流程 |
| `requirements.txt` | 已添加 `rich>=13.0.0` |

---

*指令集结束。WorkBuddy 必须严格按照此文档执行，任何偏离都需要先与创造者确认。*


---

## 十、细化文件索引（P0 阻塞级缺口已补齐）

以下三个细化文件已交付，是 WorkBuddy 执行前必须理解的关键连接点。

### 10.1 `core/panel_data_provider.py` — StoreDataProvider 实现

**状态**：✅ 已完成  
**大小**：10KB  
**职责**：面板与后端数据的唯一连接点。

**核心实现**：
- `StoreDataProvider` 实现 `DataProvider` 接口
- 支持所有 FROST 键前缀规则（`task:`, `intel:`, `family:`, `immune:`, `armory:`, `decision:`, `panel:`）
- 支持路径导航：`task.stages[0].name`、`task.current_stage`、`intel:strategist_brief`
- 依赖注入：`task_id`（用于解析 `task.*`）、`armory_registry`、`decision_flow`

**使用方式**：
```python
from core.panel_data_provider import StoreDataProvider

provider = StoreDataProvider(store, task_id="task:xxx")
data = provider.get("task.status")           # → store.get("task:xxx")["status"]
data = provider.get("intel:strategist_brief") # → store.get("intel:strategist_brief")
data = provider.get("task.stages[0].name")    # → 路径导航
```

**测试文件**：`tests/test_panel_data_provider.py`（WorkBuddy 在 Phase 1 中创建）

---

### 10.2 `core/panel_adapters.py` — 与现有代码的整合接口

**状态**：✅ 已完成  
**大小**：15KB  
**职责**：面板系统与任务、事件、武器库的无缝集成。

**包含四个适配器**：

| 适配器 | 职责 | 关键方法 |
|--------|------|---------|
| `TaskAdapter` | 将 FROST 现有任务格式适配为面板生成器期望格式 | `adapt(task_data)`, `adapt_from_store(store, task_id)` |
| `EventAdapter` | 面板交互与 V2.0 EventBus 整合 | `emit_panel_loaded()`, `emit_decision_made()`, `subscribe_to_decisions(callback)` |
| `ArmoryAdapter` | 武器元数据扩展面板组件声明 | `weapon_to_panel_components(weapon)`, `update_weapon_metadata(weapon, panel_components)` |
| `PanelSystemAdapter` | 一键集成（综合适配器） | `generate_panel_for_task(task_data)`, `create_renderer(task_id)` |

**V2.0 EventBus 接口确认**：
- `EventBus()` — 单例获取
- `event_bus.subscribe(event_type, callback)` — callback: `callback(event: Event) -> None`
- `event_bus.publish(event)` — Event: `Event(event_type, source, data)`
- `event_bus.get_event_log(event_type, limit)`
- Event 属性：`event_type`, `source`, `data`, `event_id`, `timestamp`

**面板系统新增事件类型**：
- `panel.loaded` — 面板加载完成
- `panel.component_changed` — 面板组件值变更
- `panel.decision_made` — Human Agent 做出决策
- `panel.closed` — 面板关闭
- `decision.created` — 决策记录创建（由 SOP 引擎触发）
- `decision.made` — 决策完成
- `decision.timeout` — 决策超时
- `decision.cancelled` — 决策取消

**测试文件**：`tests/test_panel_adapters.py`（WorkBuddy 在 Phase 2 中创建）

---

### 10.3 `core/panel_decision.py` — Human Agent 决策流程状态机

**状态**：✅ 已完成  
**大小**：20KB  
**职责**：决策不是一次性按钮点击，而是完整流程——展示→等待→验证→记录→触发事件→回传引擎。

**核心实现**：
- `DecisionStatus` — 七态枚举：PENDING / IN_PROGRESS / APPROVED / REJECTED / MODIFIED / TIMEOUT / CANCELLED
- `DecisionRecord` — 完整决策快照（上下文、结果、审批链、事件记录）
- `DecisionFlowConfig` — 可配置：超时时间、多级审批、必填理由、修改次数限制、自动确认阈值
- `DecisionFlow` — 状态机：create → submit → check_timeout → cancel → get_stats

**与 SOP 执行引擎的集成接口**：
```python
# SOP 引擎遇到决策点时的调用流程
from core.panel_decision import DecisionFlow, DecisionFlowConfig

# 1. 创建决策流程
decision_flow = DecisionFlow(event_bus=event_bus, store=store, config=DecisionFlowConfig())

# 2. 遇到决策点时创建决策记录
record = decision_flow.create_decision(
    task_id=task.task_id,
    stage_id=stage.id,
    stage_name=stage.name,
    context_before={"outputs": stage.outputs, "quality_score": task.quality_score}
)

# 3. 面板渲染引擎展示决策面板，Human Agent 做出选择后
record = decision_flow.submit_decision(
    decision_id=record.decision_id,
    decision="确认",  # 或 "驳回" / "修改"
    reason="",  # 驳回/修改时必填
    modified_inputs={}  # 修改时
)

# 4. SOP 引擎订阅决策事件，收到后继续/回退/重试
event_bus.subscribe("decision.made", on_decision_made)

def on_decision_made(event):
    if event.data["decision"] == "确认":
        # 继续执行下一阶段
        pass
    elif event.data["decision"] == "驳回":
        # 回退到上一阶段
        pass
    elif event.data["decision"] == "修改":
        # 使用 modified_inputs 重新执行当前阶段
        pass
```

**测试文件**：`tests/test_panel_decision.py`（WorkBuddy 在 Phase 5 中创建）

---

## 十一、更新后的执行顺序（含细化文件）

| Phase | 内容 | 新增文件 | 依赖细化文件 |
|-------|------|---------|------------|
| P1 | 核心数据类 | `core/panel.py` | — |
| P1 | **数据提供者** | `core/panel_data_provider.py` | `core/panel_renderer.py`（DataProvider接口） |
| P2 | 面板生成器 | `core/panel_generator.py` | `core/panel.py` |
| P2 | **适配器** | `core/panel_adapters.py` | `core/panel.py`, `core/event_bus.py` |
| P3 | 渲染引擎基类 | `core/panel_renderer.py` | — |
| P4 | CLI 渲染引擎 | `renderers/cli_renderer.py` | `core/panel_data_provider.py` |
| P4 | **决策状态机** | `core/panel_decision.py` | `core/event_bus.py` |
| P5 | 整合验证 | `examples/panel_demo.py` | 所有上述文件 |

---

## 十二、更新后的测试规格

### 新增测试文件

| 测试文件 | 测试内容 | 对应细化文件 | Phase |
|---------|---------|-----------|-------|
| `tests/test_panel_data_provider.py` | StoreDataProvider 解析所有数据源格式 | `core/panel_data_provider.py` | P1 |
| `tests/test_panel_adapters.py` | TaskAdapter 适配、EventAdapter 事件发布、ArmoryAdapter 组件转换 | `core/panel_adapters.py` | P2 |
| `tests/test_panel_decision.py` | DecisionFlow 状态机完整流程、超时处理、多级审批 | `core/panel_decision.py` | P4 |

### 测试深度要求

**`test_panel_data_provider.py`**（必须覆盖）：
- `task.status` → 从 Store 获取任务状态
- `task.stages[0].name` → 路径导航到数组元素
- `task.current_stage` → 特殊字段计算
- `intel:strategist_brief` → 前缀键直接读取
- `family:health_overview` → 前缀键直接读取
- `armory:skill:call_llm` → 武器库查询
- `data_binding` → 进一步路径导航
- 空数据 → 返回 None 不崩溃

**`test_panel_adapters.py`**（必须覆盖）：
- `TaskAdapter.adapt()` → 现有任务格式 → 面板生成器格式
- `TaskAdapter.adapt_from_store()` → 从 Store 读取并适配
- `EventAdapter.emit_panel_loaded()` → 事件正确发布到 EventBus
- `EventAdapter.emit_decision_made()` → 决策事件携带完整数据
- `ArmoryAdapter.weapon_to_panel_components()` → 武器声明 → PanelComponent
- `PanelSystemAdapter.generate_panel_for_task()` → 端到端：任务 → 面板

**`test_panel_decision.py`**（必须覆盖）：
- `create_decision()` → 状态 PENDING，事件触发
- `submit_decision("确认")` → 状态 APPROVED
- `submit_decision("驳回")` → 需要理由，状态 IN_PROGRESS → REJECTED
- `submit_decision("修改")` → 修改次数限制
- `check_timeout()` → 超时后自动驳回
- `cancel_decision()` → 状态 CANCELLED
- `get_decision_stats()` → 统计正确
- 多级审批 → 审批链记录完整

---

## 十三、关键确认：WorkBuddy 执行前必读

1. **StoreDataProvider 是面板与后端数据的唯一连接点**——没有它，CLI 渲染引擎无法获取任何数据。
2. **EventAdapter 使用 V2.0 EventBus 单例**——不要创建新的 EventBus 实例。
3. **DecisionFlow 需要 event_bus 和 store 参数**——在初始化时传入，不要硬编码。
4. **TaskAdapter 处理现有任务格式的所有字段**——如果未来任务格式变更，只需修改 TaskAdapter。
5. **所有细化文件已完成，不需要 WorkBuddy 再设计**——直接按代码实现，或按需调整。

---

*细化文件索引结束。三个 P0 阻塞级缺口已补齐。WorkBuddy 可以开始执行。*
