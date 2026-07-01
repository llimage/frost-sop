"""
FROST-SOP 性能监控模块。

提供 @monitor 装饰器用于关键函数性能计时，以及 PerfStats 统计聚合。

Usage:
    from core.monitor import monitor, get_perf_stats

    @monitor("orchestration.execute_stage")
    def execute_stage(...):
        ...

    stats = get_perf_stats()
    print(stats.summary())
"""

from __future__ import annotations

import time
from collections import defaultdict
from functools import wraps
from threading import Lock
from typing import Any, Callable


class PerfStats:
    """性能统计聚合器（线程安全）。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._records: dict[str, list[float]] = defaultdict(list)

    def record(self, name: str, elapsed_ms: float) -> None:
        """记录一次调用耗时（毫秒）。"""
        with self._lock:
            self._records[name].append(elapsed_ms)

    def summary(self, top_n: int = 20) -> str:
        """生成性能摘要报告。"""
        with self._lock:
            if not self._records:
                return "No performance records."

            lines = ["Performance Summary", "=" * 60]
            sorted_items = sorted(
                self._records.items(),
                key=lambda x: sum(x[1]) / len(x[1]),
                reverse=True,
            )
            for name, times in sorted_items[:top_n]:
                avg = sum(times) / len(times)
                max_t = max(times)
                min_t = min(times)
                lines.append(
                    f"  {name:<45} calls={len(times):>5}  "
                    f"avg={avg:>8.1f}ms  max={max_t:>8.1f}ms  min={min_t:>8.1f}ms"
                )
            return "\n".join(lines)

    def reset(self) -> None:
        """重置所有统计。"""
        with self._lock:
            self._records.clear()


# 全局单例
_perf_stats = PerfStats()


def get_perf_stats() -> PerfStats:
    """获取全局性能统计实例。"""
    return _perf_stats


def monitor(name: str | None = None) -> Callable:
    """
    性能监控装饰器。

    Args:
        name: 监控名称（默认使用函数限定名）。

    Example:
        @monitor("db.query")
        def query(sql: str) -> list:
            ...
    """

    def decorator(func: Callable) -> Callable:
        monitor_name = name or f"{func.__module__}.{func.__qualname__}"

        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = (time.perf_counter() - start) * 1000
                _perf_stats.record(monitor_name, elapsed)

        return wrapper

    return decorator
