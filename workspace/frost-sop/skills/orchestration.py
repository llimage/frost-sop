"""
PHILOSOPHY:
Orchestration Skills manage agent lifecycle (spawn/emit/validate/merge).
"""

from core.skill import Skill
from core.agent import Agent
from core.store import Store
from datetime import datetime


def spawn(context: dict) -> dict:
    """
    Spawn a child agent from context specification.

    Args:
        context: Dictionary containing '_spawn_spec'

    Returns:
        Updated context with child execution results
    """
    spec = context.get('_spawn_spec', {})
    if not spec:
        return context

    template = spec.get('template_agent')
    if not template:
        return context

    # Create child agent
    child = Agent(
        name=spec.get('agent_id', 'child'),
        store=Store(),
        skills=template.skills.copy() if template.skills else {},
        sop_steps=template._sop_steps.copy() if hasattr(template, '_sop_steps') else [],
    )

    # Run child agent
    result_ctx = child.run(child._sop_steps, spec.get('initial_context', {}))

    # Collect results
    context.update(result_ctx)
    if '_children_results' not in context:
        context['_children_results'] = []
    context['_children_results'].append({
        "agent_id": child.name,
        "result": result_ctx,
    })

    return context


def emit(context: dict) -> dict:
    """
    Emit specified keys from context to '_result'.

    Args:
        context: Dictionary containing '_emit_keys'

    Returns:
        Updated context with '_result' dictionary
    """
    keys = context.get('_emit_keys', ['_result'])
    context['_result'] = {k: context.get(k) for k in keys}
    return context


def validate_sop(context: dict) -> dict:
    """
    Validate SOP against compliance rules.

    Args:
        context: Dictionary containing '_sop_to_validate' and '_compliance_rules'

    Returns:
        Updated context with '_validation_result'
    """
    from core.sop import SOPValidator

    sop = context.get('_sop_to_validate')
    rules = context.get('_compliance_rules', {})

    if sop is None:
        context['_validation_result'] = {"valid": False, "errors": [{"message": "No SOP to validate"}]}
        return context

    validator = SOPValidator()
    context['_validation_result'] = validator.validate(sop, rules)

    return context


def merge_from(context: dict) -> dict:
    """
    Merge results from child store to parent store.

    Args:
        context: Dictionary containing '_child_store', '_store', and '_merge_keys'

    Returns:
        Updated context with merged data
    """
    child_store = context.get('_child_store')
    parent_store = context.get('_store')
    filter_keys = context.get('_merge_keys', [])

    if child_store is None or parent_store is None:
        return context

    for key in filter_keys:
        value = child_store.load(key)
        if value is not None:
            parent_store.save(key, value)

    return context


spawn_skill = Skill("spawn", spawn)
emit_skill = Skill("emit", emit)
validate_sop_skill = Skill("validate_sop", validate_sop)
merge_from_skill = Skill("merge_from", merge_from)


# ============================================================
# P3 新增：SOP 内化与阶段执行 Skill
# ============================================================

def internalize_sop(context: dict) -> dict:
    """
    将外部搜索到的 SOP 模板内化为可执行的步骤列表。

    输入 context 键：
        _sop_to_internalize: dict —— SOP 模板内容，包含 stages 列表
            每个 stage: {"name": "阶段名", "agent": "角色", "skills": ["skill1", ...]}

    输出 context 键：
        _internalized_steps: list —— 内化后的步骤列表
            ["execute_stage:需求分析", "execute_stage:技术设计", ...]
        _sop_stages: list —— 阶段详情（供 execute_stage 使用）
        _reason: str —— 推理痕迹

    PHILOSOPHY: 内化是 Agent 将外部知识转化为自身执行能力的过程。
    这是 Phase 2a（教学）的延伸——父辈自己教会自己。
    """

    sop_data = context.get("_sop_to_internalize", {})
    stages = sop_data.get("stages", [])

    if not stages:
        context["_internalized_steps"] = []
        context["_sop_stages"] = []
        context["_reason"] = "内化失败：SOP模板无阶段定义"
        return context

    internalized = []
    for stage in stages:
        stage_name = stage.get("name", "未命名阶段")
        internalized.append(f"execute_stage:{stage_name}")

    context["_internalized_steps"] = internalized
    context["_sop_stages"] = stages
    context["_reason"] = f"内化成功：{len(internalized)} 个阶段 -> {internalized}"

    return context


def execute_stage(context: dict) -> dict:
    """
    为当前SOP阶段动态组装孙辈Agent并执行。
    
    输入 context 键：
        _current_stage: dict —— 当前阶段定义
            {"name": "阶段名", "agent": "角色名", "skills": ["skill1"], "requirement": "任务描述"}
        _parent_agent: Agent —— 父辈Agent引用
        _asset_store: Store —— 资产Store引用
        _stage_results: list
    
    输出 context 键：
        _stage_results: list
        _current_stage_result: dict
        _child_store_data: dict
        _reason: str
    """
    
    from skills.assemble import assemble_agent
    from core.decision_manager import DecisionManager, get_decision_manager
    
    stage = context.get("_current_stage", {})
    parent_agent = context.get("_parent_agent")
    asset_store = context.get("_asset_store")
    stage_name = stage.get("name", "未知阶段")
    stage_requirement = stage.get("requirement", f"执行{stage_name}任务")
    
    # F8 新增：决策点检查
    # 检查阶段名称是否包含决策关键词
    decision_keywords = ["确认", "审核", "审批", "决策", "confirm", "approve", "review"]
    requires_decision = any(keyword in stage_name.lower() for keyword in decision_keywords)
    
    # 也检查阶段定义中是否有 requires_confirmation 字段
    if stage.get("requires_confirmation", False):
        requires_decision = True
    
    if requires_decision:
        # 触发决策点暂停（仅在有有效 task_id 时）
        task_id = context.get("_task_id", "unknown")
        if task_id == "unknown":
            # 无有效任务ID，跳过决策点创建
            print(f"  ⚠️ 跳过决策点（无有效 task_id）: {stage_name}")
        else:
            decision_manager = get_decision_manager()
            stage_id = stage.get("id", stage_name)
            question = stage.get("description", f"是否需要执行 {stage_name}？")
            options = stage.get("decision_options", ["确认", "驳回", "修改"])
            
            decision_id = decision_manager.pause_decision(
                task_id=task_id,
                stage_id=stage_id,
                question=question,
                options=options
            )
            
            # 在 context 中设置决策点信息，让上层知道需要暂停
            context["_decision_id"] = decision_id
            context["_paused_for_decision"] = True
            context["_decision_question"] = question
            context["_decision_options"] = options
    
    # 返回当前 context，不执行后续步骤（如果是决策阶段）
    if context.get("_paused_for_decision"):
        return context
    
    # 1. 动态组装孙辈Agent
    assemble_context = {
        "_agent_requirement": f"角色：{stage.get('agent', '执行者')}。任务：{stage_requirement}",
        "_asset_store": asset_store,
        "_parent_agent": parent_agent,
    }
    assemble_context = assemble_agent(assemble_context)
    
    child = assemble_context.get("_assembled_agent")
    agent_config = assemble_context.get("_agent_config", {})

    # 修复DEFECT-001：显式检查孙辈是否真的具备技能，防止静默失败
    if child is not None:
        child_skills = getattr(child, "skills", {})
        child_sop = agent_config.get("sop_steps", [])
        if not child_skills or not child_sop:
            result = {
                "stage": stage_name,
                "agent": stage.get("agent", "未知"),
                "output": (
                    f"[F6-DEFECT-001] 孙辈Agent '{child.name}' 组装失败："
                    f"skills={list(child_skills.keys())}，sop_steps={child_sop}。"
                    f"请检查LLM组装响应是否为合法JSON。"
                ),
                "status": "failed",
            }
            context["_stage_results"] = context.get("_stage_results", []) + [result]
            context["_current_stage_result"] = result
            return context

        # F14: Persist child agent to database
        try:
            from core.db import get_db
            db = get_db()
            agent_id = child.name
            existing_agent = db.select_one("agents", "id", agent_id)
            if not existing_agent:
                db.insert("agents", {
                    "id": agent_id,
                    "name": child.name,
                    "agent_type": "child",
                    "generation": child.generation,
                    "created_at": datetime.now().isoformat(),
                })
            # Update agent status for current task
            task_id = context.get("_task_id", "")
            # Check if agent_status record exists
            existing_status = db.select_one("agent_status", "agent_id", agent_id)
            if existing_status:
                db.update("agent_status", "agent_id", agent_id, {
                    "status": "active",
                    "current_task_id": task_id,
                    "last_heartbeat": datetime.now().isoformat(),
                })
            else:
                db.insert("agent_status", {
                    "agent_id": agent_id,
                    "status": "active",
                    "current_task_id": task_id,
                    "last_heartbeat": datetime.now().isoformat(),
                })
        except Exception as e:
            import traceback
            print(f"    ⚠️ [F14] Agent持久化失败: {type(e).__name__}: {e}")
            traceback.print_exc()

    if child is None:
        # 组装失败，返回错误
        result = {
            "stage": stage_name,
            "agent": stage.get("agent", "未知"),
            "output": f"[{stage_name}] Agent组装失败",
            "status": "failed",
        }
        context["_stage_results"] = context.get("_stage_results", []) + [result]
        context["_current_stage_result"] = result
        return context
    
    # 2. 孙辈执行任务
    # 注入任务上下文（含 F14 持久化所需字段）
    initial_context = {
        "_task_description": stage_requirement,
        "_output_type": stage.get("output_type", "document"),
        "_output_path": f"output/{stage_name.replace(' ', '_')}_{child.name}.md",
        "_task_id": context.get("_task_id", ""),        # F14: 传递 task_id 给 cost_log
        "_agent_id": child.name,                          # F14: 传递 agent_id 给 cost_log
    }
    
    try:
        result_context = child.run(
            sop_steps=agent_config.get("sop_steps", ["call_llm_for_output"]),
            initial_context=initial_context
        )
        result_text = result_context.get("_generated_content", result_context.get("_result", result_context.get("_llm_response", "执行完成")))
        status = "completed"
    except Exception as e:
        result_text = f"执行失败: {str(e)}"
        status = "failed"

    # V2.0: 孙辈执行完毕后，更新 agent_status 为 destroyed（run() 已调用 destroy()，此处同步 DB 状态）
    try:
        from core.db import get_db
        db_after = get_db()
        db_after.update("agent_status", "agent_id", child.name, {
            "status": "destroyed",
            "last_heartbeat": datetime.now().isoformat(),
        })
    except Exception as e:
        print(f"    ⚠️ [V2.0] 孙辈销毁状态更新失败 ({child.name}): {e}")
    
    # 3. 构建阶段结果
    result = {
        "stage": stage_name,
        "agent": stage.get("agent", "未知"),
        "skills_used": agent_config.get("skills", []),
        "skill_sources": agent_config.get("skill_sources", {}),
        "output": f"[{stage_name}] {result_text[:100]}",
        "status": status,
        "child_generation": child.generation,
        "agent_assembled": True,
    }
    
    # 4. 保存孙辈Store数据
    child_store_data = {}
    for key in child.store.list_keys():
        child_store_data[key] = child.store.load(key)
    
    stage_results = context.get("_stage_results", [])
    stage_results.append(result)
    
    context["_stage_results"] = stage_results
    context["_current_stage_result"] = result
    context["_child_store_data"] = child_store_data
    context["_reason"] = f"孙辈Agent(组装)执行阶段'{stage_name}'完成。Skills: {agent_config.get('skills')}（来源: {agent_config.get('skill_sources')}）"
    
    return context


# 新增 Skill 实例
internalize_sop_skill = Skill("internalize_sop", internalize_sop)
execute_stage_skill = Skill("execute_stage", execute_stage)


# ============================================================
# V2.0 阶段三：长老审计自动化
# ============================================================

def _trigger_elder_audit(task_id: str, asset_store=None, constitution_store=None):
    """
    V2.0: 在后台触发长老审计（不阻塞主流程）。

    流程：
    1. 创建长老 Agent 实例
    2. 执行 audit_family Skill
    3. 将审计结果写入 audit_log 表

    Args:
        task_id: 关联的任务 ID
        asset_store: 资产 Store（供长老访问任务/错题记录）
        constitution_store: 宪法 Store（可为 None）
    """
    try:
        from agents.elder import create_elder
        from core.db import get_db

        # 创建长老 Agent（静默模式：使用 asset_store 访问任务数据）
        elder = create_elder(
            name=f"elder_audit_{task_id[:8]}",
            asset_store=asset_store,
            constitution_store=constitution_store,
        )

        # 执行审计
        audit_context = elder.run(
            sop_steps=["audit_family"],
            initial_context={
                "_asset_store": asset_store,
                "_constitution_store": constitution_store,
                "_task_id": task_id,
            }
        )

        audit_report = audit_context.get("_audit_report", {})
        reason = audit_context.get("_reason", "审计完成")

        # 将审计结果写入 audit_log 表
        db = get_db()
        db.log_audit({
            "agent_id": f"elder_audit_{task_id[:8]}",
            "action": "auto_audit",
            "details": f"task_id={task_id} | {reason} | report={str(audit_report)[:500]}",
            "level": "info",
        })
        print(f"  ✅ [V2.0-长老审计] 完成 task_id={task_id}: {reason}")

    except Exception as e:
        # 长老审计失败仅记录日志，不影响任务完成状态
        try:
            from core.db import get_db
            db = get_db()
            db.log_audit({
                "agent_id": "elder_audit",
                "action": "auto_audit_failed",
                "details": f"task_id={task_id} | 长老审计失败: {str(e)[:200]}",
                "level": "warning",
            })
        except Exception:
            pass
        print(f"  ⚠️ [V2.0-长老审计] 失败（不影响任务状态）: {e}")


def finalize_task(context: dict) -> dict:
    """
    V2.0: 任务收尾 Skill。
    在所有阶段执行完成后，在后台触发长老审计。

    输入 context 键：
        _task_id: str —— 任务 ID
        _asset_store: Store —— 资产 Store
        _constitution_store: Store —— 宪法 Store（可为 None）
        _stage_results: list —— 阶段结果列表

    输出 context 键：
        _elder_audit_triggered: bool —— 是否已触发长老审计
        _reason: str —— 推理痕迹
    """
    import threading

    task_id = context.get("_task_id", "unknown")
    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")

    if not task_id or task_id == "unknown":
        # 无有效 task_id，跳过长老审计
        context["_elder_audit_triggered"] = False
        context["_reason"] = "finalize_task: 无有效 task_id，跳过长老审计"
        return context

    # 在后台线程触发长老审计（不阻塞主流程）
    audit_thread = threading.Thread(
        target=_trigger_elder_audit,
        args=(task_id, asset_store, constitution_store),
        daemon=True,   # 守护线程：主线程结束时自动结束，不阻塞
        name=f"elder_audit_{task_id[:8]}",
    )
    audit_thread.start()

    context["_elder_audit_triggered"] = True
    context["_elder_audit_thread"] = audit_thread   # 供测试等待使用
    context["_reason"] = f"finalize_task: 长老审计后台线程已启动，task_id={task_id}"

    print(f"  🔮 [V2.0-长老审计] 后台审计已启动，task_id={task_id}")
    return context


# finalize_task Skill 实例
finalize_task_skill = Skill("finalize_task", finalize_task)


# ============================================================
# V3.0: 事件驱动的阶段执行器
# ============================================================

def register_stage_executor(parent_agent, asset_store) -> bool:
    """
    V3.0: 注册 execute_stage 为 STAGE_STARTED 事件的异步订阅者。

    收到 STAGE_STARTED 后：
    1. 从事件数据中提取阶段信息
    2. 调用 execute_stage 执行阶段（assemble_agent → child.run()）
    3. 发布 STAGE_COMPLETED 事件

    Args:
        parent_agent: 父辈 Agent 实例
        asset_store: 资产 Store

    Returns:
        True 如果注册成功，False 如果 AsyncEventBus 不可用
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        from core.event_bus import get_async_event_bus, Event, EventType

        bus = get_async_event_bus()

        async def on_stage_started(event: Event):
            """STAGE_STARTED 回调：执行阶段 → 发布 STAGE_COMPLETED"""
            task_id = event.data.get("task_id", "unknown")
            stage_name = event.data.get("stage_name", "未知阶段")
            stage_order = event.data.get("stage_order", 0)
            total_stages = event.data.get("total_stages", 0)

            logger.info("[V3.0] execute_stage 收到 STAGE_STARTED: %s (阶段 %s/%s)",
                       stage_name, stage_order, total_stages)

            # 构造 execute_stage 的 context
            stage_context = {
                "_current_stage": {
                    "name": stage_name,
                    "agent": "执行者",
                    "skills": ["call_llm"],
                    "requirement": f"执行 {stage_name}",
                },
                "_parent_agent": parent_agent,
                "_asset_store": asset_store,
                "_stage_results": [],
                "_task_id": task_id,
            }

            # 调用 execute_stage
            result_context = execute_stage(stage_context)
            result = result_context.get("_current_stage_result", {})
            stage_status = result.get("status", "unknown")

            # 发布 STAGE_COMPLETED
            await bus.publish(Event(
                event_type=EventType.STAGE_COMPLETED,
                source="orchestration:stage_executor",
                data={
                    "task_id": task_id,
                    "stage_name": stage_name,
                    "stage_order": stage_order,
                    "total_stages": total_stages,
                    "status": stage_status,
                },
            ))
            logger.info("[V3.0] execute_stage 发布 STAGE_COMPLETED: %s (status=%s)",
                       stage_name, stage_status)

        bus.subscribe_async(EventType.STAGE_STARTED, on_stage_started)
        logger.info("[V3.0] execute_stage 已订阅 STAGE_STARTED 事件")
        return True

    except Exception as e:
        logger.warning("[V3.0] execute_stage 事件订阅失败（已忽略）: %s", e)
        return False
