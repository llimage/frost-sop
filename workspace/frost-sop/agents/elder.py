"""
FROST-SOP 长老Agent
PHILOSOPHY: 长老是退休的祖辈。它保留独立审计权，
不参与任务执行，不干预决策。只审计，只报告。
长老是普通Agent，不是特权组件。

V2.0: 长老可订阅 TASK_COMPLETED 事件，自动执行 audit_family（fail-safe）。
V3.1: audit_family 拆分为 _scan_store / _compute_statistics /
       _generate_report / _log_audit_result 四个子函数。
"""

import logging
from datetime import datetime
from core.agent import Agent
from core.skill import Skill

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 重构子函数: audit_family 拆分为4个子函数（每个复杂度<10）
# ---------------------------------------------------------------------------


def _scan_store(asset_store) -> dict:
    """扫描资产Store，收集原始数据（tasks、lessons、键列表）"""
    raw = {
        "all_keys": [],
        "tasks": [],
        "lessons": [],
    }
    if hasattr(asset_store, 'list_keys'):
        raw["all_keys"] = asset_store.list_keys()
    for key in raw["all_keys"]:
        if key.startswith("task:"):
            data = asset_store.load(key)
            if data is not None:
                raw["tasks"].append(data)
        elif key.startswith("lesson:"):
            data = asset_store.load(key)
            if data is not None:
                raw["lessons"].append(data)
    return raw


def _compute_statistics(raw: dict) -> dict:
    """计算统计指标（成功/失败、任务数、错题本数）"""
    tasks = raw["tasks"]
    successful = 0
    failed = 0

    for task in tasks:
        if not isinstance(task, dict):
            failed += 1
            continue
        status = task.get("status", "")
        stage_results = task.get("stage_results", task.get("stages", []))
        all_completed = all(
            isinstance(s, dict) and s.get("status", "")
            in ("completed", "success")
            for s in stage_results
        )
        if status in ("completed", "success") or all_completed:
            successful += 1
        else:
            failed += 1

    return {
        "total_tasks": len(tasks),
        "successful_tasks": successful,
        "failed_tasks": failed,
        "total_lessons": len(raw["lessons"]),
    }


def _generate_report(stats: dict, tasks: list,
        lessons: list, budget=None) -> dict:
    """生成审计报告（发现和建议）"""
    total = stats["total_tasks"]
    successful = stats["successful_tasks"]
    failed = stats["failed_tasks"]
    report = {
        "status": "healthy",
        "findings": [],
        "recommendations": [],
        "statistics": dict(stats),
        # 顶层兼容字段（供测试直接读取）
        "total_tasks": total,
        "successful_tasks": successful,
        "failed_tasks": failed,
        "total_lessons": stats["total_lessons"],
    }

    if budget:
        report["statistics"]["monthly_budget"] = budget

    if total > 0:
        report["findings"].append(
            f"家族共执行{total}个任务，成功{successful}个，失败{failed}个")
    else:
        report["findings"].append("家族尚未执行任何任务")

    if stats["total_lessons"] > 0:
        report["findings"].append(
            f"错题本积累{stats['total_lessons']}条教训")

    if total > 20:
        report["recommendations"].append(
            "任务数量较多，建议考虑增加父辈Agent")

    if failed > successful * 0.3 and total >= 5:
        report["recommendations"].append(
            f"失败率较高（{failed}/{total}），建议进行SOP优化回顾")

    return report


def _log_audit_result(context: dict, report: dict, stats: dict) -> dict:
    """写入审计日志到context"""
    context["_audit_report"] = report
    context["_reason"] = (
        f"审计完成：共{stats['total_tasks']}个任务，"
        f"成功{stats['successful_tasks']}，失败{stats['failed_tasks']}，"
        f"错题本{stats['total_lessons']}条")
    return context


def check_ancestor_alive(context: dict) -> dict:
    """
    V3.2b: Dead Man's Watch — 检查祖辈是否存活。

    不依赖祖辈自我报告，直接读取 Store 中的活动记录。
    在 audit_family 中作为第一步调用。

    输入 context 键：
        _store: Store —— 资产 Store（读取祖先活动记录）
        _heartbeat_timeout_minutes: int —— 心跳超时分钟数（默认15）

    输出 context 键：
        _dead_mans_watch_report: dict —— 存活检查报告
            {
                "status": "HEALTHY" | "WARNING",
                "report": "描述文本",
                "last_heartbeat_minutes_ago": float | None,
                "last_design_minutes_ago": float | None,
            }
    """
    store = context.get("_store") or context.get("_asset_store")
    timeout_minutes = context.get("_heartbeat_timeout_minutes", 15)
    now = datetime.now()

    report_data = {
        "status": "HEALTHY",
        "report": "",
        "last_heartbeat_minutes_ago": None,
        "last_design_minutes_ago": None,
    }

    if store is None:
        report_data["status"] = "WARNING"
        report_data["report"] = "家族警告：无法读取 Store，Dead Man's Watch 无法执行。"
        context["_dead_mans_watch_report"] = report_data
        return context

    # 读取祖辈活动记录
    try:
        last_heartbeat = store.load("ancestor:last_heartbeat")
        last_task_design = store.load("ancestor:last_task_design_time")
    except Exception as e:
        logger.error("[DeadManWatch] 读取 Store 失败: %s", e)
        report_data["status"] = "WARNING"
        report_data["report"] = f"家族警告：读取祖先活动记录失败: {e}"
        context["_dead_mans_watch_report"] = report_data
        return context

    if last_heartbeat is None and last_task_design is None:
        report_data["status"] = "WARNING"
        report_data["report"] = "家族警告：无法读取祖辈活动记录，Store 可能故障。"
        context["_dead_mans_watch_report"] = report_data
        logger.warning("[DeadManWatch] %s", report_data["report"])
        return context

    # 计算空闲时间
    heartbeat_idle = None
    design_idle = None

    if last_heartbeat is not None:
        if isinstance(last_heartbeat, datetime):
            heartbeat_idle = (now - last_heartbeat).total_seconds() / 60
            report_data["last_heartbeat_minutes_ago"] = heartbeat_idle

    if last_task_design is not None:
        if isinstance(last_task_design, datetime):
            design_idle = (now - last_task_design).total_seconds() / 60
            report_data["last_design_minutes_ago"] = design_idle

    max_idle = max(
        heartbeat_idle if heartbeat_idle is not None else 0,
        design_idle if design_idle is not None else 0,
    )

    if max_idle > timeout_minutes:
        report_data["status"] = "WARNING"
        report_data["report"] = (
            f"家族警告：祖辈心跳超时，最近一次活动记录于 {max_idle:.0f} 分钟前。"
        )
        logger.warning("[DeadManWatch] %s", report_data["report"])
    else:
        hb_msg = f"心跳 {heartbeat_idle:.0f} 分钟前" if heartbeat_idle is not None else "心跳记录缺失"
        ds_msg = f"任务拆解 {design_idle:.0f} 分钟前" if design_idle is not None else "任务拆解记录缺失"
        report_data["report"] = f"家族运转正常。祖辈{hb_msg}，{ds_msg}。"
        logger.info("[DeadManWatch] %s", report_data["report"])

    context["_dead_mans_watch_report"] = report_data
    return context


def audit_family(context: dict) -> dict:
    """
    长老审计家族健康度。

    V3.2b: 增加 Dead Man's Watch（存活检查）作为第一步。

    输入 context 键：
        _asset_store: Store —— 资产Store
        _constitution_store: Store —— 宪法Store
        _store: Store —— 通用 Store（供 check_ancestor_alive 读取）

    输出 context 键：
        _audit_report: dict —— 审计报告（含 _dead_mans_watch_report）
    """

    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")

    if not asset_store:
        context["_audit_report"] = {"status": "error", "reason": "无资产Store"}
        return context

    # V3.2b: Dead Man's Watch — 第一步：检查祖辈是否存活
    context_with_store = dict(context)
    context_with_store["_store"] = asset_store  # check_ancestor_alive 读取 _store
    context_with_store = check_ancestor_alive(context_with_store)
    dead_mans_report = context_with_store.get("_dead_mans_watch_report", {})

    # 1. 扫描资产Store
    raw = _scan_store(asset_store)

    # 2. 计算统计指标
    stats = _compute_statistics(raw)

    # 3. 获取预算并生成审计报告
    budget = None
    if constitution_store:
        budget = constitution_store.load("const.budget_monthly")
    report = _generate_report(stats, raw["tasks"], raw["lessons"], budget)

    # V3.2b: 将 Dead Man's Watch 结果并入审计报告
    if dead_mans_report:
        report["dead_mans_watch"] = dead_mans_report
        if dead_mans_report.get("status") == "WARNING":
            report["status"] = "warning"
            report["findings"].append(dead_mans_report.get("report", ""))

    # 4. 写入审计日志
    return _log_audit_result(context, report, stats)


def create_elder(name: str = "elder", asset_store=None,
        constitution_store=None) -> Agent:
    """创建长老Agent"""
    skills = {
        "audit_family": Skill("audit_family", audit_family),
    }
    return Agent(
        name=name,
        store=asset_store,
        skills=skills,
        generation=0,
        max_spawn_generation=0,
    )


audit_family_skill = Skill("audit_family", audit_family)


# ---------------------------------------------------------------------------
# V2.0: 长老事件驱动——订阅 TASK_COMPLETED，自动执行审计
# ---------------------------------------------------------------------------

def _make_elder_event_handler(elder_agent: "Agent"):
    """创建长老的 TASK_COMPLETED 事件处理函数。"""
    def _on_task_completed(event):
        try:
            ctx = {
                "_asset_store": elder_agent.store,
                "_constitution_store": None,
                "_triggered_by_event": True,
                "_event_task_id": (
                    event.data.get("task_id", "") if event.data else ""),
            }
            audit_family(ctx)
            logger.info("自动审计完成（事件触发）: %s",
                ctx.get('_reason', '已完成'))
        except Exception as e:
            import warnings
            warnings.warn(
                f"[Elder] TASK_COMPLETED 自动审计失败（已忽略）: {e}")

    return _on_task_completed


def subscribe_elder_to_events(elder_agent: "Agent") -> bool:
    """让长老订阅 TASK_COMPLETED 事件。"""
    try:
        from core.event_bus import get_event_bus, EventType
        bus = get_event_bus()
        handler = _make_elder_event_handler(elder_agent)
        bus.subscribe(EventType.TASK_COMPLETED, handler)
        elder_agent._event_handler = handler
        return True
    except Exception as e:
        import warnings
        warnings.warn(f"[Elder] 事件订阅失败（已忽略）: {e}")
        return False
