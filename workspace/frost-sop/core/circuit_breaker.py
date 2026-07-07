"""
FROST-SOP 断路器 (Circuit Breaker)

当 LLM 调用连续失败超过阈值时自动熔断，避免无效 token 消耗。
三态：CLOSED(正常) → OPEN(熔断) → HALF_OPEN(探测) → CLOSED(恢复)

设计原则：
- 按 agent_id 隔离，一个 agent 熔断不影响其他 agent
- 线程安全（Lock 保护）
- 可观测：get_all_breaker_status() 查看全局状态
- 可配置：CircuitConfig 支持自定义阈值
"""

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Lock


class CircuitState(Enum):
    """断路器三态。"""

    CLOSED = "closed"  # 正常运行
    OPEN = "open"  # 熔断中，拒绝所有调用
    HALF_OPEN = "half_open"  # 半开，允许少量探测


@dataclass
class CircuitConfig:
    """断路器配置。"""

    failure_threshold: int = 5  # 连续失败 N 次后熔断
    recovery_timeout: float = 60.0  # 熔断后等待 N 秒才尝试恢复
    half_open_max_calls: int = 3  # 半开状态最多允许 N 次探测
    success_threshold: int = 2  # 半开状态连续成功 N 次后恢复


@dataclass
class CircuitBreaker:
    """单个 agent 的断路器。

    状态流转：
        CLOSED --连续失败--> OPEN --超时--> HALF_OPEN --成功--> CLOSED
                                                  --失败--> OPEN
    """

    agent_id: str
    config: CircuitConfig = field(default_factory=CircuitConfig)
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: float = 0.0
    half_open_calls: int = 0
    _lock: Lock = field(default_factory=Lock)

    def can_call(self) -> tuple[bool, str]:
        """检查是否允许调用。

        Returns:
            (allowed, reason): 允许=True / 拒绝=False，附带原因说明
        """
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True, "circuit_closed"

            if self.state == CircuitState.OPEN:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.config.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_calls = 0
                    self.success_count = 0
                    return True, "circuit_half_open"
                remaining = int(self.config.recovery_timeout - elapsed)
                return False, f"circuit_open(wait {remaining}s)"

            # HALF_OPEN
            if self.half_open_calls < self.config.half_open_max_calls:
                self.half_open_calls += 1
                return True, "circuit_half_open_probe"
            return False, "circuit_half_open_max_reached"

    def record_success(self):
        """记录一次成功调用。"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self._reset_to_closed()
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self):
        """记录一次失败调用。"""
        with self._lock:
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.failure_count += 1
            elif self.state == CircuitState.CLOSED:
                self.failure_count += 1
                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN

    def force_reset(self):
        """强制重置为关闭状态（管理操作）。"""
        with self._lock:
            self._reset_to_closed()

    def get_status(self) -> dict:
        """获取断路器状态快照。"""
        with self._lock:
            return {
                "agent_id": self.agent_id,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "half_open_calls": self.half_open_calls,
                "last_failure_time": datetime.fromtimestamp(
                    self.last_failure_time, tz=timezone.utc
                ).isoformat()
                if self.last_failure_time
                else None,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "recovery_timeout": self.config.recovery_timeout,
                    "half_open_max_calls": self.config.half_open_max_calls,
                    "success_threshold": self.config.success_threshold,
                },
            }

    def _reset_to_closed(self):
        """重置到 CLOSED 状态（内部方法，调用方需持锁）。"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.half_open_calls = 0


# ── 全局断路器注册表 ──────────────────────────────────────────────────
_breakers: dict[str, CircuitBreaker] = {}
_breakers_lock = Lock()


def get_circuit_breaker(agent_id: str, config: CircuitConfig | None = None) -> CircuitBreaker:
    """获取或创建 agent 的断路器。

    Args:
        agent_id: Agent 标识
        config: 可选配置，仅在首次创建时生效

    Returns:
        该 agent 的断路器实例
    """
    with _breakers_lock:
        if agent_id not in _breakers:
            _breakers[agent_id] = CircuitBreaker(
                agent_id=agent_id,
                config=config or CircuitConfig(),
            )
        return _breakers[agent_id]


def get_all_breaker_status() -> list[dict]:
    """获取所有断路器状态（用于监控面板）。"""
    with _breakers_lock:
        return [cb.get_status() for cb in _breakers.values()]


def reset_all_breakers():
    """重置所有断路器（用于测试或管理操作）。"""
    with _breakers_lock:
        _breakers.clear()


def reset_breaker(agent_id: str):
    """重置指定 agent 的断路器。"""
    with _breakers_lock:
        if agent_id in _breakers:
            _breakers[agent_id].force_reset()


class CircuitOpenError(Exception):
    """断路器熔断异常。"""

    pass
