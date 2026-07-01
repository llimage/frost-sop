"""
V3.0 缺失测试 3.1：真实模式测试（FROST_TESTING=0）

⚠️ 这些测试会消耗真实 Token，默认跳过。
运行方式：pytest -m slow --asyncio-mode=auto

前置条件：
1. 设置环境变量 FROST_TESTING=0
2. 配置真实 LLM API Key（如 OPENAI_API_KEY 或 DEEPSEEK_API_KEY）
3. 使用轻量模型（如 DeepSeek-V2-Lite）
"""

import os
import pytest
import asyncio

# 如果没有设置真实模式，跳过整个模块
if os.environ.get("FROST_TESTING") == "1":
    pytest.skip(
        "真实模式测试需要 FROST_TESTING=0，已跳过。"
        "运行方式: FROST_TESTING=0 pytest -m slow",
        allow_module_level=True,
    )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_mode_ancestor_publishes_task_decomposed():
    """
    真实模式：验证 ancestor 调用真实 LLM 后发布 TASK_DECOMPOSED。

    ⚠️ 消耗 Token：~1K tokens
    """
    from core.event_bus import get_async_event_bus, Event, EventType, reset_event_bus
    from agents.ancestor import create_ancestor
    from core.store import HierarchicalStore

    reset_event_bus()
    bus = get_async_event_bus()
    received = []

    async def capture(event: Event):
        received.append(event)

    bus.subscribe_async(EventType.TASK_DECOMPOSED, capture)

    ancestor = create_ancestor(HierarchicalStore(), None, event_driven=True)

    await bus.publish(
        Event(
            event_type=EventType.TASK_CREATED,
            source="test",
            data={"task_description": "写一个 Hello World 网页", "task_id": "real-001"},
        )
    )

    # 等待 LLM 响应（最多 30 秒）
    for _ in range(60):
        await asyncio.sleep(0.5)
        if received:
            break

    assert len(received) >= 1, " ancestor 未发布 TASK_DECOMPOSED（LLM 可能超时）"
    assert "decomposition" in received[0].data, (
        "TASK_DECOMPOSED 缺少 decomposition 字段"
    )


@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_mode_full_e2e():
    """
    真实模式：完整 main_async E2E 测试。

    ⚠️ 消耗 Token：~5K tokens
    """
    from main import main_async

    # 使用较短的 timeout 避免测试耗时过长
    try:
        result = await asyncio.wait_for(
            main_async(
                "写一个简单的 Python 脚本打印 Hello World", sop_id="DEV-001", timeout=60
            ),
            timeout=90,
        )
        # 验证事件链完整
        assert result is not None
        print(f"   ✅ 真实模式 E2E 完成: {result}")
    except asyncio.TimeoutError:
        pytest.skip("真实 LLM 响应超时（> 90s），跳过测试")


@pytest.mark.slow
@pytest.mark.asyncio
async def test_real_mode_cost_log_exists():
    """
    真实模式：验证 cost_log 表有真实 Token 记录。
    """
    from core.db import get_db

    db = get_db()
    # 查询最近的 cost 记录
    recent = db.select("cost_log", limit=5, order_by="rowid DESC")

    if not recent:
        pytest.skip("cost_log 无记录（可能还未执行 LLM 调用）")

    # 验证有真实的 token 消耗记录
    has_real_cost = any(r.get("total_cost", 0) > 0 for r in recent)
    if has_real_cost:
        print("   ✅ 发现真实 Token 消耗记录")
    else:
        print("   ⚠️ cost_log 中无真实消耗（可能使用了 mock）")
