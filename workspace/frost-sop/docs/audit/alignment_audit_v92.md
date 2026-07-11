# FROST-SOP V9.1 现有代码对齐审计报告

**日期**: 2026-07-09  
**对应文档**: PRD-V2.0.md, DDD-V2.0.md  
**审计范围**: 后端核心模块 (core/), API 层 (api/), 前端 (frontend/src/)

---

## 1. 审计方法

1. **实体映射**: 对比 DDD 中的核心实体与现有代码中的类定义
2. **状态机对比**: 对比 DDD 状态机与现有代码中的状态管理
3. **API 契约对比**: 对比 DDD 接口定义与现有 API 端点
4. **缺失检测**: 识别 PRD 需求中尚未实现的模块

---

## 2. 实体映射分析

### 2.1 已存在且基本匹配的实体

| DDD 实体 | 现有代码 | 文件 | 匹配度 | 说明 |
|----------|----------|------|--------|------|
| **Agent** | `Agent` | `core/agent.py` | 70% | 有 name, store, skills, generation, max_spawn_generation, retry_config。缺少: agent_type 枚举, status 状态机, total_tasks/successful_tasks 统计, preferred_model, last_heartbeat |
| **SOP** | `SOP` | `core/sop.py` | 60% | 有 sop_id, name, version, stages, required_stages, forbidden_skills。缺少: description, is_template, evolution_history, 阶段状态机 |
| **Store** | `Store` | `core/store.py` | 80% | 有 save/load/delete/list_keys，支持 SQLite 持久化。缺少: 版本管理、跨项目隔离、键命名规范强制执行 |
| **Project** | `Project` | `core/project.py` | 75% | 有 id, name, raw_input, vision, status, parent_agent_id, footman_ids, context。缺少: plan_id 关联、completed_at、状态机完整实现 |
| **CostTracker** | `CostTracker` | `core/cost.py` | 60% | 有 monthly_budget, alert_ratio, track_cost, check_budget。缺少: 日预算、熔断阈值、fuse 机制、成本预警通知 |
| **DecisionManager** | `DecisionManager` | `core/decision_manager.py` | 50% | 有 pause_decision, resume_decision。缺少: 超时机制 (timeout_minutes, expires_at, timeout_action)、人类府兵状态管理、决策队列 |

### 2.2 部分存在的实体

| DDD 实体 | 现有代码 | 文件 | 匹配度 | 说明 |
|----------|----------|------|--------|------|
| **Task** | 隐式存在于 `api/models.py` | `api/models.py` | 40% | 有 TaskResponse Pydantic 模型，但缺少完整的 Task 领域类。缺少: 状态机、阶段关联、进度追踪、成本汇总 |
| **SOPStage** | 字典列表 | `core/sop.py` | 30% | stages 是字典列表，不是类。缺少: status 状态机、timeout、human_decision、cost_cny、started_at/completed_at |
| **DecisionPoint** | 数据库表 | `core/db.py` | 50% | 有 decision_points 表。V9.1 已添加 timeout_minutes, expires_at, timeout_action。缺少: 结构化选项、上下文、决策理由 |
| **Skill** | `Skill` | `core/skill.py` | 60% | 有 skill_id, name, handler, required_keys, output_schema。缺少: skill_type 枚举、trigger_keywords、trigger_sop_ids、version、success_rate、avg_cost、evolution_history |

### 2.3 完全缺失的实体

| DDD 实体 | 缺失影响 | 优先级 |
|----------|----------|--------|
| **Vision** | 愿景初始化流程缺失，无法做防飘逸的多轮问卷澄清 | 🔴 高 |
| **HumanFootman** | 人类只是 DecisionManager 的调用方，没有作为 Agent 的状态管理 | 🔴 高 |
| **EvolutionEngine** | 自进化流程缺失，只有 lesson_archivist.py 做教训归档，没有完整的闭环 | 🔴 高 |
| **ErrorRecord** | 错误记录只有 audit_log，没有结构化的错误分类和趋势分析 | 🟡 中 |
| **Lesson** | 有 lesson_archivist.py 生成教训，但没有独立的 Lesson 实体管理 | 🟡 中 |
| **OptimizationProposal** | 优化建议没有实体化，无法追踪批准/应用/回滚状态 | 🟡 中 |
| **CostLog** | 有 cost_log 表，但缺少 CostLog 领域类和详细查询 | 🟢 低 |
| **HierarchicalStore** | 有 HierarchicalStore 继承 Store，但缺少 AssetStore 的键命名规范 | 🟢 低 |

---

## 3. 状态机差距分析

### 3.1 Agent 状态机

**DDD 设计**:
```
idle → running → completed/failed → terminated
       ↓
     paused → running
```

**现有实现** (`core/agent.py`):
```python
# Agent 有 generation, max_spawn_generation
# run() 方法执行 SOP 步骤
# 但没有显式的状态机管理
# 状态通过事件发布 (AGENT_CREATED, STEP_COMPLETED, AGENT_DESTROYED)
```

**差距**:
- ❌ 没有 `status` 字段和状态转换方法
- ❌ 没有 `paused` 状态
- ❌ 没有 `failed` 后的重试逻辑
- ❌ 没有 `terminated` 后的资源清理
- ✅ 有生命周期事件 (created, running, destroyed)

### 3.2 SOP 阶段状态机

**DDD 设计**:
```
pending → running → completed/failed/waiting_human/timeout
```

**现有实现** (`core/sop.py` + `api/main.py`):
```python
# stages 是字典列表
# task_stages 表有 status 字段 (pending, running, completed, failed, waiting_human)
# V9.1 添加了 timeout
```

**差距**:
- ✅ 有基本的状态字段
- ❌ 没有状态转换方法（谁在什么条件下改变状态？）
- ❌ 没有前置条件检查
- ❌ 没有超时自动转换逻辑
- ❌ 没有人类决策状态的管理流程

### 3.3 任务生命周期状态机

**DDD 设计**:
```
created → initializing → running → paused → completed/failed/terminated
```

**现有实现** (`core/project.py` + `api/main.py`):
```python
# Project 有 status: created → vision_aligned → planning → executing → reviewing → completed
# Task 有 status: pending → running → completed/failed (api/models.py)
```

**差距**:
- ❌ 没有 `initializing` 状态
- ❌ 没有 `paused` 状态（V9.1 添加了 DB 字段但未实现状态机）
- ❌ 没有 `terminated` 状态
- ❌ Project 和 Task 状态不一致（Project 有 6 个状态，Task 有 3 个）
- ❌ 状态转换逻辑分散在多个文件中

### 3.4 决策点状态机

**DDD 设计**:
```
pending → notified → responding → approved/rejected/modified/timeout
```

**现有实现** (`core/decision_manager.py` + `core/panel_decision.py`):
```python
# DecisionStatus: pending, approved, rejected, modified
# V9.1 添加了 timeout
# DecisionManager.pause_decision() 创建 pending
# DecisionManager.resume_decision() 处理响应
```

**差距**:
- ✅ 有基本状态
- ❌ 没有 `notified` 状态（通知是否成功？）
- ❌ 没有 `responding` 状态（用户正在响应？）
- ❌ 超时处理只有 DB 查询，没有自动状态转换
- ❌ 没有 `timeout_action` 执行逻辑

---

## 4. API 契约差距分析

### 4.1 已实现的 API

| DDD 端点 | 现有端点 | 状态 | 差距 |
|----------|----------|------|------|
| `GET /api/projects` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/projects/{id}` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/tasks` | ✅ 已实现 | 完成 | 缺少阶段详情 |
| `POST /api/tasks` | ✅ 已实现 | 完成 | 缺少愿景关联 |
| `GET /api/tasks/{id}/stages` | ✅ V9.1 新增 | 完成 | 基本匹配 |
| `GET /api/agents` | ✅ 已实现 | 完成 | 缺少状态统计 |
| `POST /api/chat` | ✅ 已实现 | 完成 | max_tokens 已改为 4096 |
| `GET /api/skills` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/schedule` | ✅ 已实现 | 完成 | 基本匹配 |
| `POST /api/schedule` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/costs` | ✅ 已实现 | 完成 | 缺少日预算检查 |
| `POST /api/decisions/submit` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/decisions` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/decisions/{id}` | ✅ 已实现 | 完成 | 基本匹配 |
| `GET /api/events` | ✅ V9.1 SSE | 完成 | 基本匹配 |
| `POST /api/decisions/check-timeout` | ✅ V9.1 新增 | 完成 | 基本匹配 |

### 4.2 缺失的 API

| DDD 端点 | 影响 | 优先级 |
|----------|------|--------|
| `POST /api/visions` | 无法创建愿景，无法做防飘逸 | 🔴 高 |
| `POST /api/visions/{id}/clarify` | 无法多轮问卷澄清 | 🔴 高 |
| `POST /api/visions/{id}/confirm` | 无法确认愿景 | 🔴 高 |
| `GET /api/visions/{id}` | 无法查看愿景 | 🔴 高 |
| `POST /api/tasks/{id}/pause` | 无法暂停任务 | 🟡 中 |
| `POST /api/tasks/{id}/resume` | 无法恢复任务 | 🟡 中 |
| `POST /api/tasks/{id}/retry` | 无法重试失败任务 | 🟡 中 |
| `GET /api/agents/{id}/heartbeat` | 无法心跳检测 | 🟡 中 |
| `POST /api/evolution/trigger` | V9.1 已添加 | ✅ |
| `GET /api/evolution/status` | V9.1 已添加 | ✅ |
| `GET /api/evolution/proposals` | 无法查看优化建议 | 🟡 中 |
| `POST /api/evolution/proposals/{id}/approve` | 无法批准进化 | 🟡 中 |

---

## 5. 前端差距分析

### 5.1 已实现的页面

| 页面 | 文件 | 状态 | 差距 |
|------|------|------|------|
| 首页/仪表盘 | `page.tsx` | 基本可用 | 缺少实时状态聚合 |
| 项目详情 | `projects/[id]/page.tsx` | V9.1 修复 | 缺少愿景显示、Agent 树 |
| 成本页面 | `costs/page.tsx` | 基本可用 | 缺少预算预警可视化 |
| 日程页面 | `schedule/page.tsx` | 基本可用 | 基本匹配 |
| 技能页面 | `skills/page.tsx` | 基本可用 | 缺少 Skill 进化历史 |
| 面板页面 | `panels/page.tsx` | 基本可用 | 基本匹配 |
| CEO 对话 | `components/CeoChat.tsx` | V9.1 修复 | Textarea 已替换 |

### 5.2 缺失的页面/组件

| 需求 | 缺失 | 优先级 |
|------|------|--------|
| 愿景创建/澄清界面 | 完全缺失 | 🔴 高 |
| 决策面板（等待人类决策） | 部分缺失（有 API 无 UI） | 🔴 高 |
| Agent 家族树可视化 | 完全缺失 | 🟡 中 |
| 自进化仪表盘 | 完全缺失 | 🟡 中 |
| 错误/教训查看界面 | 完全缺失 | 🟡 中 |
| 本地 LLM 配置界面 | 完全缺失 | 🟡 中 |
| 隐私脱敏配置 | 完全缺失 | 🟢 低 |
| 移动端适配 | 完全缺失 | 🟢 低 |

---

## 6. 核心机制差距分析

### 6.1 Store + Skill + SOP 机制

| 机制 | 现有实现 | 差距 |
|------|----------|------|
| **Store** | `core/store.py` + `core/db.py` | ✅ 基本可用。缺少: 版本管理、跨项目隔离、键命名规范 |
| **Skill** | `core/skill.py` + `skills/` 目录 | ⚠️ 部分可用。缺少: 触发机制、版本进化、成功率统计 |
| **SOP** | `core/sop.py` + `sops/templates/` | ⚠️ 部分可用。缺少: 阶段状态机、人类决策点、超时管理 |
| **Agent 家族** | `agents/` 目录 + `core/agent.py` | ⚠️ 部分可用。缺少: 状态机、心跳、自动清理 |
| **人类府兵** | `core/decision_manager.py` | ❌ 不完整。缺少: 状态管理、超时自动处理、队列 |
| **自进化** | `skills/evolution.py` + `skills/strategy/lesson_archivist.py` | ⚠️ 部分可用。缺少: 完整闭环、人类确认、验证回滚 |
| **愿景初始化** | ❌ 完全缺失 | 🔴 高优先级 |
| **成本熔断** | `core/cost.py` | ⚠️ 部分可用。缺少: 日预算、熔断阈值、自动暂停 |
| **隐私脱敏** | ❌ 完全缺失 | 🔴 高优先级 |
| **本地 LLM** | ❌ 完全缺失 | 🔴 高优先级 |
| **多家族协同** | `core/project.py` | ⚠️ 部分可用。缺少: 跨项目 Skill 共享、教训共享 |

---

## 7. 代码质量差距

### 7.1 架构问题

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| **状态机分散** | 🔴 高 | 状态管理分散在 api/main.py, core/agent.py, core/decision_manager.py, core/project.py 中，没有统一的状态机引擎 |
| **实体不完整** | 🔴 高 | 很多实体只有 Pydantic 模型（api/models.py），没有领域类 |
| **API 与领域混合** | 🟡 中 | api/main.py 既处理 HTTP 又处理业务逻辑，没有清晰的层边界 |
| **前端与后端耦合** | 🟡 中 | 前端直接调用后端 API，没有 BFF 层或 GraphQL |
| **事件系统不完善** | 🟡 中 | 有 EventBus 但只用于部分模块，没有全局事件驱动 |

### 7.2 技术债务

| 债务 | 严重程度 | 说明 |
|------|----------|------|
| **any 类型泛滥** | 🟡 中 | 前端大量使用 `any` 类型，缺少类型安全 |
| **测试覆盖不足** | 🟡 中 | 只有 V9.1 新增的 8 个回归测试，缺少单元测试 |
| **文档不一致** | 🟢 低 | 代码注释与实现有时不一致 |
| **重复代码** | 🟢 低 | 多个文件有相似的 DB 查询逻辑 |

---

## 8. 差距总结

### 8.1 按优先级分类

#### 🔴 高优先级（必须实现）

1. **Vision 实体 + API** — 愿景初始化是整个流程的起点，缺失则无法开始任务
2. **HumanFootman 机制** — 人类作为府兵是核心设计，当前只有简单的 DecisionManager
3. **SOP 阶段状态机** — 阶段状态转换逻辑缺失，导致执行流程不稳定
4. **隐私脱敏 + 本地 LLM** — 用户明确要求的隐私保护策略
4. **EvolutionEngine 完整闭环** — 自进化是差异化竞争力，当前只有教训归档

#### 🟡 中优先级（应该实现）

6. **Agent 状态机 + 心跳** — Agent 生命周期管理不完整
7. **任务暂停/恢复/重试 API** — 基础功能缺失
8. **前端决策面板** — 有 API 但没有对应的 UI
9. **成本熔断完善** — 日预算、熔断阈值、自动暂停
10. **Skill 触发机制 + 版本进化** — Skill 系统不完整

#### 🟢 低优先级（可以延后）

11. **Store 版本管理** — 当前手动管理版本
12. **移动端适配** — 当前桌面优先
13. **GraphQL/BFF 层** — 当前 REST 直接调用
14. **全局事件驱动** — 当前部分模块使用 EventBus

### 8.2 按模块分类

| 模块 | 完成度 | 主要差距 |
|------|--------|----------|
| **Store** | 80% | 版本管理、跨项目隔离 |
| **Skill** | 60% | 触发机制、版本进化、统计 |
| **SOP** | 50% | 阶段状态机、人类决策点、超时 |
| **Agent** | 60% | 状态机、心跳、自动清理 |
| **Vision** | 0% | 完全缺失 |
| **HumanFootman** | 30% | 只有 DecisionManager |
| **CostTracker** | 60% | 日预算、熔断、自动暂停 |
| **EvolutionEngine** | 40% | 只有教训归档，缺少闭环 |
| **Privacy** | 0% | 完全缺失 |
| **Local LLM** | 0% | 完全缺失 |
| **前端** | 60% | 愿景界面、决策面板、进化仪表盘 |
| **API** | 70% | 愿景 API、任务控制 API |

---

## 9. 重构建议

### 9.1 架构重构方向

1. **引入统一状态机引擎** — 所有实体（Task, Agent, Stage, Decision）使用统一的状态机框架
2. **分离领域层与 API 层** — api/main.py 只负责 HTTP 协议转换，业务逻辑移到 core/ 领域类
3. **补齐 Vision 模块** — 新建 core/vision.py + api visions 端点 + 前端愿景界面
4. **重构 HumanFootman** — 基于 DecisionManager 扩展，添加状态、超时、队列
5. **完善 EvolutionEngine** — 基于现有 lesson_archivist.py 扩展完整闭环

### 9.2 代码重构方向

1. **类型安全** — 前端逐步替换 `any` 为具体类型
2. **测试覆盖** — 为核心领域类添加单元测试
3. **文档同步** — 确保代码注释与实现一致

---

*本审计基于 PRD-V2.0.md 和 DDD-V2.0.md 的设计要求，对现有代码进行逐项对比。所有差距均已标注优先级，供重构计划参考。*
