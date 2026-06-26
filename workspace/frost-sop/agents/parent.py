"""
FROST-SOP Parent Agent Factory
PHILOSOPHY: 父辈是成年Agent。出厂预装13个本能Skill。
所有Skill都是普通Skill，不引入特权组件。

V3.0: 支持 event_driven 模式 — 订阅 TASK_DECOMPOSED → 内化SOP → 逐阶段执行 → 发布 TASK_COMPLETED
V2.0: 保持原有同步调用方式（被 main() 直接调用）
"""

import logging
from core.agent import Agent
from skills.orchestration import (
    spawn_skill, emit_skill, validate_sop_skill, merge_from_skill,
    internalize_sop_skill, execute_stage_skill, finalize_task_skill,
)
from skills.search import search_sop_skill, search_skill_skill
from skills.llm import call_llm_skill
from skills.knowledge import archive_sop_skill, archive_lesson_skill, query_lessons_skill
from skills.assemble import assemble_agent_skill
from skills.importer import import_agency_agents_skill
from skills.evolution import (
    load_task_history_skill, analyze_trends_skill,
    generate_suggestions_skill, present_for_approval_skill,
)

logger = logging.getLogger(__name__)
import asyncio


def create_parent(name: str, coordination_store,
                  event_driven: bool = False,
                  asset_store=None,
                  sop_id: str = None) -> Agent:
    """
    创建父辈Agent。出厂预装15个本能Skill。

    Args:
        name: Agent 名称
        coordination_store: 协调 Store
        event_driven: V3.0 — 如果 True，订阅 TASK_DECOMPOSED 事件
        asset_store: V3.0 事件模式需要（用于 execute_stage）
        sop_id: V3.0 事件模式需要（用于加载 SOP 模板）

    Returns:
        Agent instance (parent)
    """
    skills = {
        "spawn": spawn_skill,
        "emit": emit_skill,
        "validate_sop": validate_sop_skill,
        "merge_from": merge_from_skill,
        "internalize_sop": internalize_sop_skill,
        "execute_stage": execute_stage_skill,
        "finalize_task": finalize_task_skill,
        "search_sop": search_sop_skill,
        "search_skill": search_skill_skill,
        "call_llm": call_llm_skill,
        "archive_sop": archive_sop_skill,
        "archive_lesson": archive_lesson_skill,
        "query_lessons": query_lessons_skill,
        "assemble_agent": assemble_agent_skill,
        "import_agency_agents": import_agency_agents_skill,
        "load_task_history": load_task_history_skill,
        "analyze_trends": analyze_trends_skill,
        "generate_suggestions": generate_suggestions_skill,
        "present_for_approval": present_for_approval_skill,
    }

    parent = Agent(
        name=name,
        store=coordination_store,
        skills=skills,
        generation=1,
    )

    # V3.0: 事件驱动模式
    if event_driven:
        _subscribe_parent_to_events(parent, asset_store, sop_id)

    return parent


def _subscribe_parent_to_events(parent: Agent, asset_store, sop_id: str) -> bool:
    """
    V3.0: 让 parent 订阅 AsyncEventBus 上的 TASK_DECOMPOSED 事件。

    收到 TASK_DECOMPOSED 后：
    1. 内化 SOP
    2. 逐阶段执行（发布 STAGE_STARTED / STAGE_COMPLETED）
    3. 全部完成后发布 TASK_COMPLETED
    """
    try:
        from core.event_bus import get_async_event_bus, Event, EventType

        bus = get_async_event_bus()

        async def on_task_decomposed(event: Event):
            """TASK_DECOMPOSED 回调：内化SOP → 逐阶段执行 → 发布 TASK_COMPLETED"""
            task_id = event.data.get("task_id", "unknown")
            decomposition = event.data.get("decomposition", "")

            logger.info("[V3.0] parent 收到 TASK_DECOMPOSED: %s", task_id)

            # 1. 加载 SOP 模板
            sop_file = f"sops/templates/{sop_id or 'DEV-001'}.yaml"
            from core.sop import SOP
            try:
                sop = SOP.load_from_yaml(sop_file)
            except Exception as e:
                logger.error("[V3.0] SOP 加载失败: %s", e)
                await bus.publish(Event(
                    event_type=EventType.TASK_FAILED,
                    source="parent:stage_executor",
                    data={"task_id": task_id, "error": f"SOP load failed: {e}"},
                ))
                return

            # 2. 内化 SOP
            sop_to_internalize = {
                "sop_id": sop.sop_id,
                "name": sop.name,
                "version": sop.version,
                "stages": sop.stages,
                "required_stages": sop.required_stages,
                "forbidden_skills": sop.forbidden_skills,
            }

            # 2. 内化 SOP（P1-1 修复：asyncio.to_thread 避免阻塞事件循环）
            int_context = await asyncio.to_thread(
                parent.run,
                sop_steps=["internalize_sop"],
                initial_context={"_sop_to_internalize": sop_to_internalize}
            )
            sop_stages = int_context.get("_sop_stages", [])
            logger.info("[V3.0] SOP 内化完成: %s 个阶段", len(sop_stages))

            # 3. 逐阶段执行
            stage_context = {
                "_stage_results": [],
                "_parent_agent": parent,
                "_task_id": task_id,
                "_asset_store": asset_store,
            }

            for i, stage in enumerate(sop_stages):
                stage_name = stage.get("name", f"阶段{i+1}")

                # 发布 STAGE_STARTED
                await bus.publish(Event(
                    event_type=EventType.STAGE_STARTED,
                    source="parent:stage_executor",
                    data={
                        "task_id": task_id,
                        "stage_name": stage_name,
                        "stage_order": i + 1,
                        "total_stages": len(sop_stages),
                    },
                ))

                # 执行阶段（P1-1 修复：asyncio.to_thread 避免阻塞事件循环）
                stage_context["_current_stage"] = stage
                stage_context = await asyncio.to_thread(
                    parent.run,
                    sop_steps=["execute_stage"],
                    initial_context=stage_context
                )

                result = stage_context.get("_current_stage_result", {})
                stage_status = result.get("status", "unknown")

                # 发布 STAGE_COMPLETED
                await bus.publish(Event(
                    event_type=EventType.STAGE_COMPLETED,
                    source="parent:stage_executor",
                    data={
                        "task_id": task_id,
                        "stage_name": stage_name,
                        "stage_order": i + 1,
                        "status": stage_status,
                    },
                ))
                logger.info("[V3.0] 阶段 %s/%s 完成: %s",
                           i + 1, len(sop_stages), stage_name)

            # 4. 全部完成 → 发布 TASK_COMPLETED
            all_results = stage_context.get("_stage_results", [])
            await bus.publish(Event(
                event_type=EventType.TASK_COMPLETED,
                source="parent:stage_executor",
                data={
                    "task_id": task_id,
                    "stages_completed": len(all_results),
                    "total_stages": len(sop_stages),
                    "stage_results": [
                        {"stage": r.get("stage", ""), "status": r.get("status", "")}
                        for r in all_results
                    ],
                },
            ))
            logger.info("[V3.0] parent 发布 TASK_COMPLETED: %s", task_id)

        bus.subscribe_async(EventType.TASK_DECOMPOSED, on_task_decomposed)
        logger.info("[V3.0] parent 已订阅 TASK_DECOMPOSED 事件")
        return True

    except Exception as e:
        logger.warning("[V3.0] parent 事件订阅失败（已忽略）: %s", e)
        return False
