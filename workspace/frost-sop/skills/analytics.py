"""
V4.0 P0-b: 军师分析小组

包含6个单维度分析Skill + 1个整合Skill。

分析深度可配置（控制Token成本）：
- light: 只统计数据，不调用LLM
- standard: 调用LLM生成简报（max_tokens=300）
- deep: 调用LLM生成完整分析（max_tokens=1000）
"""

import logging
import os

logger = logging.getLogger(__name__)

# 分析深度配置（可通过环境变量覆盖）
ANALYSIS_DEPTH = os.environ.get("FROST_ANALYSIS_DEPTH", "light")


def _load_collected_data(store, source: str, metric_type: str = None) -> list[dict]:
    """
    辅助函数：从Store加载采集终端写入的数据。

    Args:
        store: Asset Store 实例
        source: 终端ID（如 "collector_task"）
        metric_type: 指标类型（可选，用于过滤）

    Returns:
        List[dict]: 采集数据列表
    """
    if store is None:
        logger.warning("[Analytics] Store is None, cannot load data")
        return []

    try:
        prefix = f"collector:{source}_"
        if metric_type:
            prefix = f"collector:{source}_{metric_type}_"

        keys = [k for k in store.list_keys() if k.startswith(prefix)]
        data = []
        for key in keys:
            item = store.load(key)
            if item:
                data.append(item)

        logger.debug(f"[Analytics] Loaded {len(data)} records from {source}")
        return data
    except Exception as e:
        logger.error(f"[Analytics] Load failed: {type(e).__name__}: {e}")
        return []


def _call_llm_for_briefing(prompt: str, max_tokens: int = 300) -> str:
    """
    辅助函数：调用LLM生成分析简报。

    Args:
        prompt: 分析提示词
        max_tokens: 最大输出Token数

    Returns:
        str: LLM生成的分析简报
    """
    try:
        # 尝试导入LLM调用函数
        from skills.llm import call_llm

        response = call_llm({
            "_prompt": prompt,
            "_max_tokens": max_tokens,
            "_llm_profile": "review",
        })
        return response.get("_llm_response", "")
    except Exception as e:
        logger.error(f"[Analytics] LLM call failed: {e}")
        return f"[LLM调用失败: {e}]"


def analyze_finance(context: dict) -> dict:
    """
    财务分析。深度可配置。

    light: 只统计本月Token消耗和预算使用率（不调用LLM）
    standard: 调用LLM生成成本趋势简报（max_tokens=300）
    deep: 调用LLM生成完整财务分析（max_tokens=1000）

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选，覆盖全局配置）

    输出 context 键：
        _analytics_finance: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 财务分析开始 (depth={depth})")

    # 加载成本数据
    cost_data = _load_collected_data(store, "collector_cost")

    # 统计
    total_cost = sum(
        item.get("value", 0) for item in cost_data if item.get("metric_type") == "llm_cost"
    )
    total_tokens = sum(
        item.get("value", 0) for item in cost_data if item.get("metric_type") == "llm_token_usage"
    )

    # 预算使用率
    budget_usage_rates = [
        item for item in cost_data if item.get("metric_type") == "budget_usage_rate"
    ]
    latest_budget_rate = budget_usage_rates[-1].get("value", 0) if budget_usage_rates else 0.0

    result = {
        "dimension": "finance",
        "depth": depth,
        "total_cost_usd": total_cost,
        "total_tokens": total_tokens,
        "budget_usage_rate": latest_budget_rate,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = (
            f"财务简报（轻量）：本月成本 ${total_cost:.4f}，Token消耗 {total_tokens:.0f}，预算使用率 {latest_budget_rate:.1%}"
        )
        logger.info("[Analytics] 财务分析完成（light，未调用LLM）")

    elif depth == "standard":
        prompt = f"""
        请生成财务分析简报（不超过300字）：
        - 本月总成本：${total_cost:.4f}
        - 总Token消耗：{total_tokens:.0f}
        - 预算使用率：{latest_budget_rate:.1%}

        请分析成本趋势，识别异常点，给出优化建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info("[Analytics] 财务分析完成（standard，已调用LLM）")

    elif depth == "deep":
        prompt = f"""
        请生成完整财务分析报告（不超过1000字）：
        - 本月总成本：${total_cost:.4f}
        - 总Token消耗：{total_tokens:.0f}
        - 预算使用率：{latest_budget_rate:.1%}
        - 详细成本数据：{cost_data[-10:]}  # 最近10条

        请分析：
        1. 成本趋势与预测
        2. 异常支出识别
        3. 预算优化建议
        4. Token消耗效率评估
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=1000)
        logger.info("[Analytics] 财务分析完成（deep，已调用LLM）")

    context["_analytics_finance"] = result
    return context


def analyze_skill(context: dict) -> dict:
    """
    Skill分析。深度可配置。

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _analytics_skill: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] Skill分析开始 (depth={depth})")

    # 加载Skill数据
    skill_data = _load_collected_data(store, "collector_skill")

    # 统计
    total_executions = len(skill_data)
    success_count = sum(1 for item in skill_data if "success" in item.get("metric_type", ""))
    failed_count = sum(1 for item in skill_data if "failed" in item.get("metric_type", ""))
    success_rate = success_count / total_executions if total_executions > 0 else 0.0

    result = {
        "dimension": "skill",
        "depth": depth,
        "total_executions": total_executions,
        "success_count": success_count,
        "failed_count": failed_count,
        "success_rate": success_rate,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = (
            f"Skill简报（轻量）：总执行 {total_executions} 次，成功率 {success_rate:.1%}"
        )
        logger.info("[Analytics] Skill分析完成（light，未调用LLM）")

    elif depth in ("standard", "deep"):
        prompt = f"""
        请生成Skill分析简报（不超过300字）：
        - 总执行次数：{total_executions}
        - 成功次数：{success_count}
        - 失败次数：{failed_count}
        - 成功率：{success_rate:.1%}

        请识别失败频繁的Skill，给出优化建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info(f"[Analytics] Skill分析完成（{depth}，已调用LLM）")

    context["_analytics_skill"] = result
    return context


def analyze_task(context: dict) -> dict:
    """
    任务分析。深度可配置。

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _analytics_task: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 任务分析开始 (depth={depth})")

    # 加载任务数据
    task_data = _load_collected_data(store, "collector_task")

    # 统计
    total_tasks = len(task_data)
    completed_count = sum(1 for item in task_data if "completed" in item.get("metric_type", ""))
    failed_count = sum(1 for item in task_data if "failed" in item.get("metric_type", ""))
    completion_rate = completed_count / total_tasks if total_tasks > 0 else 0.0

    # 平均耗时
    durations = [item.get("tags", {}).get("duration_seconds", 0) for item in task_data]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    result = {
        "dimension": "task",
        "depth": depth,
        "total_tasks": total_tasks,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "completion_rate": completion_rate,
        "avg_duration_seconds": avg_duration,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = (
            f"任务简报（轻量）：总任务 {total_tasks} 个，完成率 {completion_rate:.1%}，平均耗时 {avg_duration:.1f}s"
        )
        logger.info("[Analytics] 任务分析完成（light，未调用LLM）")

    elif depth in ("standard", "deep"):
        prompt = f"""
        请生成任务分析简报（不超过300字）：
        - 总任务数：{total_tasks}
        - 完成数：{completed_count}
        - 失败数：{failed_count}
        - 完成率：{completion_rate:.1%}
        - 平均耗时：{avg_duration:.1f}s

        请识别耗时过长的任务，给出优化建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info(f"[Analytics] 任务分析完成（{depth}，已调用LLM）")

    context["_analytics_task"] = result
    return context


def analyze_audit(context: dict) -> dict:
    """
    合规分析。深度可配置。

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _analytics_audit: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 合规分析开始 (depth={depth})")

    # 加载审计数据
    audit_data = _load_collected_data(store, "collector_audit")

    # 统计
    total_audits = len(audit_data)
    pass_count = sum(1 for item in audit_data if "pass" in item.get("metric_type", ""))
    fail_count = sum(1 for item in audit_data if "fail" in item.get("metric_type", ""))
    pass_rate = pass_count / total_audits if total_audits > 0 else 0.0

    result = {
        "dimension": "audit",
        "depth": depth,
        "total_audits": total_audits,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "pass_rate": pass_rate,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = f"合规简报（轻量）：总审计 {total_audits} 次，通过率 {pass_rate:.1%}"
        logger.info("[Analytics] 合规分析完成（light，未调用LLM）")

    elif depth in ("standard", "deep"):
        prompt = f"""
        请生成合规分析简报（不超过300字）：
        - 总审计次数：{total_audits}
        - 通过次数：{pass_count}
        - 失败次数：{fail_count}
        - 通过率：{pass_rate:.1%}

        请识别频繁失败的合规规则，给出修订建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info(f"[Analytics] 合规分析完成（{depth}，已调用LLM）")

    context["_analytics_audit"] = result
    return context


def analyze_heartbeat(context: dict) -> dict:
    """
    心跳分析。深度可配置。

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _analytics_heartbeat: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 心跳分析开始 (depth={depth})")

    # 加载心跳数据
    heartbeat_data = _load_collected_data(store, "collector_heartbeat")

    # 统计
    total_heartbeats = len(heartbeat_data)
    timeout_count = sum(1 for item in heartbeat_data if "timeout" in item.get("metric_type", ""))
    timeout_rate = timeout_count / total_heartbeats if total_heartbeats > 0 else 0.0

    result = {
        "dimension": "heartbeat",
        "depth": depth,
        "total_heartbeats": total_heartbeats,
        "timeout_count": timeout_count,
        "timeout_rate": timeout_rate,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = (
            f"心跳简报（轻量）：总心跳 {total_heartbeats} 次，超时率 {timeout_rate:.1%}"
        )
        logger.info("[Analytics] 心跳分析完成（light，未调用LLM）")

    elif depth in ("standard", "deep"):
        prompt = f"""
        请生成心跳分析简报（不超过300字）：
        - 总心跳次数：{total_heartbeats}
        - 超时次数：{timeout_count}
        - 超时率：{timeout_rate:.1%}

        请识别超时频繁的Agent，给出优化建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info(f"[Analytics] 心跳分析完成（{depth}，已调用LLM）")

    context["_analytics_heartbeat"] = result
    return context


def analyze_hunt(context: dict) -> dict:
    """
    狩猎分析。深度可配置。

    输入 context 键：
        _asset_store: Asset Store 引用
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _analytics_hunt: dict（分析结果）
    """
    store = context.get("_asset_store")
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 狩猎分析开始 (depth={depth})")

    # 加载狩猎数据
    hunt_data = _load_collected_data(store, "collector_hunt")

    # 统计
    total_hunts = len(hunt_data)
    found_count = sum(1 for item in hunt_data if "found" in item.get("metric_type", ""))
    absorbed_count = sum(1 for item in hunt_data if "absorbed" in item.get("metric_type", ""))
    rejected_count = sum(1 for item in hunt_data if "rejected" in item.get("metric_type", ""))
    absorption_rate = absorbed_count / found_count if found_count > 0 else 0.0

    result = {
        "dimension": "hunt",
        "depth": depth,
        "total_hunts": total_hunts,
        "found_count": found_count,
        "absorbed_count": absorbed_count,
        "rejected_count": rejected_count,
        "absorption_rate": absorption_rate,
        "briefing": "",
    }

    # 根据深度决定是否调用LLM
    if depth == "light":
        result["briefing"] = (
            f"狩猎简报（轻量）：总狩猎 {total_hunts} 次，吸收率 {absorption_rate:.1%}"
        )
        logger.info("[Analytics] 狩猎分析完成（light，未调用LLM）")

    elif depth in ("standard", "deep"):
        prompt = f"""
        请生成狩猎分析简报（不超过300字）：
        - 总狩猎次数：{total_hunts}
        - 找到次数：{found_count}
        - 吸收次数：{absorbed_count}
        - 拒绝次数：{rejected_count}
        - 吸收率：{absorption_rate:.1%}

        请评估狩猎效率，给出优化建议。
        """
        result["briefing"] = _call_llm_for_briefing(prompt, max_tokens=300)
        logger.info(f"[Analytics] 狩猎分析完成（{depth}，已调用LLM）")

    context["_analytics_hunt"] = result
    return context


def integrate_briefings(context: dict) -> dict:
    """
    整合Skill：汇总各维度简报，识别跨维度关联，生成创始人简报。

    输入 context 键：
        _analytics_finance: 财务分析结果
        _analytics_skill: Skill分析结果
        _analytics_task: 任务分析结果
        _analytics_audit: 合规分析结果
        _analytics_heartbeat: 心跳分析结果
        _analytics_hunt: 狩猎分析结果
        _analysis_depth: 分析深度（可选）

    输出 context 键：
        _integrated_briefing: dict（整合简报）
    """
    depth = context.get("_analysis_depth", ANALYSIS_DEPTH)

    logger.info(f"[Analytics] 整合简报生成开始 (depth={depth})")

    # 收集所有维度简报
    briefings = {
        "finance": context.get("_analytics_finance", {}).get("briefing", ""),
        "skill": context.get("_analytics_skill", {}).get("briefing", ""),
        "task": context.get("_analytics_task", {}).get("briefing", ""),
        "audit": context.get("_analytics_audit", {}).get("briefing", ""),
        "heartbeat": context.get("_analytics_heartbeat", {}).get("briefing", ""),
        "hunt": context.get("_analytics_hunt", {}).get("briefing", ""),
    }

    # 识别跨维度关联（简化版）
    correlations = []

    # 关联1：成本上升 + 任务失败率上升
    finance = context.get("_analytics_finance", {})
    task = context.get("_analytics_task", {})
    if finance.get("total_cost_usd", 0) > 10.0 and task.get("completion_rate", 1.0) < 0.8:
        correlations.append("⚠️ 成本上升且任务完成率下降，请检查Skill质量")

    # 关联2：心跳超时 + 任务失败
    heartbeat = context.get("_analytics_heartbeat", {})
    if heartbeat.get("timeout_rate", 0) > 0.1 and task.get("completion_rate", 1.0) < 0.9:
        correlations.append("⚠️ 心跳超时率较高，可能影响任务执行")

    # 生成整合简报
    if depth == "light":
        integrated_text = "=== 家族健康简报（轻量）===\n"
        for dimension, briefing in briefings.items():
            if briefing:
                integrated_text += f"\n## {dimension.upper()}\n{briefing}\n"

        if correlations:
            integrated_text += "\n=== 跨维度关联 ===\n"
            for corr in correlations:
                integrated_text += f"- {corr}\n"

    else:  # standard / deep
        # 调用LLM生成整合简报
        prompt = f"""
        请生成家族健康整合简报（不超过500字）。

        各维度简报：
        {briefings}

        跨维度关联：
        {correlations}

        请：
        1. 总结家族整体健康度
        2. 识别需要立即关注的问题
        3. 给出优先级建议
        """
        integrated_text = _call_llm_for_briefing(prompt, max_tokens=500)

    result = {
        "depth": depth,
        "briefings": briefings,
        "correlations": correlations,
        "integrated_text": integrated_text,
        "suggested_panels": [],  # 预留：驾驶舱动态面板建议
    }

    # 根据分析结果，建议增加面板
    if finance.get("budget_usage_rate", 0) > 0.8:
        result["suggested_panels"].append(
            {
                "type": "metric",
                "title": "预算使用率",
                "value": f"{finance['budget_usage_rate']:.1%}",
                "warning": True,
            }
        )

    if task.get("completion_rate", 1.0) < 0.9:
        result["suggested_panels"].append(
            {
                "type": "metric",
                "title": "任务完成率",
                "value": f"{task['completion_rate']:.1%}",
                "warning": True,
            }
        )

    logger.info("[Analytics] 整合简报生成完成")

    context["_integrated_briefing"] = result
    return context


# 导出所有分析函数
__all__ = [
    "analyze_finance",
    "analyze_skill",
    "analyze_task",
    "analyze_audit",
    "analyze_heartbeat",
    "analyze_hunt",
    "integrate_briefings",
]
