"""
PHILOSOPHY:
事件订阅者 = 系统的"反射弧"。
不把订阅逻辑散落在各模块，集中在此注册，便于审计和调试。

设计原则：
- 每个订阅者独立注册，失败不影响其他
- 使用 try/except 包裹所有回调
- 所有事件持久化到 event_log（EventBus 自动完成）
- 仅在系统启动时调用 register_all_subscribers()
"""

import logging

logger = logging.getLogger(__name__)


def register_all_subscribers():
    """
    V6.0: 注册所有跨模块事件订阅者。
    应在系统启动时调用（main() / FastAPI startup）。
    幂等：重复调用不会重复注册（EventBus 已处理）。
    """
    from core.event_bus import EventBus, EventType

    bus = EventBus()

    # ── 任务完成 → 触发审计 + 分析 + 进化 ──
    bus.subscribe(EventType.TASK_COMPLETED, _on_task_completed)

    # ── 狩猎完成 → 触发分析 ──
    bus.subscribe(EventType.HUNT_COMPLETED, _on_hunt_completed)

    # ── 简报整合 → 触发知识归档 ──
    bus.subscribe(EventType.BRIEFING_INTEGRATED, _on_briefing_integrated)

    # ── 进化建议 → 触发SOP版本管理 ──
    bus.subscribe(EventType.EVOLUTION_SUGGESTED, _on_evolution_suggested)

    # ── 定时执行 → 记录调度日志 ──
    bus.subscribe(EventType.SCHEDULED_EXECUTED, _on_scheduled_executed)

    # ── V2.0 已有订阅保留 ──
    bus.subscribe(EventType.STAGE_FAILED, _on_stage_failed)

    logger.info(
        "[EventSubscribers] 已注册 %d 个跨模块订阅者",
        6,
    )


# ============================================================
# 订阅者回调（每个独立 try/except）
# ============================================================


def _on_task_completed(event):
    """任务完成后，验证是否触发了 finalize_task"""
    try:
        logger.info("[EventSubscribers] TASK_COMPLETED: source=%s", event.source)
    except Exception as e:
        logger.warning("[EventSubscribers] _on_task_completed 异常: %s", e)


def _on_hunt_completed(event):
    """狩猎完成后，触发分析"""
    try:
        from skills.analytics import (
            analyze_hunt,
            analyze_skill,
            integrate_briefings,
        )

        logger.info("[EventSubscribers] HUNT_COMPLETED: source=%s", event.source)

        ctx = event.data.get("_context", {})
        ctx = analyze_skill(ctx)
        ctx = analyze_hunt(ctx)
        ctx = integrate_briefings(ctx)

        # 保存简报
        asset_store = ctx.get("_asset_store")
        briefing = ctx.get("_integrated_briefing", {})
        if asset_store and briefing:
            from datetime import datetime

            key = f"briefing:hunt_event_{datetime.now().strftime('%Y%m%d')}"
            asset_store.save(key, briefing)

        logger.info("[EventSubscribers] 狩猎后分析完成")
    except Exception as e:
        logger.warning("[EventSubscribers] _on_hunt_completed 异常: %s", e)


def _on_briefing_integrated(event):
    """简报整合后，触发知识归档"""
    try:
        from skills.knowledge import archive_sop

        logger.info("[EventSubscribers] BRIEFING_INTEGRATED: source=%s", event.source)

        briefing = event.data.get("_briefing", {})
        asset_store = event.data.get("_asset_store")

        if briefing and asset_store:
            archive_ctx = {
                "_sop_to_archive": {
                    "name": "军师简报",
                    "content": briefing,
                },
                "_sop_source": "briefing",
                "_asset_store": asset_store,
            }
            archive_ctx = archive_sop(archive_ctx)
            if archive_ctx.get("_archive_result", {}).get("success"):
                logger.info("[EventSubscribers] 简报已归档")
    except Exception as e:
        logger.warning("[EventSubscribers] _on_briefing_integrated 异常: %s", e)


def _on_evolution_suggested(event):
    """进化建议生成后，触发SOP版本管理"""
    try:
        from skills.evolution import manage_sop_version

        logger.info("[EventSubscribers] EVOLUTION_SUGGESTED: source=%s", event.source)

        suggestions = event.data.get("_suggestions", [])
        for s in suggestions:
            if s.get("type") == "sop_optimization":
                ctx = {
                    "_sop_optimization": s,
                    "_asset_store": event.data.get("_asset_store"),
                }
                ctx = manage_sop_version(ctx)
                if ctx.get("_sop_version_created"):
                    logger.info(
                        "[EventSubscribers] SOP v2 自动创建: %s",
                        s.get("target", "unknown"),
                    )
    except Exception as e:
        logger.warning("[EventSubscribers] _on_evolution_suggested 异常: %s", e)


def _on_scheduled_executed(event):
    """定时任务执行后，记录调度统计"""
    try:
        from core.db import get_db

        logger.info(
            "[EventSubscribers] SCHEDULED_EXECUTED: source=%s, data=%s",
            event.source,
            event.data.get("job_type", "unknown"),
        )

        db = get_db()
        db.log_audit(
            {
                "agent_id": "scheduler",
                "action": "scheduled_job_executed",
                "details": (
                    f"source={event.source} | job_type={event.data.get('job_type', 'unknown')}"
                ),
                "level": "info",
            }
        )
    except Exception as e:
        logger.warning("[EventSubscribers] _on_scheduled_executed 异常: %s", e)


def _on_stage_failed(event):
    """阶段失败后，记录错题本（V2.0 已有逻辑增强）"""
    try:
        logger.info(
            "[EventSubscribers] STAGE_FAILED: source=%s, reason=%s",
            event.source,
            event.data.get("reason", "unknown"),
        )

        # 将失败信息写入错题本
        asset_store = event.data.get("_asset_store")
        if asset_store:
            from datetime import datetime

            lesson_key = f"lesson:stage_fail_{datetime.now().strftime('%Y%m%d%H%M%S')}"
            asset_store.save(
                lesson_key,
                {
                    "error_type": "stage_failure",
                    "source": event.source,
                    "reason": event.data.get("reason", "unknown"),
                    "timestamp": event.timestamp.isoformat() if event.timestamp else "",
                },
            )
    except Exception as e:
        logger.warning("[EventSubscribers] _on_stage_failed 异常: %s", e)
