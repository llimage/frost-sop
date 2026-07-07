"""
PHILOSOPHY:
Orchestration Skills manage agent lifecycle (spawn/emit/validate/merge).
"""

import contextlib
import logging
import os
import sys
import threading
from datetime import datetime

from core.agent import Agent
from core.panel_decision import get_decision_flow
from core.skill import Skill
from core.store import Store

logger = logging.getLogger(__name__)


def spawn(context: dict) -> dict:
    """
    Spawn a child agent from context specification.

    Args:
        context: Dictionary containing '_spawn_spec'

    Returns:
        Updated context with child execution results
    """
    spec = context.get("_spawn_spec", {})
    if not spec:
        return context

    template = spec.get("template_agent")
    if not template:
        return context

    # Create child agent
    child = Agent(
        name=spec.get("agent_id", "child"),
        store=Store(),
        skills=template.skills.copy() if template.skills else {},
        sop_steps=template._sop_steps.copy() if hasattr(template, "_sop_steps") else [],
    )

    # Run child agent
    result_ctx = child.run(child._sop_steps, spec.get("initial_context", {}))

    # Collect results
    context.update(result_ctx)
    if "_children_results" not in context:
        context["_children_results"] = []
    context["_children_results"].append(
        {
            "agent_id": child.name,
            "result": result_ctx,
        }
    )

    return context


def emit(context: dict) -> dict:
    """
    Emit specified keys from context to '_result'.

    Args:
        context: Dictionary containing '_emit_keys'

    Returns:
        Updated context with '_result' dictionary
    """
    keys = context.get("_emit_keys", ["_result"])
    context["_result"] = {k: context.get(k) for k in keys}
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

    sop = context.get("_sop_to_validate")
    rules = context.get("_compliance_rules", {})

    if sop is None:
        context["_validation_result"] = {
            "valid": False,
            "errors": [{"message": "No SOP to validate"}],
        }
        return context

    validator = SOPValidator()
    context["_validation_result"] = validator.validate(sop, rules)

    return context


def merge_from(context: dict) -> dict:
    """
    Merge results from child store to parent store.

    Args:
        context: Dictionary containing '_child_store', '_store', and '_merge_keys'

    Returns:
        Updated context with merged data
    """
    child_store = context.get("_child_store")
    parent_store = context.get("_store")
    filter_keys = context.get("_merge_keys", [])

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
            logger.warning("跳过决策点（无有效 task_id）: %s", stage_name)
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
                decision_id,
                record.status.value,
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
                logger.info("[V5.0] 决策面板已生成: %s", decision_panel.panel_id)
            except Exception as e:
                logger.warning("[V5.0] 决策面板生成失败（不影响暂停）: %s", e)

    return context.get("_paused_for_decision", False)  # type: ignore[no-any-return]


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

    # 2. 等待用户输入（安全防护：S-002 fix）
    options = context.get("_decision_options", ["确认", "驳回", "修改"])

    print()
    # 检查是否在非交互环境中运行
    # isatty() 可能在管道/重定向场景下误判，FROST_NON_INTERACTIVE 作为兜底
    non_interactive = not sys.stdin.isatty() or os.environ.get(
        "FROST_NON_INTERACTIVE", ""
    ).lower() in ("1", "true", "yes")
    if non_interactive:
        logger.warning("_wait_for_decision_and_continue: 非交互环境，使用默认决策")
        choice = options[0]  # 默认确认
    else:
        while True:
            try:
                choice = input(f"请输入决策（{'，'.join(options)}）：").strip()
                if choice in options:
                    break
                else:
                    print(f"无效输入，请重新输入（{'，'.join(options)}）")
            except EOFError:
                logger.warning("_wait_for_decision_and_continue: EOF，使用默认决策")
                choice = options[0]
                break

    # 3. 提交决策到 DecisionFlow
    return _submit_decision_and_update_context(context, decision_id, choice, "CLI 用户输入")


def _submit_decision_and_update_context(
    context: dict, decision_id: str, choice: str, reason_prefix: str = ""
) -> dict:
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
            decision_id,
            choice,
            record.status.value,
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
    # 兼容 requirement 和 prompt 两种字段名
    stage_requirement = stage.get("requirement") or stage.get("prompt", f"执行{stage_name}任务")
    # 注入任务变量（{topic} → 实际任务描述）
    task_desc = context.get("_task_description", "")
    stage_requirement = stage_requirement.replace("{topic}", task_desc)

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

                with contextlib.suppress(Exception):
                    db.insert(
                        "agents",
                        {
                            "id": agent_id,
                            "name": child.name,
                            "agent_type": "child",
                            "generation": child.generation,
                            "created_at": datetime.now().isoformat(),
                        },
                    )
            task_id = context.get("_task_id", "")
            existing_status = db.select_one("agent_status", "agent_id", agent_id)
            if existing_status:
                from datetime import datetime

                with contextlib.suppress(Exception):
                    db.update(
                        "agent_status",
                        "agent_id",
                        agent_id,
                        {
                            "status": "active",
                            "current_task_id": task_id,
                            "last_heartbeat": datetime.now().isoformat(),
                        },
                    )
            else:
                from datetime import datetime

                with contextlib.suppress(Exception):
                    db.insert(
                        "agent_status",
                        {
                            "agent_id": agent_id,
                            "status": "active",
                            "current_task_id": task_id,
                            "last_heartbeat": datetime.now().isoformat(),
                        },
                    )
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

    包含：
    1. 构造initial_context
    2. 调用child.run()
    3. A-004: merge_from — 将子Agent Store数据合并到父Store
    4. A-005: record_usage — 记录武器使用反馈
    5. 更新agent_status为destroyed
    """
    stage_name = stage.get("name", "未知阶段")
    # 兼容 requirement 和 prompt 两种字段名
    stage_requirement = stage.get("requirement") or stage.get("prompt", f"执行{stage_name}任务")
    # 注入任务变量（{topic} → 实际任务描述）
    task_desc = context.get("_task_description", "")
    stage_requirement = stage_requirement.replace("{topic}", task_desc)

    # 收集前序阶段输出，注入到当前阶段prompt中（阶段间上下文传递）
    prev_results = context.get("_stage_results", [])
    if prev_results:
        logger.info("[上下文传递] 阶段'%s'收到 %d 个前序阶段输出", stage_name, len(prev_results))
        for prev in prev_results:
            prev_stage = prev.get("stage", "未知")
            prev_output = prev.get("output", "")
            logger.info("[上下文传递]   - %s: %d字符", prev_stage, len(prev_output))
        prev_summary = "\n\n---\n\n## 前序阶段输出（你必须严格基于这些内容继续）\n\n"
        for prev in prev_results:
            prev_stage = prev.get("stage", "未知")
            prev_output = prev.get("output", "")
            prev_summary += f"### {prev_stage}的输出:\n{prev_output}\n\n"
        stage_requirement = f"{stage_requirement}{prev_summary}\n\n【强制规则】你正在执行'{stage_name}'阶段。你必须：\n1. 严格基于以上前序阶段的输出继续，不要引入与前序输出无关的新话题\n2. 如果前序输出关于'长上下文记忆管理'，你的输出也必须关于'长上下文记忆管理'\n3. 禁止凭空想象或依赖训练数据中的无关信息\n4. 如果前序输出包含具体的论文/项目/技术方案，你的分析必须围绕这些内容展开\n"

    # ── P2: web_fetch — 为阶段注入真实网页内容 ──
    web_fetch_urls = stage.get("web_fetch_urls", [])
    web_fetch_query = stage.get("web_fetch_query", "")
    # 替换 {topic} 占位符（与其他字段保持一致）
    if web_fetch_query:
        web_fetch_query = web_fetch_query.replace("{topic}", task_desc)
    if web_fetch_urls:
        web_fetch_urls = [u.replace("{topic}", task_desc) for u in web_fetch_urls]
    if web_fetch_urls or web_fetch_query:
        try:
            from skills.web_fetcher import web_fetch_skill

            wf_context = {
                "_urls": web_fetch_urls,
                "_query": web_fetch_query,
                "_max_results": stage.get("web_fetch_max_results", 3),
                "_max_chars_per_url": stage.get("web_fetch_max_chars", 3000),
            }
            wf_result = web_fetch_skill.execute(wf_context)
            web_content = wf_result.get("_web_content", "")
            web_sources = wf_result.get("_web_sources", [])
            logger.info(
                "[web_fetch] 阶段'%s'抓取了 %d 个来源，共 %d 字符",
                stage_name,
                len(web_sources),
                len(web_content),
            )
            if web_content:
                stage_requirement = (
                    f"{stage_requirement}\n\n---\n\n## 真实信息来源\n\n"
                    f"以下是真实网页内容，你必须基于这些内容进行分析，不要依赖自己的训练数据。\n\n"
                    f"{web_content}\n\n"
                    f"重要：以上是从真实网页抓取的内容，请严格基于这些内容回答问题。"
                )
        except Exception as e:
            logger.warning("[web_fetch] 阶段'%s'抓取失败: %s", stage_name, e)

    # ── P2补充：如果上下文已有预抓取内容（由外部Agent通过API传入），也注入 ──
    pre_fetched = context.get("_web_content", "")
    if pre_fetched and "真实信息来源" not in stage_requirement:
        logger.info("[web_fetch] 阶段'%s'使用预抓取内容（%d字符）", stage_name, len(pre_fetched))
        logger.info("[web_fetch] 预抓取内容前100字: %s", pre_fetched[:100])
        stage_requirement = (
            f"{stage_requirement}\n\n---\n\n## 真实信息来源（预抓取）\n\n"
            f"以下是外部Agent预抓取的网页内容，你必须基于这些内容进行分析。\n\n"
            f"{pre_fetched[:5000]}\n\n"
            f"重要：以上是从真实网页抓取的内容，请严格基于这些内容回答问题。"
        )
        logger.info("[web_fetch] stage_requirement现在长度: %d", len(stage_requirement))

    initial_context = {
        "_task_description": stage_requirement,
        "_output_type": stage.get("output_type", "document"),
        "_output_path": f"output/{stage_name.replace(' ', '_')}_{child.name}.md",
        "_task_id": context.get("_task_id", ""),
        "_agent_id": child.name,
    }

    agent_config = context.get("_agent_config", {})
    execution_success = True
    try:
        result_context = child.run(
            sop_steps=agent_config.get("sop_steps", ["call_llm_for_output"]),
            initial_context=initial_context,
        )
    except Exception as e:
        result_context = {"_generated_content": f"执行失败: {str(e)}"}
        execution_success = False

    # ── P2补充：输出验证 + 主题偏移纠正重试 ──
    _validation_retry_count = 0
    _max_validation_retries = 1
    while _validation_retry_count <= _max_validation_retries:
        # 提取本阶段输出
        stage_output = result_context.get("_generated_content", "")
        if not stage_output:
            break

        # 调用validate_output skill
        try:
            from skills.output_validator import validate_output_skill

            expected_topic = task_desc or ""
            val_context = {
                "_output_to_validate": stage_output,
                "_expected_topic": expected_topic,
                "_validation_type": "topic",
                "_stage_name": stage_name,
            }
            val_result = validate_output_skill.execute(val_context)
            validation_passed = val_result.get("_validation_passed", True)
            validation_issues = val_result.get("_validation_issues", [])
            correction_prompt = val_result.get("_correction_prompt", "")

            if validation_passed:
                logger.info("[output_validator] 阶段'%s'输出验证通过", stage_name)
                break
            else:
                _validation_retry_count += 1
                logger.warning(
                    "[output_validator] 阶段'%s'输出验证失败（%d/%d）：%s",
                    stage_name,
                    _validation_retry_count,
                    _max_validation_retries,
                    validation_issues,
                )
                if _validation_retry_count <= _max_validation_retries and correction_prompt:
                    # 注入纠正prompt，重新执行
                    logger.info("[output_validator] 阶段'%s'重新执行（纠正主题偏移）", stage_name)
                    initial_context["_task_description"] = (
                        f"{stage_requirement}\n\n【纠正指令】{correction_prompt}"
                    )
                    result_context = child.run(
                        sop_steps=agent_config.get("sop_steps", ["call_llm_for_output"]),
                        initial_context=initial_context,
                    )
                else:
                    break
        except Exception as e:
            logger.warning("[output_validator] 阶段'%s'验证失败: %s", stage_name, e)
            break

    # ── A-004: merge_from — 孙辈退出 → 父辈合并经验 ──
    _merge_child_store_to_parent(child, context)

    # ── A-005: record_usage — 武器使用反馈环 ──
    _record_weapon_usage(agent_config, context, execution_success)

    # V2.0: 更新 agent_status 为 destroyed
    try:
        from datetime import datetime

        from core.db import get_db

        db_after = get_db()
        db_after.update(
            "agent_status",
            "agent_id",
            child.name,
            {
                "status": "destroyed",
                "last_heartbeat": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.warning("[V2.0] 孙辈销毁状态更新失败 (%s): %s", child.name, e)

    return result_context  # type: ignore[no-any-return]


def _merge_child_store_to_parent(child, context: dict) -> None:
    """
    A-004: 将孙辈Agent的Store数据合并到父辈Store。

    这是FROST家族资产体系的"跨代际经验继承"核心机制：
    - 孙辈执行任务产生的结果（output/lesson/task数据）
    - 自动回流到父辈Store
    - 过滤内部键（_开头），只合并业务数据
    """
    parent_store = context.get("_store")
    if parent_store is None or child is None:
        return

    try:
        child_keys = child.store.list_keys()
        merge_count = 0
        for key in child_keys:
            # 跳过内部键
            if key.startswith("_"):
                continue
            value = child.store.load(key)
            if value is not None:
                parent_store.save(key, value)
                merge_count += 1
        if merge_count > 0:
            logger.info(
                "[A-004] merge_from: 孙辈 '%s' → 父辈合并 %d 个键",
                child.name,
                merge_count,
            )
    except Exception as e:
        logger.warning("[A-004] merge_from 失败 (%s): %s", child.name, e)


def _record_weapon_usage(agent_config: dict, context: dict, success: bool) -> None:
    """
    A-005: 记录武器使用反馈，更新健康评分。

    每次孙辈Agent执行完成后，记录其所用武器（Skills）的使用结果，
    驱动 health_score 动态更新，让武器库自然选择"优胜劣汰"。
    """
    skills_used = agent_config.get("skills", [])
    if not skills_used:
        return

    try:
        from core.armory import get_armory_registry

        parent_store = context.get("_store")
        armory = get_armory_registry(store=parent_store)

        for skill_name in skills_used:
            # 武器ID格式：skill:{skill_name}
            weapon_id = f"skill:{skill_name}"
            with contextlib.suppress(ValueError):
                armory.record_usage(weapon_id, success=success)
    except Exception as e:
        logger.debug("[A-005] record_usage 失败: %s", e)


def _validate_output(result_text: str, stage: dict, stage_name: str) -> dict:
    """
    验证LLM输出是否符合格式要求。
    返回 {"valid": bool, "issues": [str]}。
    """
    issues = []
    output = result_text.strip()

    # 1. 检查寒暄语（最常见的思维飘逸指标）
    forbidden_prefixes = ["好的", "我来", "以下是", "根据您", "好的，", "当然", "没问题", "以下是"]
    for prefix in forbidden_prefixes:
        if output[:20].startswith(prefix):
            issues.append(f"输出以寒暄语'{prefix}'开头，违反格式约束")
            break

    # 2. 检查输出长度（太短说明LLM没有认真执行）
    if len(output) < 100:
        issues.append(f"输出过短（{len(output)}字符），可能未认真执行任务")

    # 3. 检查是否以Markdown标题开头（格式约束要求）
    if not output.startswith("#") and not output.startswith("|"):
        issues.append("输出未以Markdown标题(##)或表格(|)开头，可能不符合格式要求")

    # 4. 检查是否包含"执行失败"等错误标记
    if "执行失败" in output[:50] or "Error" in output[:50]:
        issues.append("输出包含执行失败标记")

    return {"valid": len(issues) == 0, "issues": issues}


def _log_validation_failure(stage_name: str, issues: list, output_preview: str):
    """将验证失败记录到 config/AGENTS.md 失败日志。"""
    try:
        log_path = os.path.join(os.path.dirname(__file__), "..", "config", "AGENTS.md")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"""
## [{timestamp}] 输出验证失败 — {stage_name}

**问题**:
{chr(10).join(f"- {i}" for i in issues)}

**输出预览**（前200字）:
{output_preview[:200]}

**改进方向**: 检查SOP模板的prompt约束是否足够明确
---
"""
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception as e:
        logger.warning("写入AGENTS.md失败日志失败: %s", e)


def _persist_result(context: dict, stage_name: str, result_context: dict, child) -> dict:
    """
    持久化阶段执行结果到context。
    构建result字典，保存child.store数据，更新_stage_results。
    包含输出格式验证。
    """
    agent_config = context.get("_agent_config", {})
    result_text = result_context.get(
        "_generated_content",
        result_context.get("_result", result_context.get("_llm_response", "执行完成")),
    )
    status = "completed" if "_generated_content" in result_context else "failed"

    # 输出格式验证
    stage = context.get("_current_stage", {})
    validation = _validate_output(result_text, stage, stage_name)
    if not validation["valid"]:
        _log_validation_failure(stage_name, validation["issues"], result_text)
        logger.warning("[输出验证] 阶段'%s'输出不合规: %s", stage_name, validation["issues"])

    result = {
        "stage": stage_name,
        "agent": child.name if child else "未知",
        "skills_used": agent_config.get("skills", []),
        "skill_sources": agent_config.get("skill_sources", {}),
        "output": result_text,  # 不再截断，保留完整输出
        "status": status,
        "format_valid": validation["valid"],
        "format_issues": validation["issues"],
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
            context["_stage_results"].append(
                {"stage": stage_name, "status": "rejected", "reason": "用户驳回"}
            )
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

    # P0: 输出验证失败时自动重试1次
    current_result = context.get("_current_stage_result", {})
    if not current_result.get("format_valid", True) and current_result.get("status") == "completed":
        issues = current_result.get("format_issues", [])
        logger.warning("[P0重试] 阶段'%s'输出不合规，自动重试1次。问题: %s", stage_name, issues)

        # 从_stage_results中移除不合格的结果
        stage_results = context.get("_stage_results", [])
        if stage_results and stage_results[-1].get("stage") == stage_name:
            stage_results.pop()
            context["_stage_results"] = stage_results

        # 构建纠正prompt：在原requirement前加上纠正指令
        correction_prefix = (
            "【重要纠正】上一次输出存在以下问题，请修正后重新生成：\n"
            + "\n".join(f"- {issue}" for issue in issues)
            + "\n\n请严格遵守输出格式要求，直接以Markdown标题开头，不要任何寒暄语。\n\n---\n\n"
        )
        # 临时修改stage的requirement/prompt，加入纠正前缀
        original_requirement = stage.get("requirement") or stage.get("prompt", "")
        stage["requirement"] = correction_prefix + original_requirement

        # 重新组装并执行
        child_retry = _assemble_child(context, stage)
        if child_retry is not None:
            result_context_retry = _execute_child(child_retry, context, stage)
            context = _persist_result(context, stage_name, result_context_retry, child_retry)
            retry_result = context.get("_current_stage_result", {})
            if retry_result.get("format_valid", False):
                logger.info("[P0重试] 阶段'%s'重试后输出合规", stage_name)
            else:
                logger.warning("[P0重试] 阶段'%s'重试后仍不合规，保留重试结果", stage_name)

        # 恢复原始requirement（避免污染后续执行）
        stage["requirement"] = original_requirement

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
            },
        )

        audit_report = audit_context.get("_audit_report", {})
        reason = audit_context.get("_reason", "审计完成")

        # 将审计结果写入 audit_log 表
        db = get_db()
        db.log_audit(
            {
                "agent_id": f"elder_audit_{task_id[:8]}",
                "action": "auto_audit",
                "details": f"task_id={task_id} | {reason} | report={str(audit_report)[:500]}",
                "level": "info",
            }
        )
        logger.info("[V2.0-长老审计] 完成 task_id=%s: %s", task_id, reason)

    except Exception as e:
        # 长老审计失败仅记录日志，不影响任务完成状态
        try:
            from core.db import get_db

            db = get_db()
            db.log_audit(
                {
                    "agent_id": "elder_audit",
                    "action": "auto_audit_failed",
                    "details": f"task_id={task_id} | 长老审计失败: {str(e)[:200]}",
                    "level": "warning",
                }
            )
        except Exception:
            pass
        logger.warning("[V2.0-长老审计] 失败（不影响任务状态）: %s", e)


# ============================================================
# V6.0 阶段：军师分析后台线程（执行→复盘闭环）
# ============================================================


def _trigger_analytics_briefing(task_id, asset_store, constitution_store):
    """
    V6.0: 后台线程 —— 触发军师分析简报。

    流程：
    1. 调用 skills.analytics 的6个分析函数（light模式，0成本）
    2. 调用 integrate_briefings() 生成整合简报
    3. 将简报保存到 asset_store: briefing:{task_id}
    4. 将简报写入 audit_log
    5. 如果预算使用率>80%，记录 warning

    Args:
        task_id: 关联的任务 ID
        asset_store: 资产 Store
        constitution_store: 宪法 Store（可为 None）
    """
    try:
        from skills.analytics import (
            analyze_audit,
            analyze_finance,
            analyze_heartbeat,
            analyze_hunt,
            analyze_skill,
            analyze_task,
            integrate_briefings,
        )

        logger.info("[Analytics] 后台分析开始: %s", task_id)

        # 构造分析上下文（light模式不调用LLM，成本0）
        ctx = {"_asset_store": asset_store, "_analysis_depth": "light"}
        if constitution_store:
            ctx["_constitution_store"] = constitution_store

        # 顺序执行6个分析
        ctx = analyze_finance(ctx)
        ctx = analyze_skill(ctx)
        ctx = analyze_task(ctx)
        ctx = analyze_audit(ctx)
        ctx = analyze_heartbeat(ctx)
        ctx = analyze_hunt(ctx)

        # 整合简报
        ctx = integrate_briefings(ctx)
        briefing = ctx.get("_integrated_briefing", {})

        # 保存到 Store
        if asset_store:
            asset_store.save(f"briefing:{task_id}", briefing)

        # 写入 audit_log
        from core.db import get_db

        db = get_db()
        db.log_audit(
            {
                "agent_id": f"analytics_{task_id[:8]}",
                "action": "briefing_generated",
                "details": str(briefing)[:500],
                "level": "info",
            }
        )

        # 检查预算预警
        finance = ctx.get("_analytics_finance", {})
        if finance.get("budget_usage_rate", 0) > 0.8:
            logger.warning("[Analytics] 预算使用率超过80%%")
            db.log_audit(
                {
                    "agent_id": "system",
                    "action": "budget_alert",
                    "details": f"budget_usage={finance['budget_usage_rate']:.1%}",
                    "level": "warning",
                }
            )

        logger.info("[Analytics] 后台分析完成: %s", task_id)

    except Exception as e:
        logger.warning("[Analytics] 后台分析失败（不影响任务）: %s", e)
        try:
            from core.db import get_db

            get_db().log_audit(
                {
                    "agent_id": "analytics",
                    "action": "briefing_failed",
                    "details": str(e)[:200],
                    "level": "warning",
                }
            )
        except Exception:
            pass


def _trigger_evolution_analysis(task_id, asset_store):
    """
    V6.0: 后台线程 —— 触发自进化分析。

    流程：
    1. 从 asset_store 加载任务历史
    2. 调用 analyze_trends() 分析趋势
    3. 调用 generate_suggestions() 生成建议
    4. 如果建议非空，调用 present_for_approval() 生成报告
    5. 将报告保存到 asset_store: evolution:{task_id}
    6. 如果建议涉及 SOP 优化，自动调用 manage_sop_version()

    Args:
        task_id: 关联的任务 ID
        asset_store: 资产 Store
    """
    try:
        from skills.evolution import (
            analyze_trends,
            generate_suggestions,
            load_task_history,
            manage_sop_version,
            present_for_approval,
        )

        logger.info("[Evolution] 后台进化分析开始: %s", task_id)

        ctx = {"_asset_store": asset_store, "_history_limit": 20}

        # 加载历史 → 分析趋势 → 生成建议
        ctx = load_task_history(ctx)
        ctx = analyze_trends(ctx)
        ctx = generate_suggestions(ctx)

        suggestions = ctx.get("_suggestions", [])

        if suggestions:
            # 生成报告
            ctx = present_for_approval(ctx)
            report = ctx.get("_approval_report", "")

            # 保存
            if asset_store:
                asset_store.save(
                    f"evolution:{task_id}",
                    {
                        "report": report,
                        "suggestions": suggestions,
                        "timestamp": datetime.now().isoformat(),
                    },
                )

            # 如果有 SOP 优化建议，自动创建 v2
            for s in suggestions:
                if s.get("type") == "sop_optimization":
                    ctx["_sop_optimization"] = s
                    ctx = manage_sop_version(ctx)
                    if ctx.get("_sop_version_created"):
                        logger.info("[Evolution] 自动创建 SOP v2: %s", s.get("target", "unknown"))

        logger.info(
            "[Evolution] 后台进化分析完成: %s 条建议，task_id=%s", len(suggestions), task_id
        )

    except Exception as e:
        logger.warning("[Evolution] 后台进化分析失败（不影响任务）: %s", e)
        try:
            from core.db import get_db

            get_db().log_audit(
                {
                    "agent_id": "evolution",
                    "action": "evolution_failed",
                    "details": str(e)[:200],
                    "level": "warning",
                }
            )
        except Exception:
            pass


def finalize_task(context: dict) -> dict:
    """
    V2.0+V6.0: 任务收尾 Skill。
    在所有阶段执行完成后，在后台触发：
    1. 长老审计
    2. 军师分析简报
    3. 自进化分析

    输入 context 键：
        _task_id: str —— 任务 ID
        _asset_store: Store —— 资产 Store
        _constitution_store: Store —— 宪法 Store（可为 None）
        _stage_results: list —— 阶段结果列表

    输出 context 键：
        _elder_audit_triggered: bool —— 是否已触发长老审计
        _analytics_triggered: bool —— 是否已触发军师分析
        _evolution_triggered: bool —— 是否已触发进化分析
        _reason: str —— 推理痕迹
    """
    task_id = context.get("_task_id", "unknown")
    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")

    if not task_id or task_id == "unknown":
        # 无有效 task_id，跳过所有收尾
        context["_elder_audit_triggered"] = False
        context["_analytics_triggered"] = False
        context["_evolution_triggered"] = False
        context["_reason"] = "finalize_task: 无有效 task_id，跳过收尾"
        return context

    # 在后台线程触发长老审计（不阻塞主流程）
    audit_thread = threading.Thread(
        target=_trigger_elder_audit,
        args=(task_id, asset_store, constitution_store),
        daemon=True,
        name=f"elder_audit_{task_id[:8]}",
    )
    audit_thread.start()
    context["_elder_audit_triggered"] = True
    context["_elder_audit_thread"] = audit_thread

    logger.info("[V2.0-长老审计] 后台审计已启动，task_id=%s", task_id)

    # ── V6.0: 军师分析后台线程 ──
    analytics_thread = threading.Thread(
        target=_trigger_analytics_briefing,
        args=(task_id, asset_store, constitution_store),
        daemon=True,
        name=f"analytics_{task_id[:8]}",
    )
    analytics_thread.start()
    context["_analytics_triggered"] = True
    context["_analytics_thread"] = analytics_thread

    logger.info("[V6.0-军师分析] 后台分析已启动，task_id=%s", task_id)

    # ── V6.0: 自进化后台线程 ──
    evolution_thread = threading.Thread(
        target=_trigger_evolution_analysis,
        args=(task_id, asset_store),
        daemon=True,
        name=f"evolution_{task_id[:8]}",
    )
    evolution_thread.start()
    context["_evolution_triggered"] = True
    context["_evolution_thread"] = evolution_thread

    logger.info("[V6.0-自进化] 后台进化已启动，task_id=%s", task_id)

    context["_reason"] = (
        f"finalize_task: 长老审计+军师分析+自进化 后台线程已启动，task_id={task_id}"
    )

    # ── A-006: 失败复盘 ──
    context = _scan_failed_calls_for_lessons(context)

    return context


def _scan_failed_calls_for_lessons(context: dict) -> dict:
    """
    A-006: 扫描 tool_calls 目录中的失败调用，提取教训写入错题本。

    这是FROST失败闭环学习的核心机制：
    - 扫描所有 success=false 的 tool_calls 日志
    - 按错误类型分类（timeout/api/validation/execution）
    - 写入 lesson: 前缀的错题本条目
    - 重复错误递增 times_encountered 计数
    """
    try:
        from core.skill_extractor import SkillExtractor

        extractor = SkillExtractor()
        asset_store = context.get("_asset_store")

        lesson_keys = extractor.scan_and_archive_lessons(store=asset_store)

        if lesson_keys:
            context["_lessons_archived"] = len(lesson_keys)
            context["_lesson_keys"] = lesson_keys
            logger.info(
                "[A-006] 失败复盘: 从 %d 个失败调用中提取教训",
                len(lesson_keys),
            )
        else:
            context["_lessons_archived"] = 0

        # 附加失败复盘结果到 reason
        previous_reason = context.get("_reason", "")
        if lesson_keys:
            context["_reason"] = f"{previous_reason} | 失败复盘: {len(lesson_keys)} 条教训已归档"
    except Exception as e:
        logger.warning("[A-006] 失败复盘失败（不影响任务状态）: %s", e)

    return context


# finalize_task Skill 实例
finalize_task_skill = Skill("finalize_task", finalize_task)


# V3.0 事件驱动的阶段执行器已拆分至 orchestration_v3.py
# 为保持向后兼容，重新导出
from skills.orchestration_v3 import register_stage_executor  # noqa: E402, F401
