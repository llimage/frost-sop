"""
FROST-SOP V3.2b — 免疫系统 P0: 心跳监控

PHILOSOPHY:
父辈每30秒发送一次心跳事件，祖辈每60秒检查一次。
超过120秒无心跳的父辈标记为死亡（timeout_parents）。

事件类型: "agent_heartbeat"（不使用 EventType 常量，避免修改 core/）
"""

import logging
from datetime import datetime

from core.event_bus import Event, get_event_bus

logger = logging.getLogger(__name__)

# 心跳事件类型（字符串常量，不修改 core/event_bus.py）
EVENT_HEARTBEAT = "agent_heartbeat"

# 心跳超时阈值（秒）
HEARTBEAT_TIMEOUT_SECONDS = 120


# ============================================================
# Skill 1: send_heartbeat — 父辈每30秒调用
# ============================================================


def send_heartbeat(context: dict) -> dict:
    """
    发送心跳事件到 EventBus。
    父辈 Agent 每30秒调用一次。

    输入 context 键：
        _agent_id: str —— 发送方 Agent 的 ID（如 "parent_001"）
        _agent_role: str —— 发送方角色（"parent" / "elder" / "ancestor"）
        _task_id: str —— 当前任务 ID（可选）

    输出 context 键：
        _heartbeat_sent: bool —— 是否成功发送
        _heartbeat_time: str —— 发送时间（ISO格式）
    """
    agent_id = context.get("_agent_id", "unknown")
    agent_role = context.get("_agent_role", "unknown")
    task_id = context.get("_task_id", "")

    event_bus = get_event_bus()
    now = datetime.now()

    # 写入 Store（供 check_ancestor_alive / monitor_heartbeat 读取）
    store = context.get("_store")
    if store is not None:
        try:
            # key 格式: heartbeat:{agent_id}
            store_key = f"heartbeat:{agent_id}"
            store.save(
                store_key,
                {
                    "agent_id": agent_id,
                    "agent_role": agent_role,
                    "timestamp": now.isoformat(),
                },
            )
            # 如果是祖辈，额外写入 ancestor:last_heartbeat（供 check_ancestor_alive 读取）
            if agent_role == "ancestor":
                store.save("ancestor:last_heartbeat", now)
        except Exception as e:
            logger.warning("[Heartbeat] 写入 Store 失败: %s", e)

    event = Event(
        event_type=EVENT_HEARTBEAT,
        source=agent_id,
        data={
            "agent_id": agent_id,
            "agent_role": agent_role,
            "task_id": task_id,
            "timestamp": now.isoformat(),
        },
    )

    try:
        notified = event_bus.publish(event)
        logger.info(
            "[Heartbeat] %s (%s) 发送心跳，通知了 %s 个订阅者", agent_id, agent_role, notified
        )
        context["_heartbeat_sent"] = True
        context["_heartbeat_time"] = now.isoformat()
    except Exception as e:
        logger.error("[Heartbeat] %s 发送心跳失败: %s", agent_id, e)
        context["_heartbeat_sent"] = False
        context["_heartbeat_time"] = now.isoformat()

    return context


# ============================================================
# Skill 2: monitor_heartbeat — 祖辈每60秒调用
# ============================================================


def monitor_heartbeat(context: dict) -> dict:
    """
    检查所有活跃父辈的心跳记录，超过120秒无心跳的标记为死亡。

    输入 context 键：
        _store: Store —— 资产 Store（用于读取活跃父辈列表）
        _active_parents: list —— 活跃父辈 ID 列表（可选，优先级高）
        _heartbeat_timeout: int —— 超时阈值（秒，默认120）

    输出 context 键：
        _timeout_parents: list —— 超时父辈信息列表
            [{"agent_id": "...", "last_heartbeat": "...", "idle_seconds": 150}, ...]
        _monitor_result: dict —— 完整监控结果
        _dead_parents: list —— 被标记为死亡的父辈 ID 列表
    """
    store = context.get("_store")
    timeout = context.get("_heartbeat_timeout", HEARTBEAT_TIMEOUT_SECONDS)
    now = datetime.now()

    # 获取活跃父辈列表
    active_parents = context.get("_active_parents")
    if active_parents is None and store is not None:
        # 从 Store 读取（key 格式: "agent_status:{agent_id}"）
        # 为简化，使用 event_log 中的数据
        active_parents = _get_active_parents_from_store(store)
    if active_parents is None:
        active_parents = []

    event_bus = get_event_bus()

    # 从 EventBus 内存日志读取最近心跳
    # 获取最近 200 条心跳事件（按时间倒序，最新在前）
    recent_heartbeats = event_bus.get_event_log(event_type=EVENT_HEARTBEAT, limit=200)
    # get_event_log 返回最新在前，需要反转来得到时间顺序
    recent_heartbeats.reverse()

    # 构建每个 agent 的最后心跳时间
    last_heartbeat_map = {}  # agent_id -> datetime
    for event in recent_heartbeats:
        agent_id = event.data.get("agent_id", event.source)
        ts = event.timestamp
        if agent_id not in last_heartbeat_map:
            last_heartbeat_map[agent_id] = ts

    # 检查超时
    timeout_parents = []
    dead_parents = []

    for agent_id in active_parents:
        last_ts = last_heartbeat_map.get(agent_id)
        if last_ts is None:
            # 从未收到心跳，视为超时
            timeout_parents.append(
                {
                    "agent_id": agent_id,
                    "last_heartbeat": None,
                    "idle_seconds": None,
                    "status": "no_heartbeat_ever",
                }
            )
            dead_parents.append(agent_id)
        else:
            idle_seconds = (now - last_ts).total_seconds()
            if idle_seconds > timeout:
                timeout_parents.append(
                    {
                        "agent_id": agent_id,
                        "last_heartbeat": last_ts.isoformat(),
                        "idle_seconds": int(idle_seconds),
                        "status": "timeout",
                    }
                )
                dead_parents.append(agent_id)
                logger.warning(
                    "[Heartbeat] 父辈 %s 心跳超时 %s 秒（阈值 %s 秒）",
                    agent_id,
                    int(idle_seconds),
                    timeout,
                )

    monitor_result = {
        "checked_at": now.isoformat(),
        "timeout_seconds": timeout,
        "active_parents_count": len(active_parents),
        "timeout_count": len(timeout_parents),
        "timeout_parents": timeout_parents,
        "all_alive": len(timeout_parents) == 0,
    }

    context["_timeout_parents"] = timeout_parents
    context["_dead_parents"] = dead_parents
    context["_monitor_result"] = monitor_result

    logger.info(
        "[Heartbeat] 监控完成: %s 个活跃父辈，%s 个超时", len(active_parents), len(timeout_parents)
    )

    return context


def _get_active_parents_from_store(store) -> list:
    """
    从 Store 读取活跃父辈列表。
    实现: 扫描 "agent_status:*" 键，筛选 status=active 且 agent_type=parent 的条目。
    注意: 当前 Store 接口不支持前缀扫描，返回空列表（由调用方提供 _active_parents）。
    """
    # Store.list_keys() 返回所有键，前缀筛选
    try:
        keys = store.list_keys()
        parent_ids = []
        for key in keys:
            if key.startswith("agent_status:"):
                data = store.load(key)
                if isinstance(data, dict):
                    if data.get("status") == "active" and data.get("agent_type") == "parent":
                        parent_ids.append(data.get("agent_id", key.split(":")[-1]))
        return parent_ids
    except Exception as e:
        logger.error("[Heartbeat] 从 Store 读取活跃父辈失败: %s", e)
        return []


# ============================================================
# 便捷函数: 启动/停止心跳（供 Agent 调用）
# ============================================================


def start_heartbeat_loop(agent_id: str, agent_role: str, interval_seconds: int = 30):
    """
    启动心跳循环（在独立线程中运行）。
    注意: 这是一个阻塞函数，应在独立线程中调用。

    在 V3.2b 中，心跳由 main.py 通过定时器触发，
    此函数保留为未来异步模式做准备。
    """
    import time

    logger.info(
        "[Heartbeat] 启动心跳循环: %s (%s), 间隔 %ss", agent_id, agent_role, interval_seconds
    )
    while True:
        ctx = {
            "_agent_id": agent_id,
            "_agent_role": agent_role,
            "_task_id": "",
        }
        send_heartbeat(ctx)
        time.sleep(interval_seconds)


# ============================================================
# V4.0 P1: 呼吸监控
# ============================================================


def report_stage_status(context: dict) -> dict:
    """
    阶段状态上报：向 EventBus 发布 stage_status 事件。
    由父辈在每个 SOP 阶段完成时调用。

    输入 context 键：
        _stage_name: str —— 阶段名称
        _stage_status: str —— 状态（completed / failed / skipped）
        _task_id: str —— 当前任务 ID
        _agent_id: str —— 执行 Agent ID

    输出 context 键：
        _stage_status_reported: bool
    """
    event_bus = get_event_bus()
    stage_name = context.get("_stage_name", "unknown")
    stage_status = context.get("_stage_status", "unknown")
    task_id = context.get("_task_id", "unknown")
    agent_id = context.get("_agent_id", "unknown")
    now = datetime.now()

    event = Event(
        event_type="stage_status",
        source=agent_id,
        data={
            "stage_name": stage_name,
            "status": stage_status,
            "task_id": task_id,
            "agent_id": agent_id,
            "timestamp": now.isoformat(),
        },
    )

    try:
        notified = event_bus.publish(event)
        logger.info(
            "[StageStatus] %s: %s (%s), 通知了 %s 个订阅者",
            stage_name,
            stage_status,
            task_id,
            notified,
        )
        context["_stage_status_reported"] = True
    except Exception as e:
        logger.error("[StageStatus] 上报失败: %s", e)
        context["_stage_status_reported"] = False

    return context


def report_task_health(context: dict) -> dict:
    """
    任务健康上报：向 EventBus 发布 task_health 事件。
    由父辈定期检查任务健康状态时调用。

    输入 context 键：
        _task_id: str —— 任务 ID
        _health_score: float —— 健康分数 (0.0 - 1.0)
        _health_reason: str —— 健康状态原因
        _agent_id: str —— 检查 Agent ID

    输出 context 键：
        _task_health_reported: bool
        _health_level: str —— 健康等级 (healthy / warning / critical)
    """
    event_bus = get_event_bus()
    task_id = context.get("_task_id", "unknown")
    health_score = context.get("_health_score", 1.0)
    health_reason = context.get("_health_reason", "")
    agent_id = context.get("_agent_id", "unknown")
    now = datetime.now()

    # 确定健康等级
    if health_score >= 0.7:
        health_level = "healthy"
    elif health_score >= 0.4:
        health_level = "warning"
    else:
        health_level = "critical"

    event = Event(
        event_type="task_health",
        source=agent_id,
        data={
            "task_id": task_id,
            "health_score": health_score,
            "health_level": health_level,
            "reason": health_reason,
            "agent_id": agent_id,
            "timestamp": now.isoformat(),
        },
    )

    try:
        notified = event_bus.publish(event)
        logger.info(
            "[TaskHealth] %s: %s (%.2f), 通知了 %s 个订阅者",
            task_id,
            health_level,
            health_score,
            notified,
        )
        context["_task_health_reported"] = True
        context["_health_level"] = health_level
    except Exception as e:
        logger.error("[TaskHealth] 上报失败: %s", e)
        context["_task_health_reported"] = False

    return context


def check_consecutive_failures(context: dict) -> dict:
    """
    连续失败熔断：检查任务/阶段的连续失败次数，超过阈值触发熔断。

    输入 context 键：
        _task_id: str —— 任务 ID
        _failure_history: list —— 失败历史列表
        _circuit_breaker_threshold: int —— 熔断阈值（默认 3）

    输出 context 键：
        _circuit_breaker_triggered: bool
        _consecutive_failures: int
        _circuit_breaker_reason: str
    """
    task_id = context.get("_task_id", "unknown")
    failure_history = context.get("_failure_history", [])
    threshold = context.get("_circuit_breaker_threshold", 3)

    # 计算连续失败次数
    consecutive = 0
    for record in reversed(failure_history):
        if isinstance(record, dict) and record.get("status") in ("failed", "error"):
            consecutive += 1
        else:
            break

    context["_consecutive_failures"] = consecutive

    # 检查是否触发熔断
    if consecutive >= threshold:
        logger.warning("[CircuitBreaker] 任务 %s 连续失败 %s 次，触发熔断！", task_id, consecutive)
        context["_circuit_breaker_triggered"] = True
        context["_circuit_breaker_reason"] = f"连续失败 {consecutive} 次，超过阈值 {threshold}"

        # 发布熔断事件
        event_bus = get_event_bus()
        event = Event(
            event_type="circuit_breaker_triggered",
            source="watchdog",
            data={
                "task_id": task_id,
                "consecutive_failures": consecutive,
                "threshold": threshold,
                "timestamp": datetime.now().isoformat(),
            },
        )
        try:
            event_bus.publish(event)
        except Exception as e:
            logger.error("[CircuitBreaker] 发布熔断事件失败: %s", e)
    else:
        context["_circuit_breaker_triggered"] = False
        context["_circuit_breaker_reason"] = ""

    return context


# ============================================================
# Skill 注册（供 agents/parent.py 导入）
# ============================================================


def get_watchdog_skills():
    """
    返回 watchdog Skills 字典，供父辈 Agent 注册。
    """
    return {
        "send_heartbeat": send_heartbeat,
        "monitor_heartbeat": monitor_heartbeat,
        # V4.0 P1: 呼吸监控
        "report_stage_status": report_stage_status,
        "report_task_health": report_task_health,
        "check_consecutive_failures": check_consecutive_failures,
    }
