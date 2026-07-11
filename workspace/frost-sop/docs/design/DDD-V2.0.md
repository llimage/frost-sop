# FROST-SOP DDD V2.0
## 一人公司 AI 指挥平台 — 详细设计文档

**版本**: V2.0  
**日期**: 2026-07-09  
**对应 PRD**: PRD-V2.0.md  
**状态**: 设计中

---

## 1. 架构概览

### 1.1 分层架构

```
┌─────────────────────────────────────────────────────────────┐
│  表现层 (Presentation)                                       │
│  Next.js 前端 + React 组件 + TanStack Query + SSE            │
│  ErrorBoundary + 实时状态同步 + 决策面板                     │
├─────────────────────────────────────────────────────────────┤
│  应用层 (Application)                                        │
│  FastAPI REST API + 全局异常处理 + 请求校验                   │
│  任务编排器 + Agent 调度器 + 决策路由器                       │
├─────────────────────────────────────────────────────────────┤
│  领域层 (Domain)                                            │
│  Store + Skill + SOP + Agent 家族 + 人类府兵                  │
│  自进化引擎 + 成本追踪器 + 隐私脱敏器                         │
├─────────────────────────────────────────────────────────────┤
│  基础设施层 (Infrastructure)                                  │
│  SQLite (持久化) + ChromaDB (向量) + 文件系统 (资产)         │
│  LLM 客户端 (本地 Ollama + 云端 DeepSeek) + SSE 推送         │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 核心设计原则

1. **确定性编排 + LLM 推理分离**: SOP 引擎是确定性的（规则驱动），LLM 只负责阶段内的推理任务
2. **Store 为中心**: 所有状态变更通过 Store，便于审计和回滚
3. **Skill 可组合**: Skill 是原子能力，可独立测试、版本管理、跨项目共享
4. **人类是府兵**: 人类在 SOP 中是一个特殊 Agent，有状态、超时、队列

---

## 2. 领域模型

### 2.1 核心实体

#### 2.1.1 Vision（愿景）

```python
class Vision:
    vision_id: str           # 唯一标识 vis_xxx
    raw_input: str           # 用户原始输入
    clarified_questions: List[ClarifiedQuestion]  # 多轮问卷
    structured_goal: str     # 结构化目标
    success_criteria: List[str]  # 成功标准
    constraints: List[str]     # 约束条件
    suggested_sop: str       # 推荐 SOP ID
    confidence_score: float  # 置信度 0-1
    status: VisionStatus     # pending | confirmed | rejected
    created_at: datetime
    confirmed_at: datetime | None
```

**状态机**:
```
[pending] → 多轮问卷澄清 → [clarified] → 用户确认 → [confirmed]
                                              ↓
                                         [rejected] → 重新澄清
```

#### 2.1.2 SOP（标准操作程序）

```python
class SOP:
    sop_id: str              # 唯一标识 SOP-XXX
    name: str
    description: str
    version: str             # semver: 1.0.0
    stages: List[SOPStage]   # 有序阶段列表
    created_at: datetime
    updated_at: datetime
    is_template: bool        # 是否模板（可复用）
    evolution_history: List[EvolutionRecord]  # 进化历史
```

#### 2.1.3 SOPStage（阶段）

```python
class SOPStage:
    stage_id: str            # 唯一标识 SE-XXX
    name: str
    description: str
    order: int               # 执行顺序
    agent_type: str          # monitor | executor | analyst | ceo | human
    required_keys: List[str]    # 输入上下文键
    output_keys: List[str]      # 输出上下文键
    timeout_minutes: int     # 超时时间
    human_decision: bool     # 是否需要人类决策
    
    # 执行时填充
    status: StageStatus      # pending | running | completed | failed | waiting_human | timeout
    started_at: datetime | None
    completed_at: datetime | None
    output: dict | None
    error: str | None
    cost_cny: float          # 本阶段成本
```

**状态机**:
```
[pending] → 前置条件满足 → [running]
    ↓
[completed] ← 执行成功 ← [running] → 执行失败 → [failed]
    ↓                              ↓
    ↓                        需要人类决策 → [waiting_human]
    ↓                              ↓
    ↓                         超时 → [timeout]
    ↓                              ↓
    ↓                         人类响应 → [completed] 或 [failed]
    ↓
[next stage pending]
```

#### 2.1.4 Agent（家族成员）

```python
class Agent:
    agent_id: str            # 唯一标识 agent_xxx
    name: str
    agent_type: AgentType    # ancestor | parent | scout | hunter | human
    generation: int          # 代际: 0=创始人, 1=祖辈, 2=父辈, 3=孙辈
    parent_id: str | None    # 父 Agent ID
    status: AgentStatus      # idle | running | paused | completed | failed
    
    # 能力
    skills: List[str]        # 可执行的 Skill ID 列表
    max_tokens_per_call: int   # 单次调用最大 token
    preferred_model: str     # 偏好模型
    
    # 统计
    total_tasks: int
    successful_tasks: int
    total_cost_cny: float
    total_tokens_used: int
    
    created_at: datetime
    last_heartbeat: datetime
```

**Agent 类型层次**:
```
Founder（创始人）— 人类，君主，发布任务
    ↓
Ancestor（祖辈）— 编排 SOP，分配任务，监控全局
    ↓
Parent（父辈）— 协调执行，处理异常，汇报进度
    ↓
Scout（斥候）— 具体执行，收集信息，完成阶段任务
    ↓
Hunter（猎手）— 处理结果，提取知识，归档教训
```

**Agent 状态机**:
```
[idle] → 接收任务 → [running]
    ↓
[running] → 暂停 → [paused] → 恢复 → [running]
    ↓
[running] → 完成 → [completed]
    ↓
[running] → 失败 → [failed] → 重试 → [running]
    ↓
[completed/failed] → 合并/销毁 → [terminated]
```

#### 2.1.5 Skill（技能）

```python
class Skill:
    skill_id: str            # 唯一标识 skill_xxx
    name: str
    description: str
    skill_type: SkillType    # llm_call | data_fetch | file_op | notification | custom
    
    # 执行
    handler: Callable        # 执行函数
    required_keys: List[str]   # 必需输入
    optional_keys: List[str]   # 可选输入
    output_schema: dict      # 输出结构
    
    # 触发
    trigger_keywords: List[str]  # 关键词匹配触发
    trigger_sop_ids: List[str]   # 特定 SOP 触发
    
    # 元数据
    version: str             # semver
    is_active: bool
    success_rate: float      # 历史成功率
    avg_cost_cny: float      # 平均成本
    avg_duration_ms: int     # 平均耗时
    
    # 进化
    evolution_history: List[SkillEvolution]
    created_at: datetime
    updated_at: datetime
```

#### 2.1.6 Store（资产库）

```python
class Store:
    # 存储键命名规范
    # task:{task_id}        — 任务记录
    # vision:{vision_id}    — 愿景文档
    # sop:{sop_id}:v{version} — SOP 版本
    # skill:{skill_id}:v{version} — Skill 版本
    # lesson:{lesson_id}    — 教训归档
    # agent:{agent_id}       — Agent 状态
    # plan:{plan_id}/lessons — 计划关联的教训
    # config:{key}           — 配置项
    
    def save(self, key: str, value: dict) -> bool
    def load(self, key: str) -> dict | None
    def list_keys(self, prefix: str = "") -> List[str]
    def delete(self, key: str) -> bool
    def exists(self, key: str) -> bool
```

#### 2.1.7 HumanFootman（人类府兵）

```python
class HumanFootman:
    # 人类在 SOP 中作为特殊 Agent
    footman_id: str          # 通常 = user_id
    name: str                # 显示名称
    status: FootmanStatus    # idle | busy | offline
    
    # 任务队列
    pending_decisions: List[DecisionPoint]  # 待决策队列
    max_concurrent: int      # 最大并行决策数 (默认 3)
    
    # 超时
    default_timeout_minutes: int  # 默认 30
    timeout_action: TimeoutAction  # escalate | abort | auto_approve
    
    # 通知
    notification_channels: List[str]  # web | email | wechat
    
    # 统计
    total_decisions: int
    avg_response_time_minutes: float
    timeout_count: int
```

**DecisionPoint（决策点）**:
```python
class DecisionPoint:
    decision_id: str
    task_id: str
    stage_id: str
    question: str            # 决策问题
    options: List[Option]    # 选项列表
    context: dict            # 决策上下文
    
    status: DecisionStatus   # pending | approved | rejected | modified | timeout
    created_at: datetime
    expires_at: datetime     # 超时时间
    responded_at: datetime | None
    
    decision: str | None     # 用户决策
    reason: str | None       # 决策理由
```

**决策状态机**:
```
[pending] → 推送给人类 → 等待响应
    ↓
[approved] ← 用户批准 ← [pending] → 用户驳回 → [rejected]
    ↓                              ↓
    ↓                         用户修改 → [modified]
    ↓                              ↓
    ↓                         超时 → [timeout] → 执行 timeout_action
```

#### 2.1.8 CostTracker（成本追踪）

```python
class CostTracker:
    monthly_budget_cny: float    # 月度预算 (默认 300)
    daily_budget_cny: float      # 日预算 (默认 100)
    
    # 实时统计
    current_month_spent: float
    current_day_spent: float
    
    # 熔断
    fuse_threshold_cny: float    # 熔断阈值 (默认 1000)
    is_fused: bool               # 是否已熔断
    
    # 明细
    logs: List[CostLog]
    
    def check_budget(self, estimated_cost: float) -> bool
    def record(self, task_id: str, agent_id: str, tokens: int, cost_cny: float)
    def get_monthly_report(self) -> CostReport
```

**CostLog**:
```python
class CostLog:
    log_id: str
    timestamp: datetime
    task_id: str
    agent_id: str
    stage_id: str | None
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    estimated_cost_cny: float
```

#### 2.1.9 EvolutionEngine（自进化引擎）

```python
class EvolutionEngine:
    # 错误记录
    def record_error(self, error: ErrorRecord) -> str
    
    # 教训归档
    def archive_lesson(self, error_id: str) -> Lesson | None
    
    # 趋势分析
    def analyze_trends(self, time_range: str = "7d") -> TrendReport
    
    # 生成优化建议
    def generate_proposals(self, trend_report: TrendReport) -> List[OptimizationProposal]
    
    # 执行进化（需人类确认）
    def apply_evolution(self, proposal_id: str, approved: bool) -> EvolutionResult
    
    # 验证与回滚
    def validate_evolution(self, evolution_id: str) -> bool
    def rollback(self, evolution_id: str) -> bool
```

**ErrorRecord**:
```python
class ErrorRecord:
    error_id: str
    timestamp: datetime
    error_type: str          # API_ERROR | DB_ERROR | LLM_ERROR | TIMEOUT | UNKNOWN
    error_message: str
    component: str           # 出错的组件/模块
    stack_trace: str | None
    context: dict            # 执行上下文快照
    task_id: str | None
    stage_id: str | None
    agent_id: str | None
    
    # 关联
    lesson_id: str | None    # 关联的教训ID
    times_encountered: int   # 相同错误出现次数
```

**Lesson（教训）**:
```python
class Lesson:
    lesson_id: str
    error_id: str | None     # 关联的错误
    
    severity: str            # critical | major | minor | info
    category: str            # 技术 | 资源 | 假设 | SOP | 外部 | 未知
    root_cause: str          # 根本原因
    actionable_fix: str      # 具体可执行的改进建议
    preventable: bool        # 是否可预防
    applicable_to_future: str  # 适用于什么类型的未来任务
    
    archived_at: datetime
    times_applied: int       # 被应用次数
```

**OptimizationProposal（优化建议）**:
```python
class OptimizationProposal:
    proposal_id: str
    type: str                # sop_optimization | skill_update | config_change | constitution_review
    target: str              # 目标对象
    reason: str              # 原因
    priority: str            # high | medium | low
    
    # 变更内容
    current_version: str
    proposed_changes: dict   # 具体变更
    estimated_impact: str    # 预期影响
    
    # 状态
    status: str              # pending | approved | rejected | applied | rolled_back
    created_at: datetime
    approved_at: datetime | None
    applied_at: datetime | None
```

---

### 2.2 实体关系图 (ER)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Vision    │────→│     SOP     │←────│ SOPTemplate │
│  (愿景)     │     │ (操作程序)   │     │  (模板库)   │
└─────────────┘     └──────┬──────┘     └─────────────┘
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │SOPStage │  │SOPStage │  │SOPStage │  ...
        │(阶段1)  │  │(阶段2)  │  │(阶段3)  │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┴────────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │    Task     │
                    │   (任务)    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  Agent  │  │  Agent  │  │  Agent  │
        │(Ancestor)│  │(Parent) │  │(Scout)  │
        └────┬────┘  └────┬────┘  └────┬────┘
             │            │            │
             └────────────┴────────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │    Skill    │
                    │   (技能)    │
                    └─────────────┘
                          │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │ Skill   │  │ Skill   │  │ Skill   │
        │Version  │  │Version  │  │Version  │
        │  (v1)   │  │  (v2)   │  │  (v3)   │
        └─────────┘  └─────────┘  └─────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │    Store    │
                    │  (资产库)   │
                    └─────────────┘
                          │
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌─────────┐  ┌─────────┐  ┌─────────┐
        │  task:  │  │ lesson: │  │  sop:   │
        │ records │  │ records │  │templates│
        └─────────┘  └─────────┘  └─────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │HumanFootman │
                    │ (人类府兵)  │
                    └──────┬──────┘
                           │
                          ↓
                    ┌─────────────┐
                    │ DecisionPoint│
                    │  (决策点)   │
                    └─────────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │CostTracker  │
                    │ (成本追踪)  │
                    └─────────────┘
                          │
                          ↓
                    ┌─────────────┐
                    │EvolutionEngine│
                    │ (自进化引擎) │
                    └─────────────┘
```

---

## 3. 状态机详细设计

### 3.1 任务生命周期状态机

```
                    ┌─────────────┐
         ┌─────────│   created   │
         │         │  (任务创建)  │
         │         └──────┬──────┘
         │                │ 初始化 SOP
         │                ↓
         │         ┌─────────────┐
         │         │  initializing│
         │         │  (初始化中)  │
         │         └──────┬──────┘
         │                │ 分配 Agent
         │                ↓
         │         ┌─────────────┐     ┌─────────────┐
         │    ┌────│   running   │────→│   paused    │
         │    │    │  (执行中)   │     │  (已暂停)   │
         │    │    └──────┬──────┘     └──────┬──────┘
         │    │           │                   │ 恢复
         │    │           │ 阶段完成            └─────────┐
         │    │           ↓                             │
         │    │    ┌─────────────┐                      │
         │    │    │  stage_next │                      │
         │    │    │(进入下阶段) │                      │
         │    │    └──────┬──────┘                      │
         │    │           │ 还有阶段?                     │
         │    │           │ Y: 继续执行                    │
         │    │           │ N: 全部完成                    │
         │    │           ↓                               │
         │    │    ┌─────────────┐                      │
         └────┘    │  completed  │←───────────────────────┘
              │    │  (已完成)   │
              │    └─────────────┘
              │
              │    ┌─────────────┐
              └───→│   failed    │
                   │  (已失败)   │
                   └──────┬──────┘
                          │ 可重试?
                          │ Y: 重试 → [running]
                          │ N: 终止
                          ↓
                   ┌─────────────┐
                   │  terminated │
                   │  (已终止)   │
                   └─────────────┘
```

**状态转换表**:

| 当前状态 | 事件 | 下一状态 | 触发条件 | 副作用 |
|----------|------|----------|----------|--------|
| created | init_sop | initializing | 愿景已确认 | 创建 SOP 实例 |
| initializing | assign_agent | running | Agent 分配成功 | 启动第一个阶段 |
| running | stage_complete | stage_next | 阶段成功完成 | 记录输出，更新进度 |
| running | stage_fail | failed | 阶段失败且不可重试 | 记录错误，归档教训 |
| running | stage_fail | running | 阶段失败但可重试 | 重试当前阶段 |
| running | human_decision | paused | 需要人类决策 | 创建 DecisionPoint，推送通知 |
| paused | human_approve | running | 人类批准继续 | 恢复执行 |
| paused | human_reject | failed | 人类驳回 | 记录原因，终止任务 |
| paused | timeout | timeout | 超时无响应 | 执行 timeout_action |
| stage_next | has_more_stages | running | 还有后续阶段 | 启动下一阶段 |
| stage_next | all_done | completed | 所有阶段完成 | 生成总结报告 |
| failed | retry | running | 用户触发重试 | 从失败阶段重新开始 |
| failed | abort | terminated | 用户终止 | 清理资源，归档 |

### 3.2 Agent 生命周期状态机

```
┌─────────────┐
│   spawned   │
│  (已创建)   │
└──────┬──────┘
       │ 初始化
       ↓
┌─────────────┐     ┌─────────────┐
│    idle     │←────│  completed  │
│  (空闲)     │     │  (已完成)   │
└──────┬──────┘     └─────────────┘
       │ 接收任务
       ↓
┌─────────────┐     ┌─────────────┐
│   running   │────→│   paused    │
│  (执行中)   │     │  (已暂停)   │
└──────┬──────┘     └──────┬──────┘
       │ 完成               │ 恢复
       │                    ↓
       │              ┌─────────────┐
       │              │   running   │
       │              └─────────────┘
       │
       │ 失败
       ↓
┌─────────────┐
│   failed    │
│  (已失败)   │
└──────┬──────┘
       │ 重试
       ↓
┌─────────────┐
│   running   │
└─────────────┘
```

### 3.3 决策点状态机

```
┌─────────────┐
│   pending   │
│  (待决策)   │
└──────┬──────┘
       │ 推送给人类
       ↓
┌─────────────┐
│  notified   │
│  (已通知)   │
└──────┬──────┘
       │ 人类响应
       ↓
┌─────────────┐
│  responding │
│  (响应中)   │
└──────┬──────┘
       │
   ┌───┼───┐
   ↓   ↓   ↓
┌────┐┌────┐┌────┐
│approved│rejected│modified│
│(批准) │(驳回) │(修改) │
└────┘└────┘└────┘
       │
       │ 超时
       ↓
┌─────────────┐
│   timeout   │
│  (已超时)   │
└──────┬──────┘
       │ 执行 timeout_action
       ↓
   ┌───┼───┐
   ↓   ↓   ↓
┌────┐┌────┐┌────┐
│escalate│abort │auto_approve│
│(升级) │(中止)│(自动批准) │
└────┘└────┘└────┘
```

---

## 4. 接口契约

### 4.1 REST API 规范

#### 4.1.1 愿景管理

```
POST /api/visions
请求: { raw_input: string }
响应: { vision_id, status: "pending", clarification_questions: [...] }

POST /api/visions/{vision_id}/clarify
请求: { answers: [{question_id, answer}] }
响应: { vision_id, status: "clarified", structured_goal, confidence_score }

POST /api/visions/{vision_id}/confirm
请求: { confirmed: boolean, modifications?: string }
响应: { vision_id, status: "confirmed" | "rejected", suggested_sop }

GET /api/visions/{vision_id}
响应: Vision 完整对象
```

#### 4.1.2 任务管理

```
POST /api/tasks
请求: { vision_id: string, sop_id?: string, priority?: "low" | "normal" | "high" }
响应: { task_id, status: "created", message }

GET /api/tasks/{task_id}
响应: Task 完整对象 + 当前阶段 + Agent 状态

GET /api/tasks/{task_id}/stages
响应: List[Stage] 按 order 排序

POST /api/tasks/{task_id}/pause
响应: { task_id, status: "paused" }

POST /api/tasks/{task_id}/resume
响应: { task_id, status: "running" }

POST /api/tasks/{task_id}/retry
响应: { task_id, status: "running", retry_from_stage: string }

DELETE /api/tasks/{task_id}
响应: { success: boolean }
```

#### 4.1.3 Agent 管理

```
GET /api/agents
响应: List[Agent] 状态摘要

GET /api/agents/{agent_id}
响应: Agent 完整对象 + 执行历史

POST /api/agents/{agent_id}/heartbeat
请求: { status: "idle" | "running", progress?: number }
响应: { acknowledged: boolean }
```

#### 4.1.4 决策管理

```
GET /api/decisions
查询: ?status=pending&task_id=xxx
响应: List[DecisionPoint]

POST /api/decisions/{decision_id}/submit
请求: { decision: "approve" | "reject" | "modify", reason?: string, modification?: string }
响应: { decision_id, status, next_action }

POST /api/decisions/check-timeout
响应: { checked: number, resolved: number, failed: number }
```

#### 4.1.5 实时事件 (SSE)

```
GET /api/events
SSE 流: event: task.updated, stage.completed, agent.status_changed, decision.pending, cost.threshold_warning

事件格式:
event: task.updated
data: { type, data: Task, timestamp }
```

#### 4.1.6 成本管理

```
GET /api/costs
查询: ?month=2026-07
响应: CostReport { monthly_total, daily_breakdown, model_breakdown, budget_status }

GET /api/costs/logs
查询: ?task_id=xxx&limit=50
响应: List[CostLog]
```

#### 4.1.7 进化管理

```
POST /api/evolution/trigger
请求: { error_type, error_message, component, context }
响应: { task_id, status: "pending" }

GET /api/evolution/status
响应: { total_errors, archived_lessons, pending_evolutions, last_evolution }

GET /api/evolution/proposals
响应: List[OptimizationProposal]

POST /api/evolution/proposals/{proposal_id}/approve
请求: { approved: boolean, modification?: string }
响应: { proposal_id, status, applied_at? }
```

#### 4.1.8 对话

```
POST /api/chat
请求: { message: string, project_id?: string, use_real_llm?: boolean }
响应: { reply, tokens_used, model }
```

### 4.2 错误响应规范

```json
{
  "error_code": "TASK_ID_INVALID",
  "error_id": "err-a1b2c3d4",
  "message": "任务ID不能为空或undefined",
  "path": "/api/tasks/undefined/stages",
  "timestamp": "2026-07-09T17:00:00Z",
  "suggestion": "请检查任务ID是否正确"
}
```

**错误码列表**:

| 错误码 | HTTP状态 | 说明 |
|--------|----------|------|
| TASK_ID_INVALID | 400 | 任务ID无效 |
| PROJECT_ID_INVALID | 400 | 项目ID无效 |
| VISION_INPUT_EMPTY | 400 | 愿景输入为空 |
| CHAT_MESSAGE_EMPTY | 400 | 聊天消息为空 |
| DECISION_ID_EMPTY | 400 | 决策ID为空 |
| SOP_NOT_FOUND | 404 | SOP模板不存在 |
| TASK_NOT_FOUND | 404 | 任务不存在 |
| AGENT_NOT_FOUND | 404 | Agent不存在 |
| STAGES_QUERY_FAILED | 500 | 阶段查询失败 |
| EVOLUTION_TRIGGER_FAILED | 500 | 进化触发失败 |
| INTERNAL_SERVER_ERROR | 500 | 内部服务器错误 |
| REQUEST_TIMEOUT | 504 | 请求超时 |
| NETWORK_ERROR | 0 | 网络错误 |

### 4.3 前端 ↔ 后端数据流

```
┌─────────────┐                    ┌─────────────┐
│   前端      │                    │   后端      │
│  (Next.js)  │                    │  (FastAPI)  │
└──────┬──────┘                    └──────┬──────┘
       │                                 │
       │ 1. TanStack Query 初始加载      │
       │────────────────────────────────→│
       │    GET /api/tasks, /api/agents  │
       │                                 │
       │ 2. SSE 实时订阅                  │
       │←────────────────────────────────│
       │    GET /api/events (stream)     │
       │    event: task.updated          │
       │    → invalidateQueries(["tasks"])│
       │                                 │
       │ 3. 用户操作                     │
       │────────────────────────────────→│
       │    POST /api/tasks (创建任务)   │
       │                                 │
       │ 4. 需要人类决策                 │
       │←────────────────────────────────│
       │    SSE: event: decision.pending   │
       │    → 显示决策面板               │
       │                                 │
       │ 5. 人类响应                     │
       │────────────────────────────────→│
       │    POST /api/decisions/xxx/submit│
       │                                 │
       │ 6. 状态更新                     │
       │←────────────────────────────────│
       │    SSE: event: decision.resolved│
       │    → 刷新任务状态               │
       │                                 │
       │ 7. 成本预警                     │
       │←────────────────────────────────│
       │    SSE: event: cost.threshold   │
       │    → 显示警告横幅               │
```

---

## 5. 数据模型

### 5.1 数据库表结构

```sql
-- 1. 项目表
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',  -- active | paused | archived
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- 2. 愿景表
CREATE TABLE visions (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    raw_input TEXT NOT NULL,
    structured_goal TEXT,
    success_criteria TEXT,  -- JSON array
    constraints TEXT,        -- JSON array
    suggested_sop TEXT,
    confidence_score REAL,
    status TEXT DEFAULT 'pending',  -- pending | clarified | confirmed | rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    confirmed_at TIMESTAMP
);

-- 3. 任务表
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT REFERENCES projects(id),
    vision_id TEXT REFERENCES visions(id),
    sop_id TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'created',  -- created | initializing | running | paused | completed | failed | terminated
    priority TEXT DEFAULT 'normal',  -- low | normal | high
    current_stage_id TEXT,
    progress REAL DEFAULT 0,  -- 0-100
    result_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP,
    completed_at TIMESTAMP,
    total_cost_cny REAL DEFAULT 0
);

-- 4. 阶段表
CREATE TABLE task_stages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT REFERENCES tasks(id),
    stage_id TEXT NOT NULL,  -- SOP 中的阶段 ID
    stage_name TEXT,
    stage_order INTEGER,
    status TEXT DEFAULT 'pending',  -- pending | running | completed | failed | waiting_human | timeout
    output TEXT,  -- JSON
    error TEXT,
    agent_id TEXT,
    cost_cny REAL DEFAULT 0,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 5. Agent 表
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    name TEXT,
    agent_type TEXT,  -- ancestor | parent | scout | hunter | human
    generation INTEGER DEFAULT 0,
    parent_id TEXT REFERENCES agents(id),
    task_id TEXT REFERENCES tasks(id),
    status TEXT DEFAULT 'idle',  -- idle | running | paused | completed | failed | terminated
    skills TEXT,  -- JSON array of skill IDs
    total_tasks INTEGER DEFAULT 0,
    successful_tasks INTEGER DEFAULT 0,
    total_cost_cny REAL DEFAULT 0,
    total_tokens_used INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP
);

-- 6. 决策点表
CREATE TABLE decision_points (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    decision_id TEXT UNIQUE,
    task_id TEXT REFERENCES tasks(id),
    stage_id TEXT,
    agent_id TEXT,
    question TEXT,
    options TEXT,  -- JSON
    context TEXT,  -- JSON
    status TEXT DEFAULT 'pending',  -- pending | approved | rejected | modified | timeout
    decision TEXT,
    reason TEXT,
    human_agent_id TEXT DEFAULT 'web_user',
    -- V9.1: 超时机制
    timeout_minutes INTEGER DEFAULT 30,
    expires_at TIMESTAMP,
    timeout_action TEXT DEFAULT 'escalate',  -- escalate | abort | auto_approve
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    responded_at TIMESTAMP
);

-- 7. 成本日志表
CREATE TABLE cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    task_id TEXT REFERENCES tasks(id),
    stage_id TEXT,
    agent_id TEXT,
    model TEXT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    estimated_cost_cny REAL DEFAULT 0
);

-- 8. 错误记录表
CREATE TABLE error_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error_id TEXT UNIQUE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_type TEXT,  -- API_ERROR | DB_ERROR | LLM_ERROR | TIMEOUT | UNKNOWN
    error_message TEXT,
    component TEXT,
    stack_trace TEXT,
    context TEXT,  -- JSON
    task_id TEXT,
    stage_id TEXT,
    agent_id TEXT,
    lesson_id TEXT,
    times_encountered INTEGER DEFAULT 1
);

-- 9. 审计日志表
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level TEXT,  -- INFO | WARN | ERROR
    component TEXT,
    message TEXT,
    context TEXT,  -- JSON
    task_id TEXT,
    agent_id TEXT
);

-- 10. 配置表
CREATE TABLE config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 5.2 Store 键命名规范

```
-- 任务相关
task:{task_id}              → Task 对象
task:{task_id}/stages       → List[Stage] 执行历史
task:{task_id}/cost         → 成本汇总

-- 愿景相关
vision:{vision_id}          → Vision 对象
vision:{vision_id}/clarification → 澄清问答记录

-- SOP 相关
sop:{sop_id}:v{version}     → SOP 对象
sop_template:{sop_id}       → SOP 模板
sop:{sop_id}/evolution      → 进化历史

-- Skill 相关
skill:{skill_id}:v{version} → Skill 对象
skill:{skill_id}/stats      → 使用统计

-- 教训相关
lesson:{lesson_id}          → Lesson 对象
lesson:category:{category}  → 按分类索引
plan:{plan_id}/lessons      → 计划关联的教训列表

-- Agent 相关
agent:{agent_id}            → Agent 对象
agent:{agent_id}/history    → 执行历史

-- 配置相关
config:budget_limit         → 预算限制
config:fuse_threshold       → 熔断阈值
config:default_timeout      → 默认超时
```

---

## 6. 关键算法

### 6.1 愿景澄清算法

```python
def clarify_vision(raw_input: str) -> Vision:
    """
    多轮问卷澄清算法。
    
    1. 初始分析: LLM 分析 raw_input，提取关键词和意图
    2. 生成问题: 基于缺失信息生成澄清问题
    3. 用户回答: 收集用户回答
    4. 结构化: 将回答整合为结构化愿景文档
    5. 置信度评估: LLM 评估置信度，低则继续澄清
    """
    
    # 步骤1: 初始分析（本地 LLM，轻量）
    analysis = local_llm.analyze(raw_input)
    
    # 步骤2: 生成澄清问题（本地 LLM）
    missing_fields = detect_missing_fields(analysis)
    questions = generate_questions(missing_fields)
    
    # 步骤3-4: 多轮交互（最多 3 轮）
    answers = {}
    for round in range(3):
        if not questions:
            break
        answers.update(ask_user(questions))
        questions = generate_follow_up(answers)
    
    # 步骤5: 结构化（后端 LLM，脱敏后）
    sanitized = sanitize(answers)  # 脱敏
    structured = backend_llm.structure(sanitized)
    confidence = backend_llm.evaluate_confidence(structured)
    
    return Vision(
        raw_input=raw_input,
        clarified_questions=answers,
        structured_goal=structured.goal,
        confidence_score=confidence,
        status="clarified" if confidence > 0.8 else "pending"
    )
```

### 6.2 SOP 编排算法

```python
class SOPEngine:
    """
    确定性 SOP 编排引擎。
    核心原则: 编排是确定性的，LLM 只负责阶段内的推理。
    """
    
    def execute(self, task: Task) -> Task:
        while task.status == "running":
            current_stage = self.get_current_stage(task)
            
            # 检查前置条件
            if not self.check_prerequisites(current_stage, task):
                task.status = "failed"
                break
            
            # 检查是否需要人类决策
            if current_stage.human_decision:
                decision = self.create_decision_point(current_stage, task)
                if not self.wait_for_human(decision, timeout=current_stage.timeout_minutes):
                    self.handle_timeout(decision, current_stage.timeout_action)
                continue
            
            # 分配 Agent
            agent = self.assign_agent(current_stage, task)
            
            # 执行阶段
            result = self.execute_stage(current_stage, agent, task)
            
            # 更新状态
            if result.success:
                self.complete_stage(current_stage, result.output)
                if self.has_more_stages(task):
                    self.advance_to_next_stage(task)
                else:
                    task.status = "completed"
            else:
                if self.can_retry(current_stage):
                    self.retry_stage(current_stage)
                else:
                    self.fail_stage(current_stage, result.error)
                    task.status = "failed"
                    self.archive_lesson(task, current_stage, result.error)
            
            # 成本检查
            if self.cost_tracker.is_budget_exceeded():
                self.pause_task(task, reason="预算超支")
                break
        
        return task
```

### 6.3 自进化算法

```python
class EvolutionEngine:
    """
    自进化引擎: 错误记录 → 教训归档 → 趋势分析 → 复盘决策 → 系统进化 → 验证回滚
    """
    
    def evolve(self):
        # 阶段1: 错误检测与记录
        errors = self.detect_errors()
        for error in errors:
            self.record_error(error)
        
        # 阶段2: 教训归档
        for error in errors:
            if not error.lesson_id:
                lesson = self.archive_lesson(error)
                error.lesson_id = lesson.id
        
        # 阶段3: 趋势分析
        trends = self.analyze_trends(time_range="7d")
        insights = self.generate_insights(trends)
        
        # 阶段4: 生成优化建议
        proposals = self.generate_proposals(trends, insights)
        
        # 阶段5: 人类确认（决策点）
        for proposal in proposals:
            decision = self.create_decision(proposal)
            if self.wait_for_human(decision, timeout=30):
                if decision.decision == "approve":
                    # 阶段6: 执行进化
                    evolution = self.apply_evolution(proposal)
                    # 阶段7: 验证
                    if not self.validate_evolution(evolution):
                        self.rollback(evolution)
```

### 6.4 成本熔断算法

```python
class CostFuse:
    """
    成本熔断器。
    """
    
    def check(self, estimated_cost: float) -> bool:
        # 检查月度预算
        if self.monthly_spent + estimated_cost > self.monthly_budget:
            self.trigger_fuse("月度预算超支")
            return False
        
        # 检查日预算
        if self.daily_spent + estimated_cost > self.daily_budget:
            self.trigger_fuse("日预算超支")
            return False
        
        # 检查熔断阈值
        if estimated_cost > self.fuse_threshold:
            self.trigger_fuse(f"单次调用超过熔断阈值 {self.fuse_threshold}")
            return False
        
        return True
    
    def trigger_fuse(self, reason: str):
        self.is_fused = True
        self.notify_user(f"[成本熔断] {reason}。已暂停非关键任务。")
        # 记录到 audit_log
        self.log_event("cost.fuse_triggered", {"reason": reason})
```

---

## 7. 安全设计

### 7.1 输入校验

| 输入类型 | 校验规则 | 失败处理 |
|----------|----------|----------|
| ID 参数 | 非空，不为 "undefined"，匹配 `^[a-zA-Z0-9_-]+$` | 400 TASK_ID_INVALID |
| 文本输入 | 非空，长度 < 10000，过滤危险字符 | 400 INPUT_INVALID |
| JSON 输入 | 严格解析，拒绝未知字段 | 400 JSON_PARSE_ERROR |
| 文件上传 | 大小 < 10MB，类型白名单 | 400 FILE_INVALID |

### 7.2 数据隔离

- 项目级隔离: 每个项目独立的数据命名空间
- 查询限制: 所有查询必须带 project_id 过滤
- 跨项目访问: 显式授权，记录审计日志

### 7.3 隐私保护

- 本地 LLM: 处理所有敏感数据（个人信息、业务数据）
- 脱敏规则:
  - 姓名 → [NAME]
  - 电话 → [PHONE]
  - 邮箱 → [EMAIL]
  - 金额 → [AMOUNT]
  - 公司名 → [COMPANY]
- 后端 LLM: 只接收脱敏后的数据

---

## 8. 部署架构

### 8.1 开发环境

```
┌────────────────────────────────────────┐
│  本地开发机器 (Windows/Mac/Linux)       │
│  ├── Next.js 前端 (localhost:3000)    │
│  ├── FastAPI 后端 (localhost:8000)    │
│  ├── SQLite 数据库                      │
│  ├── Ollama 本地 LLM (localhost:11434)│
│  └── ChromaDB 向量库 (可选)            │
└────────────────────────────────────────┘
         │
         │ API Key
         ↓
    ┌─────────────┐
    │ DeepSeek API │
    │ (云端 LLM)   │
    └─────────────┘
```

### 8.2 生产环境（未来）

```
┌────────────────────────────────────────┐
│  VPS / 云服务器                         │
│  ├── Docker Compose                    │
│  │   ├── Next.js (Nginx 反向代理)      │
│  │   ├── FastAPI (Uvicorn)             │
│  │   ├── SQLite (卷挂载)               │
│  │   └── Ollama (可选，GPU 实例)        │
│  └── 定期备份脚本                       │
└────────────────────────────────────────┘
```

---

## 9. 下一步

1. **现有代码对齐审计**: 对比当前代码与 DDD 设计，生成差距分析表
2. **重构计划**: 按优先级排序，制定分阶段重构路线图

---

*本文档对应 PRD-V2.0.md，所有设计决策均可追溯至 PRD 中的需求条目。*
