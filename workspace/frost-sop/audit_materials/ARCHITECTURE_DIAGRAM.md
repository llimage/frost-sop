# ARCHITECTURE_DIAGRAM — 架构图 + 数据流

## 1. 系统架构分层

```
┌──────────────────────────────────────────────────────────┐
│                    ____  表现层 ____                      │
│                                                          │
│  ┌─────────────────────┐   ┌──────────────────────────┐ │
│  │   Streamlit 工作台  │   │   Next.js 16 SPA          │ │
│  │   app.py (1,927行)  │   │   frontend/src/ (3,813行) │ │
│  │                     │   │                            │ │
│  │ • 指挥官驾驶舱      │   │ • 6 个路由页面            │ │
│  │ • 成本仪表盘        │   │ • 5 个功能组件            │ │
│  │ • 日程管理          │   │ • 19 个 shadcn/ui 组件    │ │
│  │ • 能量记录          │   │ • react-query + zustand   │ │
│  │ • 决策对话框        │   │ • recharts 图表           │ │
│  │ • 家族健康面板      │   │ • 响应式移动端            │ │
│  └─────────┬───────────┘   └────────────┬─────────────┘ │
│            │                            │                │
├────────────┼────────────────────────────┼────────────────┤
│            │         API 层              │                │
│            └──────────┬─────────────────┘                │
│            ┌──────────▼──────────────────┐              │
│            │   FastAPI (api/main.py)     │              │
│            │                             │              │
│            │ GET  /api/projects          │              │
│            │ GET  /api/projects/{id}     │              │
│            │ POST /api/tasks             │              │
│            │ GET  /api/tasks             │              │
│            │ GET  /api/tasks/{id}/stages │              │
│            │ GET  /api/costs             │              │
│            │ GET  /api/agents            │              │
│            │ POST /api/chat              │              │
│            │ GET  /api/logs (SSE)        │              │
│            │ GET  /api/skills            │              │
│            │ GET  /api/schedule           │              │
│            │ POST /api/schedule           │              │
│            │ GET  /api/health            │              │
│            └──────────┬──────────────────┘              │
│                       │                                  │
├───────────────────────┼──────────────────────────────────┤
│                 核心层                                    │
│                       │                                  │
│            ┌──────────▼──────────────────┐              │
│            │   main.py (CLI入口)          │              │
│            │   参数: --task / --sop       │              │
│            └──────────┬──────────────────┘              │
│                       │                                  │
│            ┌──────────▼──────────────────┐              │
│            │   决策管理 (agent_decision)  │              │
│            │   项目选择 / 技能匹配        │              │
│            └──────────┬──────────────────┘              │
│                       │                                  │
│         ┌─────────────┼─────────────┐                   │
│         ▼             ▼             ▼                    │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│   │ Ancestor │ │  Parent  │ │  Elder   │              │
│   │  (始祖)  │▶│  (父辈)  │◀│  (长老)  │              │
│   │  gen=0   │ │  gen=1   │ │ retired  │              │
│   │ 独立审计 │ │ 任务指挥 │ │ 独立审计 │              │
│   └──────────┘ └────┬─────┘ └──────────┘              │
│                     │                                    │
│              ┌──────▼──────┐                            │
│              │  assemble   │ 孙辈 Agent 动态组装         │
│              │  按需孵化    │ gen=2+                      │
│              └──────┬──────┘                            │
│                     │                                    │
│    ┌────────────────┼────────────────┐                  │
│    ▼                ▼                ▼                    │
│ ┌─────────┐  ┌───────────┐  ┌────────────┐            │
│ │  Skill  │  │   SOP     │  │  Store     │            │
│ │ (蛋白质)│  │ (宪法文本)│  │ (记忆存储) │            │
│ │         │  │           │  │            │            │
│ │ • llm   │  │ • DEV-001 │  │ • task:    │            │
│ │ • orch  │  │ • STR-001 │  │ • lesson:  │            │
│ │ • tools │  │ • MT-001  │  │ • const:   │            │
│ └────┬────┘  └─────┬─────┘  └─────┬──────┘            │
│      │              │              │                     │
├──────┼──────────────┼──────────────┼─────────────────────┤
│      │        数据层 │              │                     │
│      └──────────────┼──────────────┘                    │
│                     ▼                                    │
│  ┌──────────────────────────────────────┐              │
│  │              SQLite                   │              │
│  │  data/frost_sop.db (17 张表)          │              │
│  │                                       │              │
│  │  tasks / task_stages / sop_executions │              │
│  │  agents / agent_status                │              │
│  │  cost_log / decision_points           │              │
│  │  projects / skills / skill_versions   │              │
│  │  schedule / energy_log / knowledge    │              │
│  │  audit_log / daily_reviews / config   │              │
│  └──────────────────────────────────────┘              │
│                                                          │
│  ┌──────────────┐  ┌───────────────┐                    │
│  │   ChromaDB   │  │  YAML SOP 模板│                    │
│  │  向量语义检索│  │  sops/ 7个文件│                    │
│  │  core/memory │  │  (DEV/STR/MT/ │                    │
│  │  知识库搜索  │  │   OPS 系列)   │                    │
│  └──────────────┘  └───────────────┘                    │
└──────────────────────────────────────────────────────────┘
```

## 2. 核心数据流：用户输入 → 执行 → 持久化

```
用户输入 (自然语言 "帮我做一个用户登录功能")
│
├─► [模式 A: 命令行] main.py --task "帮我做..."
├─► [模式 B: Web UI]  Next.js → POST /api/tasks → FastAPI
├─► [模式 C: Streamlit] app.py → execute_task()
│
▼
决策管理
├─► 确定目标项目 (project_id)
├─► 匹配 SOP 模板 (SOP匹配器)
├─► 决策是否需要人工干预 (decision_points)
│
▼
父辈 Agent (parent.py)
├─► internalize_sop(SOP) — 内化 SOP 模板
├─► 写入 tasks 表 (status=pending)
│
▼
SOP 编排 (skills/orchestration.py)
├─► execute_stage(context) — 逐阶段执行
│   ├─► Phase 1: 需求分析 → call_llm(SYSTEM_PROMPT)
│   ├─► Phase 2: 设计方案 → call_llm()
│   ├─► Phase 3: 代码生成 → assemble_agent(requirement)
│   │   ├─► 搜索 skill_gene: 前缀匹配已有 Skill
│   │   ├─► 缺失 Skill → LLM 合成 → 归档到 AssetStore
│   │   └─► 创建孙辈 Agent (gen=2+) → execute SKILL steps
│   ├─► Phase 4: 测试验证 → call_llm_for_output()
│   └─► Phase 5: 最终审查 → call_llm_for_output()
│
├─► 每阶段产出 → 写入 output/ 目录
├─► 每阶段结果 → 写入 task_stages 表
│
▼
长老审计 (agents/elder.py)
├─► audit_family(context) — 独立审计
├─► 写入 audit_log 表
│
▼
任务完成
├─► tasks.status = "completed"
├─► sop_executions.status = "completed"
├─► cost_log 累计写入
├─► agent_status 更新
│
▼
自进化 (skills/evolution.py)
├─► analyze_trends() — 从历史数据识别模式
├─► generate_suggestions() — 生成优化建议
├─► SkillExtractor — 提取新 Skill 基因
└─► 写入 skills 表 (status=draft → validate → active)
```

## 3. 关键模块依赖关系

```
api/main.py ──────► core/db.py (get_db)
    │
    ▼
main.py ──────────► agents/ancestor.py ► agents/parent.py ► agents/elder.py
    │                      │                                          │
    │                      ▼                                          │
    │               core/agent.py ◄───────────────────────────────────┘
    │                  │
    │                  ├──► core/store.py (HierarchicalStore)
    │                  ├──► core/skill.py
    │                  └──► core/sop.py
    │
    ├──► skills/orchestration.py
    │       ├──► skills/llm.py (call_llm)
    │       ├──► skills/assemble.py (assemble_agent)
    │       └──► skills/tools.py (write_file)
    │
    ├──► skills/evolution.py
    │       └──► core/skill_extractor.py
    │
    └──► core/db.py ◄── 所有模块的持久化入口

前端依赖：
frontend/src/lib/api.ts ───► http://localhost:8000/api/*
frontend/src/lib/store.ts ──► zustand (客户端状态)
frontend/src/app/page.tsx ──► 组合 AgentCard + LogTerminal + CeoChat + CostBar
```

## 4. 数据库 ER 关系

```
projects ──1:N──► tasks ──1:N──► task_stages
    │                  │
    │                  └──1:1──► sop_executions
    │
    └──N:M──► skills (via project_skills)

agents ──1:N──► agent_status
    │
    ├──1:N──► cost_log
    ├──1:N──► audit_log
    └──1:N──► energy_log

tasks ──1:N──► cost_log
tasks ──1:N──► decision_points
tasks ──1:N──► tool_calls

skills ──1:N──► skill_versions
skills ──N:M──► projects (via project_skills)

sop_templates ──N:1──► sop_executions (via sop_template_id)

独立表:
- schedule (日程管理，独立实体)
- knowledge + knowledge_tags (知识库，独立实体)
- config + config_snapshots (系统配置)
- daily_reviews (日终回顾)
- kv_store (通用键值存储)
```

## 5. 宪法五条 (Constitution)

系统运行受以下五条宪法约束（通过 `constitution:` 前缀存储在 Store 中）：

1. **命名规范**: 所有标识符必须遵循 snake_case (Python) + camelCase (JS) 约定
2. **测试要求**: 核心功能必须有对应测试覆盖
3. **文档要求**: SOP 模板必须有 description 字段
4. **审计要求**: 所有任务执行必须经 Elder 审计
5. **安全要求**: API 密钥通过环境变量管理，不硬编码
