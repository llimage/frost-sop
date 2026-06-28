"""
FROST V5.0 P4: 生命周期元数据层 (Lifecycle Metadata Layer)

PHILOSOPHY: 武器的生命周期不是简单的状态机——它是一部"编年史"。
每次状态变更都有原因、有时间、有操作者。
预置武器有"免死金牌"，批量操作有安全阀。
生命周期元数据层让武器流转可追溯、可审计、可回滚。

本模块提供：
1. LifecycleEventLog    — 生命周期事件日志（审计追溯）
2. TransitionGuard      — 状态转换守卫（规则验证 + 预置保护）
3. BatchLifecycleManager — 批量生命周期管理器
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Tuple
from enum import Enum
from collections import deque


# ────────────────────────────────────────────────────────────────────────────
# 生命周期事件
# ────────────────────────────────────────────────────────────────────────────

class LifecycleEventType(Enum):
    """生命周期事件类型"""
    STATE_TRANSITION = "state_transition"    # 状态转换
    REGISTERED = "registered"                # 注册
    UNREGISTERED = "unregistered"            # 注销
    USAGE_RECORDED = "usage_recorded"        # 使用记录
    HEALTH_UPDATED = "health_updated"        # 健康评分更新
    VERSION_CHANGED = "version_changed"      # 版本变更
    BATCH_OPERATION = "batch_operation"      # 批量操作


@dataclass
class LifecycleEvent:
    """生命周期事件记录"""
    event_id: str                          # 事件唯一ID
    weapon_id: str                         # 武器ID
    event_type: LifecycleEventType         # 事件类型
    timestamp: str                         # ISO 时间戳
    from_state: str = ""                   # 原状态
    to_state: str = ""                     # 新状态
    reason: str = ""                       # 变更原因
    operator: str = "system"               # 操作者
    metadata: Dict = field(default_factory=dict)  # 额外元数据

    def to_dict(self) -> Dict:
        return {
            "event_id": self.event_id,
            "weapon_id": self.weapon_id,
            "event_type": self.event_type.value,
            "timestamp": self.timestamp,
            "from_state": self.from_state,
            "to_state": self.to_state,
            "reason": self.reason,
            "operator": self.operator,
            "metadata": self.metadata,
        }


# ────────────────────────────────────────────────────────────────────────────
# 生命周期事件日志
# ────────────────────────────────────────────────────────────────────────────

class LifecycleEventLog:
    """
    生命周期事件日志——记录武器的完整生命周期事件。

    功能：
    - 记录每次状态变更（含原因、操作者）
    - 按武器ID查询事件历史
    - 按事件类型筛选
    - 审计追溯（谁在什么时候对哪把武器做了什么）
    """

    MAX_EVENTS = 1000  # 最多保留1000条事件

    def __init__(self):
        self._events: deque = deque(maxlen=self.MAX_EVENTS)
        self._counter = 0

    def _generate_id(self) -> str:
        self._counter += 1
        return f"evt_{self._counter:06d}"

    def log(self, weapon_id: str, event_type: LifecycleEventType,
            from_state: str = "", to_state: str = "",
            reason: str = "", operator: str = "system",
            metadata: Dict = None) -> LifecycleEvent:
        """记录一条生命周期事件"""
        event = LifecycleEvent(
            event_id=self._generate_id(),
            weapon_id=weapon_id,
            event_type=event_type,
            timestamp=datetime.now().isoformat(),
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            operator=operator,
            metadata=metadata or {},
        )
        self._events.append(event)
        return event

    def get_by_weapon(self, weapon_id: str) -> List[LifecycleEvent]:
        """获取指定武器的所有事件"""
        return [e for e in self._events if e.weapon_id == weapon_id]

    def get_by_type(self, event_type: LifecycleEventType) -> List[LifecycleEvent]:
        """获取指定类型的所有事件"""
        return [e for e in self._events if e.event_type == event_type]

    def get_recent(self, n: int = 10) -> List[LifecycleEvent]:
        """获取最近N条事件"""
        return list(self._events)[-n:]

    def get_timeline(self, weapon_id: str) -> List[Dict]:
        """获取武器的时间线（按时间正序）"""
        events = self.get_by_weapon(weapon_id)
        events.sort(key=lambda e: e.timestamp)
        return [e.to_dict() for e in events]

    def get_state_history(self, weapon_id: str) -> List[Tuple[str, str, str]]:
        """
        获取武器状态变更历史。

        Returns:
            [(timestamp, from_state, to_state), ...]
        """
        events = self.get_by_weapon(weapon_id)
        events = [e for e in events if e.event_type == LifecycleEventType.STATE_TRANSITION]
        events.sort(key=lambda e: e.timestamp)
        return [(e.timestamp, e.from_state, e.to_state) for e in events]

    def count(self) -> int:
        """事件总数"""
        return len(self._events)

    def count_by_weapon(self, weapon_id: str) -> int:
        """指定武器的事件数"""
        return len(self.get_by_weapon(weapon_id))

    def clear(self):
        """清空日志"""
        self._events.clear()
        self._counter = 0

    def to_dict(self) -> List[Dict]:
        """序列化"""
        return [e.to_dict() for e in self._events]


# ────────────────────────────────────────────────────────────────────────────
# 状态转换守卫
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class GuardResult:
    """守卫检查结果"""
    allowed: bool
    reason: str
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "warnings": self.warnings,
        }


class TransitionGuard:
    """
    状态转换守卫——验证状态转换是否合法。

    比 WeaponLifecycle._check_transition_rules 更强大：
    1. 支持预置武器保护规则
    2. 支持自定义守卫规则
    3. 返回详细的拒绝原因和警告
    4. 支持批量验证
    """

    # 有效状态转换映射
    VALID_TRANSITIONS = {
        "discovered": {"validated", "retired"},
        "validated": {"trialed", "archived", "retired"},
        "trialed": {"archived", "retired"},
        "archived": {"active", "deprecated", "retired"},
        "active": {"deprecated", "retired"},
        "deprecated": {"active", "retired"},
        "retired": set(),  # 终态，不可转换
    }

    def __init__(self, registry):
        self.registry = registry

    def check(self, weapon_id: str, to_state: str) -> GuardResult:
        """
        检查状态转换是否允许。

        Args:
            weapon_id: 武器ID
            to_state: 目标状态（字符串值）

        Returns:
            GuardResult 检查结果
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return GuardResult(allowed=False, reason=f"武器不存在: {weapon_id}")

        from_state = weapon.state.value

        # 相同状态无需转换
        if from_state == to_state:
            return GuardResult(allowed=True, reason="状态相同，无需转换")

        # 检查转换是否在允许的映射中
        allowed_targets = self.VALID_TRANSITIONS.get(from_state, set())
        if to_state not in allowed_targets:
            return GuardResult(
                allowed=False,
                reason=f"无效转换: {from_state} → {to_state}。允许的目标: {allowed_targets or '无（终态）'}"
            )

        warnings = []

        # 预置武器保护
        if weapon.is_preset and to_state == "retired":
            return GuardResult(
                allowed=False,
                reason=f"预置武器 {weapon_id} 不可退役",
                warnings=["预置武器有免死金牌，不可自动或手动退役"]
            )

        # 激活条件检查
        if to_state == "active":
            if weapon.health_score < 30:
                return GuardResult(
                    allowed=False,
                    reason=f"激活条件不满足：健康评分 {weapon.health_score} < 30",
                )
            if from_state != "archived":
                warnings.append(f"非标准激活路径: {from_state} → active（通常 archived → active）")

        # 试炼条件检查
        if to_state == "trialed":
            if weapon.usage_count < 1:
                warnings.append(f"试炼条件建议: usage_count({weapon.usage_count}) < 1，建议先运行至少1次")

        # 退役不可逆警告
        if to_state == "retired":
            warnings.append("退役是不可逆操作，武器将永久不可用")

        # 废弃后复活检查
        if from_state == "deprecated" and to_state == "active":
            warnings.append("废弃武器复活，建议先验证健康评分")

        return GuardResult(
            allowed=True,
            reason=f"转换允许: {from_state} → {to_state}",
            warnings=warnings,
        )

    def check_batch(self, transitions: List[Tuple[str, str]]) -> Dict[str, GuardResult]:
        """
        批量检查状态转换。

        Args:
            transitions: [(weapon_id, to_state), ...]

        Returns:
            {weapon_id: GuardResult}
        """
        results = {}
        for weapon_id, to_state in transitions:
            results[weapon_id] = self.check(weapon_id, to_state)
        return results

    def get_allowed_transitions(self, weapon_id: str) -> List[str]:
        """获取武器当前允许的转换目标"""
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return []
        from_state = weapon.state.value
        allowed = list(self.VALID_TRANSITIONS.get(from_state, set()))

        # 过滤掉预置武器不能去的退役
        if weapon.is_preset:
            allowed = [s for s in allowed if s != "retired"]

        return sorted(allowed)

    def is_terminal_state(self, state: str) -> bool:
        """是否为终态（不可再转换）"""
        return state == "retired"


# ────────────────────────────────────────────────────────────────────────────
# 批量生命周期管理器
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class BatchResult:
    """批量操作结果"""
    operation: str                          # 操作类型
    total: int                              # 总数
    succeeded: int                          # 成功数
    failed: int                             # 失败数
    skipped: int                            # 跳过数
    details: List[Dict] = field(default_factory=list)  # 详细结果

    def to_dict(self) -> Dict:
        return {
            "operation": self.operation,
            "total": self.total,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "skipped": self.skipped,
            "details": self.details,
        }


class BatchLifecycleManager:
    """
    批量生命周期管理器——对多个武器执行批量生命周期操作。

    安全措施：
    1. 每个操作都经过 TransitionGuard 验证
    2. 预置武器自动跳过危险操作
    3. 批量大小限制（默认50）
    4. 每个操作都记录到事件日志
    """

    MAX_BATCH_SIZE = 50

    def __init__(self, registry, event_log: Optional[LifecycleEventLog] = None):
        self.registry = registry
        self.event_log = event_log or LifecycleEventLog()
        self.guard = TransitionGuard(registry)

    def batch_transition(self, weapon_ids: List[str], to_state: str,
                         reason: str = "", operator: str = "system") -> BatchResult:
        """
        批量状态转换。

        Args:
            weapon_ids: 武器ID列表
            to_state: 目标状态
            reason: 转换原因
            operator: 操作者

        Returns:
            BatchResult 批量结果
        """
        if len(weapon_ids) > self.MAX_BATCH_SIZE:
            return BatchResult(
                operation="batch_transition",
                total=len(weapon_ids), succeeded=0, failed=0, skipped=0,
                details=[{"error": f"批量大小超过限制: {len(weapon_ids)} > {self.MAX_BATCH_SIZE}"}]
            )

        from core.armory import WeaponState
        try:
            target_state = WeaponState(to_state)
        except ValueError:
            return BatchResult(
                operation="batch_transition",
                total=len(weapon_ids), succeeded=0, failed=0, skipped=len(weapon_ids),
                details=[{"error": f"无效状态: {to_state}"}]
            )

        succeeded = 0
        failed = 0
        skipped = 0
        details = []

        for weapon_id in weapon_ids:
            weapon = self.registry.get(weapon_id)
            if not weapon:
                skipped += 1
                details.append({"weapon_id": weapon_id, "status": "skipped", "reason": "武器不存在"})
                continue

            # 守卫检查
            guard_result = self.guard.check(weapon_id, to_state)
            if not guard_result.allowed:
                failed += 1
                details.append({
                    "weapon_id": weapon_id, "status": "failed",
                    "reason": guard_result.reason
                })
                continue

            # 执行转换
            from_state = weapon.state.value
            try:
                self.registry.update_status(weapon_id, target_state)

                # 记录事件
                self.event_log.log(
                    weapon_id=weapon_id,
                    event_type=LifecycleEventType.STATE_TRANSITION,
                    from_state=from_state,
                    to_state=to_state,
                    reason=reason,
                    operator=operator,
                )

                succeeded += 1
                details.append({
                    "weapon_id": weapon_id, "status": "succeeded",
                    "from": from_state, "to": to_state
                })
            except Exception as e:
                failed += 1
                details.append({
                    "weapon_id": weapon_id, "status": "failed",
                    "reason": str(e)
                })

        return BatchResult(
            operation="batch_transition",
            total=len(weapon_ids),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            details=details,
        )

    def batch_retire_low_health(self, threshold: float = 20.0,
                                 operator: str = "system") -> BatchResult:
        """
        批量退役低健康评分武器（跳过预置武器）。

        Args:
            threshold: 健康评分阈值，低于此值退役
            operator: 操作者

        Returns:
            BatchResult
        """
        candidates = []
        for weapon in self.registry.list_all():
            if weapon.is_preset:
                continue
            if weapon.health_score < threshold:
                candidates.append(weapon.id)

        return self.batch_transition(
            candidates, "retired",
            reason=f"健康评分低于{threshold}，自动退役",
            operator=operator,
        )

    def batch_activate_archived(self, operator: str = "system") -> BatchResult:
        """
        批量激活已归档且健康的武器。

        Args:
            operator: 操作者

        Returns:
            BatchResult
        """
        from core.armory import WeaponState
        candidates = []
        for weapon in self.registry.list_all(state=WeaponState.ARCHIVED):
            if weapon.health_score >= 30:
                candidates.append(weapon.id)

        return self.batch_transition(
            candidates, "active",
            reason="归档武器健康评分达标，批量激活",
            operator=operator,
        )

    def get_lifecycle_report(self, weapon_id: str) -> Dict:
        """
        生成武器的生命周期报告。

        Args:
            weapon_id: 武器ID

        Returns:
            生命周期报告字典
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return {"error": "武器不存在"}

        timeline = self.event_log.get_timeline(weapon_id)
        state_history = self.event_log.get_state_history(weapon_id)
        allowed_transitions = self.guard.get_allowed_transitions(weapon_id)

        return {
            "weapon_id": weapon_id,
            "weapon_name": weapon.name,
            "current_state": weapon.state.value,
            "is_preset": weapon.is_preset,
            "health_score": weapon.health_score,
            "usage_count": weapon.usage_count,
            "success_rate": weapon.success_rate,
            "created_at": weapon.created_at,
            "allowed_transitions": allowed_transitions,
            "is_terminal": self.guard.is_terminal_state(weapon.state.value),
            "event_count": self.event_log.count_by_weapon(weapon_id),
            "state_change_count": len(state_history),
            "timeline": timeline,
        }
