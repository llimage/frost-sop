"""
core/monitor.py 单元测试

测试 @monitor 装饰器和 PerfStats 聚合器。
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FROST_TESTING", "1")

import pytest

from core.monitor import PerfStats, get_perf_stats, monitor


class TestPerfStats:
    """测试 PerfStats 性能统计聚合器"""

    def setup_method(self):
        get_perf_stats().reset()

    def test_initial_empty(self):
        stats = PerfStats()
        assert stats.summary() == "No performance records."

    def test_record_single(self):
        stats = PerfStats()
        stats.record("test_fn", 15.5)
        summary = stats.summary()
        assert "test_fn" in summary
        assert "15.5ms" in summary

    def test_record_multiple(self):
        stats = PerfStats()
        for _ in range(5):
            stats.record("fn_a", 10.0)
        for _ in range(3):
            stats.record("fn_b", 30.0)

        summary = stats.summary()
        assert "fn_a" in summary
        assert "fn_b" in summary

    def test_reset(self):
        stats = PerfStats()
        stats.record("fn", 100.0)
        stats.reset()
        assert stats.summary() == "No performance records."

    def test_top_n_limits(self):
        stats = PerfStats()
        for i in range(25):
            stats.record(f"fn_{i:02d}", float(i))
        summary = stats.summary(top_n=5)
        lines = [l for l in summary.split("\n") if l.strip()]
        # top_n=5 = 5 data rows + 1-2 header rows
        assert len(lines) <= 10

    def test_global_singleton(self):
        s1 = get_perf_stats()
        s2 = get_perf_stats()
        assert s1 is s2


class TestMonitorDecorator:
    """测试 @monitor 装饰器"""

    def setup_method(self):
        get_perf_stats().reset()

    def test_decorator_records_time(self):
        @monitor()
        def slow_fn():
            time.sleep(0.01)
            return 42

        result = slow_fn()
        assert result == 42

        summary = get_perf_stats().summary()
        assert "slow_fn" in summary

    def test_decorator_no_parens(self):
        """@monitor 不带括号会报错 — monitor 需要括号调用"""

        @monitor  # noqa: type-ignore
        def quick_fn():
            return "ok"

        with pytest.raises(TypeError):
            quick_fn()

    def test_decorator_custom_name(self):
        @monitor("custom_name")
        def foo():
            pass

        foo()
        summary = get_perf_stats().summary()
        assert "custom_name" in summary

    def test_decorator_exception_propagates(self):
        @monitor()
        def failing_fn():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            failing_fn()
        # 即使异常也应该记录时间
        summary = get_perf_stats().summary()
        assert "failing_fn" in summary

    def test_decorator_method(self):
        class MyClass:
            @monitor()
            def method(self):
                return self

        obj = MyClass()
        result = obj.method()
        assert result is obj
