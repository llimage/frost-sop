"""
V2.0 子阶段 4.1 + 4.2 验收测试：EventBus 核心 + 事件类型定义

验收标准：
1. EventBus 单例正确初始化
2. subscribe / unsubscribe 功能正常
3. publish 分发事件给订阅者
4. publish 持久化到 event_log 表
5. get_event_log 返回历史事件
6. 订阅者异常不影响其他订阅者
7. 所有 EventType 常量定义完整
8. 线程安全（多线程并发 publish）
"""

import os
import tempfile
import threading

os.environ["FROST_TESTING"] = "1"

from core.event_bus import Event, EventBus, EventType, get_event_bus


class TestEventBusCore:
    """子阶段 4.1: EventBus 核心功能"""

    def setup_method(self):
        """每个测试前重置 EventBus 单例"""
        EventBus.reset()

    def teardown_method(self):
        """每个测试后重置 EventBus 单例"""
        EventBus.reset()

    # ----------------------------------------------------------
    # 单例测试
    # ----------------------------------------------------------

    def test_eb_01_singleton(self):
        """EventBus 是单例"""
        bus1 = EventBus()
        bus2 = EventBus()
        assert bus1 is bus2

    def test_eb_02_get_event_bus_returns_singleton(self):
        """get_event_bus() 返回单例"""
        bus = get_event_bus()
        assert bus is EventBus()

    # ----------------------------------------------------------
    # 订阅/取消订阅
    # ----------------------------------------------------------

    def test_eb_03_subscribe_registers_callback(self):
        """subscribe 成功注册回调"""
        bus = EventBus()
        received = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: received.append(e))
        assert bus.get_subscriber_count(EventType.STEP_COMPLETED) == 1

    def test_eb_04_subscribe_no_duplicate(self):
        """同一个 callback 不重复注册"""
        bus = EventBus()
        cb = lambda e: None
        bus.subscribe(EventType.STEP_COMPLETED, cb)
        bus.subscribe(EventType.STEP_COMPLETED, cb)
        assert bus.get_subscriber_count(EventType.STEP_COMPLETED) == 1

    def test_eb_05_unsubscribe_removes_callback(self):
        """unsubscribe 成功移除回调"""
        bus = EventBus()
        cb = lambda e: None
        bus.subscribe(EventType.TASK_COMPLETED, cb)
        result = bus.unsubscribe(EventType.TASK_COMPLETED, cb)
        assert result is True
        assert bus.get_subscriber_count(EventType.TASK_COMPLETED) == 0

    def test_eb_06_unsubscribe_nonexistent_returns_false(self):
        """unsubscribe 不存在的 callback 返回 False"""
        bus = EventBus()
        result = bus.unsubscribe(EventType.TASK_FAILED, lambda e: None)
        assert result is False

    def test_eb_07_clear_subscribers_specific_type(self):
        """clear_subscribers 清空指定类型"""
        bus = EventBus()
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: None)
        bus.subscribe(EventType.STAGE_COMPLETED, lambda e: None)
        bus.clear_subscribers(EventType.STEP_COMPLETED)
        assert bus.get_subscriber_count(EventType.STEP_COMPLETED) == 0
        assert bus.get_subscriber_count(EventType.STAGE_COMPLETED) == 1

    def test_eb_08_clear_subscribers_all(self):
        """clear_subscribers(None) 清空所有类型"""
        bus = EventBus()
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: None)
        bus.subscribe(EventType.TASK_COMPLETED, lambda e: None)
        bus.clear_subscribers()
        assert bus.get_subscriber_count() == 0

    # ----------------------------------------------------------
    # 发布/分发
    # ----------------------------------------------------------

    def test_eb_09_publish_notifies_subscriber(self):
        """publish 通知订阅者"""
        bus = EventBus()
        received = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: received.append(e))

        event = Event(EventType.STEP_COMPLETED, source="test_agent", data={"step": "call_llm"})
        notified = bus.publish(event)

        assert notified == 1
        assert len(received) == 1
        assert received[0].event_type == EventType.STEP_COMPLETED
        assert received[0].data["step"] == "call_llm"

    def test_eb_10_publish_notifies_multiple_subscribers(self):
        """publish 通知多个订阅者"""
        bus = EventBus()
        counts = [0, 0]
        bus.subscribe(EventType.TASK_COMPLETED, lambda e: counts.__setitem__(0, counts[0] + 1))
        bus.subscribe(EventType.TASK_COMPLETED, lambda e: counts.__setitem__(1, counts[1] + 1))

        bus.publish(Event(EventType.TASK_COMPLETED, source="main"))
        assert counts == [1, 1]

    def test_eb_11_publish_no_subscriber_returns_zero(self):
        """无订阅者时 publish 返回 0"""
        bus = EventBus()
        notified = bus.publish(Event(EventType.AGENT_CREATED, source="orphan"))
        assert notified == 0

    def test_eb_12_subscriber_exception_does_not_block_others(self):
        """一个订阅者抛异常，其他订阅者仍然收到事件"""
        bus = EventBus()
        received = []

        def bad_cb(e):
            raise RuntimeError("故意失败")

        bus.subscribe(EventType.STEP_COMPLETED, bad_cb)
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: received.append(e))

        bus.publish(Event(EventType.STEP_COMPLETED, source="test"))
        # 第二个订阅者应收到事件
        assert len(received) == 1

    # ----------------------------------------------------------
    # 事件日志
    # ----------------------------------------------------------

    def test_eb_13_get_event_log_returns_published_events(self):
        """publish 后 get_event_log 返回事件"""
        bus = EventBus()
        bus.publish(
            Event(EventType.STAGE_COMPLETED, source="parent_dev", data={"stage": "需求分析"})
        )
        bus.publish(Event(EventType.TASK_COMPLETED, source="main"))

        log = bus.get_event_log()
        assert len(log) == 2

    def test_eb_14_get_event_log_filter_by_type(self):
        """get_event_log 按 event_type 过滤"""
        bus = EventBus()
        bus.publish(Event(EventType.STEP_COMPLETED, source="a"))
        bus.publish(Event(EventType.STAGE_COMPLETED, source="b"))
        bus.publish(Event(EventType.STEP_COMPLETED, source="c"))

        step_log = bus.get_event_log(event_type=EventType.STEP_COMPLETED)
        assert len(step_log) == 2
        for e in step_log:
            assert e.event_type == EventType.STEP_COMPLETED

    def test_eb_15_get_event_log_newest_first(self):
        """get_event_log 返回结果最新在前"""
        bus = EventBus()
        e1 = Event(EventType.STEP_COMPLETED, source="first")
        e2 = Event(EventType.STEP_COMPLETED, source="second")
        bus.publish(e1)
        bus.publish(e2)

        log = bus.get_event_log(event_type=EventType.STEP_COMPLETED)
        assert log[0].source == "second"
        assert log[1].source == "first"

    def test_eb_16_get_event_log_with_limit(self):
        """get_event_log limit 参数生效"""
        bus = EventBus()
        for i in range(10):
            bus.publish(Event(EventType.STEP_COMPLETED, source=f"agent_{i}"))

        log = bus.get_event_log(limit=3)
        assert len(log) == 3

    # ----------------------------------------------------------
    # 线程安全
    # ----------------------------------------------------------

    def test_eb_17_thread_safe_concurrent_publish(self):
        """多线程并发 publish 不崩溃，事件全部记录"""
        bus = EventBus()
        errors = []

        def publish_many():
            for i in range(20):
                try:
                    bus.publish(Event(EventType.STEP_COMPLETED, source=f"thread_{i}"))
                except Exception as e:
                    errors.append(e)

        threads = [threading.Thread(target=publish_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert len(errors) == 0
        # 5 个线程 × 20 次 = 100 个事件
        log = bus.get_event_log(limit=200)
        assert len(log) == 100

    # ----------------------------------------------------------
    # Event 数据类
    # ----------------------------------------------------------

    def test_eb_18_event_has_unique_id(self):
        """每个 Event 有唯一 event_id"""
        e1 = Event(EventType.STEP_COMPLETED, source="a")
        e2 = Event(EventType.STEP_COMPLETED, source="b")
        assert e1.event_id != e2.event_id

    def test_eb_19_event_to_dict(self):
        """Event.to_dict() 序列化正确"""
        e = Event(EventType.TASK_COMPLETED, source="main", data={"task_id": "t001"})
        d = e.to_dict()
        assert d["event_type"] == EventType.TASK_COMPLETED
        assert d["source"] == "main"
        assert d["data"]["task_id"] == "t001"
        assert "event_id" in d
        assert "timestamp" in d

    # ----------------------------------------------------------
    # 持久化
    # ----------------------------------------------------------

    def test_eb_20_publish_persists_to_db(self):
        """publish 将事件持久化到 event_log 表"""
        import os as _os

        import core.db as db_module

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_db = f.name

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

            bus = EventBus()
            event = Event(
                EventType.TASK_COMPLETED, source="test_main", data={"task_id": "t_persist"}
            )
            bus.publish(event)

            # 检查 event_log 表
            rows = test_db.select_all("event_log")
            assert len(rows) >= 1
            found = [r for r in rows if r["event_id"] == event.event_id]
            assert len(found) == 1
            assert found[0]["event_type"] == EventType.TASK_COMPLETED

        finally:
            db_module.DBManager._instance = orig["instance"]
            db_module.DBManager._connection = orig["connection"]
            db_module._db_manager = orig["global"]
            try:
                _os.unlink(tmp_db)
            except Exception:
                pass


class TestEventTypes:
    """子阶段 4.2: 事件类型定义完整性"""

    def test_et_01_all_event_types_defined(self):
        """所有必需的事件类型常量已定义"""
        required = [
            "TASK_DECOMPOSED",
            "TASK_COMPLETED",
            "TASK_FAILED",
            "STAGE_STARTED",
            "STAGE_COMPLETED",
            "STAGE_FAILED",
            "STEP_COMPLETED",
            "AGENT_CREATED",
            "AGENT_DESTROYED",
        ]
        for attr in required:
            assert hasattr(EventType, attr), f"EventType.{attr} 未定义"
            value = getattr(EventType, attr)
            assert isinstance(value, str) and len(value) > 0

    def test_et_02_event_type_values_are_unique(self):
        """所有事件类型值唯一，无重复"""
        attrs = [k for k in vars(EventType) if not k.startswith("_")]
        values = [getattr(EventType, a) for a in attrs if isinstance(getattr(EventType, a), str)]
        assert len(values) == len(set(values)), "事件类型值存在重复"

    def test_et_03_event_type_values_are_snake_case(self):
        """事件类型值符合 snake_case 规范"""
        import re

        attrs = [k for k in vars(EventType) if not k.startswith("_")]
        for attr in attrs:
            val = getattr(EventType, attr)
            if isinstance(val, str):
                assert re.match(r"^[a-z][a-z_]+$", val), (
                    f"EventType.{attr}={val!r} 不符合 snake_case"
                )
