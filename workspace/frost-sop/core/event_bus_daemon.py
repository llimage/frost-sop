"""
FROST-SOP V7.2 — 事件总线守护线程

PHILOSOPHY: 事件总线必须是一个"活的系统"，不是被动调用的函数。
后台线程持续运行，从事件队列中取出事件，分发给所有订阅者。

这是阶段1的基础设施：让 EventBus 成为"神经系统"。
"""

import logging
import queue
import threading
import time
from typing import Any

from core.event_bus import EventBus, Event, EventType

logger = logging.getLogger(__name__)


class EventBusDaemon:
    """
    事件总线守护线程。

    设计原则：
    - 单例：全局只有一个事件总线守护线程
    - 线程安全：使用 queue.Queue 作为事件队列
    - 优雅退出：stop() 方法安全关闭
    - 故障隔离：单个订阅者失败不影响其他订阅者
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self._event_queue = queue.Queue()
        self._bus = EventBus()
        self._thread = None
        self._running = False
        self._stop_event = threading.Event()

        logger.info("[EventBusDaemon] 实例已创建")

    # ────────── 生命周期 ──────────

    def start(self):
        """启动守护线程。"""
        if self._running:
            logger.warning("[EventBusDaemon] 已经在运行中")
            return True

        self._running = True
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            name="EventBusDaemon",
            daemon=True,
        )
        self._thread.start()
        logger.info("[EventBusDaemon] 守护线程已启动")
        return True

    def stop(self, timeout: float = 5.0):
        """优雅关闭守护线程。"""
        if not self._running:
            return True

        self._running = False
        self._stop_event.set()

        # 放入一个 None 作为退出信号，确保队列阻塞的线程能退出
        self._event_queue.put(None)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            if self._thread.is_alive():
                logger.warning("[EventBusDaemon] 线程未能在 %s 秒内退出", timeout)
                return False

        logger.info("[EventBusDaemon] 已停止")
        return True

    # ────────── 事件发布 ──────────

    def publish(self, event: Event) -> bool:
        """
        将事件放入队列，由守护线程异步分发。

        Args:
            event: 要发布的事件

        Returns:
            True 如果放入队列成功
        """
        if not self._running:
            logger.warning("[EventBusDaemon] 未运行，事件被丢弃: %s", event.event_type)
            return False

        try:
            self._event_queue.put(event, block=False)
            return True
        except queue.Full:
            logger.error("[EventBusDaemon] 事件队列已满，事件丢弃")
            return False

    def publish_task_created(self, task_id: str, task_description: str) -> bool:
        """发布 TASK_CREATED 事件（便捷方法）"""
        return self.publish(
            Event(
                event_type=EventType.TASK_CREATED,
                source="user_input",
                data={
                    "task_id": task_id,
                    "task_description": task_description,
                },
            )
        )

    def publish_phase_completed(self, plan_id: str, phase_id: str, outputs: dict) -> bool:
        """发布 PHASE_COMPLETED 事件（阶段完成，触发下一阶段）"""
        return self.publish(
            Event(
                event_type=EventType.STAGE_COMPLETED,  # 复用现有事件类型
                source="footman:phase_executor",
                data={
                    "plan_id": plan_id,
                    "phase_id": phase_id,
                    "outputs": outputs,
                },
            )
        )

    # ────────── 主循环 ──────────

    def _run_loop(self):
        """守护线程主循环：持续从队列取事件，分发给订阅者。"""
        logger.info("[EventBusDaemon] 事件分发循环开始")

        while self._running and not self._stop_event.is_set():
            try:
                # 从队列取事件，阻塞等待，超时 1 秒检查停止信号
                event = self._event_queue.get(timeout=1.0)
            except queue.Empty:
                continue

            if event is None:
                # 退出信号
                logger.info("[EventBusDaemon] 收到退出信号")
                break

            # 分发事件
            self._dispatch_event(event)

        logger.info("[EventBusDaemon] 事件分发循环结束")

    def _dispatch_event(self, event: Event):
        """分发单个事件到所有订阅者。"""
        event_type = event.event_type

        # 获取订阅者（复用 EventBus 的同步订阅机制）
        # 注意：EventBus 的 _subscribers 是私有属性，但我们在同一个进程，可以直接访问
        subscribers = self._bus._subscribers.get(event_type, [])

        if not subscribers:
            logger.debug("[EventBusDaemon] 无订阅者: %s", event_type)
            return

        logger.info(
            "[EventBusDaemon] 分发事件 %s 到 %d 个订阅者",
            event_type, len(subscribers)
        )

        for callback in subscribers:
            try:
                callback(event)
            except Exception as e:
                logger.error(
                    "[EventBusDaemon] 订阅者处理失败 %s: %s",
                    event_type, e
                )
                # 故障隔离：一个订阅者失败不影响其他
                continue

    # ────────── 状态查询 ──────────

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    def get_queue_size(self) -> int:
        return self._event_queue.qsize()
