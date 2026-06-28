"""
FROST-SOP V3.2b — 免疫系统 P0: 死人开关（Dead Man's Switch）

PHILOSOPHY:
死人开关监控家族整体活动。超过指定时间（默认30分钟）
无任何 EventBus 事件，则触发紧急告警。

INTEGRATION:
- 在 main.py 中初始化 DeadManSwitch
- 订阅关键 EventBus 事件来调用 on_any_event()
- 定时（每60秒）调用 check()，触发告警则打印到控制台
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Callable

logger = logging.getLogger(__name__)

# 默认超时（分钟）
DEFAULT_TIMEOUT_MINUTES = 30

# 告警级别
ALERT_LEVEL_CRITICAL = "CRITICAL"
ALERT_LEVEL_WARNING = "WARNING"


class DeadManSwitch:
    """
    死人开关：超过指定时间无任何 EventBus 事件则触发紧急告警。

    设计：
    - last_event_time: 最后一次事件时间
    - timeout_minutes: 超时阈值（分钟）
    - is_armed: 是否处于武装状态（False = 解除）
    - on_alert: 可选回调函数，触发告警时调用
    """

    def __init__(self,
                 timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
                 on_alert: Optional[Callable[[Dict], None]] = None):
        """
        初始化死人开关。

        Args:
            timeout_minutes: 超时阈值（分钟，默认30）
            on_alert: 告警回调函数 on_alert(alert_dict) -> None
        """
        self.timeout_minutes = timeout_minutes
        self.last_event_time = datetime.now()
        self.is_armed = True
        self.on_alert = on_alert
        self._alert_triggered = False  # 防止重复告警
        logger.info(
            "[DeadManSwitch] 初始化：超时阈值 %s 分钟",
            timeout_minutes
        )

    def on_any_event(self, event=None):
        """
        任何 EventBus 事件都会重置计时器。

        Args:
            event: Event 对象（可选，用于日志）
        """
        if not self.is_armed:
            return
        old_time = self.last_event_time
        self.last_event_time = datetime.now()
        self._alert_triggered = False  # 重置告警状态

        # 详细日志（可选）
        if event is not None:
            logger.debug(
                "[DeadManSwitch] 收到事件 %s，重置计时器（上次 %s 秒前）",
                event.event_type,
                int((self.last_event_time - old_time).total_seconds())
            )
        else:
            logger.debug("[DeadManSwitch] 收到事件，重置计时器")

    def check(self) -> Optional[Dict]:
        """
        检查是否超时。

        Returns:
            Dict: 告警信息（如果超时且未触发过）
            None: 未超时，或已触发过告警
        """
        if not self.is_armed:
            return None

        now = datetime.now()
        idle_seconds = (now - self.last_event_time).total_seconds()
        idle_minutes = idle_seconds / 60

        if idle_minutes > self.timeout_minutes:
            if not self._alert_triggered:
                # 首次触发告警
                alert = {
                    "alert_level": ALERT_LEVEL_CRITICAL,
                    "message": (
                        f"家族已超过 {self.timeout_minutes} 分钟无任何活动，"
                        f"请立即检查！空闲时间: {idle_minutes:.1f} 分钟"
                    ),
                    "last_event_time": self.last_event_time.isoformat(),
                    "idle_minutes": round(idle_minutes, 1),
                    "idle_seconds": int(idle_seconds),
                    "timeout_minutes": self.timeout_minutes,
                }
                self._alert_triggered = True

                # 调用回调（如果有）
                if self.on_alert:
                    try:
                        self.on_alert(alert)
                    except Exception as e:
                        logger.error("[DeadManSwitch] 告警回调异常: %s", e)

                logger.critical("[DeadManSwitch] %s", alert["message"])
                return alert
            else:
                # 已触发过告警，返回简化信息（可选）
                return None
        return None

    def reset_timer(self):
        """手动重置计时器（供测试或手动干预使用）"""
        self.last_event_time = datetime.now()
        self._alert_triggered = False
        logger.info("[DeadManSwitch] 计时器已手动重置")

    def disarm(self):
        """解除死人开关（停止监控）"""
        self.is_armed = False
        logger.warning("[DeadManSwitch] 死人开关已解除")

    def arm(self):
        """重新武装死人开关"""
        self.is_armed = True
        self.last_event_time = datetime.now()
        self._alert_triggered = False
        logger.info("[DeadManSwitch] 死人开关已重新武装")

    def get_status(self) -> Dict:
        """获取当前状态（供监控面板使用）"""
        now = datetime.now()
        idle_seconds = (now - self.last_event_time).total_seconds()
        return {
            "is_armed": self.is_armed,
            "timeout_minutes": self.timeout_minutes,
            "last_event_time": self.last_event_time.isoformat(),
            "idle_seconds": int(idle_seconds),
            "idle_minutes": round(idle_seconds / 60, 1),
            "alert_triggered": self._alert_triggered,
        }


# ============================================================
# 便捷函数: 创建 EventBus 订阅回调
# ============================================================

def create_event_subscribe_callback(dead_man_switch: DeadManSwitch):
    """
    创建 EventBus 订阅回调函数。

    Returns:
        callback(event): 可传递给 event_bus.subscribe() 的回调函数
    """
    def _callback(event):
        dead_man_switch.on_any_event(event)
    return _callback


def setup_dead_man_switch(timeout_minutes: int = DEFAULT_TIMEOUT_MINUTES,
                          event_bus=None,
                          verbose: bool = True):
    """
    一键设置死人开关：创建实例并订阅 EventBus 关键事件。

    Args:
        timeout_minutes: 超时阈值（分钟）
        event_bus: EventBus 实例（None = 自动获取）
        verbose: 是否打印设置信息

    Returns:
        DeadManSwitch 实例
    """
    from core.event_bus import get_event_bus, EventType

    dms = DeadManSwitch(timeout_minutes=timeout_minutes)

    if event_bus is None:
        event_bus = get_event_bus()

    # 订阅关键事件类型
    # 注意：EventType 可能不包含 AGENT_HEARTBEAT，使用字符串常量
    event_types_to_subscribe = [
        EventType.TASK_CREATED,
        EventType.TASK_DECOMPOSED,
        EventType.TASK_COMPLETED,
        EventType.TASK_FAILED,
        EventType.STAGE_STARTED,
        EventType.STAGE_COMPLETED,
        EventType.STAGE_FAILED,
        EventType.STEP_COMPLETED,
        EventType.AGENT_CREATED,
        EventType.AGENT_DESTROYED,
        "agent_heartbeat",  # V3.2b 心跳事件（字符串常量，非 EventType 成员）
    ]

    callback = create_event_subscribe_callback(dms)

    for event_type in event_types_to_subscribe:
        try:
            event_bus.subscribe(event_type, callback)
        except Exception as e:
            logger.warning(
                "[DeadManSwitch] 订阅事件 %s 失败: %s",
                event_type, e
            )

    if verbose:
        logger.info(
            "[DeadManSwitch] 已订阅 %s 种事件类型，超时阈值 %s 分钟",
            len(event_types_to_subscribe), timeout_minutes
        )

    return dms
