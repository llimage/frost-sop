"""
F16 FastAPI — Pydantic 请求/响应模型
"""

from pydantic import BaseModel, Field
from typing import Optional, List


# ── Projects ──
class ProjectResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    status: str = "active"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ── Tasks ──
class TaskCreateRequest(BaseModel):
    description: str = Field(..., min_length=1, description="任务描述")
    sop_id: str = Field(default="DEV-001", description="SOP模板ID")
    project_id: str = Field(default="default", description="项目ID")
    use_real_llm: bool = Field(default=False, description="是否使用真实LLM")


class TaskResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_summary: Optional[str] = None


class TaskStageResponse(BaseModel):
    id: int
    task_id: str
    stage_name: str
    stage_order: int
    status: str = "pending"
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class TaskExecuteResponse(BaseModel):
    task_id: str
    status: str
    stages: List[TaskStageResponse] = []
    message: str


# ── Agents ──
class AgentResponse(BaseModel):
    id: str
    name: str
    agent_type: str
    generation: Optional[int] = None
    parent_id: Optional[str] = None
    status: Optional[str] = "idle"
    total_tokens_used: Optional[int] = 0
    total_cost: Optional[float] = 0.0
    created_at: Optional[str] = None


# ── Costs ──
class CostLogResponse(BaseModel):
    id: int
    timestamp: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: str
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0


class CostSummaryResponse(BaseModel):
    monthly_total: float
    model_breakdown: dict = {}
    recent_logs: List[CostLogResponse] = []
    budget_limit: Optional[float] = None


# ── Chat ──
class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    project_id: Optional[str] = "default"
    use_real_llm: bool = False


class ChatResponse(BaseModel):
    reply: str
    tokens_used: Optional[dict] = None
    model: Optional[str] = None


# ── Skills ──
class SkillResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    skill_type: Optional[str] = None
    version: str = "1.0"
    is_active: bool = True
    trigger_keywords: Optional[str] = None
    success_rate: Optional[float] = 0.0
    status: Optional[str] = "active"
    task_type: Optional[str] = None
    created_at: Optional[str] = None


class SkillVersionResponse(BaseModel):
    id: int
    skill_id: str
    version: str
    changelog: Optional[str] = None
    created_at: Optional[str] = None


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
    description: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    repeat_type: str = "none"
    repeat_end: str = ""
    notified: bool = False
    created_at: Optional[str] = None


# ── Panel (V5.0) ──
class PanelGenerateRequest(BaseModel):
    task_id: str = Field(..., description="任务ID")
    sop_id: Optional[str] = Field(None, description="SOP模板ID（可选，自动从任务关联）")


class DecisionSubmitRequest(BaseModel):
    decision_id: str = Field(..., description="决策ID")
    decision: str = Field(..., description="决策结果：确认/驳回/修改")
    reason: str = Field(default="", description="决策理由")
    human_agent_id: str = Field(default="web_user", description="Human Agent ID")


class DecisionResponse(BaseModel):
    decision_id: str
    task_id: str
    status: str
    decision: Optional[str] = None
    reason: Optional[str] = None


# ── Generic ──
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
