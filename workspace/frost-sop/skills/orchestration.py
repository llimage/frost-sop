"""
PHILOSOPHY:
Orchestration Skills manage agent lifecycle (spawn/emit/validate/merge).
"""

import logging
from datetime import datetime
import asyncio
from typing import Dict, Any, Optional

from core.skill import Skill
from core.agent import Agent
from core.store import Store

logger = logging.getLogger(__name__)

# V5.0：使用 DecisionFlow 状态机替代 decision_manager
from core.panel_decision import get_decision_flow, DecisionStatus


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
        context['_validation_result'] = {"valid": False,
            "errors": [{"message": "No SOP to validate"}]}
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



# ============================================================
# execute_stage 子函数（降低复杂度，每个子函数 <10）
# ============================================================

def _check_decision_point(context: dict, stage: dict) -> bool:
    """
    检查当前阶段是否需要暂停等待 Human Agent 决策。

    如果需要暂停：
    1. 通过 DecisionFlow 状态机创建决策记录（替代 decision_manager）
    2. 在 context 中设置决策点信息
    3. 生成 DECISION 类型面板，存入 context["_decision_panel"]

    返回 True 表示已暂停，调用方应 return context。
    返回 False 表示无需暂停，继续执行。
    """
    stage_name = stage.get("name", "未知阶段")
    decision_keywords = ["确认", "审核", "审批", "决策", "confirm", "approve", "review"]
    requires_decision = any(keyword in stage_name.lower() for keyword in decision_keywords)

    if stage.get("requires_confirmation", False):
        requires_decision = True

    if requires_decision:
        task_id = context.get("_task_id", "unknown")
        if task_id == "unknown":
            logger.warning(
                "跳过决策点（无有效 task_id）: %s", stage_name
            )
        else:
            # S-002 修复：使用 DecisionFlow 状态机替代 decision_manager
            flow = get_decision_flow()
            stage_id = stage.get("id", stage_name)
            question = stage.get("description", f"是否需要执行 {stage_name}？")
            options = stage.get("decision_options", ["确认", "驳回", "修改"])

            record = flow.create_decision(
                task_id=task_id,
                stage_id=stage_id,
                stage_name=stage_name,
                context_before={
                    "stage": stage,
                    "question": question,
                    "options": options,
                    "outputs": stage.get("outputs", []),
                    "quality_score": context.get("_quality_score", {}),
                },
            )
            # create_decision 返回 DecisionRecord，decision_id 是字符串
            decision_id = record.decision_id

            context["_decision_id"] = decision_id
            context["_paused_for_decision"] = True
            context["_decision_question"] = question
            context["_decision_options"] = options

            logger.info(
                "[V5.0] DecisionFlow 决策已创建: %s (status=%s)",
                decision_id, record.status.value,
            )

            # V5.0：生成 DECISION 面板
            try:
                from core.panel_generator import PanelGenerator

                # 构造任务字典（供 PanelGenerator 使用）
                task_for_panel = {
                    "task_id": task_id,
                    "title": context.get("_task_title", stage_name),
                    "status": "waiting",
                    "stages": [stage] if isinstance(stage, dict) else list(stage),
                    "current_stage_index": 0,
                    "current_stage": stage,
                }

                generator = PanelGenerator()
                decision_panel = generator.generate(task_for_panel)
                context["_decision_panel"] = decision_panel
                logger.info(
                    "[V5.0] 决策面板已生成: %s", decision_panel.panel_id
                )
            except Exception as e:
                logger.warning(
                    "[V5.0] 决策面板生成失败（不影响暂停）: %s", e
                )

    return context.get("_paused_for_decision", False)


def _wait_for_decision_and_continue(context: dict, blocking: bool = True) -> dict:
    """
    CLI 模式：渲染决策面板，等待用户输入，提交决策，然后继续执行。

    修改 context 并返回更新后的 context。
    如果决策为"驳回"，设置 context["_rejected"] = True。
    如果决策为"修改"，设置 context["_needs_revision"] = True。

    参数:
        context: 执行上下文
        blocking: 是否阻塞等待用户输入（CLI=True, Streamlit=False）
                  当 blocking=False 时，只设置 context["_awaiting_decision"]=True
                  并返回，不等待用户输入。由调用方（如 Streamlit 应用）负责渲染
                  决策面板并调用 _submit_decision_from_ui() 提交决策。
    """
    import logging
    import sys
    logger = logging.getLogger(__name__)

    panel = context.get("_decision_panel")
    if not panel:
        logger.warning("_wait_for_decision_and_continue: 没有决策面板")
        context["_paused_for_decision"] = False
        context["_awaiting_decision"] = False
        return context

    decision_id = context.get("_decision_id")
    if not decision_id:
        logger.warning("_wait_for_decision_and_continue: 没有 decision_id")
        context["_paused_for_decision"] = False
        context["_awaiting_decision"] = False
        return context

    # 非阻塞模式（用于 Streamlit 等 UI 环境）
    if not blocking:
        logger.info("_wait_for_decision_and_continue: 非阻塞模式，等待 UI 决策")
        context["_awaiting_decision"] = True
        # 保留 _decision_panel 和 _decision_id 供 UI 渲染
        return context

    # 阻塞模式（CLI）
    # 1. 渲染决策面板
    from renderers.cli_renderer import CliRenderer
    renderer = CliRenderer()
    renderer.render(panel)

    # 2. 等待用户输入
    options = context.get("_decision_options", ["确认", "驳回", "修改"])

    print()
    if not sys.stdin.isatty():
        # 非 CLI 环境（如测试），使用默认决策
        logger.warning("_wait_for_decision_and_continue: 非 CLI 环境，使用默认决策")
        choice = options[0]  # 默认确认
    else:
        while True:
            try:
                choice = input(f"请输入决策（{"，".join(options)}）：").strip()
                if choice in options:
                    break
                else:
                    print(f"无效输入，请重新输入（{"，".join(options)}）")
            except EOFError:
                logger.warning("_wait_for_decision_and_continue: EOF，使用默认决策")
                choice = options[0]
                break

    # 3. 提交决策到 DecisionFlow
    return _submit_decision_and_update_context(context, decision_id, choice, "CLI 用户输入")


def _submit_decision_and_update_context(context: dict, decision_id: str, choice: str, reason_prefix: str = "") -> dict:
    """
    提交决策并更新 context（供 CLI 和 UI 模式共用）。
    """
    import logging
    logger = logging.getLogger(__name__)

    from core.panel_decision import get_decision_flow

    flow = get_decision_flow()
    try:
        record = flow.submit_decision(
            decision_id=decision_id,
            decision=choice,
            reason=f"{reason_prefix}：{choice}",
            human_agent_id="cli_user" if reason_prefix == "CLI 用户输入" else "ui_user",
        )
        logger.info(
            "决策已提交: decision_id=%s, decision=%s, status=%s",
            decision_id, choice, record.status.value,
        )
    except Exception as e:
        logger.error("提交决策失败: %s", e)
        context["_paused_for_decision"] = False
        context["_awaiting_decision"] = False
        return context

    # 更新 context
    context["_decision_result"] = {
        "decision_id": decision_id,
        "decision": choice,
        "reason": f"{reason_prefix}：{choice}",
        "status": record.status.value,
    }
    context["_paused_for_decision"] = False
    context["_awaiting_decision"] = False

    # 根据决策结果设置标志
    if choice == "驳回":
        context["_rejected"] = True
        logger.info("决策：驳回，跳过当前阶段")
    elif choice == "修改":
        context["_needs_revision"] = True
        logger.info("决策：修改，需要重新执行当前阶段")
    else:
        # 确认，继续执行
        logger.info("决策：确认，继续执行当前阶段")

    return context


def _assemble_child(context: dict, stage: dict):
    """
    为当前阶段动态组装孙辈Agent。
    包含 DEFECT-001 修复（显式检查技能）和 F14 持久化。
    成功返回 child，失败返回 None（错误信息已写入context）。
    """
    from skills.assemble import assemble_agent

    asset_store = context.get("_asset_store")
    parent_agent = context.get("_parent_agent")
    stage_name = stage.get("name", "未知阶段")
    stage_requirement = stage.get("requirement", f"执行{stage_name}任务")

    assemble_context = {
        "_agent_requirement": f"角色：{stage.get('agent', '执行者')}。任务：{stage_requirement}",
        "_asset_store": asset_store,
        "_parent_agent": parent_agent,
    }
    assemble_context = assemble_agent(assemble_context)

    child = assemble_context.get("_assembled_agent")
    agent_config = assemble_context.get("_agent_config", {})

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
            return None

        # F14: Persist child agent to database
        try:
            from core.db import get_db
            db = get_db()
            agent_id = child.name
            existing_agent = db.select_one("agents", "id", agent_id)
            if not existing_agent:
                from datetime import datetime
                db.insert("agents", {
                    "id": agent_id,
                    "name": child.name,
                    "agent_type": "child",
                    "generation": child.generation,
                    "created_at": datetime.now().isoformat(),
                })
            task_id = context.get("_task_id", "")
            existing_status = db.select_one("agent_status", "agent_id", agent_id)
            if existing_status:
                from datetime import datetime
                db.update("agent_status", "agent_id", agent_id, {
                    "status": "active",
                    "current_task_id": task_id,
                    "last_heartbeat": datetime.now().isoformat(),
                })
            else:
                from datetime import datetime
                db.insert("agent_status", {
                    "agent_id": agent_id,
                    "status": "active",
                    "current_task_id": task_id,
                    "last_heartbeat": datetime.now().isoformat(),
                })
        except Exception as e:
            import traceback
            logger.warning("[F14] Agent持久化失败: %s: %s", type(e).__name__, e)
            traceback.print_exc()

    if child is None:
        result = {
            "stage": stage_name,
            "agent": stage.get("agent", "未知"),
            "output": f"[{stage_name}] Agent组装失败",
            "status": "failed",
        }
        context["_stage_results"] = context.get("_stage_results", []) + [result]
        context["_current_stage_result"] = result
        return None

    # 将 agent_config 存入 context，供 _execute_child 使用
    context["_agent_config"] = agent_config
    return child


def _execute_child(child, context: dict, stage: dict) -> dict:
    """
    执行孙辈Agent，返回结果上下文。
    包含：构造initial_context、调用child.run()、更新agent_status为destroyed。
    """
    stage_name = stage.get("name", "未知阶段")
    stage_requirement = stage.get("requirement", f"执行{stage_name}任务")

    initial_context = {
        "_task_description": stage_requirement,
        "_output_type": stage.get("output_type", "document"),
        "_output_path": f"output/{stage_name.replace(' ', '_')}_{child.name}.md",
        "_task_id": context.get("_task_id", ""),
        "_agent_id": child.name,
    }

    agent_config = context.get("_agent_config", {})
    try:
        result_context = child.run(
            sop_steps=agent_config.get("sop_steps", ["call_llm_for_output"]),
            initial_context=initial_context
        )
    except Exception as e:
        result_context = {"_generated_content": f"执行失败: {str(e)}"}

    # V2.0: 更新 agent_status 为 destroyed
    try:
        from core.db import get_db
        from datetime import datetime
        db_after = get_db()
        db_after.update("agent_status", "agent_id", child.name, {
            "status": "destroyed",
            "last_heartbeat": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.warning("[V2.0] 孙辈销毁状态更新失败 (%s): %s", child.name, e)

    return result_context


def _persist_result(context: dict, stage_name: str, result_context: dict, child) -> dict:
    """
    持久化阶段执行结果到context。
    构建result字典，保存child.store数据，更新_stage_results。
    """
    agent_config = context.get("_agent_config", {})
    result_text = result_context.get(
        "_generated_content",
        result_context.get("_result", result_context.get("_llm_response", "执行完成"))
    )
    status = "completed" if "_generated_content" in result_context else "failed"

    result = {
        "stage": stage_name,
        "agent": child.name if child else "未知",
        "skills_used": agent_config.get("skills", []),
        "skill_sources": agent_config.get("skill_sources", {}),
        "output": f"[{stage_name}] {result_text[:100]}",
        "status": status,
        "child_generation": child.generation if child else 0,
        "agent_assembled": True,
    }

    child_store_data = {}
    if child is not None:
        for key in child.store.list_keys():
            child_store_data[key] = child.store.load(key)

    stage_results = context.get("_stage_results", [])
    stage_results.append(result)

    context["_stage_results"] = stage_results
    context["_current_stage_result"] = result
    context["_child_store_data"] = child_store_data
    context["_reason"] = (
        f"孙辈Agent(组装)执行阶段'{stage_name}'完成。"
        f"Skills: {agent_config.get('skills')}（来源: {agent_config.get('skill_sources')}）"
    )

    return context


def execute_stage(context: dict) -> dict:
    """
    为当前SOP阶段动态组装孙辈Agent并执行。

    输入 context 键：
        _current_stage: dict —— 当前阶段定义
        _parent_agent: Agent —— 父辈Agent引用
        _asset_store: Store —— 资产Store引用
        _stage_results: list

    输出 context 键：
        _stage_results: list
        _current_stage_result: dict
        _child_store_data: dict
        _reason: str
    """

    stage = context.get("_current_stage", {})
    stage_name = stage.get("name", "未知阶段")

    # 1. 决策点检查
    if _check_decision_point(context, stage):
        # 不立即返回！等待决策完成，然后继续执行
        # 支持非阻塞模式（如 Streamlit UI）
        blocking = not context.get("_non_blocking_decision", False)
        context = _wait_for_decision_and_continue(context, blocking=blocking)
        # 非阻塞模式：如果正在等待决策，返回 context 让调用方渲染决策面板
        if context.get("_awaiting_decision"):
            return context
        # 检查决策结果
        if context.get("_rejected"):
            # 被驳回，不执行当前阶段
            if "_stage_results" not in context:
                context["_stage_results"] = []
            context["_stage_results"].append({
                "stage": stage_name,
                "status": "rejected",
                "reason": "用户驳回"
            })
            context["_current_stage_result"] = {"status": "rejected", "reason": "用户驳回"}
            return context
        # 如果 needs_revision，暂时先执行（后续可扩展）
        # 否则（确认），继续执行

    # 2. 组装子Agent
    child = _assemble_child(context, stage)
    if child is None:
        return context  # 组装失败，已写入错误结果

    # 3. 执行子Agent
    result_context = _execute_child(child, context, stage)

    # 4. 持久化结果
    context = _persist_result(context, stage_name, result_context, child)
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
        logger.info("[V2.0-长老审计] 完成 task_id=%s: %s", task_id, reason)

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
        logger.warning("[V2.0-长老审计] 失败（不影响任务状态）: %s", e)


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

    logger.info("[V2.0-长老审计] 后台审计已启动，task_id=%s", task_id)
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
    4. 如果所有阶段已完成，发布 TASK_COMPLETED 事件

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

        # V3.0 修复：跟踪每个任务的阶段完成状态
        # {task_id: {"total": N, "completed": set(), "total_stages": N}}
        _task_progress: dict = {}

        async def on_stage_started(event: Event):
            """STAGE_STARTED 回调：执行阶段 → 发布 STAGE_COMPLETED → 检查是否全部完成"""
            nonlocal _task_progress

            task_id = event.data.get("task_id", "unknown")
            stage_name = event.data.get("stage_name", "未知阶段")
            stage_order = event.data.get("stage_order", 0)
            total_stages = event.data.get("total_stages", 0)

            logger.info("[V3.0] execute_stage 收到 STAGE_STARTED: %s (阶段 %s/%s)",
                        stage_name, stage_order, total_stages)

            # 初始化任务进度跟踪
            if task_id not in _task_progress:
                _task_progress[task_id] = {
                    "total": total_stages,
                    "completed": set(),
                    "total_stages": total_stages,
                }

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

            # 调用 execute_stage（P1-1 修复：asyncio.to_thread 避免阻塞事件循环）
            result_context = await asyncio.to_thread(execute_stage, stage_context)
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

            # V3.0 修复：检查是否所有阶段已完成
            progress = _task_progress[task_id]
            progress["completed"].add(stage_order)

            if len(progress["completed"]) >= progress["total"]:
                # 所有阶段已完成 → 发布 TASK_COMPLETED
                logger.info("[V3.0] 所有阶段已完成 (%s/%s)，发布 TASK_COMPLETED: %s",
                            len(progress["completed"]), progress["total"], task_id)
                await bus.publish(Event(
                    event_type=EventType.TASK_COMPLETED,
                    source="orchestration:stage_executor",
                    data={
                        "task_id": task_id,
                        "stages_completed": len(progress["completed"]),
                        "total_stages": progress["total"],
                        "status": "completed",
                    },
                ))
                # 清理进度跟踪
                del _task_progress[task_id]

        bus.subscribe_async(EventType.STAGE_STARTED, on_stage_started)
        logger.info("[V3.0] execute_stage 已订阅 STAGE_STARTED 事件")
        return True

    except Exception as e:
        logger.warning("[V3.0] execute_stage 事件订阅失败（已忽略）: %s", e)
        return False
