"""
FROST-SOP V2.0 — EventBus 事件总线

PHILOSOPHY:
事件总线是 Agent 家族的神经网络。
Agent 通过发布/订阅事件通信，而不是直接调用彼此。
这使得 Agent 之间高度解耦，便于扩展和观测。

V2.0 子阶段 4.1 + 4.2:
- Event 数据类
- EventBus 单例（subscribe / unsubscribe / publish / get_event_log）
- 事件类型常量定义
- 事件持久化到 event_log 表

设计原则：
- EventBus 是单例，全局共享
- 订阅者回调在发布线程中同步执行（保持可预测性）
- 持久化失败不影响事件分发（fail-safe）
- 所有公共 API 线程安全

架构说明：双轨制事件总线
─────────────────────────
EventBus（同步）和 AsyncEventBus（异步）是两个独立的单例。

使用场景：
- 同步代码（main.py、Streamlit UI、Agent.run）→ 使用 EventBus
- 异步代码（main_async.py、FastAPI 异步端点）→ 使用 AsyncEventBus

注意事项：
1. 两个总线互不干扰，事件不会自动跨总线传播
2. 如果同步代码订阅了 EventBus，异步代码发布到 AsyncEventBus，
   同步订阅者不会收到事件
3. 生产环境建议统一使用一种模式（推荐：同步 EventBus）

未来规划：V4.0 可能合并为一个统一总线（自动检测同步/异步上下文）
"""

import asyncio
import json
import logging
import threading
import uuid
from collections.abc import Callable
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ============================================================
# V2.0: 事件类型常量（子阶段 4.2）
# ============================================================


class EventType:
    """
    FROST-SOP V2.0 标准事件类型。

    命名规范：<层级>_<动词>
    - TASK_*:  任务生命周期事件
    - STAGE_*: SOP 阶段生命周期事件
    - STEP_*:  Agent 步骤事件
    - AGENT_*: Agent 自身生命周期事件
    """

    # 任务生命周期
    TASK_CREATED = "task_created"  # V3.0: 任务创建（main_async 发布）
    TASK_DECOMPOSED = "task_decomposed"  # 祖辈完成任务分解
    TASK_COMPLETED = "task_completed"  # 任务全部阶段完成
    TASK_FAILED = "task_failed"  # 任务失败（不可恢复）
    TASK_TIMEOUT = "task_timeout"  # 任务超时（V3.0: main_async 超时触发）

    # SOP 阶段生命周期
    STAGE_STARTED = "stage_started"  # 阶段开始执行
    STAGE_COMPLETED = "stage_completed"  # 阶段执行完成
    STAGE_FAILED = "stage_failed"  # 阶段执行失败

    # Agent 步骤
    STEP_COMPLETED = "step_completed"  # Agent 单步 Skill 执行完成

    # Agent 自身生命周期
    AGENT_CREATED = "agent_created"  # Agent 被创建
    AGENT_DESTROYED = "agent_destroyed"  # Agent 被销毁

    # ── V6.0: 闭环与运营事件 ──
    HUNT_COMPLETED = "hunt_completed"  # 狩猎完成
    BRIEFING_INTEGRATED = "briefing_integrated"  # 简报整合完成
    EVOLUTION_SUGGESTED = "evolution_suggested"  # 进化建议已生成
    SCHEDULED_EXECUTED = "scheduled_executed"  # 定时任务已执行
    DAILY_SNAPSHOT_COMPLETED = "daily_snapshot_completed"  # 每日快照完成
    WEEKLY_RETROSPECTIVE_COMPLETED = "weekly_retrospective_completed"  # 周度复盘完成

    # ── V7.4: 计划与编排事件（武器库驱动）──
    PLAN_GENERATED = "plan_generated"  # 计划生成完成（祖辈）
    PLAN_REFINED = "plan_refined"  # 计划细化完成（父辈）
    PLAN_REJECTED = "plan_rejected"  # 计划被拒绝（审计不通过）
    AUDIT_REQUESTED = "audit_requested"  # 请求审计计划
    AUDIT_COMPLETED = "audit_completed"  # 审计完成

    # ── V8.0: 项目生命周期事件 ──
    USER_INPUT = "user_input"  # 使用者输入（朝廷消息）
    DEVIATION_REPORTED = "deviation_reported"  # 执行偏差报告
    PROJECT_CREATED = "project_created"  # 项目创建
    PROJECT_COMPLETED = "project_completed"  # 项目完成
    PLAN_GENERATED = "plan_generated"  # 计划生成完成（祖辈）
    PLAN_REFINED = "plan_refined"  # 计划细化完成（父辈）
    PLAN_REJECTED = "plan_rejected"  # 计划被拒绝（审计不通过）
    AUDIT_REQUESTED = "audit_requested"  # 请求审计计划
    AUDIT_COMPLETED = "audit_completed"  # 审计完成
    PLAN_GENERATED = "plan_generated"  # 计划生成完成
    PLAN_REJECTED = "plan_rejected"  # 计划被拒绝（审计不通过）
    AUDIT_REQUESTED = "audit_requested"  # 请求审计计划
    AUDIT_COMPLETED = "audit_completed"  # 审计完成


# ============================================================
# V2.0: Event 数据类（子阶段 4.1）
# ============================================================


class Event:
    """
    V2.0 事件对象。

    Attributes:
        event_type: 事件类型（见 EventType 常量）
        source:     事件来源（发布方 Agent 的 name）
        data:       事件附带数据（任意字典）
        event_id:   唯一标识符（UUID hex）
        timestamp:  事件创建时间
    """

    def __init__(
        self,
        event_type: str,
        source: str = "unknown",
        data: dict[str, Any] | None = None,
        event_id: str = None,
        timestamp: datetime = None,
    ):
        self.event_type: str = event_type
        self.source: str = source
        self.data: dict[str, Any] = data or {}
        self.event_id: str = event_id or uuid.uuid4().hex
        self.timestamp: datetime = timestamp or datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典，供持久化使用"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "source": self.source,
            "data": self.data,
            "timestamp": self.timestamp.isoformat(),
        }

    def __repr__(self) -> str:
        return f"Event(type={self.event_type!r}, source={self.source!r}, id={self.event_id[:8]!r})"


# ============================================================
# V2.0: EventBus 单例（子阶段 4.1）
# ============================================================


class EventBus:
    """
    V2.0 全局事件总线（单例）。

    功能：
    - subscribe(event_type, callback): 注册订阅者
    - unsubscribe(event_type, callback): 取消订阅
    - publish(event): 同步分发事件给所有订阅者，并持久化
    - get_event_log(event_type, limit): 从内存缓冲获取事件历史
    - clear_subscribers(): 清空所有订阅（主要用于测试隔离）

    线程安全：所有订阅/发布操作通过锁保护。
    """

    _instance: Optional["EventBus"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "EventBus":
        """单例实现"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # 订阅者注册表：event_type -> [callback, ...]
        self._subscribers: dict[str, list[Callable]] = {}
        # 内存事件缓冲（最多保留最近 500 条，FIFO）
        self._event_log: list[Event] = []
        self._max_log_size: int = 500
        # 订阅/发布操作锁
        self._rw_lock: threading.Lock = threading.Lock()
        self._db_write_lock: threading.Lock = threading.Lock()
        self._initialized = True

    # ----------------------------------------------------------
    # 订阅管理
    # ----------------------------------------------------------

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """
        注册事件订阅者。

        Args:
            event_type: 要订阅的事件类型（使用 EventType 常量）
            callback: 回调函数，签名为 callback(event: Event) -> None
        """
        with self._rw_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> bool:
        """
        取消订阅。

        Args:
            event_type: 事件类型
            callback: 要移除的回调

        Returns:
            True 如果成功移除，False 如果未找到
        """
        with self._rw_lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                    return True
                except ValueError:
                    pass
        return False

    def clear_subscribers(self, event_type: str = None) -> None:
        """
        清空订阅者（用于测试隔离）。

        Args:
            event_type: 仅清空指定类型（None = 清空全部）
        """
        with self._rw_lock:
            if event_type is None:
                self._subscribers.clear()
            elif event_type in self._subscribers:
                del self._subscribers[event_type]

    # ----------------------------------------------------------
    # 事件发布
    # ----------------------------------------------------------

    def publish(self, event: Event) -> int:
        """
        发布事件：通知所有订阅者，并持久化到数据库。

        事件分发是同步的（在调用线程中执行），
        单个订阅者回调异常不影响其他订阅者。

        Args:
            event: 要发布的事件

        Returns:
            实际通知的订阅者数量
        """
        # 1. 记录到内存缓冲
        with self._rw_lock:
            self._event_log.append(event)
            if len(self._event_log) > self._max_log_size:
                # FIFO：删除最旧的
                self._event_log = self._event_log[-self._max_log_size :]
            # 快照订阅者列表（避免回调期间修改导致问题）
            callbacks = list(self._subscribers.get(event.event_type, []))

        # 2. 持久化到数据库（失败不影响分发）
        self._persist_event(event)

        # 3. 同步分发给所有订阅者
        notified = 0
        for callback in callbacks:
            # P1-8: 循环事件防护 — 源与订阅者同名时跳过（排除 lambda）
            if (
                hasattr(callback, "__name__")
                and callback.__name__ != "<lambda>"
                and callback.__name__ == event.source
            ):
                continue
            try:
                callback(event)
                notified += 1
            except Exception as e:
                logger.error(
                    "订阅者回调异常 (event=%s, callback=%s): %s", event.event_type, callback, e
                )

        return notified

    # ----------------------------------------------------------
    # 事件日志查询
    # ----------------------------------------------------------

    def get_event_log(self, event_type: str = None, limit: int = 50) -> list[Event]:
        """
        从内存缓冲获取事件历史（最新在前）。

        Args:
            event_type: 过滤的事件类型（None = 全部）
            limit: 最多返回条数

        Returns:
            事件列表（最新在前）
        """
        with self._rw_lock:
            log = list(self._event_log)

        if event_type:
            log = [e for e in log if e.event_type == event_type]

        # 最新在前
        log.reverse()
        return log[:limit]

    def get_subscriber_count(self, event_type: str = None) -> int:
        """
        获取订阅者数量（用于调试/测试）。

        Args:
            event_type: 指定类型（None = 全部订阅者总数）
        """
        with self._rw_lock:
            if event_type:
                return len(self._subscribers.get(event_type, []))
            return sum(len(v) for v in self._subscribers.values())

    # ----------------------------------------------------------
    # V2.2: event_log 清理
    # ----------------------------------------------------------

    def prune_event_log(self, days: int = 30) -> int:
        """
        删除指定天数之前的 event_log 记录，防止无限增长。

        Args:
            days: 保留最近多少天的记录（默认 30 天）

        Returns:
            删除的记录数
        """
        try:
            from core.db import get_db

            db = get_db()
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM event_log WHERE timestamp < datetime('now', '-' || ? || ' days')",
                (str(days),),
            )
            affected = cursor.rowcount
            conn.commit()
            if affected > 0:
                logger.info("清理了 %s 条 event_log 记录（> %s 天）", affected, days)
            return affected
        except Exception as e:
            logger.error("event_log 清理失败: %s", e)
            return 0

    # ----------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------

    # P1-7: 敏感数据键名列表
    _SENSITIVE_KEYS = {
        "api_key",
        "token",
        "password",
        "secret",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
    }

    def _sanitize_data(self, data: dict) -> dict:
        """递归过滤敏感键，替换为 '***REDACTED***'。"""
        if not isinstance(data, dict):
            return data
        sanitized: dict[Any, Any] = {}
        for k, v in data.items():
            if k.lower() in self._SENSITIVE_KEYS:
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_data(v)
            else:
                sanitized[k] = v
        return sanitized

    def _persist_event(self, event: Event) -> None:
        """
        将事件持久化到 event_log 表。
        失败时仅打印警告，不抛出异常。

        线程安全：使用 _db_write_lock 序列化 DB 写操作，
        防止多线程并发写入导致 "database is locked"。
        """
        import time

        max_retries = 3
        for attempt in range(max_retries):
            try:
                from core.db import get_db

                db = get_db()
                safe_data = (
                    self._sanitize_data(event.data) if isinstance(event.data, dict) else event.data
                )
                with self._db_write_lock:
                    db.insert(
                        "event_log",
                        {
                            "event_id": event.event_id,
                            "event_type": event.event_type,
                            "source": event.source,
                            "data": json.dumps(safe_data, ensure_ascii=False),
                            "timestamp": event.timestamp.isoformat(),
                        },
                    )
                return  # 成功，退出重试循环
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(0.001 * (attempt + 1))  # 1ms, 2ms 退避（DB层已有写锁保护）
                    continue
                # 持久化失败不影响事件分发
                logger.error("事件持久化失败 (%s): %s", event.event_type, e)

    @classmethod
    def reset(cls) -> None:
        """
        重置单例（主要用于测试隔离）。
        生产环境不应调用此方法。
        """
        with cls._lock:
            cls._instance = None


# ============================================================
# 模块级便捷函数
# ============================================================


def get_event_bus() -> EventBus:
    """
    获取 EventBus 全局单例。

    Returns:
        EventBus 实例
    """
    return EventBus()


# ============================================================
# V3.0: AsyncEventBus — 异步事件总线（独立实现，不继承 EventBus）
# ============================================================


class AsyncEventBus:
    """
    V3.0 异步事件总线。

    设计决策（Kimi Work 评审修正）：
    - 独立实现，不继承 EventBus（避免同步/异步语义混淆）
    - 使用 asyncio.Lock 替代 threading.Lock
    - 同步回调和异步回调可共存
    - 同步回调通过 asyncio.to_thread() 在线程池中执行
    - 持久化复用 EventBus._persist_event 的逻辑（同步 DB 写，不读共享状态）

    与 V2.0 EventBus 的关系：
    - EventBus（同步）继续用于 V2.0 兼容模式和 Streamlit UI
    - AsyncEventBus 用于 V3.0 事件驱动控制流（main_async 入口）
    - 两者各自独立单例，互不干扰
    """

    _instance: Optional["AsyncEventBus"] = None

    def __new__(cls) -> "AsyncEventBus":
        if cls._instance is None:
            instance = super().__new__(cls)
            instance._initialized = False
            cls._instance = instance
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        # 订阅者注册表：event_type -> [(callback, is_async), ...]
        self._subscribers: dict[str, list[tuple]] = {}
        # 内存事件缓冲
        self._event_log: list[Event] = []
        self._max_log_size: int = 500
        # asyncio.Lock（必须在事件循环内创建）
        self._lock: asyncio.Lock | None = None
        self._initialized = True

    def _get_lock(self) -> asyncio.Lock:
        """延迟创建 asyncio.Lock（确保在事件循环内）"""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    # ----------------------------------------------------------
    # 订阅管理
    # ----------------------------------------------------------

    def subscribe(self, event_type: str, callback: Callable) -> None:
        """
        注册同步订阅者。

        Args:
            event_type: 事件类型
            callback: 同步回调函数 callback(event: Event) -> None
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((callback, False))

    def subscribe_async(self, event_type: str, callback: Callable) -> None:
        """
        注册异步订阅者。

        Args:
            event_type: 事件类型
            callback: 异步回调函数 async callback(event: Event) -> None
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append((callback, True))

    def unsubscribe(self, event_type: str, callback: Callable, is_async: bool = None) -> int:
        """
        取消订阅。

        Args:
            event_type: 事件类型
            callback: 回调函数
            is_async: 是否异步回调（None=匹配所有，True=只匹配异步，False=只匹配同步）

        Returns:
            实际移除的订阅数量
        """
        removed = 0
        if event_type in self._subscribers:
            new_list = []
            for cb, async_flag in self._subscribers[event_type]:
                if cb == callback and (is_async is None or async_flag == is_async):
                    removed += 1
                else:
                    new_list.append((cb, async_flag))
            self._subscribers[event_type] = new_list
        return removed

    def clear_subscribers(self, event_type: str = None) -> None:
        """清空订阅者"""
        if event_type is None:
            self._subscribers.clear()
        elif event_type in self._subscribers:
            del self._subscribers[event_type]

    # ----------------------------------------------------------
    # 事件发布（异步）
    # ----------------------------------------------------------

    async def publish(self, event: Event) -> int:
        """
        异步发布事件：通知所有订阅者，并持久化。

        - 异步订阅者通过 await 调用
        - 同步订阅者通过 asyncio.to_thread() 在线程池中执行
        - 单个订阅者异常不影响其他订阅者

        Args:
            event: 要发布的事件

        Returns:
            实际通知的订阅者数量
        """
        lock = self._get_lock()

        # 1. 记录到内存缓冲 + 快照订阅者
        async with lock:
            self._event_log.append(event)
            if len(self._event_log) > self._max_log_size:
                self._event_log = self._event_log[-self._max_log_size :]
            callbacks = list(self._subscribers.get(event.event_type, []))

        # 2. 持久化（同步 DB 写，通过 to_thread 避免阻塞事件循环）
        try:
            await asyncio.to_thread(self._persist_event, event)
        except Exception as e:
            logger.error("[AsyncEventBus] 持久化失败 (%s): %s", event.event_type, e)

        # 3. 异步分发（并发执行）
        async def _run_one(cb, is_async, evt):
            """执行单个订阅者回调"""
            try:
                if is_async:
                    await cb(evt)
                else:
                    await asyncio.to_thread(cb, evt)
                return True
            except Exception as e:
                logger.error(
                    "[AsyncEventBus] 订阅者回调异常 (event=%s, callback=%s): %s",
                    evt.event_type,
                    cb,
                    e,
                )
                return False

        tasks = []
        for callback, is_async in callbacks:
            # 循环事件防护
            if (
                hasattr(callback, "__name__")
                and callback.__name__ != "<lambda>"
                and callback.__name__ == event.source
            ):
                continue
            tasks.append(_run_one(callback, is_async, event))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            # results 中包含 True（成功）/ False（失败）/ Exception（意外异常）
            notified = sum(1 for r in results if r is True)
            for r in results:
                if isinstance(r, Exception):
                    logger.error("[AsyncEventBus] gather 意外异常: %s", r)
        else:
            notified = 0

        return notified

    # ----------------------------------------------------------
    # 事件日志查询
    # ----------------------------------------------------------

    async def get_event_log(self, event_type: str = None, limit: int = 50) -> list[Event]:
        """从内存缓冲获取事件历史（最新在前）"""
        lock = self._get_lock()
        async with lock:
            log = list(self._event_log)

        if event_type:
            log = [e for e in log if e.event_type == event_type]

        log.reverse()
        return log[:limit]

    def get_subscriber_count(self, event_type: str = None) -> int:
        """获取订阅者数量"""
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(v) for v in self._subscribers.values())

    # ----------------------------------------------------------
    # 持久化（复用 V2.0 逻辑）
    # ----------------------------------------------------------

    _SENSITIVE_KEYS = {
        "api_key",
        "token",
        "password",
        "secret",
        "authorization",
        "access_token",
        "refresh_token",
        "private_key",
        "credential",
    }

    def _sanitize_data(self, data: dict) -> dict:
        """递归过滤敏感键"""
        if not isinstance(data, dict):
            return data
        sanitized: dict[Any, Any] = {}
        for k, v in data.items():
            if k.lower() in self._SENSITIVE_KEYS:
                sanitized[k] = "***REDACTED***"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize_data(v)
            else:
                sanitized[k] = v
        return sanitized

    def _persist_event(self, event: Event) -> None:
        """持久化到 event_log 表（同步，通过 to_thread 调用）"""
        try:
            from core.db import get_db

            db = get_db()
            safe_data = (
                self._sanitize_data(event.data) if isinstance(event.data, dict) else event.data
            )
            db.insert(
                "event_log",
                {
                    "event_id": event.event_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "data": json.dumps(safe_data, ensure_ascii=False),
                    "timestamp": event.timestamp.isoformat(),
                },
            )
        except Exception as e:
            logger.error("[AsyncEventBus] 持久化失败 (%s): %s", event.event_type, e)

    # ----------------------------------------------------------
    # 重置（测试用）
    # ----------------------------------------------------------

    @classmethod
    def reset(cls) -> None:
        """重置单例（测试隔离用）"""
        cls._instance = None


def get_async_event_bus() -> AsyncEventBus:
    """获取 AsyncEventBus 全局单例"""
    return AsyncEventBus()
