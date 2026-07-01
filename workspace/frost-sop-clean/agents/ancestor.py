"""
PHILOSOPHY:
Ancestor Agent is the root of the agent family tree (generation=0).
It holds the constitution and has the highest authority to spawn parent agents.

V3.0: 支持 event_driven 模式 — 订阅 TASK_CREATED → LLM分解 → 发布 TASK_DECOMPOSED
V2.0: 保持原有同步调用方式（被 main() 直接调用）
"""

import logging
from core.agent import Agent
from skills.orchestration import spawn_skill, emit_skill, validate_sop_skill
from skills.llm import call_llm_skill

logger = logging.getLogger(__name__)
import asyncio


def create_ancestor(
    constitution_store, asset_store, event_driven: bool = False
) -> Agent:
    """
    Create ancestor Agent with constitution store.

    Args:
        constitution_store: HierarchicalStore containing constitution rules
        asset_store: HierarchicalStore for asset storage
        event_driven: V3.0 — 如果 True，订阅 TASK_CREATED 事件

    Returns:
        Agent instance (ancestor)
    """
    skills = {
        "spawn": spawn_skill,
        "emit": emit_skill,
        "validate_sop": validate_sop_skill,
        "call_llm": call_llm_skill,
    }

    ancestor = Agent(
        name="ancestor",
        store=constitution_store,
        skills=skills,
        generation=0,
        max_spawn_generation=1,
    )

    # V3.0: 事件驱动模式 — 订阅 TASK_CREATED
    if event_driven:
        _subscribe_ancestor_to_events(ancestor)

    return ancestor


def _subscribe_ancestor_to_events(ancestor: Agent) -> bool:
    """
    V3.0: 让 ancestor 订阅 AsyncEventBus 上的 TASK_CREATED 事件。

    收到 TASK_CREATED 后：
    1. 调用 LLM 分解任务
    2. 发布 TASK_DECOMPOSED 事件

    Returns:
        True 如果订阅成功，False 如果 AsyncEventBus 不可用
    """
    try:
        from core.event_bus import get_async_event_bus, Event, EventType

        bus = get_async_event_bus()

        async def on_task_created(event: Event):
            """TASK_CREATED 回调：LLM 分解任务 → 发布 TASK_DECOMPOSED"""
            task_input = event.data.get("task_description", "")
            task_id = event.data.get("task_id", "unknown")

            logger.info("[V3.0] ancestor 收到 TASK_CREATED: %s", task_id)

            # 调用 LLM 分解任务（P1-1 修复：asyncio.to_thread 避免阻塞事件循环）
            context = await asyncio.to_thread(
                ancestor.run,
                sop_steps=["call_llm"],
                initial_context={
                    "_prompt": f"Analyze the following task, decompose into 1-3 parent agents, return JSON: {task_input}"
                },
            )
            llm_response = context.get("_llm_response", "")

            # 发布 TASK_DECOMPOSED
            await bus.publish(
                Event(
                    event_type=EventType.TASK_DECOMPOSED,
                    source="ancestor:task_decomposer",
                    data={
                        "task_id": task_id,
                        "task_description": task_input,
                        "decomposition": llm_response,
                    },
                )
            )
            logger.info("[V3.0] ancestor 发布 TASK_DECOMPOSED: %s", task_id)

        bus.subscribe_async(
            EventType.TASK_CREATED
            if hasattr(EventType, "TASK_CREATED")
            else "task_created",
            on_task_created,
        )
        logger.info("[V3.0] ancestor 已订阅 TASK_CREATED 事件")
        return True

    except Exception as e:
        logger.warning("[V3.0] ancestor 事件订阅失败（已忽略）: %s", e)
        return False
