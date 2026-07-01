"""
V3.0: 事件驱动的阶段执行器（从 orchestration.py 拆分）

收到 STAGE_STARTED 事件后自动执行阶段，完成后发布 STAGE_COMPLETED 和 TASK_COMPLETED。
"""

import asyncio
import logging

logger = logging.getLogger(__name__)


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
    try:
        from core.event_bus import Event, EventType, get_async_event_bus
        from skills.orchestration import execute_stage

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

            logger.info(
                "[V3.0] execute_stage 收到 STAGE_STARTED: %s (阶段 %s/%s)",
                stage_name,
                stage_order,
                total_stages,
            )

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
            await bus.publish(
                Event(
                    event_type=EventType.STAGE_COMPLETED,
                    source="orchestration:stage_executor",
                    data={
                        "task_id": task_id,
                        "stage_name": stage_name,
                        "stage_order": stage_order,
                        "total_stages": total_stages,
                        "status": stage_status,
                    },
                )
            )
            logger.info(
                "[V3.0] execute_stage 发布 STAGE_COMPLETED: %s (status=%s)",
                stage_name,
                stage_status,
            )

            # V3.0 修复：检查是否所有阶段已完成
            progress = _task_progress[task_id]
            progress["completed"].add(stage_order)

            if len(progress["completed"]) >= progress["total"]:
                # 所有阶段已完成 → 发布 TASK_COMPLETED
                logger.info(
                    "[V3.0] 所有阶段已完成 (%s/%s)，发布 TASK_COMPLETED: %s",
                    len(progress["completed"]),
                    progress["total"],
                    task_id,
                )
                await bus.publish(
                    Event(
                        event_type=EventType.TASK_COMPLETED,
                        source="orchestration:stage_executor",
                        data={
                            "task_id": task_id,
                            "stages_completed": len(progress["completed"]),
                            "total_stages": progress["total"],
                            "status": "completed",
                        },
                    )
                )
                # 清理进度跟踪
                del _task_progress[task_id]

        bus.subscribe_async(EventType.STAGE_STARTED, on_stage_started)
        logger.info("[V3.0] execute_stage 已订阅 STAGE_STARTED 事件")
        return True

    except Exception as e:
        logger.warning("[V3.0] execute_stage 事件订阅失败（已忽略）: %s", e)
        return False
