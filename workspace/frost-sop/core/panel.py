"""
FROST V5.0 第六个原子——Panel（交互面板）

PHILOSOPHY: 面板不是UI代码，面板是元数据驱动的UI配置。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any

# ────────────────────────────────────────────────────────────────────────────
# 面板类型
# ────────────────────────────────────────────────────────────────────────────


class PanelType(Enum):
    """面板类型——根据使用场景定义"""

    COCKPIT = "cockpit"  # 驾驶舱：家族概览（君主日常查看）
    TASK = "task"  # 任务面板：单个任务的驾驶舱（执行中查看）
    DECISION = "decision"  # 决策面板：Human Agent 做决策（审批/驳回/修改）
    BRIEFING = "briefing"  # 简报面板：军师/长老/免疫系统的简报展示
    LINEAGE = "lineage"  # 族谱面板：任务血缘、家族历史可视化
    ALERT = "alert"  # 告警面板：免疫系统告警、紧急通知
    CONFIG = "config"  # 配置面板：宪法规则、平台绑定、武器管理


# ────────────────────────────────────────────────────────────────────────────
# 布局系统
# ────────────────────────────────────────────────────────────────────────────


class LayoutType(Enum):
    """布局类型"""

    SINGLE = "single"  # 单列布局（所有组件垂直排列）
    SPLIT = "split"  # 分栏布局（左右/上下分栏）
    TABS = "tabs"  # 标签页布局（每个标签一个区域）
    GRID = "grid"  # 网格布局（组件按网格排列）
    OVERLAY = "overlay"  # 叠加布局（弹窗/模态框）


@dataclass
class Region:
    """布局区域"""

    name: str  # 区域名称（如 "input", "output", "decision"）
    ratio: float = 1.0  # 区域占比（0.0-1.0，仅 SPLIT 布局有效）
    content_type: str = ""  # 区域内容类型标识（如 "current_stage_inputs"）
    components: list[str] = field(default_factory=list)  # 组件ID列表


@dataclass
class Layout:
    """面板布局"""

    type: LayoutType = LayoutType.SINGLE
    regions: list[Region] = field(default_factory=list)

    # 响应式断点（可选，Web渲染时有效）
    breakpoints: dict[str, str] = field(default_factory=dict)


# ────────────────────────────────────────────────────────────────────────────
# 组件系统
# ────────────────────────────────────────────────────────────────────────────


class ComponentType(Enum):
    """组件类型——所有UI组件的原子分类"""

    # 输入组件
    TEXT_INPUT = "text_input"  # 单行文本输入
    TEXTAREA = "textarea"  # 多行文本输入
    CODE_EDITOR = "code_editor"  # 代码编辑器（带语法高亮）
    SELECT = "select"  # 下拉选择
    MULTI_SELECT = "multi_select"  # 多选
    FILE_UPLOAD = "file_upload"  # 文件上传

    # 输出组件
    TEXT_DISPLAY = "text_display"  # 纯文本展示
    MARKDOWN = "markdown"  # Markdown 渲染
    CODE_PREVIEW = "code_preview"  # 代码预览（带语法高亮）
    CHART = "chart"  # 图表（柱状图/折线图/饼图）
    TABLE = "table"  # 表格
    IMAGE = "image"  # 图片展示
    PDF = "pdf"  # PDF 预览

    # 决策组件
    DECISION_BUTTONS = "decision_buttons"  # 决策按钮组（确认/驳回/修改）
    CONFIRM_DIALOG = "confirm_dialog"  # 确认对话框
    RATING = "rating"  # 评分组件（1-5星）

    # 状态组件
    STATUS_BAR = "status_bar"  # 状态栏（任务状态、进度）
    PROGRESS_BAR = "progress_bar"  # 进度条
    HEALTH_GAUGE = "health_gauge"  # 健康度仪表盘（0-100）
    ALERT_BANNER = "alert_banner"  # 告警横幅

    # 组织组件
    COLLAPSIBLE_CARD = "collapsible_card"  # 可折叠卡片
    TABS = "tabs"  # 标签页容器
    DIVIDER = "divider"  # 分割线

    # 导航组件
    TASK_LIST = "task_list"  # 任务列表
    BREADCRUMB = "breadcrumb"  # 面包屑导航
    TIMELINE = "timeline"  # 时间线

    # 特殊组件
    CHAT = "chat"  # 聊天界面（与Agent对话）
    GRAPH = "graph"  # 图谱可视化（节点/边图）
    TERMINAL = "terminal"  # 终端模拟器（日志输出）


@dataclass
class PanelComponent:
    """面板组件——面板的基本构建单元"""

    id: str  # 组件唯一ID（如 "comp:task_status"）
    type: ComponentType  # 组件类型

    # 基础属性
    label: str = ""  # 组件标签/标题
    description: str = ""  # 组件描述/提示文本

    # 数据源——组件展示的数据从哪来
    data_source: str = ""  # 数据源标识（如 "task.status", "intel:strategist_brief"）
    data_binding: str = ""  # 数据绑定路径（如 "task.stages[0].output"）

    # 交互属性——组件如何响应用户操作
    editable: bool = False  # 是否可编辑
    required: bool = False  # 是否必填（输入组件）
    readonly: bool = False  # 是否只读

    # 样式属性
    width: str = "100%"  # 宽度（CSS格式）
    height: str = "auto"  # 高度（CSS格式）
    style: dict[str, str] = field(default_factory=dict)  # 额外CSS样式

    # 类型特定属性（根据 ComponentType 变化）
    properties: dict[str, Any] = field(default_factory=dict)
    # 例如：CODE_EDITOR 的 properties = {"language": "python", "theme": "dark"}
    # 例如：CHART 的 properties = {"chart_type": "bar", "x_axis": "date", "y_axis": "cost"}
    # 例如：DECISION_BUTTONS 的 properties = {"options": ["确认", "驳回", "修改"]}

    # 条件渲染——在什么条件下显示此组件
    show_when: str = ""  # 条件表达式（如 "task.status == 'running'"）
    hide_when: str = ""  # 条件表达式

    # 动作——用户交互后触发什么
    on_change: str = ""  # 值变更时触发的动作（如 "emit:stage_input_changed"）
    on_click: str = ""  # 点击时触发的动作（如 "emit:decision_made"）
    on_submit: str = ""  # 提交时触发的动作


# ────────────────────────────────────────────────────────────────────────────
# 主题系统
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class Theme:
    """面板主题——定义视觉风格"""

    name: str = "default"  # 主题名称
    primary_color: str = "#2c3e50"  # 主色调
    secondary_color: str = "#3498db"  # 次要色调
    background_color: str = "#ffffff"  # 背景色
    text_color: str = "#333333"  # 文字颜色
    font_family: str = "system"  # 字体
    font_size: str = "14px"  # 字体大小
    border_radius: str = "4px"  # 圆角
    spacing: str = "16px"  # 组件间距

    # 暗色模式（可选）
    dark_mode: dict[str, str] = field(default_factory=dict)


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
    panel_id: str  # 唯一ID（如 "panel:task_cockpit_auth_001"）
    panel_type: PanelType  # 面板类型
    title: str = ""  # 面板标题
    subtitle: str = ""  # 面板副标题

    # 关联关系
    task_id: str | None = None  # 关联任务ID
    sop_id: str | None = None  # 关联SOP ID
    agent_id: str | None = None  # 关联Agent ID

    # 布局
    layout: Layout = field(default_factory=lambda: Layout(type=LayoutType.SINGLE))

    # 组件
    components: list[PanelComponent] = field(default_factory=list)

    # 主题
    theme: Theme = field(default_factory=Theme)

    # 元数据
    version: str = "1.0"  # 面板版本
    created_at: str = ""  # 创建时间（ISO格式）
    updated_at: str = ""  # 更新时间

    # 交互配置
    refresh_interval: int | None = None  # 自动刷新间隔（秒），None=不刷新
    auto_close: int | None = None  # 自动关闭时间（秒），None=不关闭

    # 权限
    allowed_roles: list[str] = field(
        default_factory=list
    )  # 允许查看的角色（如 ["monarch", "strategist"]）

    # 动作绑定——面板级别的事件响应
    actions: dict[str, str] = field(
        default_factory=dict
    )  # {"on_load": "emit:panel_loaded", "on_close": "emit:panel_closed"}

    # 扩展属性
    meta: dict[str, Any] = field(default_factory=dict)  # 扩展字段

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典"""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PanelDefinition:
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
    values: dict[str, Any] = field(
        default_factory=dict
    )  # {"comp:input_1": "用户输入", "comp:rating": 4}

    # 展开/折叠状态
    expanded: dict[str, bool] = field(default_factory=dict)  # {"comp:briefing": True}

    # 当前激活的标签页
    active_tab: str = ""

    # 滚动位置
    scroll_position: int = 0

    # 最后更新时间
    last_updated: str = ""

    # 用户交互记录
    interaction_log: list[dict[str, Any]] = field(default_factory=list)
    # [{"timestamp": "2026-06-28T10:00:00", "component_id": "comp:btn_approve", "action": "click", "value": "确认"}]


# ────────────────────────────────────────────────────────────────────────────
# 面板快照——历史记录
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class PanelSnapshot:
    """面板快照——任务完成后保存的面板状态"""

    snapshot_id: str
    panel_id: str
    task_id: str | None

    # 快照时的面板定义
    panel_definition: PanelDefinition

    # 快照时的面板状态
    panel_state: PanelState

    # 快照时的任务状态
    task_status: str = ""

    # 快照时间
    captured_at: str = ""
