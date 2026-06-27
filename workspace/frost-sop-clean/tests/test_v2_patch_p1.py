"""
V2.1 修补验证：P1-6/7/8/9 新增测试
- P1-6: TASK_DECOMPOSED 事件发布
- P1-7: 敏感数据过滤
- P1-8: 循环事件防护
- P1-9: agents 表 UPSERT
"""

import pytest
import json
import threading
from unittest.mock import patch, MagicMock

from core.event_bus import EventBus, Event, EventType, get_event_bus
from core.agent import Agent
from core.skill import Skill
from core.store import Store


# ============================================================
# P1-6: TASK_DECOMPOSED 事件
# ============================================================

def test_task_decomposed_event_type_exists():
    """EventType.TASK_DECOMPOSED 常量存在"""
    assert hasattr(EventType, 'TASK_DECOMPOSED')
    assert isinstance(EventType.TASK_DECOMPOSED, str)
    assert len(EventType.TASK_DECOMPOSED) > 0


def test_task_decomposed_event_publish():
    """TASK_DECOMPOSED 事件可以正常发布"""
    bus = get_event_bus()
    event = Event(
        event_type=EventType.TASK_DECOMPOSED,
        source="test",
        data={"task_id": "t-p1-6", "stage_count": 5, "stages": ["a", "b", "c", "d", "e"]},
    )
    notified = bus.publish(event)
    assert notified >= 0  # 可能无订阅者
    log = bus.get_event_log(event_type=EventType.TASK_DECOMPOSED)
    assert len(log) >= 1
    assert log[0].data["task_id"] == "t-p1-6"
    assert log[0].data["stage_count"] == 5


def test_task_decomposed_subscriber():
    """TASK_DECOMPOSED 可以被订阅并触发回调"""
    bus = get_event_bus()
    received = []

    def handler(event):
        received.append(event.data.get("task_id"))

    bus.subscribe(EventType.TASK_DECOMPOSED, handler)
    try:
        bus.publish(Event(
            event_type=EventType.TASK_DECOMPOSED,
            source="test",
            data={"task_id": "t-sub"},
        ))
        assert "t-sub" in received
    finally:
        bus.unsubscribe(EventType.TASK_DECOMPOSED, handler)


# ============================================================
# P1-7: 敏感数据过滤
# ============================================================

def test_sensitive_keys_in_filter_list():
    """敏感键列表包含标准敏感字段"""
    bus = get_event_bus()
    assert "api_key" in bus._SENSITIVE_KEYS
    assert "token" in bus._SENSITIVE_KEYS
    assert "password" in bus._SENSITIVE_KEYS
    assert "secret" in bus._SENSITIVE_KEYS
    assert "authorization" in bus._SENSITIVE_KEYS


def test_sanitize_redacts_api_key():
    """_sanitize_data 将 api_key 替换为 ***REDACTED***"""
    bus = get_event_bus()
    data = {"api_key": "sk-1234567890", "name": "test"}
    result = bus._sanitize_data(data)
    assert result["api_key"] == "***REDACTED***"
    assert result["name"] == "test"


def test_sanitize_redacts_token_case_insensitive():
    """_sanitize_data 对大小写不敏感"""
    bus = get_event_bus()
    data = {"Authorization": "Bearer xyz", "API_KEY": "sk-abc"}
    result = bus._sanitize_data(data)
    assert result["Authorization"] == "***REDACTED***"
    assert result["API_KEY"] == "***REDACTED***"


def test_sanitize_preserves_non_sensitive_data():
    """_sanitize_data 保留非敏感数据"""
    bus = get_event_bus()
    data = {"task_id": "t-001", "stage_count": 3, "name": "正常数据"}
    result = bus._sanitize_data(data)
    assert result == data  # 全部保留


def test_sanitize_recursive_nested_objects():
    """_sanitize_data 递归过滤嵌套对象中的敏感键"""
    bus = get_event_bus()
    data = {
        "task_id": "t-001",
        "config": {
            "api_key": "sk-nested",
            "timeout": 30,
            "auth": {
                "token": "tok-nested",
                "username": "admin",
            }
        }
    }
    result = bus._sanitize_data(data)
    assert result["task_id"] == "t-001"
    assert result["config"]["api_key"] == "***REDACTED***"
    assert result["config"]["timeout"] == 30
    assert result["config"]["auth"]["token"] == "***REDACTED***"
    assert result["config"]["auth"]["username"] == "admin"


def test_sanitize_handles_non_dict_input():
    """_sanitize_data 对非 dict 直接返回"""
    bus = get_event_bus()
    assert bus._sanitize_data("string") == "string"
    assert bus._sanitize_data(123) == 123
    assert bus._sanitize_data([1, 2, 3]) == [1, 2, 3]


def test_persist_sanitizes_before_write():
    """_persist_event 在写入前调用 _sanitize_data"""
    from unittest.mock import patch
    import core.db as db_module

    bus = get_event_bus()
    event = Event(
        event_type=EventType.STEP_COMPLETED,
        source="test",
        data={"api_key": "sk-leak", "step": "process", "token": "secret-token"},
    )

    # 通过检查写入 DB 的数据来验证过滤效果
    with patch.object(bus, '_sanitize_data', wraps=bus._sanitize_data) as mock_sanitize:
        bus._persist_event(event)
        assert mock_sanitize.called

    # 验证 DB 中存储的 data 已被过滤
    db = db_module.get_db()
    rows = db.select_all("event_log", f"event_id = '{event.event_id}'")
    assert len(rows) >= 1
    stored_data = json.loads(rows[0]["data"])
    assert stored_data["api_key"] == "***REDACTED***", f"期望 REDACTED，实际: {stored_data}"
    assert stored_data["token"] == "***REDACTED***"
    assert stored_data["step"] == "process"


# ============================================================
# P1-8: 循环事件防护
# ============================================================

def test_circular_event_prevention():
    """源与回调同名时跳过分发，防止循环事件"""
    bus = get_event_bus()
    called = []

    def test_source(event):
        called.append(event.event_id)

    bus.subscribe(EventType.STEP_COMPLETED, test_source)
    try:
        event = Event(
            event_type=EventType.STEP_COMPLETED,
            source="test_source",  # 与回调函数同名
            data={"step": "x"},
        )
        notified = bus.publish(event)
        # 应跳过同名的 test_source 回调
        assert called == [], f"同名回调应被跳过，但被调用了 {called}"
    finally:
        bus.unsubscribe(EventType.STEP_COMPLETED, test_source)


def test_circular_prevention_different_source():
    """不同名时正常分发"""
    bus = get_event_bus()
    called = []

    def handler_a(event):
        called.append("a")

    bus.subscribe(EventType.STEP_COMPLETED, handler_a)
    try:
        event = Event(
            event_type=EventType.STEP_COMPLETED,
            source="handler_b",  # 不同于 handler_a
            data={},
        )
        notified = bus.publish(event)
        assert "a" in called, "不同名回调应正常触发"
    finally:
        bus.unsubscribe(EventType.STEP_COMPLETED, handler_a)


def test_circular_prevention_lambda_always_runs():
    """lambda 函数没有 __name__，不应被跳过"""
    bus = get_event_bus()
    called = []

    # lambda 没有 __name__（或 __name__ 为 '<lambda>'），不会匹配任何 source
    bus.subscribe(EventType.STEP_COMPLETED, lambda e: called.append("lambda"))

    event = Event(
        event_type=EventType.STEP_COMPLETED,
        source="<lambda>",
        data={},
    )
    bus.publish(event)
    # lambda 应该被调用，因为没有 hasattr '。'__name__' 或 __name__ 不等于 source
    assert "lambda" in called

    # 清理
    bus.clear_subscribers()


# ============================================================
# P1-9: agents 表 UPSERT
# ============================================================

def test_agent_repeated_run_no_unique_constraint_error():
    """Agent 重复写入 agents 表不报 UNIQUE 约束错误"""
    import tempfile
    import core.db as db_module

    # 创建临时 DB 隔离
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp_db = f.name
    f.close()

    orig = {
        "instance": db_module.DBManager._instance,
        "connection": db_module.DBManager._connection,
        "global": db_module._db_manager,
    }
    db_module.DBManager._instance = None
    db_module.DBManager._connection = None
    db_module._db_manager = None

    try:
        test_db = db_module.DBManager(db_path=tmp_db)
        db_module._db_manager = test_db

        store = Store()
        skill = Skill("dummy", lambda ctx: ctx)
        agent = Agent(name="test-upsert", store=store, skills={"dummy": skill})

        # 第一次写入
        agent._write_agent_status("running", "t-upsert")
        # 第二次写入同一 Agent — 不应报错
        agent._write_agent_status("running", "t-upsert")
        # 第三次 — 也不应报错
        agent._write_agent_status("destroyed", "t-upsert")

        # 验证 agents 表中有一条记录
        conn = test_db.get_connection()
        rows = conn.execute("SELECT * FROM agents WHERE id = 'test-upsert'").fetchall()
        assert len(rows) == 1
    finally:
        # 先关闭 DB 连接再清理临时文件
        db_module.DBManager._instance = None
        db_module.DBManager._connection = None
        db_module._db_manager = None
        import os as _os
        try:
            _os.unlink(tmp_db)
        except PermissionError:
            pass  # Windows 文件锁延迟释放，忽略
