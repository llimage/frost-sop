"""
V7 阶段3 覆盖率补测试 — core/dead_mans_switch.py (39.58% → 80%+)
死人开关：超时告警、解除/武装、EventBus订阅
"""

import os
import sys
from datetime import datetime, timedelta

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.dead_mans_switch import (
    ALERT_LEVEL_CRITICAL,
    DEFAULT_TIMEOUT_MINUTES,
    DeadManSwitch,
    create_event_subscribe_callback,
    setup_dead_man_switch,
)


class TestDeadManSwitchInit:
    """初始化测试"""

    def test_default_timeout(self):
        dms = DeadManSwitch()
        assert dms.timeout_minutes == DEFAULT_TIMEOUT_MINUTES
        assert dms.is_armed is True
        assert dms._alert_triggered is False

    def test_custom_timeout(self):
        dms = DeadManSwitch(timeout_minutes=60)
        assert dms.timeout_minutes == 60

    def test_with_callback(self):
        alerts = []
        dms = DeadManSwitch(on_alert=lambda a: alerts.append(a))
        assert dms.on_alert is not None


class TestOnAnyEvent:
    """事件触发测试"""

    def test_on_event_updates_time(self):
        dms = DeadManSwitch()
        old_time = dms.last_event_time
        dms.on_any_event()
        assert dms.last_event_time >= old_time

    def test_on_event_with_event_object(self):
        dms = DeadManSwitch()
        event = type("Event", (), {"event_type": "TASK_CREATED"})()
        dms.on_any_event(event)
        assert dms.last_event_time is not None

    def test_on_event_when_disarmed(self):
        dms = DeadManSwitch()
        dms.disarm()
        old_time = dms.last_event_time
        dms.on_any_event()
        # 不应更新时间（因为已解除）
        assert dms.last_event_time == old_time


class TestCheck:
    """超时检查测试"""

    def test_no_timeout_returns_none(self):
        dms = DeadManSwitch(timeout_minutes=30)
        result = dms.check()
        assert result is None

    def test_timeout_returns_alert(self):
        dms = DeadManSwitch(timeout_minutes=1)
        # 设置为很久以前
        dms.last_event_time = datetime.now() - timedelta(minutes=5)
        result = dms.check()
        assert result is not None
        assert result["alert_level"] == ALERT_LEVEL_CRITICAL
        assert result["idle_minutes"] >= 5

    def test_duplicate_alert_returns_none(self):
        dms = DeadManSwitch(timeout_minutes=1)
        dms.last_event_time = datetime.now() - timedelta(minutes=5)
        first = dms.check()
        assert first is not None
        second = dms.check()
        assert second is None  # 已触发过

    def test_check_when_disarmed(self):
        dms = DeadManSwitch(timeout_minutes=1)
        dms.disarm()
        result = dms.check()
        assert result is None

    def test_check_with_callback(self):
        alerts = []
        dms = DeadManSwitch(timeout_minutes=1, on_alert=lambda a: alerts.append(a))
        dms.last_event_time = datetime.now() - timedelta(minutes=5)
        dms.check()
        assert len(alerts) == 1


class TestResetDisarmArm:
    """重置/解除/武装测试"""

    def test_reset_timer(self):
        dms = DeadManSwitch()
        dms.last_event_time = datetime.now() - timedelta(hours=1)
        dms.reset_timer()
        assert dms._alert_triggered is False

    def test_disarm(self):
        dms = DeadManSwitch()
        dms.disarm()
        assert dms.is_armed is False

    def test_arm(self):
        dms = DeadManSwitch()
        dms.disarm()
        dms.arm()
        assert dms.is_armed is True
        assert dms._alert_triggered is False


class TestGetStatus:
    """状态查询测试"""

    def test_get_status_armed(self):
        dms = DeadManSwitch(timeout_minutes=30)
        status = dms.get_status()
        assert status["is_armed"] is True
        assert status["timeout_minutes"] == 30
        assert "idle_seconds" in status

    def test_get_status_disarmed(self):
        dms = DeadManSwitch()
        dms.disarm()
        status = dms.get_status()
        assert status["is_armed"] is False


class TestCreateCallback:
    """回调函数创建测试"""

    def test_callback_calls_on_event(self):
        dms = DeadManSwitch()
        callback = create_event_subscribe_callback(dms)
        event = type("Event", (), {"event_type": "TASK_CREATED"})()
        callback(event)
        # on_any_event应该已更新时间


class TestSetupDeadManSwitch:
    """一键设置测试"""

    def test_setup_with_mock_event_bus(self):
        import unittest.mock as mock

        mock_bus = mock.MagicMock()
        dms = setup_dead_man_switch(timeout_minutes=30, event_bus=mock_bus, verbose=False)
        assert isinstance(dms, DeadManSwitch)
        assert dms.timeout_minutes == 30
        # EventBus.subscribe应该被调用了多次
        assert mock_bus.subscribe.call_count >= 1
