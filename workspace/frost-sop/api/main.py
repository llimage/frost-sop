"""
F16 FastAPI — REST API 层封装
将 Python 核心能力封装为 REST API，供 Next.js 前端调用。

启动方式：
    cd workspace/frost-sop
    python -X utf8 -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

测试：
    curl http://localhost:8000/api/projects
    curl -X POST http://localhost:8000/api/tasks -H "Content-Type: application/json" -d '{"description":"test"}'
"""

import os
import sys
import json
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
import asyncio

# Ensure frost-sop root is on path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from api.models import (
    ProjectResponse, TaskCreateRequest, TaskResponse, TaskStageResponse,
    TaskExecuteResponse, AgentResponse, CostSummaryResponse, ChatRequest,
    ChatResponse, SkillResponse, ScheduleCreateRequest, ScheduleResponse,
    PanelGenerateRequest, DecisionSubmitRequest, DecisionResponse,
)
from core.db import get_db

app = FastAPI(
    title="FROST-SOP API",
    description="FROST 家族AI指挥平台 REST API",
    version="1.0.0",
)

# CORS — S-004 修复：限制为特定域名
cors_origins = os.environ.get(
    "FROST_CORS_ORIGINS",
    "http://localhost:3000,http://localhost:8501,http://localhost:8080",
).split(",")
if os.environ.get("FROST_ENV") == "production":
    cors_origins = [o for o in cors_origins if o != "*"]
    if not cors_origins:
        cors_origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)


# ── Helpers ──
def _row_to_dict(row) -> dict:
    """Convert sqlite3.Row to dict, handling non-serializable types."""
    if row is None:
        return None
    d = dict(row) if hasattr(row, "keys") else row
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, bytes):
                d[k] = v.decode("utf-8", errors="replace")
            elif isinstance(v, (datetime,)):
                d[k] = v.isoformat()
    return d


def _rows_to_list(rows) -> list:
    return [_row_to_dict(r) for r in rows] if rows else []


def _ensure_project_exists(db, project_id="default"):
    """Ensure a default project exists."""
    existing = db.select_one("projects", "id", project_id)
    if not existing:
        db.insert("projects", {
            "id": project_id,
            "name": "默认项目",
            "description": "FROST-SOP 默认项目",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
    return project_id


# ═══════════════════════════════════════════════════════════════
# 1. GET /api/projects — 项目列表
# ═══════════════════════════════════════════════════════════════
@app.get("/api/projects", response_model=List[ProjectResponse])
def list_projects():
    db = get_db()
    rows = db.select_all("projects", "status = 'active'")
    return _rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# 2. GET /api/projects/{id} — 项目详情
# ═══════════════════════════════════════════════════════════════
@app.get("/api/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str):
    db = get_db()
    row = db.select_one("projects", "id", project_id)
    if not row:
        _ensure_project_exists(db, project_id)
        row = db.select_one("projects", "id", project_id)
    return _row_to_dict(row)


# ═══════════════════════════════════════════════════════════════
# 3. POST /api/tasks — 执行任务（触发 SOP）
# ═══════════════════════════════════════════════════════════════
@app.post("/api/tasks", response_model=TaskExecuteResponse)
def create_and_run_task(req: TaskCreateRequest):
    """
    创建并执行一个 SOP 任务。
    使用 FROST 家族 Agent 体系：Ancestor → Parent → 5孙辈。
    """
    task_id = f"task-{uuid.uuid4().hex[:8]}"
    db = get_db()
    _ensure_project_exists(db, req.project_id)

    # 初始化任务记录
    db.insert("tasks", {
        "id": task_id,
        "title": req.description[:60],
        "description": req.description,
        "project_id": req.project_id,
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })

    # 加载 SOP 模板并记录（使用请求中的 sop_id）
    from core.sop import SOP
    sop = SOP.load_from_yaml(f"sops/templates/{req.sop_id}.yaml")

    sop_template_id = f"sop_template:{sop.sop_id}"
    existing_sop = db.select_one("sop_templates", "id", sop_template_id)
    if not existing_sop:
        db.insert("sop_templates", {
            "id": sop_template_id,
            "sop_id": sop.sop_id,
            "name": sop.name,
            "version": sop.version,
            "content": json.dumps(sop.stages if hasattr(sop, "stages") else {}, ensure_ascii=False),
            "is_preset": 1,
            "is_validated": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })

    sop_execution_id = db.insert("sop_executions", {
        "task_id": task_id,
        "sop_template_id": sop_template_id,
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "total_stages": len(sop.stages) if hasattr(sop, "stages") else 5,
        "completed_stages": 0,
    })

    # 执行 SOP（使用 FROST 家族体系）
    stages_result = []
    try:
        from stores.constitution import create_constitution_store
        from stores.asset import create_asset_store
        from agents.ancestor import create_ancestor
        from agents.parent import create_parent

        constitution_store = create_constitution_store()
        asset_store = create_asset_store()
        ancestor = create_ancestor(constitution_store, asset_store)
        parent = create_parent(name="parent-api", coordination_store=asset_store)

        phases = sop.stages if hasattr(sop, "stages") else []
        stage_context = {"_stage_results": [], "_parent_agent": parent}

        for i, phase in enumerate(phases):
            stage_name = phase.get("name", phase.get("phase_id", f"阶段{i+1}"))
            stage_order = i + 1
            started = datetime.now().isoformat()

            stage_context["_current_stage"] = phase
            stage_context = parent.run(
                sop_steps=["execute_stage"],
                initial_context=stage_context
            )

            result = stage_context.get("_current_stage_result", {})
            output = str(result.get("output", ""))[:500]
            completed = datetime.now().isoformat()

            # 写入 task_stages
            stage_id = db.insert("task_stages", {
                "task_id": task_id,
                "stage_name": stage_name,
                "stage_order": stage_order,
                "status": "completed",
                "output": output,
                "started_at": started,
                "completed_at": completed,
            })

            stages_result.append(TaskStageResponse(
                id=stage_id,
                task_id=task_id,
                stage_name=stage_name,
                stage_order=stage_order,
                status="completed",
                output=output,
                started_at=started,
                completed_at=completed,
            ))

        # 标记任务完成
        db.update("tasks", "id", task_id, {
            "status": "completed",
            "completed_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "result_summary": f"SOP {sop.name} 执行完成，{len(phases)} 个阶段全部通过",
        })
        db.update("sop_executions", "id", sop_execution_id, {
            "status": "completed",
            "completed_stages": len(phases),
            "completed_at": datetime.now().isoformat(),
        })

        return TaskExecuteResponse(
            task_id=task_id,
            status="completed",
            stages=stages_result,
            message=f"任务完成：{len(phases)} 阶段全部通过",
        )

    except Exception as e:
        db.update("tasks", "id", task_id, {
            "status": "failed",
            "updated_at": datetime.now().isoformat(),
            "result_summary": str(e)[:200],
        })
        db.update("sop_executions", "id", sop_execution_id, {
            "status": "failed",
            "error": str(e)[:200],
        })
        return TaskExecuteResponse(
            task_id=task_id,
            status="failed",
            stages=stages_result,
            message=f"执行失败：{str(e)}",
        )


# ═══════════════════════════════════════════════════════════════
# 4. GET /api/tasks — 任务列表
# ═══════════════════════════════════════════════════════════════
@app.get("/api/tasks", response_model=List[TaskResponse])
def list_tasks(
    project_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    db = get_db()
    where = []
    params = []
    if project_id:
        where.append("project_id = ?")
        params.append(project_id)
    if status:
        where.append("status = ?")
        params.append(status)
    clause = " AND ".join(where) if where else "1=1"
    sql = f"SELECT * FROM tasks WHERE {clause} ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = db.execute_sql(sql, params)
    return _rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# 5. GET /api/tasks/{id}/stages — 任务阶段详情
# ═══════════════════════════════════════════════════════════════
@app.get("/api/tasks/{task_id}/stages", response_model=List[TaskStageResponse])
def get_task_stages(task_id: str):
    db = get_db()
    rows = db.select_all("task_stages", "task_id = ? ORDER BY stage_order ASC", [task_id])
    return _rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# 6. GET /api/costs — 成本统计
# ═══════════════════════════════════════════════════════════════
@app.get("/api/costs", response_model=CostSummaryResponse)
def get_costs(
    month: Optional[str] = Query(None, description="YYYY-MM"),
):
    db = get_db()
    now = datetime.now()
    year = now.year
    mo = now.month
    if month:
        parts = month.split("-")
        year = int(parts[0])
        mo = int(parts[1])

    monthly_total = db.get_monthly_cost(year, mo)

    # 模型细分
    sql = """
    SELECT model, SUM(estimated_cost) as total, SUM(total_tokens) as tokens
    FROM cost_log
    WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?
    GROUP BY model
    """
    breakdown_rows = db.execute_sql(sql, [str(year), str(mo).zfill(2)])
    model_breakdown = {}
    for r in breakdown_rows:
        model_breakdown[r.get("model", "unknown")] = {
            "total_cost": round(float(r.get("total", 0)), 6),
            "total_tokens": int(r.get("tokens", 0)),
        }

    # 最近日志
    recent = db.execute_sql(
        "SELECT * FROM cost_log ORDER BY id DESC LIMIT 20"
    )
    recent_logs = _rows_to_list(recent)

    # 预算限制
    budget_limit = None
    try:
        from core.config import get_config
        budget_limit = float(get_config("budget_limit", "50.0"))
    except Exception:
        budget_limit = 50.0

    return CostSummaryResponse(
        monthly_total=round(monthly_total, 6),
        model_breakdown=model_breakdown,
        recent_logs=recent_logs,
        budget_limit=budget_limit,
    )


# ═══════════════════════════════════════════════════════════════
# 7. GET /api/agents — Agent 状态列表
# ═══════════════════════════════════════════════════════════════
@app.get("/api/agents", response_model=List[AgentResponse])
def list_agents():
    db = get_db()
    agents = db.select_all("agents")
    result = []
    for a in agents:
        ad = _row_to_dict(a)
        # 合并 agent_status
        status_row = db.select_one("agent_status", "agent_id", ad["id"])
        if status_row:
            sd = _row_to_dict(status_row)
            ad["status"] = sd.get("status", "idle")
            ad["total_tokens_used"] = sd.get("total_tokens_used", 0)
            ad["total_cost"] = sd.get("total_cost", 0.0)
        else:
            ad["status"] = "idle"
            ad["total_tokens_used"] = 0
            ad["total_cost"] = 0.0
        result.append(ad)
    return result


# ═══════════════════════════════════════════════════════════════
# 8. POST /api/chat — CEO 对话
# ═══════════════════════════════════════════════════════════════
@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    from skills.llm import call_llm

    # 根据 use_real_llm 控制测试模式
    if not req.use_real_llm:
        os.environ["FROST_TESTING"] = "1"
    else:
        os.environ.pop("FROST_TESTING", None)

    context = {
        "_prompt": req.message,
        "_system_prompt": "你是FROST家族AI指挥平台的CEO Agent，负责回答关于项目进展、成本、Agent状态等问题。请用中文简洁回复。",
        "_model": "deepseek-chat",
        "_temperature": 0.7,
        "_max_tokens": 1024,
        "_agent_id": "ceo-agent",
    }

    result = call_llm(context)

    return ChatResponse(
        reply=result.get("_llm_response", ""),
        tokens_used=result.get("_llm_tokens"),
        model=result.get("_llm_model"),
    )


# ═══════════════════════════════════════════════════════════════
# 9. GET /api/logs — 实时日志 (SSE 流式输出)
# ═══════════════════════════════════════════════════════════════
@app.get("/api/logs")
async def stream_logs():
    db = get_db()

    async def event_generator():
        last_id = 0
        while True:
            try:
                rows = db.execute_sql(
                    "SELECT * FROM audit_log WHERE id > ? ORDER BY id DESC LIMIT 10",
                    [last_id]
                )
                if rows:
                    for row in reversed(rows):
                        rd = _row_to_dict(row)
                        yield f"data: {json.dumps(rd, ensure_ascii=False)}\n\n"
                        last_id = max(last_id, rd["id"])
            except Exception:
                pass
            await asyncio.sleep(2)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ═══════════════════════════════════════════════════════════════
# 10. GET /api/skills — Skill 列表
# ═══════════════════════════════════════════════════════════════
@app.get("/api/skills", response_model=List[SkillResponse])
def list_skills(
    status_filter: Optional[str] = Query(None, alias="status"),
    skill_type: Optional[str] = Query(None),
):
    db = get_db()
    where = []
    params = []
    if status_filter:
        where.append("status = ?")
        params.append(status_filter)
    if skill_type:
        where.append("skill_type = ?")
        params.append(skill_type)
    clause = " AND ".join(where) if where else "1=1"
    sql = f"SELECT * FROM skills WHERE {clause} ORDER BY created_at DESC"
    rows = db.execute_sql(sql, params)
    return _rows_to_list(rows)


# ═══════════════════════════════════════════════════════════════
# 11. GET /api/schedule — 日程列表
# ═══════════════════════════════════════════════════════════════
@app.get("/api/schedule", response_model=List[ScheduleResponse])
def list_schedules(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    db = get_db()
    rows = db.get_schedules(date_from or "", date_to or "")
    return [
        ScheduleResponse(
            id=r["id"],
            title=r.get("title", r.get("name", "")),
            description=r.get("description", ""),
            start_time=r.get("start_time"),
            end_time=r.get("end_time"),
            repeat_type=r.get("repeat_type", "none"),
            repeat_end=r.get("repeat_end", ""),
            notified=bool(r.get("notified", 0)),
            created_at=r.get("created_at"),
        )
        for r in rows
    ]


# ═══════════════════════════════════════════════════════════════
# 12. POST /api/schedule — 新增日程
# ═══════════════════════════════════════════════════════════════
@app.post("/api/schedule", response_model=ScheduleResponse)
def create_schedule(req: ScheduleCreateRequest):
    db = get_db()
    sid = db.add_schedule(
        title=req.title,
        start_time=req.start_time,
        end_time=req.end_time,
        repeat_type=req.repeat_type,
        repeat_end=req.repeat_end,
        description=req.description,
    )
    return ScheduleResponse(
        id=sid,
        title=req.title,
        description=req.description,
        start_time=req.start_time,
        end_time=req.end_time,
        repeat_type=req.repeat_type,
        repeat_end=req.repeat_end,
        notified=False,
        created_at=datetime.now().isoformat(),
    )


# ═══════════════════════════════════════════════════════════════
# SOPs — list all available SOP templates
# ═══════════════════════════════════════════════════════════════
@app.get("/api/sops")
def list_sops():
    """
    List all available SOP templates.
    Reads from sops/templates/ directory.
    """
    import yaml
    from pathlib import Path
    
    sops_dir = Path(__file__).parent.parent / "sops" / "templates"
    sops = []
    
    if sops_dir.exists():
        for yaml_file in sorted(sops_dir.glob("*.yaml")):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                sop_id = data.get("sop_id", yaml_file.stem)
                stages = data.get("stages", [])
                sops.append({
                    "id": sop_id,
                    "name": data.get("name", sop_id),
                    "version": data.get("version", "1.0"),
                    "stage_count": len(stages),
                    "stages": [s.get("name", "?") for s in stages],
                    "description": data.get("description", ""),
                    "required_stages": data.get("required_stages", []),
                    "category": data.get("category", "general"),
                })
            except Exception as e:
                sops.append({
                    "id": yaml_file.stem,
                    "name": yaml_file.stem,
                    "error": str(e),
                })
    
    return sops


# ═══════════════════════════════════════════════════════════════
# Health check
# ═══════════════════════════════════════════════════════════════
@app.get("/api/health")
def health():
    db = get_db()
    counts = db.get_table_counts()
    return {
        "status": "ok",
        "version": "1.0.0",
        "db_tables": len([c for c in counts.values() if c >= 0]),
        "timestamp": datetime.now().isoformat(),
    }


# ── Helper — Panel JSON 序列化 ──────────────────────────────

def _enum_to_str(v):
    """递归把 Enum / dataclass 转换成可 JSON 序列化的结构。"""
    from enum import Enum as EnumType
    if isinstance(v, EnumType):
        return v.value
    if hasattr(v, "__dataclass_fields__"):
        return {k: _enum_to_str(getattr(v, k)) for k in v.__dataclass_fields__}
    if isinstance(v, dict):
        return {k: _enum_to_str(vv) for k, vv in v.items()}
    if isinstance(v, (list, tuple)):
        return type(v)(_enum_to_str(i) for i in v)
    return v


def panel_to_json(panel) -> dict:
    """把 PanelDefinition 转换成纯字典（所有 Enum → str）。"""
    d = panel.to_dict()
    return _enum_to_str(d)


# ── 13. POST /api/panels/generate — 生成 Panel JSON ─────
@app.post("/api/panels/generate")
def generate_panel(req: PanelGenerateRequest):
    """
    根据任务和 SOP 生成 Panel 定义，返回 JSON。
    前端拿到 JSON 后用 PanelRenderer.tsx 渲染。
    """
    db = get_db()

    # 1. 读取任务
    task_row = db.select_one("tasks", "id", req.task_id)
    if not task_row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Task {req.task_id} not found")
    task = _row_to_dict(task_row)

    # 2. 读取 SOP（自动关联或手动指定）
    sop_id = req.sop_id
    if not sop_id:
        exec_row = db.execute_sql(
            "SELECT sop_template_id FROM sop_executions WHERE task_id = ? ORDER BY id DESC LIMIT 1",
            [req.task_id]
        )
        if exec_row:
            raw = exec_row[0]["sop_template_id"]
            sop_id = raw.replace("sop_template:", "") if raw else None

    sop = None
    if sop_id:
        try:
            from core.sop import SOP
            sop = SOP.load_from_yaml(f"sops/templates/{sop_id}.yaml")
        except Exception:
            pass

    # 3. 读取 stages
    stage_rows = db.select_all("task_stages", "task_id = ? ORDER BY stage_order ASC", [req.task_id])
    task["stages"] = _rows_to_list(stage_rows)

    # 4. 生成 Panel
    from core.panel_generator import PanelGenerator
    generator = PanelGenerator()
    panel = generator.generate(task, sop)

    return panel_to_json(panel)


# ── 14. POST /api/decisions/submit — 提交决策 ───────────
@app.post("/api/decisions/submit", response_model=DecisionResponse)
def submit_decision(req: DecisionSubmitRequest):
    """
    Human Agent 通过前端提交决策。
    写入 decision_points 表，触发 DecisionFlow 状态推进。
    """
    from core.panel_decision import get_decision_flow
    from fastapi import HTTPException

    flow = get_decision_flow()
    try:
        record = flow.submit_decision(
            decision_id=req.decision_id,
            decision=req.decision,
            reason=req.reason or f"Web用户提交：{req.decision}",
            human_agent_id=req.human_agent_id,
        )
        return DecisionResponse(
            decision_id=req.decision_id,
            task_id=record.task_id,
            status=record.status.value,
            decision=req.decision,
            reason=req.reason,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── 15. GET /api/decisions/{decision_id} ───────────────────
@app.get("/api/decisions/{decision_id}")
def get_decision(decision_id: str):
    """获取单个决策的状态。"""
    from core.panel_decision import get_decision_flow
    from fastapi import HTTPException

    flow = get_decision_flow()
    record = flow.get_decision(decision_id)
    if not record:
        raise HTTPException(status_code=404, detail="Decision not found")
    return {
        "decision_id": record.decision_id,
        "task_id": record.task_id,
        "stage_name": record.stage_name,
        "status": record.status.value,
        "decision": record.decision,
        "reason": record.reason,
        "created_at": record.created_at,
        "updated_at": record.updated_at,
    }


# ── 16. GET /api/decisions — 列出 pending 决策 ───────────
@app.get("/api/decisions")
def list_pending_decisions(
    task_id: Optional[str] = Query(None),
):
    """
    列出等待 Human Agent 决策的 pending 记录。
    前端轮询此接口渲染决策面板。
    """
    db = get_db()
    conn = db.get_connection()
    cursor = conn.cursor()

    sql = "SELECT * FROM decision_points WHERE status = 'pending'"
    params = []
    if task_id:
        sql += " AND task_id = ?"
        params.append(task_id)
    sql += " ORDER BY created_at ASC"

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    return [dict(r) for r in rows]
