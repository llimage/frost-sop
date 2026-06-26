# PROJECT_OVERVIEW — Solo-Ops-Platform (S-O-P) 项目概览

## 项目身份

| 属性 | 值 |
|------|-----|
| 项目名称 | Solo-Ops-Platform（S-O-P） |
| 内部代号 | FROST-SOP |
| 项目目标 | 一人公司 AI 指挥平台 |
| 核心思想 | FROST 分形架构：家族式多 Agent 协作，SOP 驱动执行 |
| 技术栈 | Python 3.13 + Next.js 16 + FastAPI + SQLite + Streamlit |
| 代码总量 | ~19,595 行（Python ~15,782 + TypeScript ~3,813） |

## 项目目标

构建一个可自我进化的 AI 家族指挥平台，使 **一人运营者** 能够：

1. **自然语言派发任务** — 用对话方式指挥 AI 家族做事
2. **SOP 模板化执行** — 工作流程标准化，可复用
3. **自动孵化子 Agent** — 按需动态组装孙辈 Agent 处理专业任务
4. **家族自我进化** — 从历史数据中提炼经验，自动优化
5. **全流程可观察** — 任务状态、成本追踪、Agent 健康一览

## 技术架构总览

```
┌─────────────────────────────────────────────────┐
│              表现层 (Presentation)                │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Streamlit   │  │  Next.js 16 + shadcn/ui │  │
│  │  app.py      │  │  frontend/src/           │  │
│  │  指挥官工作台 │  │  现代化 SaaS 风格 Web UI │  │
│  └──────┬───────┘  └───────────┬─────────────┘  │
│         │                      │                 │
├─────────┼──────────────────────┼─────────────────┤
│         │          API 层       │                 │
│         │  ┌───────────────────┴──────┐         │
│         └──►  FastAPI (api/main.py)    ◄─────────┤
│            │  /api/tasks /api/agents   │         │
│            │  /api/costs /api/chat ... │         │
│            └───────────┬───────────────┘         │
├────────────────────────┼─────────────────────────┤
│                  核心层 (Core Layer)              │
│  ┌─────────────────────┴─────────────────────┐  │
│  │              main.py (CLI 入口)             │  │
│  └─────────────────────┬─────────────────────┘  │
│                        │                         │
│  ┌─────────────────────┼─────────────────────┐  │
│  │         agents/ (Agent 工厂层)              │  │
│  │  ancestor.py ─► parent.py ─► elder.py     │  │
│  └─────────────────────┼─────────────────────┘  │
│                        │                         │
│  ┌─────────────────────┼─────────────────────┐  │
│  │         skills/ (能力模块层)                │  │
│  │  orchestration / llm / assemble /         │  │
│  │  evolution / tools                        │  │
│  └─────────────────────┼─────────────────────┘  │
│                        │                         │
│  ┌─────────────────────┼─────────────────────┐  │
│  │         core/ (核心抽象层)                  │  │
│  │  store.py  agent.py  skill.py  sop.py     │  │
│  │  db.py  skill_extractor.py  skill_version │  │
│  └─────────────────────┼─────────────────────┘  │
│                        │                         │
├────────────────────────┼─────────────────────────┤
│                  数据层 (Data Layer)              │
│  ┌──────────┐  ┌───────────┐  ┌──────────────┐ │
│  │ SQLite   │  │ ChromaDB  │  │ YAML SOP模板  │ │
│  │ 17张表   │  │ 向量检索  │  │ sops/ 目录    │ │
│  └──────────┘  └───────────┘  └──────────────┘ │
└─────────────────────────────────────────────────┘
```

## 核心模块列表及职责

| 模块 | 行数 | 职责 |
|------|------|------|
| `core/store.py` | 308 | 三级键值存储（Store / HierarchicalStore / AssetStore） |
| `core/agent.py` | 245 | Agent 核心类，持有记忆+能力，行为由 SOP 决定 |
| `core/skill.py` | 35 | 最小能力单元（类蛋白质），输入 context 输出 context |
| `core/sop.py` | 104 | SOP 宪法文本，结构化阶段序列 + 验证器 |
| `core/db.py` | 936 | SQLite 单例管理器，17张表的 CRUD |
| `core/skill_extractor.py` | 316 | 从工具调用日志自动提取可复用 Skill 模式 |
| `core/skill_version.py` | 230 | Skill 版本管理（创建/回滚/清理） |
| `agents/ancestor.py` | 37 | 始祖 Agent 工厂 (gen=0)，持有宪法 |
| `agents/parent.py` | 67 | 父辈 Agent 工厂，预装13个本能 Skill |
| `agents/elder.py` | 134 | 长老 Agent，独立审计权，不参与执行 |
| `skills/orchestration.py` | 357 | SOP 编排：spawn、emit、validate、merge、execute |
| `skills/llm.py` | 284 | LLM 调用 + mock 路由（测试模式） |
| `skills/assemble.py` | 283 | 孙辈 Agent 动态组装 + Skill 合成 |
| `skills/evolution.py` | 212 | 家族自进化：从历史数据提炼优化建议 |
| `skills/tools.py` | 112 | 文件写入、LLM 输出等真实工具 Skill |
| `api/main.py` | 523 | FastAPI REST 层，13个端点 |
| `api/models.py` | 153 | Pydantic 请求/响应模型 |
| `app.py` | 1,927 | Streamlit 家族 AI 指挥平台 |
| `main.py` | 311 | CLI 入口 |

## 设计哲学

1. **分形架构**: Agent → Skill → Store 三层抽象，每层遵循相同接口契约
2. **家族模型**: Ancestor(始祖) → Parent(父辈) → Children(孙辈瞬态)，层级继承
3. **SOP 驱动**: Agent 行为完全由外部 SOP 步骤决定，不硬编码
4. **自进化**: Elder 独立审计 + evolution 趋势分析 + SkillExtractor 模式提取
5. **前后端分离**: FastAPI + Next.js，UX 层与核心层完全解耦

## 开发历史摘要

| 阶段 | 日期 | 内容 |
|------|------|------|
| **F1-F4** | 2026 Q2 早期 | 核心四原子：Agent / Skill / SOP / Store |
| **F5** | 2026-06 | 长老审计 (Elder) + Constitution (宪法五条) |
| **F6** | 2026-06 | LLM 集成 + SOP 编排 + 孙辈动态组装 |
| **F6.5** | 2026-06-22 | 配置持久化 (Zustand snapshot) |
| **F7** | 2026-06-22 | Strive 自进化循环 |
| **F8** | 2026-06-22 | Decision 决策管理 |
| **F9** | 2026-06-22 | Founder Tools (能量/日程/健康) |
| **F10** | 2026-06-23 | SkillExtractor + 验证激活 + 版本管理 |
| **F11** | 2026-06-23 | 项目工作台 (Streamlit) + SaaS UI |
| **F12** | 2026-06-24 | E2E UI 测试 |
| **F14** | 2026-06-24 | 持久化修复 (agents + cost_log 写入) |
| **F16** | 2026-06-24 | FastAPI REST API 层 (13端点) |
| **F15** | 2026-06-25 | Next.js 16 前端重构 (shadcn/ui) |

## 数据库规模

- **17 张 SQLite 表**
- 核心表: tasks, task_stages, sop_executions, agents, cost_log
- 支持性表: projects, skills, skill_versions, schedule, energy_log, decision_points 等
- ChromaDB: 向量语义检索（知识库）
