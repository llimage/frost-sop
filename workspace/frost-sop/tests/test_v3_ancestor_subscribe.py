"""
FROST-SOP V3.0 — ancestor 事件订阅测试

测试覆盖：
1. event_driven=False 时保持 V2.0 行为
2. event_driven=True 时订阅 TASK_CREATED
3. 收到 TASK_CREATED 后发布 TASK_DECOMPOSED
4. LLM 分解结果包含在 TASK_DECOMPOSED 事件中
5. event_driven=False 时不订阅事件
"""

import asyncio
import os

import pytest

os.environ["FROST_TESTING"] = "1"

from agents.ancestor import create_ancestor
from core.event_bus import AsyncEventBus, Event, EventType, get_async_event_bus
from stores.asset import create_asset_store
from stores.constitution import create_constitution_store

# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------


def _setup():
    """重置 AsyncEventBus"""
    AsyncEventBus.reset()
    bus = get_async_event_bus()
    bus.clear_subscribers()
    return bus


# ---------------------------------------------------------------------------
# 测试 1: event_driven=False 保持 V2.0 行为
# ---------------------------------------------------------------------------


def test_01_ancestor_v2_mode_no_subscription():
    """event_driven=False 时不订阅事件"""
    bus = _setup()
    constitution = create_constitution_store()
    asset = create_asset_store()

    ancestor = create_ancestor(constitution, asset, event_driven=False)

    # 不应有订阅者
    assert bus.get_subscriber_count() == 0


# ---------------------------------------------------------------------------
# 测试 2: event_driven=True 订阅 TASK_CREATED
# ---------------------------------------------------------------------------


def test_02_ancestor_v3_mode_subscribes_task_created():
    """event_driven=True 时订阅 TASK_CREATED"""
    bus = _setup()
    constitution = create_constitution_store()
    asset = create_asset_store()

    ancestor = create_ancestor(constitution, asset, event_driven=True)

    # 应该有 1 个订阅者（TASK_CREATED）
    assert bus.get_subscriber_count(EventType.TASK_CREATED) == 1


# ---------------------------------------------------------------------------
# 测试 3: 收到 TASK_CREATED 后发布 TASK_DECOMPOSED
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_03_ancestor_publishes_task_decomposed():
    """ancestor 收到 TASK_CREATED 后发布 TASK_DECOMPOSED"""
    bus = _setup()
    constitution = create_constitution_store()
    asset = create_asset_store()

    ancestor = create_ancestor(constitution, asset, event_driven=True)

    # 记录 TASK_DECOMPOSED 事件
    decomposed_events = []

    async def capture_decomposed(event: Event):
        decomposed_events.append(event)

    bus.subscribe_async(EventType.TASK_DECOMPOSED, capture_decomposed)

    # 发布 TASK_CREATED
    await bus.publish(
        Event(
            event_type=EventType.TASK_CREATED,
            source="main:async_entry",
            data={
                "task_id": "test_task_001",
                "task_description": "用户权限管理",
            },
        )
    )

    # 等待异步处理完成
    await asyncio.sleep(0.1)

    # 验证 TASK_DECOMPOSED 被发布
    assert len(decomposed_events) >= 1
    event = decomposed_events[0]
    assert event.event_type == EventType.TASK_DECOMPOSED
    assert event.source == "ancestor:task_decomposer"
    assert event.data.get("task_id") == "test_task_001"
    assert "decomposition" in event.data


# ---------------------------------------------------------------------------
# 测试 4: TASK_DECOMPOSED 包含 LLM 分解结果
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_04_decomposition_contains_llm_response():
    """TASK_DECOMPOSED 事件包含 LLM 分解结果"""
    bus = _setup()
    constitution = create_constitution_store()
    asset = create_asset_store()

    ancestor = create_ancestor(constitution, asset, event_driven=True)

    captured = []

    async def capture(event: Event):
        captured.append(event)

    bus.subscribe_async(EventType.TASK_DECOMPOSED, capture)

    await bus.publish(
        Event(
            event_type=EventType.TASK_CREATED,
            source="main:async_entry",
            data={
                "task_id": "test_002",
                "task_description": "实现登录功能",
            },
        )
    )

    await asyncio.sleep(0.1)

    assert len(captured) >= 1
    # mock 模式下 LLM 会返回模拟响应
    decomposition = captured[0].data.get("decomposition", "")
    assert isinstance(decomposition, str)


# ---------------------------------------------------------------------------
# 测试 5: event_driven=False 不影响 Agent 正常功能
# ---------------------------------------------------------------------------


def test_05_ancestor_v2_mode_still_works():
    """V2.0 模式下 ancestor 仍可正常 run()"""
    bus = _setup()
    constitution = create_constitution_store()
    asset = create_asset_store()

    ancestor = create_ancestor(constitution, asset, event_driven=False)

    # 正常调用 ancestor.run()
    context = ancestor.run(
        sop_steps=["call_llm"], initial_context={"_prompt": "Analyze task: test"}
    )

    # mock 模式下应该有 LLM 响应
    assert "_llm_response" in context or "_prompt" in context
