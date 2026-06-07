"""
tests/test_logger.py - 日志标准化测试
Solo-Ops-Platform V0.9.0

覆盖：init_logging、get_logger、sanitize_message、_SensitiveFilter
"""
import pytest
import logging
from unittest.mock import patch, MagicMock


class TestSanitizeMessage:
    """敏感信息过滤测试。"""

    def test_sanitize_api_key(self):
        """API Key 过滤。"""
        from config.logger import sanitize_message
        msg = "使用 sk-abc123def456 调用 API"
        result = sanitize_message(msg)
        assert "sk-abc123def456" not in result
        assert "****" in result

    def test_sanitize_bearer_token(self):
        """Bearer Token 过滤。"""
        from config.logger import sanitize_message
        msg = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9"
        result = sanitize_message(msg)
        assert "eyJhbGciOiJIUzI1NiJ9" not in result
        assert "Bearer ****" in result

    def test_sanitize_password(self):
        """密码字段过滤。"""
        from config.logger import sanitize_message
        msg = "password=MySecret123"
        result = sanitize_message(msg)
        assert "MySecret123" not in result
        assert "****" in result

    def test_sanitize_passwd_variant(self):
        """passwd 变体过滤。"""
        from config.logger import sanitize_message
        msg = "passwd: test1234"
        result = sanitize_message(msg)
        assert "test1234" not in result

    def test_sanitize_preserves_normal_text(self):
        """普通文本不过滤。"""
        from config.logger import sanitize_message
        msg = "这是一个普通日志消息"
        result = sanitize_message(msg)
        assert result == msg

    def test_sanitize_empty_string(self):
        """空字符串处理。"""
        from config.logger import sanitize_message
        assert sanitize_message("") == ""
        assert sanitize_message(None) is None

    def test_sanitize_api_key_in_url(self):
        """URL 中的 API Key 过滤。"""
        from config.logger import sanitize_message
        msg = "请求 https://api.example.com?key=sk-abc123def456"
        result = sanitize_message(msg)
        assert "sk-abc123def456" not in result


class TestGetLogger:
    """Logger 获取测试。"""

    def test_get_logger_returns_logger(self):
        """get_logger 返回 Logger 实例。"""
        from config.logger import get_logger
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_get_logger_different_names(self):
        """不同名称返回不同 logger。"""
        from config.logger import get_logger
        logger1 = get_logger("module_a")
        logger2 = get_logger("module_b")
        assert logger1 is not logger2
        assert logger1.name != logger2.name


class TestInitLogging:
    """日志初始化测试。"""

    def test_init_logging_creates_handlers(self):
        """初始化后应有 handler。"""
        from config.logger import init_logging, _initialized
        # 重置初始化标记
        import config.logger
        config.logger._initialized = False

        # 清除已有 handlers
        root = logging.getLogger()
        root.handlers.clear()

        init_logging(level=logging.DEBUG, console=True)

        assert len(root.handlers) >= 1
        # 恢复
        root.handlers.clear()
        config.logger._initialized = False

    def test_init_logging_idempotent(self):
        """重复初始化不会创建重复 handler。"""
        from config.logger import init_logging
        import config.logger

        config.logger._initialized = False
        root = logging.getLogger()
        root.handlers.clear()

        init_logging(console=True)
        count_after_first = len(root.handlers)

        init_logging(console=True)
        count_after_second = len(root.handlers)

        assert count_after_first == count_after_second

        # 恢复
        root.handlers.clear()
        config.logger._initialized = False


class TestSensitiveFilter:
    """_SensitiveFilter 过滤器测试。"""

    def test_filter_sanitizes_record_msg(self):
        """过滤器处理 LogRecord 的 msg。"""
        from config.logger import _SensitiveFilter
        f = _SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="API Key: sk-abc123def456", args=None, exc_info=None,
        )
        f.filter(record)
        assert "sk-abc123def456" not in record.msg

    def test_filter_sanitizes_dict_args(self):
        """过滤器处理 dict 类型的 args。"""
        from config.logger import _SensitiveFilter
        f = _SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Message", args=None, exc_info=None,
        )
        # 手动设置 args 为 dict（模拟 % 格式化的 dict 参数）
        record.args = {"key": "sk-abc123def456"}
        f.filter(record)
        assert "sk-abc123def456" not in str(record.args)

    def test_filter_sanitizes_tuple_args(self):
        """过滤器处理 tuple 类型的 args。"""
        from config.logger import _SensitiveFilter
        f = _SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="Key: %s", args=("sk-abc123def456",), exc_info=None,
        )
        f.filter(record)
        assert "sk-abc123def456" not in str(record.args)

    def test_filter_returns_true(self):
        """过滤器始终返回 True（不过滤日志记录）。"""
        from config.logger import _SensitiveFilter
        f = _SensitiveFilter()
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="", lineno=0,
            msg="normal message", args=None, exc_info=None,
        )
        assert f.filter(record) is True
