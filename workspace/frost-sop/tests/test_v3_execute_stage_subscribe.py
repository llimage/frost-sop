"""
FROST-SOP V3.0 — execute_stage 事件订阅测试

测试覆盖：
1. register_stage_executor 注册 STAGE_STARTED 订阅
2. 收到 STAGE_STARTED 后执行阶段
3. 发布 STAGE_COMPLETED 事件
4. STAGE_COMPLETED 包含正确的状态信息
5. 未注册时不订阅事件
6. 多个阶段顺序执行
"""

import os
import asyncio
import pytest

os.environ['FROST_TESTING'] = '1'

from core.event_bus import (
    AsyncEventBus, Event, EventType, get_async_event_bus
)
from skills.orchestration import register_stage_executor
from agents.parent import create_parent
from stores.asset import create_asset_store
from core.store import Store


def _setup():
    AsyncEventBus.reset()
    bus = get_async_event_bus()
    bus.clear_subscribers()
    return bus


# ---------------------------------------------------------------------------
# 测试 1: register_stage_executor 注册 STAGE_STARTED 订阅
# ---------------------------------------------------------------------------

def test_01_register_subscribes_to_stage_started():
    """register_stage_executor 注册后应有 STAGE_STARTED 订阅者"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_test", Store(), event_driven=False)

    result = register_stage_executor(parent, asset)

    assert result is True
    assert bus.get_subscriber_count(EventType.STAGE_STARTED) == 1


# ---------------------------------------------------------------------------
# 测试 2: 收到 STAGE_STARTED 后发布 STAGE_COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_02_stage_started_triggers_stage_completed():
    """STAGE_STARTED 事件触发 execute_stage 并发布 STAGE_COMPLETED"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_test", Store(), event_driven=False)
    register_stage_executor(parent, asset)

    completed_events = []

    async def capture(e): completed_events.append(e)
    bus.subscribe_async(EventType.STAGE_COMPLETED, capture)

    # 发布 STAGE_STARTED
    await bus.publish(Event(
        event_type=EventType.STAGE_STARTED,
        source="parent:stage_executor",
        data={
            "task_id": "test_v3_stage_002",
            "stage_name": "需求分析",
            "stage_order": 1,
            "total_stages": 3,
        },
    ))

    await asyncio.sleep(0.3)

    assert len(completed_events) >= 1
    event = completed_events[0]
    assert event.event_type == EventType.STAGE_COMPLETED
    assert event.source == "orchestration:stage_executor"
    assert event.data.get("stage_name") == "需求分析"
    assert event.data.get("stage_order") == 1


# ---------------------------------------------------------------------------
# 测试 3: STAGE_COMPLETED 包含状态信息
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_03_stage_completed_contains_status():
    """STAGE_COMPLETED 事件包含执行状态"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_test", Store(), event_driven=False)
    register_stage_executor(parent, asset)

    completed = []

    async def capture(e): completed.append(e)
    bus.subscribe_async(EventType.STAGE_COMPLETED, capture)

    await bus.publish(Event(
        event_type=EventType.STAGE_STARTED,
        source="parent:stage_executor",
        data={
            "task_id": "test_v3_stage_003",
            "stage_name": "技术设计",
            "stage_order": 2,
            "total_stages": 5,
        },
    ))

    await asyncio.sleep(0.3)

    assert len(completed) >= 1
    assert "status" in completed[0].data
    assert "task_id" in completed[0].data


# ---------------------------------------------------------------------------
# 测试 4: 未注册时不订阅
# ---------------------------------------------------------------------------

def test_04_no_subscription_without_register():
    """不调用 register_stage_executor 时没有 STAGE_STARTED 订阅"""
    bus = _setup()
    assert bus.get_subscriber_count(EventType.STAGE_STARTED) == 0


# ---------------------------------------------------------------------------
# 测试 5: 多个阶段顺序执行
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_05_multiple_stages_sequential():
    """多个 STAGE_STARTED 事件都能触发对应的 STAGE_COMPLETED"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_test", Store(), event_driven=False)
    register_stage_executor(parent, asset)

    completed = []

    async def capture(e): completed.append(e)
    bus.subscribe_async(EventType.STAGE_COMPLETED, capture)

    # 发布两个 STAGE_STARTED
    for i in range(1, 3):
        await bus.publish(Event(
            event_type=EventType.STAGE_STARTED,
            source="parent:stage_executor",
            data={
                "task_id": "test_v3_stage_005",
                "stage_name": f"阶段{i}",
                "stage_order": i,
                "total_stages": 2,
            },
        ))
        await asyncio.sleep(0.2)

    assert len(completed) >= 2
    assert completed[0].data.get("stage_order") == 1
    assert completed[1].data.get("stage_order") == 2


# ---------------------------------------------------------------------------
# 测试 6: register_stage_executor 返回 True
# ---------------------------------------------------------------------------

def test_06_register_returns_true():
    """register_stage_executor 成功注册返回 True"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_test", Store(), event_driven=False)

    result = register_stage_executor(parent, asset)
    assert result is True
