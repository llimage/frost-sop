"""
V7 阶段3 覆盖率补测试 — core/notifier.py (66% → 85%+)
桌面通知模块
"""

import os
import sys
from datetime import datetime, timedelta

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.notifier import (
    check_decision_timeout,
    send_timeout_notification,
    send_windows_notification,
)


class TestCheckDecisionTimeout:
    """决策超时检查测试"""

    def test_old_decision_is_timeout(self):
        old_time = datetime.now() - timedelta(hours=2)
        result = check_decision_timeout(old_time, timeout_seconds=3600)
        assert result is True

    def test_recent_decision_not_timeout(self):
        recent_time = datetime.now() - timedelta(minutes=30)
        result = check_decision_timeout(recent_time, timeout_seconds=3600)
        assert result is False

    def test_iso_string_old(self):
        old_time = (datetime.now() - timedelta(hours=2)).isoformat()
        result = check_decision_timeout(old_time, timeout_seconds=3600)
        assert result is True

    def test_iso_string_recent(self):
        recent_time = datetime.now().isoformat()
        result = check_decision_timeout(recent_time, timeout_seconds=3600)
        assert result is False

    def test_invalid_string_no_timeout(self):
        result = check_decision_timeout("invalid-date", timeout_seconds=3600)
        assert result is False

    def test_exact_boundary(self):
        boundary_time = datetime.now() - timedelta(seconds=3600)
        result = check_decision_timeout(boundary_time, timeout_seconds=3600)
        # 刚好等于超时时间
        assert result is True

    def test_custom_timeout(self):
        recent_time = datetime.now() - timedelta(minutes=5)
        result = check_decision_timeout(recent_time, timeout_seconds=600)
        assert result is False


class TestSendWindowsNotification:
    """桌面通知发送测试"""

    def test_notification_fallback(self):
        """没有通知库时降级为print"""
        import unittest.mock as mock

        # mock两个通知库都 ImportError
        with mock.patch.dict("sys.modules", {"win10toast": None, "plyer": None}):
            result = send_windows_notification("标题", "内容", duration=5)
            assert result is False  # 降级模式返回False

    def test_notification_with_win10toast(self):
        """使用win10toast成功"""
        import unittest.mock as mock

        mock_toast = mock.MagicMock()
        mock_toast.show_toast.return_value = None

        with mock.patch.dict(
            "sys.modules",
            {"win10toast": mock.MagicMock(ToastNotifier=mock.MagicMock(return_value=mock_toast))},
        ):
            result = send_windows_notification("标题", "内容")
            assert result is True


class TestSendTimeoutNotification:
    """超时通知测试"""

    def test_timeout_notification(self):
        """调用send_timeout_notification"""
        import unittest.mock as mock

        with mock.patch("core.notifier.send_windows_notification", return_value=True):
            result = send_timeout_notification("d-001", "task-001", "stage-001")
            assert result is True
