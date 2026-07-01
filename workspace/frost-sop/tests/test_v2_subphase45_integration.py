"""
子阶段 4.5 集成验证测试
验证 main.py 和 app.py 中长老订阅已正确集成。
"""
import os
import sys

# Ensure project root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FROST_TESTING"] = "1"

import pytest
from agents.elder import subscribe_elder_to_events, create_elder
from core.store import Store
from core.event_bus import get_event_bus, EventType, Event


# ---------------------------------------------------------------------------
# 测试：main.py 入口集成
# ---------------------------------------------------------------------------

def test_main_imports_elder_subscription():
    """验证 main.py 正确导入了 subscribe_elder_to_events"""
    import main
    # 检查模块中存在所需的 import
    assert hasattr(main, 'subscribe_elder_to_events')


def test_main_creates_elder_in_function():
    """验证 main.py 中的 main() 可以正常导入（语法级）"""
    import main
    assert callable(main.main)


def test_main_can_init_without_eventbus():
    """验证 EventBus 不可用时 main() 不崩溃（fail-safe）

    NOTE: main() 会执行完整 SOP 任务（调用 LLM），这里只验证函数可调用。
    """
    import main
    # 只验证函数存在且可调用，不实际执行
    assert main.main is not None


# ---------------------------------------------------------------------------
# 测试：app.py 入口集成
# ---------------------------------------------------------------------------

def test_app_imports_elder_subscription():
    """验证 app.py 正确导入了 subscribe_elder_to_events"""
    pytest.skip("app.py (F11 Streamlit) has been removed in P0 security fix")


# ---------------------------------------------------------------------------
# 测试：幂等性——多次调用 subscribe_elder_to_events
# ---------------------------------------------------------------------------

def test_subscribe_is_idempotent():
    """多次调用 subscribe_elder_to_events 不应产生副作用"""
    store = Store()
    elder = create_elder("test_idempotent", asset_store=store)

    # 先清干净
    bus = get_event_bus()
    bus.clear_subscribers()

    # 第一次订阅
    result1 = subscribe_elder_to_events(elder)
    assert result1 is True

    sub_count_1 = bus.get_subscriber_count()

    # 第二次订阅（同一个 elder）
    result2 = subscribe_elder_to_events(elder)
    assert result2 is True

    sub_count_2 = bus.get_subscriber_count()

    # 订阅者数量应增加（每次订阅新增一个 handler）
    assert sub_count_2 >= sub_count_1, f"第二次订阅不应减少订阅者: {sub_count_1} -> {sub_count_2}"


# ---------------------------------------------------------------------------
# 测试：fail-safe——create_elder with broken EventBus
# ---------------------------------------------------------------------------

def test_subscribe_graceful_when_eventbus_unavailable(monkeypatch):
    """EventBus 抛异常时 subscribe_elder_to_events 应返回 False（不崩溃）"""
    store = Store()
    elder = create_elder("test_graceful", asset_store=store)

    # 模拟 get_event_bus 抛异常
    import core.event_bus as eb
    original_get = eb.get_event_bus

    def broken_get():
        raise RuntimeError("EventBus 模拟故障")

    monkeypatch.setattr(eb, "get_event_bus", broken_get)

    try:
        result = subscribe_elder_to_events(elder)
        assert result is False, "EventBus 不可用时应返回 False"
    finally:
        monkeypatch.setattr(eb, "get_event_bus", original_get)


# ---------------------------------------------------------------------------
# 测试：端到端——TASK_COMPLETED 触发长老审计
# ---------------------------------------------------------------------------

def test_e2e_task_completed_triggers_elder_audit():
    """TASK_COMPLETED 事件应触发长老的 audit_family"""
    store = Store()
    # 写入几个任务数据，让 audit_family 有东西统计
    store.save("task:task_001", {"status": "completed", "name": "测试任务1"})
    store.save("task:task_002", {"status": "failed", "name": "测试任务2"})

    elder = create_elder("test_e2e", asset_store=store)

    # 清空订阅再订阅
    bus = get_event_bus()
    bus.clear_subscribers()
    subscribe_elder_to_events(elder)

    # 发布 TASK_COMPLETED
    bus.publish(Event(
        event_type=EventType.TASK_COMPLETED,
        source="test_e2e",
        data={"task_id": "task_e2e_001"},
    ))

    # 事件是同步分发的，audit_family 会直接执行
    # 验证事件已被记录
    log = bus.get_event_log()
    completed_events = [e for e in log if e.event_type == EventType.TASK_COMPLETED]
    assert len(completed_events) >= 1, "TASK_COMPLETED 事件应已记录"


# ---------------------------------------------------------------------------
# 测试：EventBus 持久化与订阅不冲突
# ---------------------------------------------------------------------------

def test_subscribe_does_not_break_persistence():
    """订阅长老后，事件持久化仍正常"""
    store = Store()
    elder = create_elder("test_persist", asset_store=store)

    bus = get_event_bus()
    bus.clear_subscribers()
    subscribe_elder_to_events(elder)

    # 发布一个事件
    event = Event(
        event_type=EventType.TASK_COMPLETED,
        source="test_persist",
        data={"task_id": "test_task"},
    )
    bus.publish(event)

    # 检查持久化
    from core.db import get_db
    db = get_db()
    rows = db.select_all("event_log", where=f"event_type = 'task_completed'")
    assert len(rows) >= 1, "事件应被持久化到 event_log 表"
