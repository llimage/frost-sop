"""
F16 FastAPI — Pydantic 请求/响应模型
"""

from pydantic import BaseModel, Field


# ── Projects ──
class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    status: str = "active"
    created_at: str | None = None
    updated_at: str | None = None


# ── Tasks ──
class TaskCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, description="任务描述")
    sop_id: str = Field(default="DEV-001", description="SOP模板ID")
    project_id: str = Field(default="default", description="项目ID")
    use_real_llm: bool = Field(default=False, description="是否使用真实LLM")
    web_content: str = Field(default=None, description="预抓取的网页内容（由外部Agent提供）")


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str | None = None
    project_id: str | None = None
    status: str = "pending"
    created_at: str | None = None
    updated_at: str | None = None
    completed_at: str | None = None
    result_summary: str | None = None


class TaskStageResponse(BaseModel):
    id: int
    task_id: str
    stage_name: str
    stage_order: int
    status: str = "pending"
    output: str | None = None
    error: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class TaskExecuteResponse(BaseModel):
    task_id: str
    status: str
    stages: list[TaskStageResponse] = []
    message: str


# ── Agents ──
class AgentResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    generation: int | None = None
    parent_id: str | None = None
    status: str | None = "idle"
    total_tokens_used: int | None = 0
    total_cost: float | None = 0.0
    created_at: str | None = None


# ── Costs ──
class CostLogResponse(BaseModel):
    id: int
    timestamp: str | None = None
    task_id: str | None = None
    agent_id: str
    model: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class CostSummaryResponse(BaseModel):
    monthly_total: float
    model_breakdown: dict = {}
    recent_logs: list[CostLogResponse] = []
    budget_limit: float | None = None


# ── Chat ──
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    project_id: str | None = "default"
    use_real_llm: bool = False


class ChatResponse(BaseModel):
    reply: str
    tokens_used: dict | None = None
    model: str | None = None


# ── Skills ──
class SkillResponse(BaseModel):
    id: str
    name: str
    description: str | None = None
    skill_type: str | None = None
    version: str = "1.0"
    is_active: bool = True
    trigger_keywords: str | None = None
    success_rate: float | None = 0.0
    status: str | None = "active"
    task_type: str | None = None
    created_at: str | None = None


class SkillVersionResponse(BaseModel):
    id: int
    skill_id: str
    version: str
    changelog: str | None = None
    created_at: str | None = None


# ── Schedule ──
class ScheduleCreateRequest(BaseModel):
    title: str = Field(..., min_length=1)
    start_time: str = Field(..., description="ISO 8601 datetime")
    end_time: str = Field(..., description="ISO 8601 datetime")
    repeat_type: str = "none"
    repeat_end: str = ""
    description: str = ""


class ScheduleResponse(BaseModel):
    id: int
    title: str
    description: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    repeat_type: str = "none"
    repeat_end: str = ""
    notified: bool = False
    created_at: str | None = None


# ── Panel (V5.0) ──
class PanelGenerateRequest(BaseModel):
    task_id: str = Field(..., description="任务ID")
    sop_id: str | None = Field(None, description="SOP模板ID（可选，自动从任务关联）")


class DecisionSubmitRequest(BaseModel):
    decision_id: str = Field(..., description="决策ID")
    decision: str = Field(..., description="决策结果：确认/驳回/修改")
    reason: str = Field(default="", description="决策理由")
    human_agent_id: str = Field(default="web_user", description="Human Agent ID")


class DecisionResponse(BaseModel):
    decision_id: str
    task_id: str
    status: str
    decision: str | None = None
    reason: str | None = None


# ── Generic ──
class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
