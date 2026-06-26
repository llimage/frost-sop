# FROST-SOP 项目工作台设计蓝图

> 版本: v1.0 | 日期: 2026-06-23 | 基于: F10+ 能力基线

---

## 一、背景与目标

### 1.1 现状

当前 FROST-SOP 驾驶舱本质上是一个「单页单项目」面板，所有任务执行、成本追踪、Skill 学习都绑定在同一个上下文中运行。虽然 F6.5 已实现了配置的保存/唤醒能力，但缺少多项目维度的组织层。

```
现状导航结构:
├── 侧边栏: 兵器库 / 能量日志
├── 导航: 指挥面板 / 📅 日程管理
└── 标签页: 💬 指挥面板 | 💰 成本仪表盘 | 🏥 家族健康
```

### 1.2 目标

构建「**项目工作台（Project Workbench）**」作为驾驶舱的最外层入口，使得：

1. **一个驾驶舱管理多个项目**：每个项目拥有独立的 SOP、Skill 基因库、成本记录、能量日志
2. **一键唤醒项目全貌**：借助 F6.5 撒豆成兵能力，保存并快速恢复项目运行态
3. **Skill 跨项目共享与隔离**：F10 提取的 Skill 可在项目间复用（基因池），但执行时按项目隔离

---

## 二、数据模型

### 2.1 核心实体

```
┌─────────────────────────────────────────────────────────────┐
│                        Project                              │
├─────────────────────────────────────────────────────────────┤
│ id              TEXT PRIMARY KEY     (project_id)           │
│ name            TEXT NOT NULL        项目名称                │
│ description     TEXT                 项目描述                │
│ status          TEXT                 active/paused/archived │
│ sop_template    TEXT                 关联的 SOP 模板 ID      │
│ created_at      TEXT                 ISO 8601               │
│ updated_at      TEXT                 ISO 8601               │
│ last_active_at  TEXT                 最近活跃时间            │
│ energy_level    REAL                 项目能量值 (0-100)      │
│ config_ref      TEXT                 关联 F6.5 配置文件名    │
│ metadata        TEXT                 JSON 扩展字段           │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 关联关系

```
Project (1) ──────────── (N) Task           (执行历史)
Project (1) ──────────── (1) CostTracker     (F7 成本追踪)
Project (1) ──────────── (N) EnergyLog       (F9 能量日志)
Project (1) ──────────── (N) ConfigSnapshot  (F6.5 配置快照)
Project (N) ──────────── (N) Skill           (F10 技能关联)
Project (1) ──────────── (N) ScheduleItem    (F9 日程)
```

### 2.3 SQLite 新增表

```sql
-- 项目主表
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT DEFAULT 'active',
    sop_template TEXT DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_active_at TEXT,
    energy_level REAL DEFAULT 100.0,
    config_ref TEXT DEFAULT '',
    metadata TEXT DEFAULT '{}'
);

-- 项目-技能关联表（F10 集成）
CREATE TABLE IF NOT EXISTS project_skills (
    project_id TEXT NOT NULL,
    skill_id TEXT NOT NULL,
    activated_at TEXT NOT NULL,
    usage_count INTEGER DEFAULT 0,
    PRIMARY KEY (project_id, skill_id),
    FOREIGN KEY (project_id) REFERENCES projects(id),
    FOREIGN KEY (skill_id) REFERENCES skills(id)
);

-- 配置快照表（F6.5 增强）
CREATE TABLE IF NOT EXISTS config_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    snapshot_name TEXT NOT NULL,
    task_description TEXT DEFAULT '',
    sop_state TEXT DEFAULT '{}',
    available_skills TEXT DEFAULT '[]',
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);
```

---

## 三、三核心卡片

### 3.1 卡片总览

```
┌──────────────────────────────────────────────────────────────────┐
│                    🏛️ 项目工作台                                  │
│  [项目选择器: ▼ FROST-SOP 主项目]  [+ 新建项目]                    │
├───────────────────┬───────────────────┬──────────────────────────┤
│                   │                   │                          │
│  📊 项目概览卡片   │  📋 任务执行卡片   │  🧬 Skill 基因卡片        │
│                   │                   │                          │
│  - 项目状态与能量  │  - 当前 SOP 阶段   │  - 已激活 Skill 数       │
│  - 任务统计       │  - 进度百分比      │  - 本周新提取 Skill       │
│  - 成本摘要       │  - 最近产出        │  - 基因库健康度           │
│  - 最后活跃时间   │  - 下一步行动      │  - F10 提取状态           │
│                   │                   │                          │
├───────────────────┴───────────────────┴──────────────────────────┤
│  📍 当前项目详情区（继承现有 3 标签页 + F9 日程）                    │
└──────────────────────────────────────────────────────────────────┘
```

### 3.2 卡片一：📊 项目概览卡片（ProjectStatusCard）

| 字段 | 数据源 | 说明 |
|------|--------|------|
| 项目名称 + 状态灯 | `projects` 表 | 🟢 active / 🟡 paused / ⚫ archived |
| 能量条 (0-100%) | `projects.energy_level` | 从 F9 energy_log 聚合计算 |
| 总任务数 / 今日任务 | `tasks` 表 | 统计维度 |
| 本月成本 | `cost_tracker` (F7) | ¥ 格式显示 |
| 最后活跃 | `projects.last_active_at` | 相对时间（"3 分钟前"） |
| 快捷操作 | — | 🚀 开始任务 / ⏸️ 暂停 / 📦 归档 |

### 3.3 卡片二：📋 任务执行卡片（SOPProgressCard）

| 字段 | 数据源 | 说明 |
|------|--------|------|
| 当前 SOP 名称 | `projects.sop_template` | 如 "DEV-001 新功能开发" |
| 阶段进度条 | 运行时状态 | Phase 1/5 → Phase 2/5 → ... |
| 当前阶段名称 | SOP yaml | "需求分析" / "代码实现" ... |
| 最近产出摘要 | `output/` 目录 | 最后生成的文件名 + 时间 |
| 下一步行动 | SOP 下一阶段 | "执行第 3 阶段: 代码审查" |
| 执行按钮 | — | ▶️ 继续执行 / ⏹️ 停止 |

### 3.4 卡片三：🧬 Skill 基因卡片（SkillGeneCard）

| 字段 | 数据源 | 说明 |
|------|--------|------|
| 激活 Skill 数 | `project_skills` | 当前项目已激活的 Skill 总数 |
| 本周新 Skill | `skills.created_at` | 本周通过 F10 新提取的 Skill |
| 待验证 Skill | `skills.status='draft'` | 已提取但未通过验证的 Skill |
| 基因库共享率 | 跨项目统计 | 多少个 Skill 被多项目复用 |
| F10 提取器状态 | `skill_extractor` 日志 | 最近一次提取时间 + 结果 |
| 快捷操作 | — | 🧬 手动提取 / 📋 查看 Skill 列表 |

---

## 四、与 F6.5/F10 集成方案

### 4.1 F6.5 撒豆成兵集成

```
当前 F6.5 行为:
  保存配置 → 单文件 JSON → assets/config_*.json
  唤醒配置 → 加载最新 JSON → 填充 task_input

增强后 F6.5 行为:
  保存配置 → 项目级快照 → config_snapshots 表 + assets/ 目录
           → 快照内容: task_description + sop_state + available_skills
  唤醒配置 → 按项目加载 → 恢复 task_input + SOP 阶段 + Skill 上下文
           → 侧边栏显示快照列表，可选择任意历史版本唤醒
```

**关键改动**:
1. `AssetStore.save()` 增加 `project_id` 参数 → 文件命名 `assets/{project_id}_config_{timestamp}.json`
2. `AssetStore.load_latest()` 增加 `project_id` 过滤
3. app.py 保存按钮从全局改为项目级上下文

### 4.2 F10 Skill 自学习集成

```
当前 F10 行为:
  SkillExtractor 扫描 data/tool_calls/*.json
  提取 Skill → 写入全局 skills 表
  验证激活 → 写入全局 skill_versions 表

增强后 F10 行为:
  Skill 提取时关联当前 active 的 project_id
  project_skills 表记录项目-技能激活关系
  跨项目 Skill 通过基因池（skills 表）共享
  侧边栏「可用 Skill」按当前项目过滤
```

**关键改动**:
1. `SkillExtractor.extract()` 增加 `project_id` 参数
2. 提取成功后自动写入 `project_skills` 关联
3. 侧边栏 Skill 列表增加项目过滤，同时显示"跨项目共享"标记

### 4.3 数据流图

```
                    ┌──────────────────┐
                    │   项目工作台入口   │
                    │  (项目选择器)      │
                    └────────┬─────────┘
                             │ 选择项目
                             ▼
              ┌──────────────────────────────┐
              │       三核心卡片渲染           │
              │  📊概览 │ 📋任务 │ 🧬技能      │
              └──────────┬───────────────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ F6.5     │  │ SOP 引擎  │  │ F10      │
    │ 配置快照  │  │ 阶段执行  │  │ Skill提取 │
    └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │             │
         ▼             ▼             ▼
    ┌──────────────────────────────────────┐
    │              SQLite 持久层            │
    │  projects | config_snapshots |        │
    │  project_skills | skills | tasks |    │
    │  cost_logs | energy_logs | schedules  │
    └──────────────────────────────────────┘
```

---

## 五、UI 布局草图

### 5.1 页面结构

```
┌──────────────────────────────────────────────────────────────┐
│  🏛️ FROST-SOP 家族AI指挥平台                        F10+     │
├───────────────┬──────────────────────────────────────────────┤
│               │                                              │
│  📂 项目列表   │  ┌─────────────────────────────────────────┐ │
│               │  │  📍 当前项目: FROST-SOP 主项目  [切换]   │ │
│  ● FROST-SOP  │  └─────────────────────────────────────────┘ │
│    主项目      │                                              │
│  ○ 财务小助手  │  ┌──────────┬──────────┬──────────────────┐ │
│  ○ 营销内容库  │  │          │          │                  │ │
│  ○ 知识管理   │  │  📊 概览  │  📋 任务  │  🧬 Skill 基因   │ │
│               │  │          │          │                  │ │
│  [+ 新建项目] │  │  状态🟢  │  DEV-001 │  12 激活 Skill   │ │
│               │  │  能量 87% │  Phase3/5│  3 本周新增      │ │
│  ───────────  │  │  本月 ¥12 │  ▶️ 继续  │  🧬 手动提取     │ │
│               │  │          │          │                  │ │
│  ⚔️ 兵器库    │  └──────────┴──────────┴──────────────────┘ │
│  ⚡ 能量日志   │                                              │
│               │  ┌─────────────────────────────────────────┐ │
│               │  │  [💬 指挥面板 | 💰 成本仪表盘 | 🏥 健康] │ │
│               │  │  (继承现有 3 标签页内容)                  │ │
│               │  └─────────────────────────────────────────┘ │
├───────────────┴──────────────────────────────────────────────┤
│  💡 项目工作台 v1.0 | FROST-SOP F10+                          │
└──────────────────────────────────────────────────────────────┘
```

### 5.2 侧边栏改造

```
当前侧边栏:
├── ⚔️ 兵器库 (基因列表)
├── ⚡ 能量记录 (滑动条 + 情绪 + 曲线)
├── 📅 日程管理 (导航切换)
└── 🧬 可用 Skill (F10)

改造后侧边栏:
├── 📂 项目列表 (新增)
│   ├── ● 项目 A  (active, 选中)
│   ├── ○ 项目 B  (paused)
│   └── [+ 新建项目]
├── ⚔️ 兵器库 (按项目过滤)
├── ⚡ 能量记录 (项目级聚合)
├── 📅 日程管理
└── 🧬 可用 Skill (F10, 项目过滤)
```

### 5.3 交互流程

```
用户进入驾驶舱
    │
    ├─ 无 project_id → 展示「新建第一个项目」引导页
    │
    └─ 有 project_id
        │
        ├─ F6.5 auto_wake() → 加载最近配置
        │
        ├─ 渲染三卡片
        │   ├─ 概览卡片: 查询 projects + cost_logs
        │   ├─ 任务卡片: 查询 tasks + sop 引擎
        │   └─ 技能卡片: 查询 project_skills + skills
        │
        ├─ 渲染详情区 (3 标签页)
        │
        └─ 侧边栏按项目过滤展示
```

---

## 六、实施路线图

### Phase 3a: 数据层（1 天）

- [ ] SQLite 迁移: 创建 `projects`, `project_skills`, `config_snapshots` 三张表
- [ ] `core/db.py` 新增 CRUD 方法: `create_project()`, `get_projects()`, `update_project()`, `archive_project()`
- [ ] `core/store.py` AssetStore 支持 `project_id` 过滤
- [ ] 单元测试: `tests/test_project_workbench_data.py`

### Phase 3b: 项目工作台 UI（1 天）

- [ ] `app.py` 新增 `render_project_workbench()` 函数（三卡片渲染）
- [ ] 侧边栏新增项目列表 + 新建项目表单
- [ ] 卡片组件: `render_project_card()`, `render_sop_card()`, `render_skill_card()`
- [ ] 响应式布局: Streamlit columns 实现 3 列卡片网格

### Phase 3c: F6.5/F10 集成（半天）

- [ ] F6.5 保存/唤醒 → 项目级作用域
- [ ] F10 Skill 提取 → 关联 project_id
- [ ] 侧边栏兵器库 / Skill 列表按项目过滤
- [ ] 集成测试: `tests/test_project_workbench_integration.py`

### Phase 3d: 回归测试 + 文档（半天）

- [ ] 全量回归测试（≥105 passed）
- [ ] 更新验收报告
- [ ] 更新 MEMORY.md 架构速记

---

## 七、验收标准

| 编号 | 标准 | 验证方式 |
|------|------|----------|
| AC-1 | 三核心卡片正确渲染项目数据 | 端到端测试 |
| AC-2 | 项目切换后卡片/标签页/侧边栏全部更新 | 手动 + 自动测试 |
| AC-3 | F6.5 保存的配置按项目隔离，唤醒不串数据 | 集成测试 |
| AC-4 | F10 提取的 Skill 正确关联到项目 | 单元测试 |
| AC-5 | 新建/归档项目不影响其他项目 | 回归测试 |
| AC-6 | 回归测试 ≥105 passed | pytest 全量 |

---

*文档版本: v1.0 | 作者: FROST-SOP 架构组*
