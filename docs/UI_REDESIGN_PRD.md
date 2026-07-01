# Solo-Ops-Platform V0.10.0 界面重构 PRD

**版本**: V0.10.0 — 「员工仪表盘」专项
**目标**: 将混乱的多页签界面重构为单页仪表盘，用 Solo-Ops 自身开发进度作为真实数据展示
**风格对标**: MyCompany 仪表盘（陈杨参考图）
**技术约束**: 保持 Streamlit 框架，不引入新依赖

---

## 一、设计原则

1. **单页优先**: 默认打开就是仪表盘，所有核心信息一眼看完
2. **Agent 即员工**: 把 researcher/writer/CEO 等做成「员工工牌」，有头像、状态、进度、成本
3. **实时透明**: 任务进度、Agent 状态、成本消耗、预计完成时间全部可视化
4. **对话式交互**: 右侧固定 CEO 对话面板，像和项目经理聊天一样下达指令
5. **零跳转**: 除「历史任务」「知识库」「设置」外，核心操作全部在仪表盘完成

---

## 二、信息架构

```
┌─────────────────────────────────────────────────────────────┐
│  🔮 Solo-Ops-Platform    [仪表盘] [历史] [知识库] [设置]      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Solo-Ops-Platform V0.10.0 界面重构                         │
│  一人公司 AI 指挥平台 · 进行中                              │
│                                                             │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐            │
│  │ 9/10   │ │ 1 运行 │ │ ¥0.00  │ │ ~2天   │   ← KPI     │
│  │ 步骤   │ │ Agents │ │ /¥50   │ │ 预计   │            │
│  └────────┘ └────────┘ └────────┘ └────────┘            │
│                                                             │
│  开发投入 ▓▓▓▓▓▓▓▓▓▓ 90% 已完成                             │
│  前端 ¥20 · 后端 ¥15 · 测试 ¥10 · 文档 ¥5                   │
│                                                             │
│  AI 员工团队                                                 │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 🤖 CEO      │ │ 🔍 研究员   │ │ ✍️ 写手     │           │
│  │ 监控中      │ │ 已完成 ✓  │ │ 待命     │              │
│  │ ¥5.00      │ │ ¥8.00      │ │ -        │              │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐           │
│  │ 📋 需求分析 │ │ 🏗️ 架构师   │ │ 🗄️ 数据平台 │           │
│  │ 已完成 ✓  │ │ 已完成 ✓  │ │ 已完成 ✓  │              │
│  │ ¥3.00      │ │ ¥4.00      │ │ ¥6.00      │              │
│  └─────────────┘ └─────────────┘ └─────────────┘           │
│  ┌─────────────┐ ┌─────────────┐                           │
│  │ 📊 成本估算 │ │ 🔍 QA审核  │ │                          │
│  │ 已完成 ✓  │ │ 运行中 ▓▓▓ │ │                          │
│  │ ¥2.00      │ │ ¥1.00      │ │                          │
│  └─────────────┘ └─────────────┘                           │
│                                                             │
│  实时日志                                                    │
│  [10:00] CEO: 执行计划已确认，监控中                         │
│  [10:05] 研究员: 知识库架构分析完成                          │
│  [10:12] 写手: 前端组件文档已输出                            │
│  [10:15] QA: 正在执行界面重构验收测试...                     │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────┐ ┌───────────────┐ │
│  │                                     │ │ 🤖 CEO Agent  │ │
│  │  任务执行结果展示区（可折叠）       │ │ ● 监控中      │ │
│  │                                     │ │               │ │
│  │  当用户下达新任务时，结果在此显示    │ │ 执行计划已启动│ │
│  │                                     │ │ 界面重构专项  │ │
│  │                                     │ │ 进行中        │ │
│  │                                     │ │               │ │
│  │                                     │ │ [输入指令...] │ │
│  │                                     │ │ [进度如何?]   │ │
│  │                                     │ │ [成本正常吗?] │ │
│  └─────────────────────────────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## 三、模块拆分

### 新目录结构

```
frontend_v2/
├── __init__.py
├── data.py              # 项目数据源（Solo-Ops 开发进度硬编码）
├── state.py             # 统一状态管理（封装 session_state）
├── styles.py            # 全局 CSS + 主题色
├── components/
│   ├── __init__.py
│   ├── navbar.py        # 顶部导航
│   ├── kpi_cards.py     # KPI 指标卡片行
│   ├── budget_bar.py    # 预算消耗进度条
│   ├── agent_grid.py    # Agent 团队卡片网格
│   ├── log_panel.py     # 实时日志面板
│   ├── ceo_panel.py     # 右侧 CEO 对话面板
│   └── task_output.py   # 任务结果展示区
└── pages/
    ├── __init__.py
    ├── dashboard.py     # 主仪表盘（唯一核心页面）
    ├── history.py       # 历史任务（简化列表）
    ├── knowledge.py     # 知识库（简化管理）
    └── settings.py      # 设置（API Key + 模型）
```

### 入口文件

`app.py` 重写为仅 50-80 行：导入、导航路由、全局初始化。

---

## 四、数据模型

### 项目状态（`frontend_v2/data.py`）

```python
PROJECT = {
    "name": "Solo-Ops-Platform V0.10.0",
    "description": "一人公司 AI 指挥平台 · 界面重构专项",
    "status": "进行中",  # 进行中 / 已完成 / 暂停

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
        {
            "id": "ceo",
            "short_id": "CEO",
            "name": "CEO Agent",
            "role": "Orchestrator",
            "status": "monitoring",      # idle / running / done / error
            "status_text": "执行计划已确认，监控中",
            "provider": "DeepSeek",
            "cost": 5.0,
            "progress": None,            # None 或 0-100
            "color": "#4F46E5",          # 靛蓝
            "icon": "🤖"
        },
        {
            "id": "researcher",
            "short_id": "TR",
            "name": "Tech Researcher",
            "role": "行业研究",
            "status": "done",
            "status_text": "知识库架构分析完成",
            "provider": "DeepSeek",
            "cost": 8.0,
            "progress": 100,
            "color": "#059669",          # 翠绿
            "icon": "🔍"
        },
        {
            "id": "writer",
            "short_id": "PW",
            "name": "Proposal Writer",
            "role": "提案撰写",
            "status": "idle",
            "status_text": "待命",
            "provider": "DeepSeek",
            "cost": 0.0,
            "progress": None,
            "color": "#D97706",          # 琥珀
            "icon": "✍️"
        },
        {
            "id": "analyst",
            "short_id": "RA",
            "name": "Requirements Analyst",
            "role": "需求分析",
            "status": "done",
            "status_text": "PRD 文档已输出",
            "provider": "DeepSeek",
            "cost": 3.0,
            "progress": 100,
            "color": "#7C3AED",          # 紫罗兰
            "icon": "📋"
        },
        {
            "id": "architect",
            "short_id": "SA",
            "name": "AI Solution Architect",
            "role": "方案架构",
            "status": "done",
            "status_text": "模块拆分方案已确认",
            "provider": "DeepSeek",
            "cost": 4.0,
            "progress": 100,
            "color": "#DC2626",          # 红
            "icon": "🏗️"
        },
        {
            "id": "data_platform",
            "short_id": "DP",
            "name": "Data Platform Designer",
            "role": "数据平台",
            "status": "done",
            "status_text": "记忆/知识库数据层完成",
            "provider": "OpenAI",
            "cost": 6.0,
            "progress": 100,
            "color": "#0891B2",          # 青
            "icon": "🗄️"
        },
        {
            "id": "estimator",
            "short_id": "PE",
            "name": "Project Estimator",
            "role": "成本估算",
            "status": "done",
            "status_text": "工时与成本估算完成",
            "provider": "DeepSeek",
            "cost": 2.0,
            "progress": 100,
            "color": "#BE185D",          # 玫红
            "icon": "📊"
        },
        {
            "id": "qa",
            "short_id": "QA",
            "name": "QA Reviewer",
            "role": "质量审核",
            "status": "running",
            "status_text": "正在执行界面重构验收测试...",
            "provider": "DeepSeek",
            "cost": 1.0,
            "progress": 65,
            "color": "#4338CA",          # 靛青
            "icon": "🔍"
        }
    ],

    "logs": [
        {"time": "10:00", "agent_id": "ceo", "agent_name": "CEO", "message": "执行计划已确认，监控中"},
        {"time": "10:05", "agent_id": "researcher", "agent_name": "研究员", "message": "知识库架构分析完成"},
        {"time": "10:12", "agent_id": "writer", "agent_name": "写手", "message": "前端组件文档已输出"},
        {"time": "10:15", "agent_id": "qa", "agent_name": "QA", "message": "正在执行界面重构验收测试..."}
    ]
}
```

---

## 五、组件规范

### 5.1 顶部导航（Navbar）

- 左侧：Logo + 产品名
- 中间/右侧：4 个导航项（仪表盘、历史、知识库、设置）
- 当前项高亮（底部蓝线或背景色）
- 最右侧：系统状态灯（绿色=正常，黄色=降级，红色=异常）

### 5.2 KPI 卡片

- 4 列等宽
- 圆角卡片（border-radius: 12px）
- 浅色背景（#F8FAFC）
- 大数字 + 小标签
- 无图标，纯文字排版

### 5.3 Agent 卡片

- 圆角卡片，白色背景，细边框
- 顶部：彩色圆形头像（含 short_id）+ 状态灯（右侧小圆点）
- 中部：Agent 名 + 角色描述
- 下部：状态文字（灰色小字）
- 底部：Provider 标签（彩色 pill）+ 成本（右对齐）
- running 状态：卡片顶部有彩色进度条
- done 状态：右上角显示绿色 ✓

### 5.4 预算进度条

- 全宽卡片
- 左侧标题「开发投入」
- 中间：st.progress 样式进度条
- 右侧：各模块成本明细（pill 标签）
- 底部：剩余金额

### 5.5 实时日志

- 固定高度（200px），可滚动
- 深色背景终端风格（#0F172A）
- 时间戳（灰色）+ Agent 名（彩色）+ 消息（白色）
- 新日志从底部追加，自动滚动

### 5.6 CEO 右侧面板

- 固定宽度（占 25%）
- 顶部：CEO 头像 + 名称 + 状态灯
- 中部：当前执行计划摘要
- 下部：对话输入框（st.text_input）
- 底部：3 个快捷问题按钮
- 整体浅色背景，与主区区分

---

## 六、交互逻辑

### 仪表盘页

1. **页面加载**：显示项目状态、Agent 网格、日志、CEO 面板
2. **下达任务**：在 CEO 面板输入框输入主题 → 点击发送
   - CEO 面板显示「正在编排...」
   - 对应 Agent 卡片状态变为 running
   - 日志实时追加
   - 任务完成后，结果出现在「任务执行结果展示区」
3. **查看历史**：点击顶部「历史」导航 → 切换到历史列表页
4. **管理知识库**：点击「知识库」导航 → 简化版知识库页

### 状态流转

```
用户输入任务
    ↓
CEO 卡片: idle → running（思考中）
    ↓
CEO 完成编排，分派给 Agent X
    ↓
Agent X 卡片: idle → running（进度条动画）
CEO 卡片: running → monitoring（保持蓝色）
    ↓
Agent X 完成
    ↓
Agent X 卡片: running → done（绿色 ✓）
日志追加完成消息
任务结果展示区更新
```

---

## 七、样式规范

### 主题色

| 用途 | 色值 |
|------|------|
| 主背景 | #F1F5F9 |
| 卡片背景 | #FFFFFF |
| 卡片边框 | #E2E8F0 |
| 主文字 | #1E293B |
| 次要文字 | #64748B |
| 强调蓝 | #3B82F6 |
| 成功绿 | #10B981 |
| 警告黄 | #F59E0B |
| 错误红 | #EF4444 |

### 字体

- 数字：等宽或粗体无衬线
- 中文：系统默认（Streamlit 已处理）

---

## 八、验收标准

### Must Have（必须有）

- [ ] 单页仪表盘布局，默认打开即显示
- [ ] 顶部导航栏，4 个入口可切换
- [ ] 4 个 KPI 卡片显示正确数据
- [ ] 8 个 Agent 卡片网格，状态/进度/成本正确
- [ ] 预算进度条显示正确
- [ ] 实时日志面板，至少显示 4 条日志
- [ ] 右侧 CEO 面板，含输入框和快捷按钮
- [ ] 任务结果展示区（空状态有引导文案）
- [ ] 使用 Solo-Ops 真实开发进度作为数据

### Nice to Have（加分项）

- [ ] Agent 卡片 running 状态有呼吸动画
- [ ] 日志自动滚动到底部
- [ ] 快捷按钮点击后自动填入输入框
- [ ] 响应式布局（移动端适配）

---

## 九、不变模块

以下模块完全不变，新界面直接调用：

- `agents/` 全部
- `tools/` 全部
- `memory/` 全部
- `knowledge/` 全部
- `config/` 全部
- `data/task_recorder.py`
- `crew.py`

---

## 十、任务拆分

### 任务 1：基础设施（Agent 1）
- 创建 `frontend_v2/` 目录结构
- 创建 `data.py` — 项目数据源
- 创建 `state.py` — 统一状态管理
- 创建 `styles.py` — 全局 CSS

### 任务 2：核心组件（Agent 2，依赖任务 1）
- 创建 `components/navbar.py`
- 创建 `components/kpi_cards.py`
- 创建 `components/budget_bar.py`
- 创建 `components/agent_grid.py`
- 创建 `components/log_panel.py`
- 创建 `components/ceo_panel.py`
- 创建 `components/task_output.py`

### 任务 3：页面与入口（Agent 3，依赖任务 1+2）
- 创建 `pages/dashboard.py` — 组装所有组件
- 创建 `pages/history.py` — 简化历史页
- 创建 `pages/knowledge.py` — 简化知识库页
- 创建 `pages/settings.py` — 设置页
- 重写 `app.py` — 新入口（50-80 行）

---

*PRD 版本: V1.0*
*日期: 2026-06-05*
