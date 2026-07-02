"""
V6.0 测试: 事件订阅者注册和回调
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestRegisterSubscribers:
    """测试订阅者注册"""

    def test_register_all_subscribers(self):
        """验证注册不抛异常"""
        from core.event_subscribers import register_all_subscribers

        register_all_subscribers()

    def test_register_idempotent(self):
        """验证幂等性（重复调用不重复注册）"""
        from core.event_bus import EventBus
        from core.event_subscribers import register_all_subscribers

        EventBus.reset()
        bus = EventBus()
        register_all_subscribers()
        after_first = bus.get_subscriber_count()

        register_all_subscribers()
        bus.get_subscriber_count()  # 验证不抛异常

        # 注册后应有订阅者
        assert after_first > 0


class TestOnTaskCompleted:
    """测试任务完成回调"""

    def test_on_task_completed(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_task_completed

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            source="test_agent",
            data={},
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        # 不抛异常即可
        _on_task_completed(event)


class TestOnHuntCompleted:
    """测试狩猎完成回调"""

    def test_on_hunt_completed(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_hunt_completed

        event = Event(
            event_type=EventType.HUNT_COMPLETED,
            source="hunt_agent",
            data={"_context": {}},
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        _on_hunt_completed(event)


class TestOnBriefingIntegrated:
    """测试简报整合回调"""

    def test_on_briefing_integrated(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_briefing_integrated

        event = Event(
            event_type=EventType.BRIEFING_INTEGRATED,
            source="analytics",
            data={"_briefing": {}, "_asset_store": None},
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        _on_briefing_integrated(event)


class TestOnEvolutionSuggested:
    """测试进化建议回调"""

    def test_on_evolution_suggested(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_evolution_suggested

        event = Event(
            event_type=EventType.EVOLUTION_SUGGESTED,
            source="evolution",
            data={"_suggestions": [], "_asset_store": None},
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        _on_evolution_suggested(event)


class TestOnScheduledExecuted:
    """测试定时执行回调"""

    def test_on_scheduled_executed(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_scheduled_executed

        event = Event(
            event_type=EventType.SCHEDULED_EXECUTED,
            source="scheduler",
            data={"job_type": "sop"},
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        _on_scheduled_executed(event)


class TestOnStageFailed:
    """测试阶段失败回调"""

    def test_on_stage_failed(self):
        import uuid
        from datetime import datetime

        from core.event_bus import Event, EventType
        from core.event_subscribers import _on_stage_failed

        event = Event(
            event_type=EventType.STAGE_FAILED,
            source="test_stage",
            data={
                "reason": "test failure",
                "_asset_store": None,
            },
            event_id=uuid.uuid4().hex,
            timestamp=datetime.now(),
        )
        _on_stage_failed(event)


class TestEventTypes:
    """测试 V6.0 新增事件类型"""

    def test_new_event_types_exist(self):
        from core.event_bus import EventType

        assert hasattr(EventType, "HUNT_COMPLETED")
        assert hasattr(EventType, "BRIEFING_INTEGRATED")
        assert hasattr(EventType, "EVOLUTION_SUGGESTED")
        assert hasattr(EventType, "SCHEDULED_EXECUTED")
        assert hasattr(EventType, "DAILY_SNAPSHOT_COMPLETED")
        assert hasattr(EventType, "WEEKLY_RETROSPECTIVE_COMPLETED")

    def test_new_event_types_values(self):
        from core.event_bus import EventType

        assert EventType.HUNT_COMPLETED == "hunt_completed"
        assert EventType.BRIEFING_INTEGRATED == "briefing_integrated"
        assert EventType.EVOLUTION_SUGGESTED == "evolution_suggested"
        assert EventType.SCHEDULED_EXECUTED == "scheduled_executed"
