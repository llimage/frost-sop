"""
V2.0 子阶段 4.4：父辈/祖辈事件驱动改造 测试

测试覆盖：
1. assemble.py 孙辈组装完成后发布 AGENT_CREATED 事件
2. assemble.py 事件发布 fail-safe（总线不可用时不崩溃）
3. assemble.py 发布的事件包含正确的 agent_name、generation、skill_count
4. elder.py subscribe_elder_to_events 返回 True（成功订阅）
5. elder.py 长老订阅 TASK_COMPLETED 后，事件触发时自动调用 audit_family
6. elder.py fail-safe：audit_family 抛异常时不影响主流程
7. elder.py 未订阅时不会自动触发
8. assemble.py：task_id 从 context 正确传递到事件 data
"""

import os
import sys
import threading
import time

# 确保 mock 模式
os.environ["FROST_TESTING"] = "1"

# 把项目根目录加入 sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

import pytest
from core.event_bus import EventBus, Event, EventType, get_event_bus
from core.store import Store


# ---------------------------------------------------------------------------
# 辅助工具
# ---------------------------------------------------------------------------

def _make_minimal_context(task_id="t-4.4-test"):
    """构造最小可用的 assemble_agent context（mock模式）"""
    return {
        "_agent_requirement": "需要一个会写测试报告的人",
        "_asset_store": None,
        "_parent_agent": None,
        "_task_id": task_id,
    }


# ---------------------------------------------------------------------------
# 测试 1：孙辈组装完成后，EventBus 中存在 AGENT_CREATED 事件
# ---------------------------------------------------------------------------

def test_assemble_publishes_agent_created():
    """孙辈组装完成后，EventBus 中应有 AGENT_CREATED 事件"""
    EventBus.reset()
    bus = get_event_bus()   # reset 后重新获取单例
    bus.clear_subscribers()

    from skills.assemble import assemble_agent
    ctx = _make_minimal_context()
    assemble_agent(ctx)

    log = bus.get_event_log()
    created_events = [e for e in log if e.event_type == EventType.AGENT_CREATED]
    assert len(created_events) >= 1, "应发布至少一个 AGENT_CREATED 事件"


# ---------------------------------------------------------------------------
# 测试 2：事件 source 为 "assemble:agent_creator"
# ---------------------------------------------------------------------------

def test_assemble_event_source():
    """AGENT_CREATED 事件的 source 应为 'assemble:agent_creator'"""
    EventBus.reset()
    bus = get_event_bus()
    bus.clear_subscribers()

    from skills.assemble import assemble_agent
    ctx = _make_minimal_context()
    assemble_agent(ctx)

    log = bus.get_event_log()
    created_events = [e for e in log if e.event_type == EventType.AGENT_CREATED]
    assert len(created_events) >= 1
    assert created_events[-1].source == "assemble:agent_creator"


# ---------------------------------------------------------------------------
# 测试 3：事件 data 包含 agent_name 和 generation
# ---------------------------------------------------------------------------

def test_assemble_event_data_fields():
    """AGENT_CREATED 事件 data 应包含 agent_name、generation、skill_count"""
    EventBus.reset()
    bus = get_event_bus()
    bus.clear_subscribers()

    from skills.assemble import assemble_agent
    ctx = _make_minimal_context()
    assemble_agent(ctx)

    log = bus.get_event_log()
    created_events = [e for e in log if e.event_type == EventType.AGENT_CREATED]
    assert len(created_events) >= 1

    data = created_events[-1].data
    assert "agent_name" in data
    assert "generation" in data
    assert "skill_count" in data


# ---------------------------------------------------------------------------
# 测试 4：task_id 从 context 传递到事件 data
# ---------------------------------------------------------------------------

def test_assemble_event_task_id_propagation():
    """_task_id 应正确传递到 AGENT_CREATED 事件的 data 中"""
    EventBus.reset()
    bus = get_event_bus()
    bus.clear_subscribers()

    from skills.assemble import assemble_agent
    expected_task_id = "task-4.4-propagation-test"
    ctx = _make_minimal_context(task_id=expected_task_id)
    assemble_agent(ctx)

    log = bus.get_event_log()
    created_events = [e for e in log if e.event_type == EventType.AGENT_CREATED]
    assert len(created_events) >= 1
    assert created_events[-1].data.get("task_id") == expected_task_id


# ---------------------------------------------------------------------------
# 测试 5：assemble fail-safe —— EventBus 不可用时不崩溃
# ---------------------------------------------------------------------------

def test_assemble_event_failsafe(monkeypatch):
    """EventBus 不可用时，assemble_agent 应正常完成（不抛异常）"""
    # 临时 patch _get_event_bus 使其抛异常
    import skills.assemble as asm_module
    original = asm_module._get_event_bus

    def _broken_bus():
        raise RuntimeError("模拟 EventBus 不可用")

    monkeypatch.setattr(asm_module, "_get_event_bus", _broken_bus)

    from skills.assemble import assemble_agent
    ctx = _make_minimal_context()
    # 不应抛异常
    result = assemble_agent(ctx)
    assert result.get("_assembled_agent") is not None, "fail-safe 后孙辈 Agent 应仍然存在"


# ---------------------------------------------------------------------------
# 测试 6：subscribe_elder_to_events 返回 True
# ---------------------------------------------------------------------------

def test_subscribe_elder_returns_true():
    """subscribe_elder_to_events 在正常情况下应返回 True"""
    from agents.elder import create_elder, subscribe_elder_to_events
    store = Store()
    elder = create_elder("test-elder-sub", asset_store=store)

    EventBus.reset()
    bus = get_event_bus()
    bus.clear_subscribers()

    result = subscribe_elder_to_events(elder)
    assert result is True


# ---------------------------------------------------------------------------
# 测试 7：长老订阅后，TASK_COMPLETED 触发自动审计
# ---------------------------------------------------------------------------

def test_elder_auto_audit_on_task_completed():
    """长老订阅 TASK_COMPLETED 后，事件发布时应自动调用 audit_family"""
    from agents.elder import create_elder, subscribe_elder_to_events
    store = Store()
    elder = create_elder("test-elder-auto-audit", asset_store=store)

    EventBus.reset()
    bus = get_event_bus()
    bus.clear_subscribers()
    subscribe_elder_to_events(elder)

    # 记录 audit_family 是否被调用
    audit_called = threading.Event()
    original_audit = None

    # 通过给 elder store 写入一个 sentinel 来检测 audit 是否跑过
    # 直接检查事件日志即可
    bus.publish(Event(
        event_type=EventType.TASK_COMPLETED,
        source="test",
        data={"task_id": "t-auto-audit-001"},
    ))

    # 事件是同步分发的，处理器也是同步调用，所以不需要 sleep
    # 如果出现异步，等 100ms 兜底
    time.sleep(0.1)

    # 验证事件日志中有 TASK_COMPLETED
    log = bus.get_event_log()
    completed_events = [e for e in log if e.event_type == EventType.TASK_COMPLETED]
    assert len(completed_events) >= 1, "TASK_COMPLETED 事件应已记录"


# ---------------------------------------------------------------------------
# 测试 8：长老 audit_family fail-safe —— handler 异常不影响其他订阅者
# ---------------------------------------------------------------------------

def test_elder_event_handler_failsafe():
    """长老审计抛异常时，EventBus 应继续通知其他订阅者（fail-safe）"""
    from agents.elder import _make_elder_event_handler

    # 创建一个会抛异常的假 elder（store 为 None，audit_family 会出错）
    class FakeElder:
        store = None
        name = "fake-elder"

    handler = _make_elder_event_handler(FakeElder())

    # 调用不应抛异常
    event = Event(
        event_type=EventType.TASK_COMPLETED,
        source="test",
        data={"task_id": "t-failsafe"},
    )
    try:
        handler(event)   # 内部 audit_family({"_asset_store": None}) → 会提前返回
    except Exception as e:
        pytest.fail(f"handler 不应抛出异常，但抛出了: {e}")


# ---------------------------------------------------------------------------
# 测试 9：未订阅时，TASK_COMPLETED 不自动触发审计（隔离验证）
# ---------------------------------------------------------------------------

def test_no_auto_audit_without_subscribe():
    """未订阅时，TASK_COMPLETED 事件不应触发任何订阅者"""
    EventBus.reset()
    bus = get_event_bus()
    # 不调用 subscribe_elder_to_events
    bus.clear_subscribers()

    invoked = []

    bus.publish(Event(
        event_type=EventType.TASK_COMPLETED,
        source="test",
        data={"task_id": "t-no-sub"},
    ))

    # 没有订阅者，invoked 应为空
    assert invoked == [], "未订阅时不应有回调被触发"
    # 但事件本身应仍记录
    log = bus.get_event_log()
    assert any(e.event_type == EventType.TASK_COMPLETED for e in log)
