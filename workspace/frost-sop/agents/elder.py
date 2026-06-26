"""
FROST-SOP 长老Agent
PHILOSOPHY: 长老是退休的祖辈。它保留独立审计权，
不参与任务执行，不干预决策。只审计，只报告。
长老是普通Agent，不是特权组件。

V2.0: 长老可订阅 TASK_COMPLETED 事件，自动执行 audit_family（fail-safe）。
"""

import threading
from core.agent import Agent
from core.skill import Skill


def audit_family(context: dict) -> dict:
    """
    长老审计家族健康度。

    输入 context 键：
        _asset_store: Store —— 资产Store
        _constitution_store: Store —— 宪法Store

    输出 context 键：
        _audit_report: dict —— 审计报告
    """

    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")

    if not asset_store:
        context["_audit_report"] = {"status": "error", "reason": "无资产Store"}
        return context

    report = {
        "status": "healthy",
        "findings": [],
        "recommendations": [],
        "statistics": {},
    }

    # 获取所有键
    all_keys = asset_store.list_keys() if hasattr(asset_store, 'list_keys') else []

    # 统计任务记录
    tasks = []
    for key in all_keys:
        if key.startswith("task:"):
            task_data = asset_store.load(key)
            if task_data is not None:
                tasks.append(task_data)

    report["statistics"]["total_tasks"] = len(tasks)

    # 统计成功/失败
    successful = 0
    failed = 0
    for task in tasks:
        if isinstance(task, dict):
            status = task.get("status", "")
            # 兼容两种字段名：stage_results / stages
            stage_results = task.get("stage_results", task.get("stages", []))
            all_completed = True
            for s in stage_results:
                if isinstance(s, dict):
                    s_status = s.get("status", "")
                    # 兼容两种状态值：completed / success
                    if s_status not in ("completed", "success"):
                        all_completed = False
                        break
            # 兼容两种状态值
            if status in ("completed", "success"):
                successful += 1
            elif all_completed:
                successful += 1
            else:
                failed += 1

    report["statistics"]["successful_tasks"] = successful
    report["statistics"]["failed_tasks"] = failed

    # 检查宪法合规
    if constitution_store:
        budget = constitution_store.load("const.budget_monthly")
        if budget:
            report["statistics"]["monthly_budget"] = budget

    # 统计错题本
    lessons = []
    for key in all_keys:
        if key.startswith("lesson:"):
            lesson_data = asset_store.load(key)
            if lesson_data is not None:
                lessons.append(lesson_data)

    report["statistics"]["total_lessons"] = len(lessons)

    # 同步写入顶层字段（供测试读取）
    report["total_tasks"] = len(tasks)
    report["successful_tasks"] = successful
    report["failed_tasks"] = failed
    report["total_lessons"] = len(lessons)

    # 生成发现和建议
    if len(tasks) > 0:
        report["findings"].append(f"家族共执行{len(tasks)}个任务，成功{successful}个，失败{failed}个")
    else:
        report["findings"].append("家族尚未执行任何任务")

    if len(lessons) > 0:
        report["findings"].append(f"错题本积累{len(lessons)}条教训")

    if len(tasks) > 20:
        report["recommendations"].append("任务数量较多，建议考虑增加父辈Agent")

    if failed > successful * 0.3 and len(tasks) >= 5:
        report["recommendations"].append(f"失败率较高（{failed}/{len(tasks)}），建议进行SOP优化回顾")

    context["_audit_report"] = report
    context["_reason"] = f"审计完成：共{len(tasks)}个任务，成功{successful}，失败{failed}，错题本{len(lessons)}条"
    return context


def create_elder(name: str = "elder", asset_store=None, constitution_store=None) -> Agent:
    """创建长老Agent"""
    skills = {
        "audit_family": Skill("audit_family", audit_family),
    }
    return Agent(
        name=name,
        store=asset_store,
        skills=skills,
        generation=0,
        max_spawn_generation=0,  # 长老不能spawn任何Agent
    )


audit_family_skill = Skill("audit_family", audit_family)


# ---------------------------------------------------------------------------
# V2.0: 长老事件驱动——订阅 TASK_COMPLETED，自动执行审计
# ---------------------------------------------------------------------------

def _make_elder_event_handler(elder_agent: "Agent"):
    """
    创建长老的 TASK_COMPLETED 事件处理函数。
    
    当任务完成时，在后台守护线程中自动运行 audit_family。
    fail-safe：任何异常只打印警告，不影响主流程。
    """
    def _on_task_completed(event):
        try:
            ctx = {
                "_asset_store": elder_agent.store,
                "_constitution_store": None,
                "_triggered_by_event": True,
                "_event_task_id": event.data.get("task_id", "") if event.data else "",
            }
            audit_family(ctx)
            report = ctx.get("_audit_report", {})
            print(f"[Elder] 自动审计完成（事件触发）: {ctx.get('_reason', '已完成')}")
        except Exception as e:
            import warnings
            warnings.warn(f"[Elder] TASK_COMPLETED 自动审计失败（已忽略）: {e}")

    return _on_task_completed


def subscribe_elder_to_events(elder_agent: "Agent") -> bool:
    """
    让长老订阅 TASK_COMPLETED 事件。
    
    返回 True 表示订阅成功，False 表示不支持事件总线（fail-safe）。
    """
    try:
        from core.event_bus import get_event_bus, EventType
        bus = get_event_bus()
        handler = _make_elder_event_handler(elder_agent)
        bus.subscribe(EventType.TASK_COMPLETED, handler)
        elder_agent._event_handler = handler   # 保存引用，方便后续 unsubscribe
        return True
    except Exception as e:
        import warnings
        warnings.warn(f"[Elder] 事件订阅失败（已忽略）: {e}")
        return False
