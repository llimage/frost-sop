"""
FROST-SOP 交棒机制 Skill
PHILOSOPHY: 祖辈不是永恒的。交棒是家族自治的核心能力。
旧祖辈变长老，新祖辈继承宪法Store写入权。
"""

from core.skill import Skill


def propose_succession(context: dict) -> dict:
    """
    祖辈发起交棒提案。

    输入 context 键：
        _asset_store: Store —— 资产Store（读取历史数据）
        _succession_threshold: float（可选）—— 异常率阈值，默认 0.3

    输出 context 键：
        _succession_proposal: dict —— 交棒提案
    """

    asset_store = context.get("_asset_store")
    threshold = context.get("_succession_threshold", 0.3)

    if not asset_store:
        context["_succession_proposal"] = {"recommend": False, "reason": "无资产Store"}
        return context

    all_keys = asset_store.list_keys() if hasattr(asset_store, "list_keys") else []

    tasks = []
    for key in all_keys:
        if key.startswith("task:"):
            task_data = asset_store.load(key)
            if task_data is not None:
                tasks.append(task_data)

    if len(tasks) < 5:
        context["_succession_proposal"] = {
            "recommend": False,
            "reason": f"历史任务不足（{len(tasks)}<5）",
            "total_tasks_analyzed": len(tasks),
        }
        return context

    # 统计合规失败率
    recent_tasks = tasks[-20:]
    compliance_failures = 0
    total_stages = 0

    for task in recent_tasks:
        if isinstance(task, dict):
            # 兼容两种字段名：stage_results / stages
            stages = task.get("stage_results", task.get("stages", []))
            total_stages += len(stages)
            for stage in stages:
                if isinstance(stage, dict):
                    s_status = stage.get("status", "")
                    # 兼容两种状态值：failed / fail
                    if s_status in ("failed", "fail"):
                        output = stage.get("output", "")
                        if "合规" in output or "compliance" in output.lower():
                            compliance_failures += 1

    failure_rate = compliance_failures / max(total_stages, 1)

    context["_succession_proposal"] = {
        "recommend": failure_rate >= threshold,
        "reason": f"合规失败率 {failure_rate:.1%} {'超过' if failure_rate >= threshold else '未超过'}阈值 {threshold:.1%}",
        "failure_rate": failure_rate,
        "total_tasks_analyzed": len(recent_tasks),
        "suggested_successor": "需要创始人从长期表现优秀的父辈中指定"
        if failure_rate >= threshold
        else None,
    }
    context["_reason"] = (
        f"交棒评估完成：分析{len(recent_tasks)}个任务，合规失败率{failure_rate:.1%}"
    )
    return context


def execute_succession(context: dict) -> dict:
    """
    执行交棒。创始人批准后调用。

    输入 context 键：
        _old_ancestor: Agent —— 旧祖辈
        _new_ancestor: Agent —— 新祖辈（由父辈升级）
        _constitution_store: Store —— 宪法Store

    输出 context 键：
        _succession_result: dict
    """

    old_ancestor = context.get("_old_ancestor")
    new_ancestor = context.get("_new_ancestor")
    constitution_store = context.get("_constitution_store")

    if not old_ancestor or not new_ancestor or not constitution_store:
        context["_succession_result"] = {"success": False, "reason": "缺少必要参数"}
        return context

    new_ancestor.generation = 0
    new_ancestor.max_spawn_generation = 1
    new_ancestor.store = constitution_store
    old_ancestor.name = f"elder_{old_ancestor.name}"

    import datetime

    succession_record = {
        "event": "succession",
        "timestamp": str(datetime.datetime.now()),
        "old_ancestor": old_ancestor.name,
        "new_ancestor": new_ancestor.name,
    }
    constitution_store.save("family:succession_history", succession_record)

    context["_succession_result"] = {
        "success": True,
        "old_ancestor": old_ancestor.name,
        "new_ancestor": new_ancestor.name,
    }
    context["_reason"] = f"交棒完成: {old_ancestor.name} → {new_ancestor.name}"
    return context


propose_succession_skill = Skill("propose_succession", propose_succession)
execute_succession_skill = Skill("execute_succession", execute_succession)
