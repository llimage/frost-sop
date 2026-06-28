"""
V4.0 P0-a: 数据采集终端

所有终端统一数据格式：
{
    "timestamp": "2026-06-28T10:30:00",
    "source": "collector_task",
    "metric_type": "task_completed",
    "value": 1.0,
    "tags": {
        "task_id": "task_xxx",
        "sop_id": "DEV-001",
        "agent_id": "parent_yyy"
    }
}
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Store 键前缀
COLLECTOR_PREFIX = "collector:"


def _write_collected_data(store, source: str, metric_type: str, value: float, tags: Dict[str, Any]) -> bool:
    """
    辅助函数：将标准化数据写入Store。
    
    Args:
        store: Asset Store 实例
        source: 终端ID（如 "collector_task"）
        metric_type: 指标类型（如 "task_completed"）
        value: 指标值
        tags: 标签字典（如 {"task_id": "...", "sop_id": "..."}）
    
    Returns:
        bool: 是否写入成功
    """
    if store is None:
        logger.warning("[Collector] Store is None, cannot write data")
        return False
    
    try:
        data = {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "metric_type": metric_type,
            "value": float(value),
            "tags": tags or {}
        }
        
        # 生成唯一键
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        key = f"{COLLECTOR_PREFIX}{source}_{metric_type}_{timestamp}"
        
        store.store(key, data)
        logger.debug(f"[Collector] Written: {key}")
        return True
    except Exception as e:
        logger.error(f"[Collector] Write failed: {type(e).__name__}: {e}")
        return False


def collect_task_data(context: dict) -> dict:
    """
    采集任务完成/失败/耗时数据。
    触发方式：每次任务完成后。
    
    输入 context 键：
        _task_id: 任务ID
        _task_status: 任务状态（"completed" / "failed"）
        _task_start_time: 任务开始时间（ISO格式）
        _task_end_time: 任务结束时间（ISO格式）
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_task_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    task_id = context.get("_task_id", "unknown")
    task_status = context.get("_task_status", "unknown")
    task_start = context.get("_task_start_time")
    task_end = context.get("_task_end_time")
    
    # 计算耗时
    duration = 0.0
    if task_start and task_end:
        try:
            start_dt = datetime.fromisoformat(task_start)
            end_dt = datetime.fromisoformat(task_end)
            duration = (end_dt - start_dt).total_seconds()
        except Exception:
            pass
    
    # 写入任务完成/失败指标
    metric_type = f"task_{task_status}"
    tags = {
        "task_id": task_id,
        "status": task_status,
        "duration_seconds": duration
    }
    
    # 加入 SOP ID（如果有）
    sop_id = context.get("_sop_id")
    if sop_id:
        tags["sop_id"] = sop_id
    
    success = _write_collected_data(store, "collector_task", metric_type, 1.0, tags)
    
    result = {
        "source": "collector_task",
        "metric_type": metric_type,
        "written": success,
        "tags": tags
    }
    context["_collector_task_result"] = result
    return context


def collect_cost_data(context: dict) -> dict:
    """
    采集LLM调用Token消耗/成本/预算使用率数据。
    触发方式：每次LLM调用后。
    **P0-a中第一个实现。**
    
    输入 context 键：
        _llm_model: LLM模型名称
        _llm_input_tokens: 输入Token数
        _llm_output_tokens: 输出Token数
        _llm_cost: 成本（USD）
        _llm_budget_used: 已使用预算（USD）
        _llm_budget_total: 总预算（USD）
        _task_id: 任务ID
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_cost_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    model = context.get("_llm_model", "unknown")
    input_tokens = context.get("_llm_input_tokens", 0)
    output_tokens = context.get("_llm_output_tokens", 0)
    cost = context.get("_llm_cost", 0.0)
    budget_used = context.get("_llm_budget_used", 0.0)
    budget_total = context.get("_llm_budget_total", 0.0)
    task_id = context.get("_task_id", "unknown")
    
    # 计算预算使用率
    budget_usage_rate = 0.0
    if budget_total > 0:
        budget_usage_rate = budget_used / budget_total
    
    # 写入 Token 消耗指标
    tags_token = {
        "task_id": task_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens
    }
    success_token = _write_collected_data(store, "collector_cost", "llm_token_usage", 
                                         input_tokens + output_tokens, tags_token)
    
    # 写入成本指标
    tags_cost = {
        "task_id": task_id,
        "model": model,
        "cost_usd": cost
    }
    success_cost = _write_collected_data(store, "collector_cost", "llm_cost", cost, tags_cost)
    
    # 写入预算使用率指标
    tags_budget = {
        "task_id": task_id,
        "budget_used_usd": budget_used,
        "budget_total_usd": budget_total,
        "budget_usage_rate": budget_usage_rate
    }
    success_budget = _write_collected_data(store, "collector_cost", "budget_usage_rate", 
                                            budget_usage_rate, tags_budget)
    
    result = {
        "source": "collector_cost",
        "written": success_token and success_cost and success_budget,
        "tokens": input_tokens + output_tokens,
        "cost_usd": cost,
        "budget_usage_rate": budget_usage_rate
    }
    context["_collector_cost_result"] = result
    return context


def collect_skill_data(context: dict) -> dict:
    """
    采集Skill执行/成功/失败/耗时数据。
    触发方式：每次Skill执行后。
    
    输入 context 键：
        _skill_name: Skill名称
        _skill_status: Skill执行状态（"success" / "failed"）
        _skill_duration: Skill执行耗时（秒）
        _skill_error: 错误信息（如果有）
        _task_id: 任务ID
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_skill_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    skill_name = context.get("_skill_name", "unknown")
    skill_status = context.get("_skill_status", "unknown")
    skill_duration = context.get("_skill_duration", 0.0)
    skill_error = context.get("_skill_error", "")
    task_id = context.get("_task_id", "unknown")
    
    # 写入 Skill 执行指标
    metric_type = f"skill_{skill_status}"
    tags = {
        "task_id": task_id,
        "skill_name": skill_name,
        "status": skill_status,
        "duration_seconds": skill_duration
    }
    if skill_error:
        tags["error"] = skill_error
    
    success = _write_collected_data(store, "collector_skill", metric_type, 1.0, tags)
    
    result = {
        "source": "collector_skill",
        "metric_type": metric_type,
        "written": success,
        "skill_name": skill_name,
        "status": skill_status
    }
    context["_collector_skill_result"] = result
    return context


def collect_audit_data(context: dict) -> dict:
    """
    采集合规校验执行/通过/失败/规则触发数据。
    触发方式：每次合规校验后。
    
    输入 context 键：
        _audit_rule_id: 规则ID
        _audit_result: 审计结果（"pass" / "fail"）
        _audit_triggered: 是否触发规则（bool）
        _audit_message: 审计消息
        _task_id: 任务ID
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_audit_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    rule_id = context.get("_audit_rule_id", "unknown")
    audit_result = context.get("_audit_result", "unknown")
    triggered = context.get("_audit_triggered", False)
    audit_message = context.get("_audit_message", "")
    task_id = context.get("_task_id", "unknown")
    
    # 写入审计结果指标
    metric_type = f"audit_{audit_result}"
    tags = {
        "task_id": task_id,
        "rule_id": rule_id,
        "result": audit_result,
        "triggered": triggered,
        "message": audit_message[:100]  # 截断长消息
    }
    
    success = _write_collected_data(store, "collector_audit", metric_type, 1.0, tags)
    
    result = {
        "source": "collector_audit",
        "metric_type": metric_type,
        "written": success,
        "rule_id": rule_id,
        "result": audit_result
    }
    context["_collector_audit_result"] = result
    return context


def collect_heartbeat_data(context: dict) -> dict:
    """
    采集心跳发送/超时/空闲时间数据。
    预留接口，标记"待免疫系统P0完成后激活"。
    
    输入 context 键：
        _heartbeat_agent_id: Agent ID
        _heartbeat_status: 心跳状态（"sent" / "timeout"）
        _heartbeat_idle_seconds: 空闲时间（秒）
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_heartbeat_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    agent_id = context.get("_heartbeat_agent_id", "unknown")
    heartbeat_status = context.get("_heartbeat_status", "unknown")
    idle_seconds = context.get("_heartbeat_idle_seconds", 0.0)
    
    # 写入心跳指标
    metric_type = f"heartbeat_{heartbeat_status}"
    tags = {
        "agent_id": agent_id,
        "status": heartbeat_status,
        "idle_seconds": idle_seconds
    }
    
    success = _write_collected_data(store, "collector_heartbeat", metric_type, 1.0, tags)
    
    result = {
        "source": "collector_heartbeat",
        "metric_type": metric_type,
        "written": success,
        "agent_id": agent_id,
        "status": heartbeat_status
    }
    context["_collector_heartbeat_result"] = result
    return context


def collect_hunt_data(context: dict) -> dict:
    """
    采集狩猎完成/找到/吸收/拒绝数据。
    预留接口，标记"待斥候狩猎完成后激活"。
    
    输入 context 键：
        _hunt_skill_id: 狩猎目标Skill ID
        _hunt_result: 狩猎结果（"found" / "absorbed" / "rejected"）
        _hunt_score: 技能健康评分（0.0-1.0）
        _hunt_reason: 拒绝原因（如果有）
        _task_id: 任务ID
        _asset_store: Asset Store 引用
    
    输出 context 键：
        _collector_hunt_result: dict（写入结果）
    """
    store = context.get("_asset_store")
    skill_id = context.get("_hunt_skill_id", "unknown")
    hunt_result = context.get("_hunt_result", "unknown")
    hunt_score = context.get("_hunt_score", 0.0)
    hunt_reason = context.get("_hunt_reason", "")
    task_id = context.get("_task_id", "unknown")
    
    # 写入狩猎指标
    metric_type = f"hunt_{hunt_result}"
    tags = {
        "task_id": task_id,
        "skill_id": skill_id,
        "result": hunt_result,
        "score": hunt_score
    }
    if hunt_reason:
        tags["reason"] = hunt_reason
    
    success = _write_collected_data(store, "collector_hunt", metric_type, 1.0, tags)
    
    result = {
        "source": "collector_hunt",
        "metric_type": metric_type,
        "written": success,
        "skill_id": skill_id,
        "result": hunt_result
    }
    context["_collector_hunt_result"] = result
    return context


# 导出所有采集函数
__all__ = [
    "_write_collected_data",
    "collect_task_data",
    "collect_cost_data",
    "collect_skill_data",
    "collect_audit_data",
    "collect_heartbeat_data",
    "collect_hunt_data"
]
