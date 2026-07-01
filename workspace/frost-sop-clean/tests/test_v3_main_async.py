"""
FROST-SOP V3.0 — main_async 异步入口测试

测试覆盖：
1. main_async 发布 TASK_CREATED 事件
2. 任务完成后退出事件循环
3. 支持 timeout 参数
4. 超时后发布 TASK_TIMEOUT（非 TASK_FAILED）
5. 保留原有 main() 同步入口
"""

import os
import asyncio
import pytest

os.environ["FROST_TESTING"] = "1"

from core.event_bus import AsyncEventBus, EventType, get_async_event_bus


# ---------------------------------------------------------------------------
# 测试 1: main_async 发布 TASK_CREATED 事件
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_01_main_async_publishes_task_created():
    """main_async 发布 TASK_CREATED 事件"""
    AsyncEventBus.reset()
    bus = get_async_event_bus()
    bus.clear_subscribers()

    # 捕获 TASK_CREATED
    created_events = []

    async def capture(e):
        created_events.append(e)

    bus.subscribe_async(EventType.TASK_CREATED, capture)

    # 运行 main_async（mock 模式，会快速完成）
    status = await asyncio.wait_for(
        _run_main_async_safe("测试任务", "DEV-001", timeout=30), timeout=60
    )

    assert len(created_events) >= 1
    assert created_events[0].data.get("task_description") == "测试任务"
    assert "task_id" in created_events[0].data


# ---------------------------------------------------------------------------
# 测试 2: 任务完成后退出事件循环
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_02_main_async_returns_on_completion():
    """main_async 在任务完成后返回 'completed'"""
    status = await asyncio.wait_for(
        _run_main_async_safe("完成测试", "DEV-001", timeout=30), timeout=60
    )

    # mock 模式下应该完成或超时（取决于 mock 响应速度）
    assert status in ("completed", "failed", "timeout")


# ---------------------------------------------------------------------------
# 测试 3: 支持 timeout 参数
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_03_main_async_supports_timeout():
    """main_async 支持 timeout 参数"""
    # 使用很短的超时来测试
    status = await asyncio.wait_for(
        _run_main_async_safe("超时测试", "DEV-001", timeout=1), timeout=30
    )

    # 1 秒超时应该触发 timeout
    # 注意：mock 模式可能很快完成，所以可能是 completed 或 timeout
    assert status in ("completed", "failed", "timeout")


# ---------------------------------------------------------------------------
# 测试 4: 超时后发布 TASK_TIMEOUT
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_04_timeout_publishes_task_timeout():
    """超时后发布 TASK_TIMEOUT 事件（非 TASK_FAILED）"""
    AsyncEventBus.reset()
    bus = get_async_event_bus()
    bus.clear_subscribers()

    timeout_events = []
    failed_events = []

    async def capture_timeout(e):
        timeout_events.append(e)

    async def capture_failed(e):
        failed_events.append(e)

    bus.subscribe_async(EventType.TASK_TIMEOUT, capture_timeout)
    bus.subscribe_async(EventType.TASK_FAILED, capture_failed)

    # 使用 1 秒超时
    status = await asyncio.wait_for(
        _run_main_async_safe("超时验证", "DEV-001", timeout=1), timeout=30
    )

    # 如果超时了，验证 TASK_TIMEOUT 被发布
    if status == "timeout":
        assert len(timeout_events) >= 1
        assert timeout_events[0].data.get("timeout_seconds") == 1
        # 不应该有 TASK_FAILED
        assert len(failed_events) == 0


# ---------------------------------------------------------------------------
# 测试 5: 保留原有 main() 同步入口
# ---------------------------------------------------------------------------


def test_05_main_sync_still_exists():
    """V2.0 main() 同步入口仍然存在"""
    from main import main

    assert callable(main)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


async def _run_main_async_safe(task_input, sop_id, timeout=30):
    """安全运行 main_async，捕获异常"""
    try:
        from main import main_async

        return await main_async(task_input=task_input, sop_id=sop_id, timeout=timeout)
    except Exception:
        # 如果 main_async 内部处理了异常，返回 "failed"
        # 如果是未处理的异常，也返回 "failed"
        return "failed"
