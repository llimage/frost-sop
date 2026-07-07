"""
FROST-SOP V7.2 — 计划阶段调度器

专门负责计划阶段的定时触发和事件发布。
调度器只负责"时间到了"，不负责"执行什么"。
执行由府兵等订阅者通过事件总线处理。

PHILOSOPHY: 计划驱动，时间触发，事件分发。
"""

import logging
from core.scheduler import parse_cron
from core.event_bus_daemon import EventBusDaemon
from core.event_bus import Event, EventType

try:
    from apscheduler.schedulers.background import BackgroundScheduler

    HAS_APSCHEDULER = True
except ImportError:
    HAS_APSCHEDULER = False
    BackgroundScheduler = None

logger = logging.getLogger(__name__)


class PlanScheduler:
    """
    计划阶段调度器。

    使用 APScheduler BackgroundScheduler 进行定时触发，
    触发时发布事件到 EventBusDaemon，由订阅者执行。

    与 FrostScheduler 的区别：
    - FrostScheduler：直接执行 job（SOP 执行、狩猎执行）
    - PlanScheduler：只发布事件，不执行任何逻辑
    """

    def __init__(self, daemon: EventBusDaemon = None):
        self.daemon = daemon or EventBusDaemon()
        self._scheduler = None
        self._started = False

    # ────────── 生命周期 ──────────

    def start(self):
        """启动调度器（同时确保事件总线守护线程已启动）"""
        if self._started:
            return

        if not HAS_APSCHEDULER:
            logger.warning("[PlanScheduler] apscheduler 未安装，使用 No-Op 模式")
            self._started = True
            return

        self._scheduler = BackgroundScheduler(
            timezone="Asia/Shanghai",
            job_defaults={
                "misfire_grace_time": 300,
                "coalesce": True,
                "max_instances": 1,
            },
        )

        # 确保事件总线守护线程已启动
        if not self.daemon.is_running():
            self.daemon.start()

        self._scheduler.start()
        self._started = True
        logger.info("[PlanScheduler] 已启动")

    def stop(self):
        """停止调度器"""
        if self._scheduler and self._started:
            self._scheduler.shutdown()
            self._started = False
            logger.info("[PlanScheduler] 已停止")

    # ────────── 阶段调度 ──────────

    def schedule_phase(self, plan_id: str, phase_id: str, cron_expr: str) -> str:
        """
        为计划阶段注册定时触发。

        Args:
            plan_id: 计划ID
            phase_id: 阶段ID
            cron_expr: cron 表达式（如 "0 9 * * 1" = 每周一 9:00）

        Returns:
            job_id: 调度任务ID
        """
        if not self._started:
            raise RuntimeError("PlanScheduler 未启动，请先调用 start()")

        job_id = f"phase_{plan_id}_{phase_id}"

        def _job():
            self._publish_phase_trigger(plan_id, phase_id)

        self._scheduler.add_job(
            _job,
            "cron",
            id=job_id,
            **parse_cron(cron_expr),
        )
        logger.info(
            "[PlanScheduler] 阶段调度: plan=%s phase=%s @ %s",
            plan_id,
            phase_id,
            cron_expr,
        )
        return job_id

    def trigger_immediate(self, plan_id: str, phase_id: str) -> bool:
        """
        立即触发一个阶段（不等待定时器）。

        Args:
            plan_id: 计划ID
            phase_id: 阶段ID

        Returns:
            True 如果发布事件成功
        """
        return self._publish_phase_trigger(plan_id, phase_id, immediate=True)

    def _publish_phase_trigger(self, plan_id: str, phase_id: str, immediate: bool = False) -> bool:
        """发布阶段触发事件到事件总线"""
        event_data = {
            "job_type": "plan_phase",
            "plan_id": plan_id,
            "phase_id": phase_id,
        }
        if immediate:
            event_data["immediate"] = True

        return self.daemon.publish(
            Event(
                event_type=EventType.SCHEDULED_EXECUTED,
                source="plan_scheduler",
                data=event_data,
            )
        )

    # ────────── 状态查询 ──────────

    def is_running(self) -> bool:
        return self._started

    def list_jobs(self):
        """列出所有调度任务"""
        if not self._scheduler:
            return []
        return self._scheduler.get_jobs()
