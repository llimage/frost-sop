# Solo-Ops-Platform V0.10.0 界面重构 — WorkBuddy 任务书

**项目路径**: `D:/my_ai/Solo-Ops-Platform`
**目标**: 将混乱的多页签界面重构为单页仪表盘（对标 MyCompany 仪表盘风格）
**技术约束**: 保持 Streamlit 框架，不引入新依赖
**执行方式**: WorkBuddy 本地编码，按任务顺序逐个完成

---

## 任务总览

| 阶段 | 任务 | 文件 | 依赖 |
|------|------|------|------|
| T1 | 基础设施层 | `frontend_v2/` 目录 + 4 个基础文件 | 无 |
| T2 | 核心组件层 | `frontend_v2/components/` 7 个组件 | T1 |
| T3 | 页面组装层 | `frontend_v2/pages/` 4 个页面 | T1+T2 |
| T4 | 入口重写 | `app.py` 重写 + 旧文件备份 | T1+T2+T3 |

---

## 任务 T1：基础设施层

### T1.1 创建目录结构

**操作**: 创建以下空目录
```
frontend_v2/
frontend_v2/components/
frontend_v2/pages/
```

### T1.2 创建 `frontend_v2/__init__.py`

**内容**: 空文件或简单包声明
```python
"""Solo-Ops-Platform V0.10.0 前端重构层."""
```

### T1.3 创建 `frontend_v2/data.py`

**目标**: 硬编码 Solo-Ops-Platform 自身开发进度数据，作为仪表盘展示内容

**必须包含的数据结构**:

```python
PROJECT = {
    "name": "Solo-Ops-Platform V0.10.0",
    "description": "一人公司 AI 指挥平台 · 界面重构专项",
    "status": "进行中",
    "kpi": {
        "task_progress": {"current": 9, "total": 10, "label": "步骤"},
        "running_agents": {"count": 1, "label": "agents"},
        "cost": {"current": 0.0, "total": 50.0, "currency": "¥", "label": ""},
        "eta": {"value": "~2", "unit": "天", "label": "预计完成"}
    },
    "budget": {
        "used_percent": 90,
        "breakdown": [
            {"name": "前端", "cost": 20.0},
            {"name": "后端", "cost": 15.0},
            {"name": "测试", "cost": 10.0},
            {"name": "文档", "cost": 5.0}
        ],
        "total": 50.0,
        "remaining": 5.0
    },
    "agents": [
        {"id": "ceo", "short_id": "CEO", "name": "CEO Agent", "role": "Orchestrator", "status": "monitoring", "status_text": "执行计划已确认，监控中", "provider": "DeepSeek", "cost": 5.0, "progress": None, "color": "#4F46E5", "icon": "🤖"},
        {"id": "researcher", "short_id": "TR", "name": "Tech Researcher", "role": "行业研究", "status": "done", "status_text": "知识库架构分析完成", "provider": "DeepSeek", "cost": 8.0, "progress": 100, "color": "#059669", "icon": "🔍"},
        {"id": "writer", "short_id": "PW", "name": "Proposal Writer", "role": "提案撰写", "status": "idle", "status_text": "待命", "provider": "DeepSeek", "cost": 0.0, "progress": None, "color": "#D97706", "icon": "✍️"},
        {"id": "analyst", "short_id": "RA", "name": "Requirements Analyst", "role": "需求分析", "status": "done", "status_text": "PRD 文档已输出", "provider": "DeepSeek", "cost": 3.0, "progress": 100, "color": "#7C3AED", "icon": "📋"},
        {"id": "architect", "short_id": "SA", "name": "AI Solution Architect", "role": "方案架构", "status": "done", "status_text": "模块拆分方案已确认", "provider": "DeepSeek", "cost": 4.0, "progress": 100, "color": "#DC2626", "icon": "🏗️"},
        {"id": "data_platform", "short_id": "DP", "name": "Data Platform Designer", "role": "数据平台", "status": "done", "status_text": "记忆/知识库数据层完成", "provider": "OpenAI", "cost": 6.0, "progress": 100, "color": "#0891B2", "icon": "🗄️"},
        {"id": "estimator", "short_id": "PE", "name": "Project Estimator", "role": "成本估算", "status": "done", "status_text": "工时与成本估算完成", "provider": "DeepSeek", "cost": 2.0, "progress": 100, "color": "#BE185D", "icon": "📊"},
        {"id": "qa", "short_id": "QA", "name": "QA Reviewer", "role": "质量审核", "status": "running", "status_text": "正在执行界面重构验收测试...", "provider": "DeepSeek", "cost": 1.0, "progress": 65, "color": "#4338CA", "icon": "🔍"}
    ],
    "logs": [
        {"time": "10:00", "agent_id": "ceo", "agent_name": "CEO", "message": "执行计划已确认，监控中"},
        {"time": "10:05", "agent_id": "researcher", "agent_name": "研究员", "message": "知识库架构分析完成"},
        {"time": "10:12", "agent_id": "writer", "agent_name": "写手", "message": "前端组件文档已输出"},
        {"time": "10:15", "agent_id": "qa", "agent_name": "QA", "message": "正在执行界面重构验收测试..."}
    ]
}
```

**必须提供的函数**:
```python
def get_project() -> dict:
    """返回完整的 PROJECT 字典."""

def get_agent(agent_id: str) -> dict | None:
    """根据 ID 返回单个 agent 字典，未找到返回 None."""

def get_running_agents() -> list:
    """返回 status 为 running 或 monitoring 的 agent 列表."""

def get_done_agents() -> list:
    """返回 status 为 done 的 agent 列表."""

def add_log(agent_id: str, agent_name: str, message: str) -> None:
    """在 logs 列表追加一条新日志，时间戳自动使用当前 HH:MM."""
```

**验收标准**:
- [ ] `get_project()` 返回的字典包含完整的 name、kpi、budget、agents、logs 键
- [ ] `get_agent("ceo")` 返回 CEO Agent 字典
- [ ] `get_running_agents()` 返回 2 个 agent（CEO + QA）
- [ ] `get_done_agents()` 返回 5 个 agent
- [ ] `add_log("user", "用户", "测试消息")` 后 logs 长度变为 5

### T1.4 创建 `frontend_v2/state.py`

**目标**: 统一封装 Streamlit session_state，禁止任何页面直接操作 `st.session_state`

**必须提供的函数**:
```python
def init_state() -> None:
    """初始化所有 session_state 键，如果已存在则不覆盖."""
    # 需要初始化的键：
    # - "current_page": "dashboard"
    # - "task_topic": ""
    # - "task_result": ""
    # - "task_running": False
    # - "selected_agent": None
    # - "show_settings": False

def get_current_page() -> str:
def set_current_page(page: str) -> None:

def get_task_topic() -> str:
def set_task_topic(topic: str) -> None:

def get_task_result() -> str:
def set_task_result(result: str) -> None:

def get_task_running() -> bool:
def set_task_running(running: bool) -> None:

def get_selected_agent() -> str | None:
def set_selected_agent(agent_id: str | None) -> None:

def get_show_settings() -> bool:
def set_show_settings(show: bool) -> None:
```

**重要约束**:
- `import streamlit as st` 必须在函数内部导入，避免模块级导入问题
- 所有 getter/setter 必须成对出现
- `init_state()` 使用 `st.session_state.setdefault()` 避免覆盖已有值

**验收标准**:
- [ ] `init_state()` 执行后所有键都存在
- [ ] `set_current_page("history")` 后 `get_current_page()` 返回 "history"
- [ ] `set_task_running(True)` 后 `get_task_running()` 返回 True

### T1.5 创建 `frontend_v2/styles.py`

**目标**: 全局 CSS 样式，通过 `st.markdown(..., unsafe_allow_html=True)` 注入

**必须包含的 CSS 内容**:

```css
/* 全局背景 */
.main { background-color: #F1F5F9 !important; }

/* 卡片通用 */
.sop-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

/* KPI 卡片 */
.sop-kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 20px;
    text-align: center;
}
.sop-kpi-value {
    font-size: 2em;
    font-weight: 700;
    color: #1E293B;
    line-height: 1.2;
}
.sop-kpi-label {
    font-size: 0.85em;
    color: #64748B;
    margin-top: 4px;
}

/* Agent 卡片 */
.sop-agent-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px;
    position: relative;
    overflow: hidden;
}
.sop-agent-avatar {
    width: 40px;
    height: 40px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-weight: 600;
    font-size: 0.85em;
}
.sop-agent-status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    position: absolute;
    top: 12px;
    right: 12px;
}
.sop-agent-status-dot.idle { background: #94A3B8; }
.sop-agent-status-dot.running { background: #3B82F6; box-shadow: 0 0 6px rgba(59,130,246,0.5); }
.sop-agent-status-dot.done { background: #10B981; }
.sop-agent-status-dot.error { background: #EF4444; }
.sop-agent-status-dot.monitoring { background: #3B82F6; box-shadow: 0 0 6px rgba(59,130,246,0.5); }
.sop-agent-progress {
    height: 3px;
    border-radius: 2px;
    margin-top: 8px;
}
.sop-agent-done-check {
    position: absolute;
    top: 12px;
    right: 28px;
    color: #10B981;
    font-size: 1.1em;
}

/* 预算条 */
.sop-budget-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px 20px;
}

/* 日志面板 */
.sop-log-panel {
    background: #0F172A;
    border-radius: 12px;
    padding: 12px 16px;
    font-family: 'Courier New', monospace;
    font-size: 0.85em;
    max-height: 200px;
    overflow-y: auto;
}
.sop-log-time { color: #64748B; }
.sop-log-agent { color: #3B82F6; font-weight: 600; }
.sop-log-message { color: #E2E8F0; }

/* CEO 面板 */
.sop-ceo-panel {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 16px;
    height: 100%;
}

/* 导航 */
.sop-nav {
    background: #FFFFFF;
    border-bottom: 1px solid #E2E8F0;
    padding: 8px 24px;
}
.sop-nav-item {
    padding: 8px 16px;
    border-radius: 8px;
    color: #64748B;
    font-size: 0.9em;
}
.sop-nav-item.active {
    background: #EFF6FF;
    color: #3B82F6;
    font-weight: 600;
}

/* Provider pill */
.sop-pill {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75em;
    font-weight: 500;
}
```

**必须提供的函数**:
```python
def inject_styles() -> None:
    """注入全局 CSS 到 Streamlit 页面."""
    # 使用 st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
```

**验收标准**:
- [ ] `inject_styles()` 函数存在且可调用
- [ ] CSS 字符串包含所有上述样式类名

---

## 任务 T2：核心组件层

**前置条件**: T1 全部完成（`frontend_v2/data.py`, `state.py`, `styles.py` 已存在）

### T2.1 创建 `frontend_v2/components/__init__.py`
空文件。

### T2.2 创建 `frontend_v2/components/navbar.py`

**目标**: 顶部导航栏，4 个页面入口 + 系统状态灯

**函数签名**:
```python
def render_navbar() -> str:
    """
    渲染顶部导航栏。
    返回当前选中的页面名称（"dashboard"/"history"/"knowledge"/"settings"）。
    """
```

**实现要求**:
- 使用 `st.segmented_control` 实现 4 个导航项
- 默认选中 "dashboard"
- 最右侧显示绿色状态灯（● 正常）
- 样式使用 `.sop-nav` 和 `.sop-nav-item`
- 从 `frontend_v2.state` 导入 `get_current_page`, `set_current_page`

**验收标准**:
- [ ] 返回字符串类型页面名
- [ ] 4 个导航项全部显示
- [ ] 默认选中 "dashboard"

### T2.3 创建 `frontend_v2/components/kpi_cards.py`

**目标**: 4 个 KPI 指标卡片

**函数签名**:
```python
def render_kpi_cards() -> None:
    """
    渲染 4 个 KPI 卡片。
    使用 st.columns(4) 布局。
    数据来源：get_project()["kpi"]
    """
```

**实现要求**:
- 4 列等宽 `st.columns(4)`
- 每个卡片用 `st.markdown(..., unsafe_allow_html=True)` 渲染 HTML
- 卡片 CSS 类名: `.sop-kpi-card`, `.sop-kpi-value`, `.sop-kpi-label`
- 4 个卡片内容:
  1. 任务进度: 大数字 "9/10" + 小字 "步骤"
  2. 运行中: 大数字 "1" + 小字 "agents"
  3. 已消耗: 大数字 "¥0.00" + 小字 "/¥50"
  4. 预计完成: 大数字 "~2" + 小字 "天"
- 从 `frontend_v2.data` 导入 `get_project`

**验收标准**:
- [ ] 4 个白色圆角卡片横向排列
- [ ] 大数字使用 `<div class="sop-kpi-value">`
- [ ] 标签使用 `<div class="sop-kpi-label">`

### T2.4 创建 `frontend_v2/components/budget_bar.py`

**目标**: 预算消耗进度条

**函数签名**:
```python
def render_budget_bar() -> None:
    """
    渲染预算消耗进度条。
    数据来源：get_project()["budget"]
    """
```

**实现要求**:
- 全宽卡片，CSS 类名 `.sop-budget-card`
- 顶部一行：左侧标题「开发投入」，右侧显示各模块成本明细（pill 标签）
- 中间：`st.progress()` 显示 `used_percent / 100` (即 0.9)
- 底部一行：左侧 "90% 已完成"，右侧 "剩余 ¥5.0"
- 成本明细 pill 样式：
  - DeepSeek: 背景 `#DBEAFE`，文字 `#1E40AF`
  - OpenAI: 背景 `#F3E8FF`，文字 `#6B21A8`
- 从 `frontend_v2.data` 导入 `get_project`

**验收标准**:
- [ ] 显示 `st.progress(0.9)`
- [ ] 顶部显示 "前端 ¥20 · 后端 ¥15 · 测试 ¥10 · 文档 ¥5"
- [ ] 底部显示 "90% 已完成" 和 "剩余 ¥5.0"

### T2.5 创建 `frontend_v2/components/agent_grid.py`

**目标**: Agent 团队卡片网格（8 个 Agent，2 行 × 4 列）

**函数签名**:
```python
def render_agent_grid() -> None:
    """
    渲染 Agent 团队卡片网格。
    数据来源：get_project()["agents"]
    """
```

**实现要求**:
- 标题「AI 员工团队」
- 每行 4 个卡片，共 2 行（`st.columns(4)` 循环两次）
- 每个卡片 HTML 结构（用 `st.markdown(..., unsafe_allow_html=True)`）:

```html
<div class="sop-agent-card">
  <!-- 顶部行：头像 + 状态灯 -->
  <div style="display:flex; justify-content:space-between; align-items:center;">
    <div class="sop-agent-avatar" style="background:{color};">{short_id}</div>
    <div class="sop-agent-status-dot {status}"></div>
  </div>
  <!-- 如果 done，显示绿色 ✓ -->
  <div class="sop-agent-done-check">✓</div>
  <!-- 名称和角色 -->
  <div style="margin-top:12px;">
    <div style="font-weight:600; color:#1E293B;">{name}</div>
    <div style="font-size:0.85em; color:#64748B;">{role}</div>
  </div>
  <!-- 状态文字 -->
  <div style="margin-top:8px; font-size:0.8em; color:#94A3B8;">{status_text}</div>
  <!-- 进度条（仅 running/monitoring） -->
  <div class="sop-agent-progress" style="width:{progress}%; background:{color};"></div>
  <!-- 底部：Provider pill + 成本 -->
  <div style="margin-top:12px; display:flex; justify-content:space-between; align-items:center;">
    <span class="sop-pill" style="background:{pill_bg}; color:{pill_color};">{provider}</span>
    <span style="font-size:0.85em; color:#64748B;">¥{cost}</span>
  </div>
</div>
```

- 状态灯颜色映射:
  - `idle` → `#94A3B8` (灰色)
  - `running` → `#3B82F6` + `box-shadow: 0 0 6px rgba(59,130,246,0.5)`
  - `monitoring` → `#3B82F6` + 同上发光
  - `done` → `#10B981` (绿色)
  - `error` → `#EF4444` (红色)
- Provider pill 颜色:
  - DeepSeek → 背景 `#DBEAFE`，文字 `#1E40AF`
  - OpenAI → 背景 `#F3E8FF`，文字 `#6B21A8`
- 进度条: 仅当 `progress is not None` 且 `status in ("running", "monitoring")` 时显示
- done 状态的 ✓: 仅当 `status == "done"` 时显示
- 从 `frontend_v2.data` 导入 `get_project`

**验收标准**:
- [ ] 8 个 Agent 卡片，2 行 × 4 列
- [ ] 每个卡片有彩色圆形头像（short_id 白色文字）
- [ ] 状态灯颜色正确（QA 是蓝色发光，研究员是绿色，写手是灰色）
- [ ] done 状态的卡片右上角有绿色 ✓
- [ ] running/monitoring 状态有进度条
- [ ] 底部有 Provider pill 和成本

### T2.6 创建 `frontend_v2/components/log_panel.py`

**目标**: 实时日志面板（深色终端风格）

**函数签名**:
```python
def render_log_panel() -> None:
    """
    渲染实时日志面板。
    数据来源：get_project()["logs"]
    """
```

**实现要求**:
- 标题「实时日志」
- 深色背景面板 `#0F172A`，圆角 12px，固定高度 200px
- 每条日志格式: `<span class="sop-log-time">[HH:MM]</span> <span class="sop-log-agent">Agent名</span>: <span class="sop-log-message">消息</span>`
- 所有日志用 `<br>` 连接，包在一个 `<div class="sop-log-panel">` 中
- 从 `frontend_v2.data` 导入 `get_project`

**验收标准**:
- [ ] 深色背景终端风格
- [ ] 至少显示 4 条日志
- [ ] 时间戳灰色，Agent 名蓝色粗体，消息白色

### T2.7 创建 `frontend_v2/components/ceo_panel.py`

**目标**: 右侧 CEO 对话面板

**函数签名**:
```python
def render_ceo_panel() -> None:
    """
    渲染右侧 CEO 对话面板。
    包含 CEO 信息、执行计划摘要、输入框、快捷按钮。
    """
```

**实现要求**:
- 整体用 `<div class="sop-ceo-panel">` 包裹
- 从上到下:
  1. CEO 信息行: 左侧彩色圆形头像（CEO 的 color `#4F46E5` + short_id "CEO"），右侧 "CEO Agent" + 蓝色状态灯
  2. `st.divider()`
  3. 执行计划摘要（灰色小字）: "执行计划已启动\n界面重构专项\n进行中"
  4. `st.divider()`
  5. 对话输入框: `st.text_input("", placeholder="输入指令...", key="ceo_input")`
  6. 发送按钮: `st.button("发送", type="primary", key="ceo_send", use_container_width=True)`
  7. 快捷按钮行: 3 个 `st.button`（"进度如何？", "成本正常吗？", "关注国产化替代"），用 `st.columns(3)` 排列
- 当用户点击发送按钮或快捷按钮时:
  - 调用 `set_task_topic()` 保存输入内容
  - 调用 `add_log("user", "用户", f"下达指令: {topic}")` 添加日志
  - 显示 `st.toast("指令已下达")`
- 从 `frontend_v2.data` 导入 `get_project`, `add_log`
- 从 `frontend_v2.state` 导入 `set_task_topic`

**验收标准**:
- [ ] CEO 头像和名称显示正确
- [ ] 执行计划摘要显示
- [ ] 输入框 + 发送按钮
- [ ] 3 个快捷按钮横向排列
- [ ] 点击后调用 set_task_topic 和 add_log

### T2.8 创建 `frontend_v2/components/task_output.py`

**目标**: 任务执行结果展示区

**函数签名**:
```python
def render_task_output() -> None:
    """
    渲染任务执行结果展示区。
    处理三种状态：空状态 / 运行中 / 有结果。
    """
```

**实现要求**:
- 标题「任务执行结果」
- 三种状态分支:
  1. **运行中**: `get_task_running() == True` → 显示 `st.spinner("Agent 正在协作执行中...")`
  2. **有结果**: `get_task_result()` 非空 → 用白色卡片展示结果，左边框 `#3B82F6`，圆角 12px，padding 20px
  3. **空状态**: 以上都不满足 → 居中显示引导文案:
     - 大 emoji "📋"
     - "暂无执行结果"
     - "在右侧 CEO 面板输入任务主题，Agent 团队将协作完成分析。"
- 从 `frontend_v2.state` 导入 `get_task_result`, `get_task_running`

**验收标准**:
- [ ] 空状态有引导文案
- [ ] 运行中显示 spinner
- [ ] 有结果时显示白色卡片

---

## 任务 T3：页面组装层

**前置条件**: T1 + T2 全部完成

### T3.1 创建 `frontend_v2/pages/__init__.py`
空文件。

### T3.2 创建 `frontend_v2/pages/dashboard.py`

**目标**: 主仪表盘页面，唯一核心页面

**函数签名**:
```python
def render_dashboard() -> None:
    """
    渲染主仪表盘页面。
    从上到下：标题区 → KPI → 预算 → 左右分栏(左侧: Agent+日志+结果, 右侧: CEO面板)
    """
```

**实现要求**:
1. 项目标题区:
   - 大标题: "Solo-Ops-Platform V0.10.0 界面重构"
   - 小字: "一人公司 AI 指挥平台 · 进行中"
2. 调用 `render_kpi_cards()`
3. 调用 `render_budget_bar()`
4. 主内容区左右分栏 `st.columns([3, 1])`:
   - 左侧 (占 75%):
     - 调用 `render_agent_grid()`
     - `st.divider()`
     - 调用 `render_log_panel()`
     - `st.divider()`
     - 调用 `render_task_output()`
   - 右侧 (占 25%):
     - 调用 `render_ceo_panel()`

**导入要求**:
```python
from frontend_v2.components.kpi_cards import render_kpi_cards
from frontend_v2.components.budget_bar import render_budget_bar
from frontend_v2.components.agent_grid import render_agent_grid
from frontend_v2.components.log_panel import render_log_panel
from frontend_v2.components.ceo_panel import render_ceo_panel
from frontend_v2.components.task_output import render_task_output
```

**验收标准**:
- [ ] 标题区显示正确
- [ ] KPI 卡片在预算条上方
- [ ] 左右分栏比例 3:1
- [ ] 左侧从上到下：Agent 网格 → 日志 → 任务结果
- [ ] 右侧是 CEO 面板

### T3.3 创建 `frontend_v2/pages/history.py`

**目标**: 简化版历史任务页面

**函数签名**:
```python
def render_history() -> None:
    """
    渲染历史任务页面。
    从 data/task_recorder.py 读取历史记录。
    """
```

**实现要求**:
- 标题「📋 历史任务」
- 从 `data.task_recorder` 导入 `load_all_tasks`, `delete_task`
- 如果无记录: 显示空状态 "暂无历史任务" + 引导去仪表盘
- 如果有记录: 用 `st.dataframe` 或简单列表展示
  - 每行显示: 主题（截断30字）、时间、状态、耗时
  - 每行有「查看」按钮，点击后用 `st.expander` 展开详情
  - 详情内显示完整主题、模型、模式、状态、耗时、最终输出
  - 详情内有「删除」按钮，点击后确认删除
- 保留 `delete_task` 功能

**验收标准**:
- [ ] 能读取并显示历史任务
- [ ] 空状态有引导
- [ ] 点击查看能展开详情
- [ ] 删除功能可用

### T3.4 创建 `frontend_v2/pages/knowledge.py`

**目标**: 简化版知识库页面

**函数签名**:
```python
def render_knowledge() -> None:
    """
    渲染知识库页面。
    从 knowledge 模块读取统计和文档列表。
    """
```

**实现要求**:
- 标题「📚 知识库」
- 从 `knowledge` 导入 `list_documents`, `get_knowledge_stats`
- 统计信息卡片: 文档数、分块数、后端类型
- 文档列表: 简单表格或列表，显示 doc_name、category、chunk_count、import_time
- 空状态: "知识库空空如也" + 引导文案
- **不实现上传功能**（保持简化）

**验收标准**:
- [ ] 显示知识库统计
- [ ] 显示文档列表
- [ ] 空状态有引导

### T3.5 创建 `frontend_v2/pages/settings.py`

**目标**: 设置页面

**函数签名**:
```python
def render_settings() -> None:
    """
    渲染设置页面。
    API Key、模型选择、基础配置。
    """
```

**实现要求**:
- 标题「⚙️ 设置」
- API Key 输入: `st.text_input("API Key", type="password", value=os.getenv("DEEPSEEK_API_KEY", ""))`
- 提供商选择: `st.selectbox("AI 提供商", ["DeepSeek", "OpenAI"])`
- Base URL: `st.text_input("Base URL", value="https://api.deepseek.com")`
- 模型名称: `st.text_input("模型名称", value="deepseek-chat")`
- 保存按钮: `st.button("保存配置", type="primary")`
- 保存时设置环境变量:
  ```python
  os.environ["DEEPSEEK_API_KEY"] = api_key
  os.environ["LLM_BASE_URL"] = base_url
  os.environ["LLM_MODEL_NAME"] = model_name
  ```
- 保存成功后显示 `st.success("配置已保存")`

**验收标准**:
- [ ] 4 个配置项全部显示
- [ ] 保存按钮可用
- [ ] 保存后设置环境变量

---

## 任务 T4：入口重写

**前置条件**: T1 + T2 + T3 全部完成

### T4.1 备份旧 `app.py`

**操作**: 将现有 `app.py`（1760 行）复制为 `app_v090.py`

```bash
cp app.py app_v090.py
```

### T4.2 重写 `app.py`

**目标**: 精简入口文件（50-80 行）

**必须包含的内容**:

```python
"""
app.py - Solo-Ops-Platform 入口（V0.10.0 仪表盘版）
"""
import streamlit as st

from frontend_v2.styles import inject_styles
from frontend_v2.state import init_state, get_current_page, set_current_page
from frontend_v2.pages.dashboard import render_dashboard
from frontend_v2.pages.history import render_history
from frontend_v2.pages.knowledge import render_knowledge
from frontend_v2.pages.settings import render_settings

st.set_page_config(
    page_title="Solo-Ops-Platform · 一人公司指挥平台",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="collapsed",  # 关键：收起侧栏
)

# 注入全局样式
inject_styles()

# 初始化状态
init_state()

# 顶部导航（返回当前页面）
from frontend_v2.components.navbar import render_navbar
current_page = render_navbar()

# 如果导航切换了页面，更新状态
if current_page != get_current_page():
    set_current_page(current_page)
    st.rerun()

# 根据当前页面渲染内容
if current_page == "dashboard":
    render_dashboard()
elif current_page == "history":
    render_history()
elif current_page == "knowledge":
    render_knowledge()
elif current_page == "settings":
    render_settings()
```

**验收标准**:
- [ ] 新 `app.py` 行数在 50-80 行之间
- [ ] 旧 `app.py` 已备份为 `app_v090.py`
- [ ] `st.set_page_config` 包含 `initial_sidebar_state="collapsed"`
- [ ] 默认打开显示仪表盘
- [ ] 顶部导航可切换 4 个页面
- [ ] 页面切换时 `st.rerun()` 正确触发

---

## 全局约束

1. **不要修改任何旧模块**: `agents/`, `tools/`, `memory/`, `knowledge/`, `config/`, `data/`, `crew.py` 全部保持不动
2. **只创建新文件**: 所有工作都在 `frontend_v2/` 目录和 `app.py` 中进行
3. **Streamlit 导入**: `import streamlit as st` 可以在模块顶部导入（组件和页面文件）
4. **HTML 渲染**: 所有自定义样式通过 `st.markdown(..., unsafe_allow_html=True)` 注入
5. **编码**: 所有文件使用 UTF-8 编码
6. **颜色严格**: 使用任务书中指定的色值，不要自创颜色

---

## 执行顺序

```
T1.1 → T1.2 → T1.3 → T1.4 → T1.5
                    ↓
T2.1 → T2.2 → T2.3 → T2.4 → T2.5 → T2.6 → T2.7 → T2.8
                    ↓
T3.1 → T3.2 → T3.3 → T3.4 → T3.5
                    ↓
T4.1 → T4.2
```

---

## 最终验收（全部完成后）

- [ ] `streamlit run app.py` 启动后默认显示仪表盘
- [ ] 侧栏默认收起
- [ ] 顶部 4 个导航项可切换页面
- [ ] 仪表盘显示：标题 → 4 个 KPI → 预算条 → Agent 网格(2×4) → 日志面板 → 任务结果区 → CEO 面板
- [ ] 8 个 Agent 卡片状态正确（QA 蓝色运行中，研究员绿色完成，写手灰色待命）
- [ ] 日志面板显示 4 条深色终端风格日志
- [ ] CEO 面板有输入框和 3 个快捷按钮
- [ ] 历史页面能读取并显示历史任务
- [ ] 知识库页面显示统计和文档列表
- [ ] 设置页面有 API Key 和模型配置
- [ ] 旧 `app.py` 已备份为 `app_v090.py`

---

*任务书版本: V1.0*  
*日期: 2026-06-05*
