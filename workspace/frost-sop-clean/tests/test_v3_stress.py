"""
V3.0 缺失测试 3.4：压力测试

验证高并发/高负载场景下事件总线的稳定性。
"""

import asyncio
import time
import pytest
from core.event_bus import get_async_event_bus, Event, EventType, AsyncEventBus


@pytest.fixture(autouse=True)
def _reset_bus():
    yield
    AsyncEventBus.reset()


async def test_high_volume_event_publish():
    """
    验证：发布 1000 个事件，全部正确分发。
    """
    bus = get_async_event_bus()
    received = []

    async def collector(event: Event):
        received.append(event.data.get("seq"))

    bus.subscribe_async(EventType.TASK_CREATED, collector)

    # 发布 1000 个事件
    for i in range(1000):
        await bus.publish(
            Event(event_type=EventType.TASK_CREATED, source="stress", data={"seq": i})
        )

    # 等待所有回调完成
    await asyncio.sleep(0.5)

    assert len(received) == 1000, f"只收到 {len(received)}/1000 个事件"
    # 验证序号完整
    assert sorted(received) == list(range(1000))


async def test_concurrent_event_publish():
    """
    验证：10 个并发任务同时发布事件，无数据竞争。
    """
    bus = get_async_event_bus()
    logs = []

    async def publisher(task_id: int):
        for i in range(50):
            await bus.publish(
                Event(
                    event_type=EventType.TASK_CREATED,
                    source=f"task-{task_id}",
                    data={"task": task_id, "seq": i},
                )
            )
            logs.append(("pub", task_id, i))

    async def collector(event: Event):
        logs.append(("recv", event.data.get("task"), event.data.get("seq")))

    bus.subscribe_async(EventType.TASK_CREATED, collector)

    # 10 个并发发布者
    await asyncio.gather(*[publisher(i) for i in range(10)])

    await asyncio.sleep(0.5)

    # 验证：收到了 10*50 = 500 个事件
    recv_logs = [l for l in logs if l[0] == "recv"]
    assert len(recv_logs) == 500, f"只收到 {len(recv_logs)}/500 个事件"


async def test_many_subscribers_performance():
    """
    验证：注册 50 个订阅者，发布 1 个事件，分发时间 < 1 秒。
    """
    bus = get_async_event_bus()
    call_count = 0

    async def dummy(event: Event):
        nonlocal call_count
        call_count += 1

    # 注册 50 个订阅者
    for i in range(50):
        await asyncio.sleep(0)  # 让出控制权，防止测试超时
        bus.subscribe_async(EventType.TASK_CREATED, lambda e, idx=i: dummy(e))

    # 发布 1 个事件，计时
    start = time.monotonic()
    await bus.publish(
        Event(event_type=EventType.TASK_CREATED, source="stress", data={})
    )
    # 等待所有回调完成
    await asyncio.sleep(0.3)
    elapsed = time.monotonic() - start

    assert call_count == 50, f"只有 {call_count}/50 个订阅者被调用"
    assert elapsed < 1.0, f"分发太慢: {elapsed:.2f}s (预期 < 1s)"


async def test_event_log_no_missing():
    """
    验证：高并发下 event_log 表记录完整（无丢失）。
    """
    bus = get_async_event_bus()
    count = 100

    for i in range(count):
        await bus.publish(
            Event(event_type=EventType.TASK_CREATED, source="stress", data={"seq": i})
        )

    await asyncio.sleep(1.0)

    # 验证 event_log 中有 count 条记录（提高 limit）
    log = await bus.get_event_log(limit=count)
    assert len(log) == count, f"event_log 只有 {len(log)}/{count} 条记录"


async def test_bus_still_responsive_after_stress():
    """
    验证：压力测试后，事件总线仍然正常响应。
    """
    bus = get_async_event_bus()
    received = []

    async def collector(event: Event):
        received.append(event.data.get("check"))

    bus.subscribe_async(EventType.TASK_CREATED, collector)

    # 先压力测试：发布 500 个事件
    for i in range(500):
        await bus.publish(
            Event(event_type=EventType.TASK_CREATED, source="stress", data={"seq": i})
        )
    await asyncio.sleep(0.3)

    # 再发一个"健康检查"事件
    await bus.publish(
        Event(
            event_type=EventType.TASK_CREATED,
            source="health_check",
            data={"check": "alive"},
        )
    )
    await asyncio.sleep(0.1)

    assert "alive" in received, "压力测试后事件总线无响应"
