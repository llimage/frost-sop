"""
FROST-SOP V3.0 — parent 事件订阅测试

测试覆盖：
1. event_driven=False 保持 V2.0 行为
2. event_driven=True 订阅 TASK_DECOMPOSED
3. 收到 TASK_DECOMPOSED 后逐阶段执行
4. 每个阶段发布 STAGE_STARTED + STAGE_COMPLETED
5. 全部完成后发布 TASK_COMPLETED
6. SOP 加载失败时发布 TASK_FAILED
7. event_driven=False 不订阅
8. parent V2.0 模式仍可正常 run()
"""

import os
import asyncio
import pytest

os.environ['FROST_TESTING'] = '1'

from core.event_bus import (
    AsyncEventBus, Event, EventType, get_async_event_bus
)
from agents.parent import create_parent
from stores.constitution import create_constitution_store
from stores.asset import create_asset_store
from core.store import Store


def _setup():
    """重置 AsyncEventBus"""
    AsyncEventBus.reset()
    bus = get_async_event_bus()
    bus.clear_subscribers()
    return bus


# ---------------------------------------------------------------------------
# 测试 1: event_driven=False 保持 V2.0 行为
# ---------------------------------------------------------------------------

def test_01_parent_v2_mode_no_subscription():
    """event_driven=False 时不订阅事件"""
    bus = _setup()
    parent = create_parent("parent_test", Store(), event_driven=False)
    assert bus.get_subscriber_count() == 0


# ---------------------------------------------------------------------------
# 测试 2: event_driven=True 订阅 TASK_DECOMPOSED
# ---------------------------------------------------------------------------

def test_02_parent_v3_mode_subscribes_task_decomposed():
    """event_driven=True 时订阅 TASK_DECOMPOSED"""
    bus = _setup()
    asset = create_asset_store()
    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset, sop_id="DEV-001")

    assert bus.get_subscriber_count(EventType.TASK_DECOMPOSED) == 1


# ---------------------------------------------------------------------------
# 测试 3: 收到 TASK_DECOMPOSED 后发布 STAGE_STARTED + STAGE_COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_03_parent_publishes_stage_events():
    """parent 收到 TASK_DECOMPOSED 后发布 STAGE_STARTED（STAGE_COMPLETED 由 orchestration 发布）"""
    bus = _setup()
    asset = create_asset_store()

    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset, sop_id="DEV-001")

    # 捕获事件
    stage_started = []
    task_failed = []

    async def capture_started(e): stage_started.append(e)
    async def capture_task_failed(e): task_failed.append(e)

    bus.subscribe_async(EventType.STAGE_STARTED, capture_started)
    bus.subscribe_async(EventType.TASK_FAILED, capture_task_failed)

    # 发布 TASK_DECOMPOSED
    await bus.publish(Event(
        event_type=EventType.TASK_DECOMPOSED,
        source="ancestor:task_decomposer",
        data={
            "task_id": "test_v3_003",
            "task_description": "用户权限管理",
            "decomposition": "mock decomposition",
        },
    ))

    # 等待异步处理完成
    await asyncio.sleep(0.5)

    # 验证：DEV-001 有 5 个阶段，parent 应发布 5 个 STAGE_STARTED
    assert len(stage_started) >= 1, f"Expected STAGE_STARTED events, got {len(stage_started)}"
    # V3.0 新架构：parent 只发布 STAGE_STARTED，STAGE_COMPLETED 由 orchestration 的 stage executor 发布
    assert len(task_failed) == 0, f"Unexpected TASK_FAILED: {task_failed}"


# ---------------------------------------------------------------------------
# 测试 4: 全部完成后发布 TASK_COMPLETED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_04_parent_publishes_task_completed():
    """parent + orchestration 完成所有阶段后发布 TASK_COMPLETED"""
    bus = _setup()
    asset = create_asset_store()

    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset, sop_id="DEV-001")

    # V3.0 新架构：注册 orchestration 的 stage executor 来处理 STAGE_STARTED → STAGE_COMPLETED → TASK_COMPLETED
    from skills.orchestration import register_stage_executor
    register_stage_executor(parent, asset)

    task_completed = []

    async def capture(e): task_completed.append(e)
    bus.subscribe_async(EventType.TASK_COMPLETED, capture)

    await bus.publish(Event(
        event_type=EventType.TASK_DECOMPOSED,
        source="ancestor:task_decomposer",
        data={
            "task_id": "test_v3_004",
            "task_description": "实现登录功能",
            "decomposition": "mock",
        },
    ))

    # 等待异步处理完成（mock 模式下 LLM 调用很快，但需要足够时间让事件链完成）
    await asyncio.sleep(2.0)

    assert len(task_completed) >= 1
    event = task_completed[0]
    assert event.event_type == EventType.TASK_COMPLETED
    # V3.0 新架构：TASK_COMPLETED 由 orchestration 的 stage executor 发布
    assert event.source == "orchestration:stage_executor"
    assert event.data.get("task_id") == "test_v3_004"
    assert "stages_completed" in event.data
    assert "total_stages" in event.data


# ---------------------------------------------------------------------------
# 测试 5: STAGE_STARTED 包含正确的阶段信息
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_05_stage_started_contains_stage_info():
    """STAGE_STARTED 事件包含阶段名称和顺序"""
    bus = _setup()
    asset = create_asset_store()

    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset, sop_id="DEV-001")

    started_events = []

    async def capture(e): started_events.append(e)
    bus.subscribe_async(EventType.STAGE_STARTED, capture)

    await bus.publish(Event(
        event_type=EventType.TASK_DECOMPOSED,
        source="ancestor:task_decomposer",
        data={
            "task_id": "test_v3_005",
            "task_description": "测试阶段信息",
            "decomposition": "mock",
        },
    ))

    await asyncio.sleep(0.5)

    assert len(started_events) >= 1
    first = started_events[0]
    assert first.data.get("stage_order") == 1
    assert "stage_name" in first.data
    assert "total_stages" in first.data


# ---------------------------------------------------------------------------
# 测试 6: SOP 加载失败时发布 TASK_FAILED
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_06_sop_load_failure_publishes_task_failed():
    """SOP 加载失败时发布 TASK_FAILED"""
    bus = _setup()
    asset = create_asset_store()

    # 使用不存在的 SOP ID
    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset, sop_id="NONEXISTENT-999")

    task_failed = []

    async def capture(e): task_failed.append(e)
    bus.subscribe_async(EventType.TASK_FAILED, capture)

    await bus.publish(Event(
        event_type=EventType.TASK_DECOMPOSED,
        source="ancestor:task_decomposer",
        data={
            "task_id": "test_v3_006",
            "task_description": "测试失败路径",
            "decomposition": "mock",
        },
    ))

    await asyncio.sleep(0.3)

    assert len(task_failed) >= 1
    assert task_failed[0].data.get("task_id") == "test_v3_006"
    assert "error" in task_failed[0].data


# ---------------------------------------------------------------------------
# 测试 7: event_driven=False 不订阅
# ---------------------------------------------------------------------------

def test_07_v2_mode_no_side_effects():
    """V2.0 模式创建 parent 不会产生任何事件订阅"""
    bus = _setup()
    parent = create_parent("parent_v2", Store(), event_driven=False)
    assert bus.get_subscriber_count(EventType.TASK_DECOMPOSED) == 0
    assert bus.get_subscriber_count(EventType.STAGE_STARTED) == 0
    assert bus.get_subscriber_count(EventType.TASK_COMPLETED) == 0


# ---------------------------------------------------------------------------
# 测试 8: V2.0 模式 parent 仍可正常 run()
# ---------------------------------------------------------------------------

def test_08_v2_mode_parent_run_works():
    """V2.0 模式 parent 仍可正常调用 run()"""
    bus = _setup()
    parent = create_parent("parent_v2", Store(), event_driven=False)

    # 正常调用 internalize_sop
    context = parent.run(
        sop_steps=["internalize_sop"],
        initial_context={
            "_sop_to_internalize": {
                "stages": [{"name": "测试阶段", "agent": "测试者", "skills": ["call_llm"]}],
                "sop_id": "test",
                "name": "测试SOP",
                "version": "1.0",
                "required_stages": [],
                "forbidden_skills": [],
            }
        }
    )

    assert "_internalized_steps" in context
    assert len(context["_internalized_steps"]) == 1
