"""
FROST-SOP 自进化 Skill
PHILOSOPHY: 家族从经验中学习。
STR-002 是宪法第五条（瞬态生命周期）的延伸——
孙辈瞬态执行，父辈收割，祖辈从历史数据中提炼优化建议。
"""

from datetime import datetime

from core.skill import Skill


def load_task_history(context: dict) -> dict:
    """从资产 Store 加载历史任务记录"""
    asset_store = context.get("_asset_store")
    limit = context.get("_history_limit", 20)

    if not asset_store:
        context["_task_history"] = []
        context["_reason"] = "无资产 Store，无法加载历史"
        return context

    all_keys = asset_store.list_keys() if hasattr(asset_store, "list_keys") else []
    tasks = []
    for key in all_keys:
        if key.startswith("task:"):
            task_data = asset_store.load(key)
            if task_data is not None:
                tasks.append(task_data)

    # 按时间排序（如果有 timestamp 字段）
    tasks.sort(key=lambda t: t.get("timestamp", ""), reverse=True)
    tasks = tasks[:limit]

    context["_task_history"] = tasks
    context["_reason"] = f"加载 {len(tasks)} 条历史任务记录"
    return context


def analyze_trends(context: dict) -> dict:
    """分析历史任务数据中的趋势和模式"""
    tasks = context.get("_task_history", [])

    if not tasks:
        context["_trends"] = {"total": 0, "insights": []}
        context["_reason"] = "无历史数据可分析"
        return context

    total = len(tasks)
    successful = sum(
        1 for t in tasks if isinstance(t, dict) and t.get("status") in ("completed", "success")
    )
    failed = total - successful
    success_rate = successful / max(total, 1)

    sop_stats = {}
    error_types = {}

    for task in tasks:
        if isinstance(task, dict):
            sop_name = task.get("sop", "unknown")
            if sop_name not in sop_stats:
                sop_stats[sop_name] = {"total": 0, "success": 0, "failed": 0}
            sop_stats[sop_name]["total"] += 1
            if task.get("status") in ("completed", "success"):
                sop_stats[sop_name]["success"] += 1
            else:
                sop_stats[sop_name]["failed"] += 1

            # 兼容两种字段名：stages / stage_results
            stages = task.get("stages", task.get("stage_results", []))
            for stage in stages:
                if isinstance(stage, dict) and stage.get("status") in ("failed", "error"):
                    error_msg = stage.get("output", stage.get("error", "未知错误"))
                    error_type = "compliance" if "合规" in error_msg else "execution"
                    error_types[error_type] = error_types.get(error_type, 0) + 1

    insights = []

    # 洞察1：成功率
    if success_rate >= 0.8:
        insights.append(f"家族整体成功率 {success_rate:.0%}，运行状态良好")
    elif success_rate >= 0.5:
        insights.append(f"家族成功率 {success_rate:.0%}，有优化空间")
    else:
        insights.append(f"家族成功率 {success_rate:.0%}，需要重点关注")

    # 洞察2：哪个 SOP 失败率最高
    for sop_name, stats in sop_stats.items():
        if stats["failed"] > 0:
            sop_failure_rate = stats["failed"] / max(stats["total"], 1)
            if sop_failure_rate >= 0.3:
                insights.append(
                    f"SOP '{sop_name}' 失败率 {sop_failure_rate:.0%}（{stats['failed']}/{stats['total']}），建议优化"
                )

    # 洞察3：主要错误类型
    if error_types:
        main_error = max(error_types, key=error_types.get)
        insights.append(f"主要错误类型：{main_error}（{error_types[main_error]} 次）")

    context["_trends"] = {
        "total": total,
        "successful": successful,
        "failed": failed,
        "success_rate": success_rate,
        "sop_stats": sop_stats,
        "error_types": error_types,
        "insights": insights,
    }
    context["_reason"] = (
        f"分析 {total} 条任务，成功率 {success_rate:.0%}，生成 {len(insights)} 条洞察"
    )
    return context


def generate_suggestions(context: dict) -> dict:
    """基于趋势分析生成 SOP 优化建议"""
    trends = context.get("_trends", {})
    task_history = context.get("_task_history", [])

    if not trends or trends.get("total", 0) == 0:
        context["_suggestions"] = []
        context["_reason"] = "无趋势数据，无法生成建议"
        return context

    suggestions = []

    # 建议1：基于 SOP 失败率
    sop_stats = trends.get("sop_stats", {})
    for sop_name, stats in sop_stats.items():
        if stats["failed"] > 0:
            sop_failure_rate = stats["failed"] / max(stats["total"], 1)
            if sop_failure_rate >= 0.5:
                suggestions.append(
                    {
                        "type": "sop_optimization",
                        "target": sop_name,
                        "reason": f"失败率 {sop_failure_rate:.0%}（{stats['failed']}/{stats['total']}），建议重新设计 SOP 阶段",
                        "priority": "high" if sop_failure_rate >= 0.7 else "medium",
                    }
                )
            elif sop_failure_rate >= 0.3:
                suggestions.append(
                    {
                        "type": "sop_review",
                        "target": sop_name,
                        "reason": f"失败率 {sop_failure_rate:.0%}（{stats['failed']}/{stats['total']}），建议审查失败阶段",
                        "priority": "low",
                    }
                )

    # 建议2：基于错误类型
    error_types = trends.get("error_types", {})
    if error_types.get("compliance", 0) >= 2:
        suggestions.append(
            {
                "type": "constitution_review",
                "target": "compliance_rules",
                "reason": f"合规错误 {error_types['compliance']} 次，建议审查合规规则是否过严",
                "priority": "medium",
            }
        )

    # 建议3：基于成功率
    if trends.get("success_rate", 1.0) < 0.5:
        suggestions.append(
            {
                "type": "urgent_review",
                "target": "family_health",
                "reason": f"整体成功率 {trends['success_rate']:.0%}，建议创始人介入审查",
                "priority": "high",
            }
        )

    if not suggestions:
        suggestions.append(
            {
                "type": "no_action",
                "target": "family_health",
                "reason": "家族运行状态良好，暂无优化建议",
                "priority": "low",
            }
        )

    context["_suggestions"] = suggestions
    context["_reason"] = f"生成 {len(suggestions)} 条优化建议"
    return context


def present_for_approval(context: dict) -> dict:
    """将优化建议呈现给创始人确认"""
    suggestions = context.get("_suggestions", [])
    trends = context.get("_trends", {})

    report_lines = ["# 家族自进化报告", ""]
    report_lines.append("## 数据概览")
    report_lines.append(f"- 分析任务数：{trends.get('total', 0)}")
    report_lines.append(f"- 成功率：{trends.get('success_rate', 0):.0%}")
    report_lines.append(f"- 成功：{trends.get('successful', 0)}，失败：{trends.get('failed', 0)}")
    report_lines.append("")

    if trends.get("insights"):
        report_lines.append("## 趋势洞察")
        for insight in trends["insights"]:
            report_lines.append(f"- {insight}")
        report_lines.append("")

    report_lines.append("## 优化建议")
    for i, s in enumerate(suggestions, 1):
        report_lines.append(f"### 建议 {i}：{s['type']}（优先级：{s['priority']}）")
        report_lines.append(f"- 目标：{s['target']}")
        report_lines.append(f"- 原因：{s['reason']}")
        report_lines.append("")

    report_lines.append("## 创始人决策")
    report_lines.append("请对以上建议逐条回复：批准/驳回/修改")

    report = "\n".join(report_lines)
    context["_approval_report"] = report
    context["_result"] = report
    context["_reason"] = "自进化报告已生成，等待创始人确认"
    return context


# 导出 Skill 实例
load_task_history_skill = Skill("load_task_history", load_task_history)
analyze_trends_skill = Skill("analyze_trends", analyze_trends)
generate_suggestions_skill = Skill("generate_suggestions", generate_suggestions)
present_for_approval_skill = Skill("present_for_approval", present_for_approval)


# ================================================================
# V4.0 P1: 传承系统激活
# ================================================================


def update_skill_graph(context: dict) -> dict:
    """
    技能图增量进化：新Skill归档后自动调用。
    输入 context 键：
        _new_skill_id: str —— 新归档的 Skill ID
        _skill_graph: object —— 技能图对象（可选）
    输出 context 键：
        _skill_graph_updated: bool
        _skill_graph_nodes: int
    """
    new_skill_id = context.get("_new_skill_id")
    if not new_skill_id:
        context["_skill_graph_updated"] = False
        context["_reason"] = "无新Skill ID，跳过技能图更新"
        return context

    try:
        # 尝试导入技能图（如果已存在）
        from core.skill_graph import SkillGraph

        sg = context.get("_skill_graph") or SkillGraph()

        # 添加节点
        sg.add_node(new_skill_id, metadata=context.get("_new_skill_metadata", {}))

        # 尝试添加边（基于 trigger_keywords 或 skill_type）
        related_skills = context.get("_related_skills", [])
        for related in related_skills:
            sg.add_edge(new_skill_id, related, relation="related")

        context["_skill_graph"] = sg
        context["_skill_graph_updated"] = True
        context["_skill_graph_nodes"] = len(sg.nodes) if hasattr(sg, "nodes") else 0
        context["_reason"] = f"技能图已更新：添加节点 {new_skill_id}"
    except ImportError:
        # core.skill_graph 尚未实现，记录但不报错
        context["_skill_graph_updated"] = False
        context["_reason"] = "core.skill_graph 尚未实现，跳过技能图更新"

    return context


def update_mistake_book(context: dict) -> dict:
    """
    错题本自动更新：终端采集的失败记录自动归类。
    更新 `lesson:` 键的 `times_encountered` 字段。

    输入 context 键：
        _failure_record: dict —— 失败记录
        _asset_store: Store —— 资产 Store
    输出 context 键：
        _mistake_book_updated: bool
        _lesson_key: str
    """
    failure = context.get("_failure_record", {})
    asset_store = context.get("_asset_store")

    if not failure or not asset_store:
        context["_mistake_book_updated"] = False
        context["_reason"] = "无失败记录或资产Store，跳过错题本更新"
        return context

    # 提取失败类型
    error_msg = failure.get("error", failure.get("output", ""))
    error_type = "execution_error"
    if "合规" in error_msg:
        error_type = "compliance_error"
    elif "timeout" in error_msg.lower() or "超时" in error_msg:
        error_type = "timeout_error"
    elif "api" in error_msg.lower():
        error_type = "api_error"

    # 查找或创建错题本条目
    lesson_key = f"lesson:{error_type}"
    existing = asset_store.load(lesson_key) or {}

    # 更新 times_encountered
    times = existing.get("times_encountered", 0) + 1
    existing["times_encountered"] = times
    existing["last_encountered"] = datetime.now().isoformat()
    existing["error_type"] = error_type
    existing["last_error"] = error_msg[:200]

    asset_store.save(lesson_key, existing)

    context["_mistake_book_updated"] = True
    context["_lesson_key"] = lesson_key
    context["_reason"] = f"错题本已更新：{lesson_key}，累计 {times} 次"
    return context


def manage_sop_version(context: dict) -> dict:
    """
    SOP 模板版本管理：STR-002 优化建议自动创建 v2 版本。
    保留 v1 供回滚。

    输入 context 键：
        _sop_optimization: dict —— SOP 优化建议
        _asset_store: Store —— 资产 Store
    输出 context 键：
        _sop_version_created: bool
        _sop_version: str
    """
    sop_opt = context.get("_sop_optimization", {})
    asset_store = context.get("_asset_store")

    if not sop_opt or not asset_store:
        context["_sop_version_created"] = False
        context["_reason"] = "无SOP优化建议或资产Store，跳过版本管理"
        return context

    target = sop_opt.get("target", "")
    if not target:
        context["_sop_version_created"] = False
        context["_reason"] = "无目标SOP，跳过版本管理"
        return context

    # 读取原版 SOP
    original_key = f"sop_template:{target}:v1"
    original = asset_store.load(original_key)

    if not original:
        # v1 不存在，先创建 v1
        original = {
            "sop_id": target,
            "version": "v1",
            "content": sop_opt.get("original_content", ""),
            "created_at": datetime.now().isoformat(),
        }
        asset_store.save(original_key, original)

    # 创建 v2
    v2_key = f"sop_template:{target}:v2"
    v2_content = original.get("content", "") + "\n\n# 优化建议\n" + sop_opt.get("reason", "")

    v2_data = {
        "sop_id": target,
        "version": "v2",
        "content": v2_content,
        "created_at": datetime.now().isoformat(),
        "based_on": "v1",
        "optimization": sop_opt,
    }
    asset_store.save(v2_key, v2_data)

    context["_sop_version_created"] = True
    context["_sop_version"] = "v2"
    context["_reason"] = f"SOP 版本管理：{target} v2 已创建，v1 保留供回滚"
    return context


# 导出新增 Skill 实例
update_skill_graph_skill = Skill("update_skill_graph", update_skill_graph)
update_mistake_book_skill = Skill("update_mistake_book", update_mistake_book)
manage_sop_version_skill = Skill("manage_sop_version", manage_sop_version)
