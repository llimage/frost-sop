"""
PHILOSOPHY:
狩猎不是孤立动作，是闭环的起点。
hunt → analyze → integrate → evolve → schedule 五阶段流水线。

设计原则：
- 每个阶段独立为一个子函数（复杂度<10）
- 所有阶段在单个函数调用内串行完成
- 失败不阻断后续阶段
- 所有产出持久化到 asset_store
"""

import logging
from datetime import datetime

from core.skill import Skill

logger = logging.getLogger(__name__)


# ============================================================
# Phase 1: 狩猎阶段
# ============================================================


def _run_hunt_phase(context: dict) -> dict:
    """子函数：执行狩猎阶段（McCabe复杂度<10）"""
    logger.info("[HuntOrchestration] Phase 1: 狩猎")
    from skills.hunt import hunt_sop

    context = hunt_sop(context)
    hunt_result = context.get("_hunt_sop_result", {})
    logger.info(
        "[HuntOrchestration] 狩猎完成: absorbed=%s, rejected=%s",
        hunt_result.get("absorbed_count", 0),
        hunt_result.get("rejected_count", 0),
    )
    return context


# ============================================================
# Phase 2: 分析阶段
# ============================================================


def _run_analysis_phase(context: dict) -> dict:
    """子函数：执行分析阶段（light模式，0成本，McCabe复杂度<10）"""
    logger.info("[HuntOrchestration] Phase 2: 分析")

    from skills.analytics import (
        analyze_audit,
        analyze_finance,
        analyze_heartbeat,
        analyze_hunt,
        analyze_skill,
        analyze_task,
        integrate_briefings,
    )

    ctx = dict(context)
    ctx["_analysis_depth"] = "light"

    ctx = analyze_finance(ctx)
    ctx = analyze_skill(ctx)
    ctx = analyze_task(ctx)
    ctx = analyze_audit(ctx)
    ctx = analyze_heartbeat(ctx)
    ctx = analyze_hunt(ctx)

    # 整合简报
    ctx = integrate_briefings(ctx)

    # 合并关键结果回主context
    _merge_analytics_results(context, ctx)

    briefing = ctx.get("_integrated_briefing", {})
    logger.info(
        "[HuntOrchestration] 分析完成: correlations=%s",
        len(briefing.get("correlations", [])),
    )
    return context


def _merge_analytics_results(context: dict, ctx: dict) -> None:
    """辅助函数：将分析结果合并到主context（McCabe复杂度=2）"""
    keys = [
        "_analytics_finance",
        "_analytics_skill",
        "_analytics_task",
        "_analytics_audit",
        "_analytics_heartbeat",
        "_analytics_hunt",
        "_integrated_briefing",
    ]
    for key in keys:
        if key in ctx:
            context[key] = ctx[key]


# ============================================================
# Phase 3: 整合阶段
# ============================================================


def _run_integration_phase(context: dict) -> dict:
    """子函数：整合吸收阶段（McCabe复杂度<10）"""
    logger.info("[HuntOrchestration] Phase 3: 整合")

    hunt_result = context.get("_hunt_sop_result", {})
    asset_store = context.get("_asset_store")
    actions: list[str] = []

    # 3.1 归档狩猎结果
    if hunt_result.get("absorbed_count", 0) > 0:
        _archive_hunt_result(hunt_result, asset_store, actions)

    # 3.2 更新技能图
    _update_skill_graph_from_hunt(context, hunt_result, actions)

    # 3.3 保存简报
    _save_briefing_to_store(context, asset_store, actions)

    context["_integration_actions"] = actions
    logger.info("[HuntOrchestration] 整合完成: %s", actions)
    return context


def _archive_hunt_result(hunt_result: dict, asset_store, actions: list) -> None:
    """归档狩猎结果为 SOP 知识"""
    from skills.knowledge import archive_sop

    sop_data = {
        "sop_id": f"hunt_{datetime.now().strftime('%Y%m%d')}",
        "name": "狩猎结果",
        "content": hunt_result,
    }
    archive_ctx = {
        "_sop_to_archive": sop_data,
        "_sop_source": "hunt",
        "_asset_store": asset_store,
    }
    archive_ctx = archive_sop(archive_ctx)
    if archive_ctx.get("_archive_result", {}).get("success"):
        actions.append("归档狩猎结果")


def _update_skill_graph_from_hunt(context: dict, hunt_result: dict, actions: list) -> None:
    """从狩猎结果更新技能图"""
    from skills.evolution import update_skill_graph

    absorb_results = hunt_result.get("absorb_results", [])
    for result in absorb_results:
        if result.get("action") == "absorbed":
            skill_id = result.get("new_skill_id")
            if skill_id:
                context["_new_skill_id"] = skill_id
                context = update_skill_graph(context)
                actions.append(f"更新技能图: {skill_id}")


def _save_briefing_to_store(context: dict, asset_store, actions: list) -> None:
    """保存简报"""
    briefing = context.get("_integrated_briefing", {})
    if briefing and asset_store:
        key = f"briefing:hunt_{datetime.now().strftime('%Y%m%d')}"
        asset_store.save(key, briefing)
        actions.append("保存整合简报")


# ============================================================
# Phase 4: 进化阶段
# ============================================================


def _run_evolution_phase(context: dict) -> dict:
    """子函数：进化阶段（McCabe复杂度<10）"""
    logger.info("[HuntOrchestration] Phase 4: 进化")

    from skills.evolution import (
        analyze_trends,
        generate_suggestions,
        load_task_history,
        present_for_approval,
    )

    asset_store = context.get("_asset_store")
    ctx = dict(context)
    ctx["_history_limit"] = 20

    ctx = load_task_history(ctx)
    ctx = analyze_trends(ctx)
    ctx = generate_suggestions(ctx)

    suggestions = ctx.get("_suggestions", [])
    evolution_actions: list[str] = []

    if suggestions:
        ctx = present_for_approval(ctx)
        report = ctx.get("_approval_report", "")

        _process_sop_optimizations(ctx, suggestions, evolution_actions)

        if asset_store:
            key = f"evolution:hunt_{datetime.now().strftime('%Y%m%d')}"
            asset_store.save(
                key,
                {
                    "report": report,
                    "suggestions": suggestions,
                    "actions": evolution_actions,
                },
            )

    context["_evolution_suggestions"] = suggestions
    context["_evolution_actions"] = evolution_actions
    logger.info("[HuntOrchestration] 进化完成: %s条建议", len(suggestions))
    return context


def _process_sop_optimizations(ctx: dict, suggestions: list, actions: list) -> None:
    """处理SOP优化建议，自动创建v2版本"""
    from skills.evolution import manage_sop_version

    for s in suggestions:
        if s.get("type") == "sop_optimization":
            ctx["_sop_optimization"] = s
            ctx = manage_sop_version(ctx)
            if ctx.get("_sop_version_created"):
                actions.append(f"SOP优化: {s.get('target')} → v2")


# ============================================================
# Phase 5: 执行安排阶段
# ============================================================


def _run_execution_schedule(context: dict) -> dict:
    """子函数：执行安排阶段（McCabe复杂度<10）"""
    logger.info("[HuntOrchestration] Phase 5: 执行安排")

    if not context.get("_auto_execute", False):
        logger.info("[HuntOrchestration] 自动执行关闭，跳过")
        context["_scheduled_actions"] = ["自动执行关闭"]
        return context

    evolution_actions = context.get("_evolution_actions", [])
    scheduled = []

    for action in evolution_actions:
        if "SOP优化" not in action:
            continue
        # 提取 SOP ID
        sop_id = action.split("→")[0].strip().replace("SOP优化: ", "")
        try:
            from core.scheduler import FrostScheduler

            scheduler = FrostScheduler(context.get("_asset_store"))
            scheduler.schedule_sop(
                sop_id=sop_id,
                cron_expr="0 9 * * 1",  # 下周一 9:00
            )
            scheduled.append(action)
        except Exception as e:
            logger.warning("[HuntOrchestration] 安排执行失败: %s, error=%s", action, e)

    context["_scheduled_actions"] = scheduled
    logger.info("[HuntOrchestration] 安排完成: %s", scheduled)
    return context


# ============================================================
# 主入口：hunt_and_evolve
# ============================================================


def hunt_and_evolve(context: dict) -> dict:
    """
    狩猎→分析→整合→进化→执行安排 完整闭环入口。

    输入 context 键：
        _hunt_targets: 狩猎目标列表（可选，默认从配置文件加载）
        _hunt_mode: 狩猎模式 ("continuous" / "predictive")
        _asset_store: Store
        _auto_execute: bool — 是否自动执行新SOP（默认False）

    输出 context 键：
        _hunt_evolution_result: dict — 完整闭环结果
        _reason: str — 推理痕迹
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("[HuntOrchestration] 狩猎进化闭环开始")
    logger.info("=" * 60)

    # Phase 1: 狩猎
    context = _run_hunt_phase(context)

    # Phase 2: 分析
    context = _run_analysis_phase(context)

    # Phase 3: 整合
    context = _run_integration_phase(context)

    # Phase 4: 进化
    context = _run_evolution_phase(context)

    # Phase 5: 执行安排
    context = _run_execution_schedule(context)

    # 汇总结果
    duration = (datetime.now() - start_time).total_seconds()
    result = {
        "status": "completed",
        "duration_seconds": duration,
        "hunt": context.get("_hunt_sop_result", {}),
        "briefing": context.get("_integrated_briefing", {}),
        "integration": context.get("_integration_actions", []),
        "evolution": {
            "suggestions": len(context.get("_evolution_suggestions", [])),
            "actions": context.get("_evolution_actions", []),
        },
        "schedule": context.get("_scheduled_actions", []),
    }

    context["_hunt_evolution_result"] = result
    context["_reason"] = (
        f"狩猎进化闭环完成: {duration:.1f}s, {result['evolution']['suggestions']}条建议"
    )

    logger.info("=" * 60)
    logger.info("[HuntOrchestration] 闭环完成: %s", context["_reason"])
    logger.info("=" * 60)

    return context


# Skill 实例
hunt_and_evolve_skill = Skill("hunt_and_evolve", hunt_and_evolve)
