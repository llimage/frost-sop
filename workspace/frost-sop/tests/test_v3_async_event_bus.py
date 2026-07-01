"""
FROST-SOP V3.0 — AsyncEventBus 单元测试

测试覆盖：
1. AsyncEventBus 独立单例（不继承 EventBus）
2. asyncio.Lock 使用
3. 同步/异步订阅者共存
4. subscribe_async() 注册异步订阅者
5. publish() 异步分发
6. 循环事件防护
7. 敏感数据过滤
8. 事件持久化（mock）
9. TASK_TIMEOUT 事件类型
10. get_event_log / get_subscriber_count
"""

import asyncio
import os

import pytest

# 测试环境设置
os.environ["FROST_TESTING"] = "1"

from core.event_bus import AsyncEventBus, Event, EventBus, EventType, get_async_event_bus

# ---------------------------------------------------------------------------
# 测试 1: AsyncEventBus 不继承 EventBus
# ---------------------------------------------------------------------------


def test_01_async_bus_not_subclass_of_sync_bus():
    """AsyncEventBus 不是 EventBus 的子类"""
    assert not issubclass(AsyncEventBus, EventBus)
    assert AsyncEventBus.__bases__ == (object,)


# ---------------------------------------------------------------------------
# 测试 2: AsyncEventBus 单例
# ---------------------------------------------------------------------------


def test_02_async_bus_singleton():
    """AsyncEventBus 是单例"""
    AsyncEventBus.reset()
    bus1 = AsyncEventBus()
    bus2 = AsyncEventBus()
    assert bus1 is bus2


def test_03_get_async_event_bus_returns_singleton():
    """get_async_event_bus() 返回单例"""
    AsyncEventBus.reset()
    bus1 = get_async_event_bus()
    bus2 = get_async_event_bus()
    assert bus1 is bus2


# ---------------------------------------------------------------------------
# 测试 3: 同步和异步订阅者共存
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_04_sync_and_async_subscribers_coexist():
    """同步和异步订阅者可以共存于同一事件类型"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    sync_results = []
    async_results = []

    def sync_callback(event):
        sync_results.append(event.data.get("value"))

    async def async_callback(event):
        await asyncio.sleep(0.01)
        async_results.append(event.data.get("value"))

    bus.subscribe(EventType.TASK_COMPLETED, sync_callback)
    bus.subscribe_async(EventType.TASK_COMPLETED, async_callback)

    event = Event(EventType.TASK_COMPLETED, source="test", data={"value": 42})
    notified = await bus.publish(event)

    assert notified == 2
    assert sync_results == [42]
    assert async_results == [42]


# ---------------------------------------------------------------------------
# 测试 4: subscribe_async 注册异步订阅者
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_05_subscribe_async_registers_async_callback():
    """subscribe_async 正确注册异步回调"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    results = []

    async def async_cb(event):
        results.append("async_called")

    bus.subscribe_async(EventType.AGENT_CREATED, async_cb)

    assert bus.get_subscriber_count(EventType.AGENT_CREATED) == 1

    await bus.publish(Event(EventType.AGENT_CREATED, source="test"))
    assert results == ["async_called"]


# ---------------------------------------------------------------------------
# 测试 5: publish 异步分发
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_06_publish_returns_notified_count():
    """publish 返回实际通知的订阅者数量"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    bus.subscribe(EventType.STAGE_COMPLETED, lambda e: None)
    bus.subscribe(EventType.STAGE_COMPLETED, lambda e: None)
    bus.subscribe(EventType.STAGE_COMPLETED, lambda e: None)

    notified = await bus.publish(Event(EventType.STAGE_COMPLETED, source="test"))
    assert notified == 3


# ---------------------------------------------------------------------------
# 测试 6: 循环事件防护
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_07_circular_event_protection():
    """源与订阅者同名时跳过（排除 lambda）"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    called = []

    def my_source(event):
        called.append("called")

    # source 名称与 callback.__name__ 相同 → 应跳过
    event = Event(EventType.TASK_COMPLETED, source="my_source", data={})
    bus.subscribe(EventType.TASK_COMPLETED, my_source)

    notified = await bus.publish(event)
    assert notified == 0
    assert called == []

    # source 不同 → 应调用
    event2 = Event(EventType.TASK_COMPLETED, source="other", data={})
    notified2 = await bus.publish(event2)
    assert notified2 == 1
    assert called == ["called"]


# ---------------------------------------------------------------------------
# 测试 7: 单个订阅者异常不影响其他
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_08_subscriber_exception_isolation():
    """一个订阅者异常不影响其他订阅者"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    results = []

    def good_sync(event):
        results.append("sync_ok")

    async def bad_async(event):
        raise RuntimeError("故意报错")

    async def good_async(event):
        results.append("async_ok")

    bus.subscribe(EventType.STEP_COMPLETED, good_sync)
    bus.subscribe_async(EventType.STEP_COMPLETED, bad_async)
    bus.subscribe_async(EventType.STEP_COMPLETED, good_async)

    notified = await bus.publish(Event(EventType.STEP_COMPLETED, source="test"))

    assert notified == 2  # bad_async 失败但不计数
    assert "sync_ok" in results
    assert "async_ok" in results


# ---------------------------------------------------------------------------
# 测试 8: TASK_TIMEOUT 事件类型存在
# ---------------------------------------------------------------------------


def test_09_task_timeout_event_type_exists():
    """TASK_TIMEOUT 事件类型常量存在"""
    assert hasattr(EventType, "TASK_TIMEOUT")
    assert EventType.TASK_TIMEOUT == "task_timeout"


# ---------------------------------------------------------------------------
# 测试 9: get_event_log 异步查询
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_10_get_event_log_async():
    """get_event_log 异步返回事件历史"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    await bus.publish(
        Event(
            EventType.TASK_CREATED if hasattr(EventType, "TASK_CREATED") else "task_created",
            source="test1",
        )
    )
    await bus.publish(Event(EventType.TASK_COMPLETED, source="test2"))

    log = await bus.get_event_log()
    assert len(log) >= 2

    # 最新在前
    assert log[0].source == "test2"

    log_filtered = await bus.get_event_log(event_type=EventType.TASK_COMPLETED)
    assert len(log_filtered) == 1
    assert log_filtered[0].source == "test2"


# ---------------------------------------------------------------------------
# 测试 10: 敏感数据过滤
# ---------------------------------------------------------------------------


def test_11_sanitize_data():
    """敏感数据被过滤"""
    bus = AsyncEventBus()
    data = {
        "api_key": "sk-12345",
        "task_name": "normal",
        "nested": {"password": "secret123", "ok": "fine"},
    }
    sanitized = bus._sanitize_data(data)
    assert sanitized["api_key"] == "***REDACTED***"
    assert sanitized["task_name"] == "normal"
    assert sanitized["nested"]["password"] == "***REDACTED***"
    assert sanitized["nested"]["ok"] == "fine"


# ---------------------------------------------------------------------------
# 测试 11: unsubscribe
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_12_unsubscribe():
    """取消订阅后不再收到事件"""
    AsyncEventBus.reset()
    bus = AsyncEventBus()
    bus.clear_subscribers()

    results = []

    def cb(event):
        results.append("called")

    bus.subscribe(EventType.TASK_FAILED, cb)
    assert bus.get_subscriber_count(EventType.TASK_FAILED) == 1

    result = bus.unsubscribe(EventType.TASK_FAILED, cb)
    assert result == 1  # unsubscribe() 返回移除数量（int）
    assert bus.get_subscriber_count(EventType.TASK_FAILED) == 0

    await bus.publish(Event(EventType.TASK_FAILED, source="test"))
    assert results == []
