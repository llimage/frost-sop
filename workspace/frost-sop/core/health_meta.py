"""
FROST V5.0 P3: 健康元数据层 (Health Metadata Layer)

PHILOSOPHY: 武器有"健康史"——不是一次评分定终身。
一把武器可能刚开始表现差，但随版本迭代越来越好；
也可能曾经是主力，但随时间推移逐渐被遗忘。
健康元数据层记录这些变化，驱动自然选择。

本模块提供：
1. HealthHistory        — 健康评分历史记录与趋势分析
2. NaturalSelectionEngine — 自然选择引擎（自动废弃/退役/晋升）
3. HealthRanker         — 健康排名器（多维排序）
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

# ────────────────────────────────────────────────────────────────────────────
# 健康趋势
# ────────────────────────────────────────────────────────────────────────────


class HealthTrend(Enum):
    """健康趋势方向"""

    IMPROVING = "improving"  # 上升
    STABLE = "stable"  # 稳定
    DECLINING = "declining"  # 下降
    VOLATILE = "volatile"  # 波动
    NEW = "new"  # 新武器，数据不足


# ────────────────────────────────────────────────────────────────────────────
# 健康历史记录
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class HealthSnapshot:
    """健康评分快照"""

    timestamp: str  # ISO 格式时间戳
    health_score: float  # 健康评分
    usage_count: int  # 使用次数
    success_count: int  # 成功次数
    failure_count: int  # 失败次数
    weapon_state: str  # 当时武器状态

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "health_score": self.health_score,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "weapon_state": self.weapon_state,
        }


class HealthHistory:
    """
    健康评分历史——记录武器评分随时间的变化。

    每次武器被使用或状态变更时，可以记录一个快照。
    历史数据用于趋势分析和自然选择决策。
    """

    MAX_SNAPSHOTS = 100  # 最多保留100个快照

    def __init__(self):
        self._snapshots: deque = deque(maxlen=self.MAX_SNAPSHOTS)

    def record(
        self,
        health_score: float,
        usage_count: int = 0,
        success_count: int = 0,
        failure_count: int = 0,
        weapon_state: str = "active",
    ) -> None:
        """记录一个健康快照"""
        snapshot = HealthSnapshot(
            timestamp=datetime.now().isoformat(),
            health_score=health_score,
            usage_count=usage_count,
            success_count=success_count,
            failure_count=failure_count,
            weapon_state=weapon_state,
        )
        self._snapshots.append(snapshot)

    def get_all(self) -> list[HealthSnapshot]:
        """获取所有快照"""
        return list(self._snapshots)

    def get_recent(self, n: int = 10) -> list[HealthSnapshot]:
        """获取最近N个快照"""
        return list(self._snapshots)[-n:]

    def get_trend(self) -> HealthTrend:
        """
        分析健康趋势。

        判断逻辑：
        - 少于3个快照 → NEW
        - 最近5个快照评分方差大 → VOLATILE
        - 最近5个快照评分持续上升 → IMPROVING
        - 最近5个快照评分持续下降 → DECLINING
        - 其他 → STABLE
        """
        if len(self._snapshots) < 3:
            return HealthTrend.NEW

        recent = list(self._snapshots)[-5:]
        scores = [s.health_score for s in recent]

        # 计算方差判断波动
        if len(scores) >= 3:
            mean = sum(scores) / len(scores)
            variance = sum((s - mean) ** 2 for s in scores) / len(scores)
            std_dev = math.sqrt(variance)
            if std_dev > 15:  # 标准差>15视为波动
                return HealthTrend.VOLATILE

        # 判断趋势方向
        increasing = all(scores[i] <= scores[i + 1] + 2 for i in range(len(scores) - 1))
        decreasing = all(scores[i] >= scores[i + 1] - 2 for i in range(len(scores) - 1))

        if increasing and scores[-1] > scores[0] + 5:
            return HealthTrend.IMPROVING
        if decreasing and scores[-1] < scores[0] - 5:
            return HealthTrend.DECLINING

        return HealthTrend.STABLE

    def get_average_score(self, window: int = 10) -> float:
        """获取最近N个快照的平均健康评分"""
        recent = self.get_recent(window)
        if not recent:
            return 0.0
        return sum(s.health_score for s in recent) / len(recent)

    def get_score_range(self, window: int = 10) -> tuple[float, float]:
        """获取最近N个快照的评分范围 (min, max)"""
        recent = self.get_recent(window)
        if not recent:
            return (0.0, 0.0)
        scores = [s.health_score for s in recent]
        return (min(scores), max(scores))

    def count(self) -> int:
        """快照数量"""
        return len(self._snapshots)

    def to_dict(self) -> list[dict]:
        """序列化"""
        return [s.to_dict() for s in self._snapshots]


# ────────────────────────────────────────────────────────────────────────────
# 自然选择引擎
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class SelectionDecision:
    """自然选择决策"""

    weapon_id: str
    action: str  # "promote" | "deprecate" | "retire" | "keep"
    reason: str
    current_score: float
    trend: str
    recommended_state: str = ""

    def to_dict(self) -> dict:
        return {
            "weapon_id": self.weapon_id,
            "action": self.action,
            "reason": self.reason,
            "current_score": self.current_score,
            "trend": self.trend,
            "recommended_state": self.recommended_state,
        }


class NaturalSelectionEngine:
    """
    自然选择引擎——基于健康评分和历史趋势自动决策武器生命周期。

    决策规则：
    1. health_score < 20 + 非预置 → RETIRE（退役）
    2. health_score 20-30 + 趋势下降 + 非预置 → DEPRECATE（废弃）
    3. health_score > 80 + 趋势上升 + 状态=ARCHIVED → PROMOTE（晋升为ACTIVE）
    4. 连续30天未使用 + 非预置 → DEPRECATE
    5. 其他 → KEEP（保持现状）
    """

    # 阈值配置
    RETIRE_THRESHOLD = 20.0
    DEPRECATE_THRESHOLD = 30.0
    PROMOTE_THRESHOLD = 80.0
    INACTIVITY_DAYS = 30

    def __init__(self, registry):
        self.registry = registry

    def evaluate(self, weapon_id: str, history: HealthHistory | None = None) -> SelectionDecision:
        """
        评估单个武器，返回自然选择决策。

        Args:
            weapon_id: 武器ID
            history: 健康历史（可选，如果没有则只看当前评分）

        Returns:
            SelectionDecision 决策
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return SelectionDecision(
                weapon_id=weapon_id,
                action="keep",
                reason="武器不存在",
                current_score=0,
                trend="unknown",
            )

        current_score = weapon.health_score
        trend = HealthTrend.NEW

        if history and history.count() >= 3:
            trend = history.get_trend()

        # 预置武器不自动淘汰
        if weapon.is_preset:
            if current_score < self.RETIRE_THRESHOLD:
                return SelectionDecision(
                    weapon_id=weapon_id,
                    action="keep",
                    reason="预置武器不自动淘汰",
                    current_score=current_score,
                    trend=trend.value,
                    recommended_state=weapon.state.value,
                )
            return SelectionDecision(
                weapon_id=weapon_id,
                action="keep",
                reason="预置武器",
                current_score=current_score,
                trend=trend.value,
                recommended_state=weapon.state.value,
            )

        # 规则1: 退役
        if current_score < self.RETIRE_THRESHOLD:
            return SelectionDecision(
                weapon_id=weapon_id,
                action="retire",
                reason=f"健康评分过低 ({current_score:.1f} < {self.RETIRE_THRESHOLD})",
                current_score=current_score,
                trend=trend.value,
                recommended_state="retired",
            )

        # 规则2: 废弃（低分+下降趋势）
        if current_score < self.DEPRECATE_THRESHOLD and trend == HealthTrend.DECLINING:
            return SelectionDecision(
                weapon_id=weapon_id,
                action="deprecate",
                reason=f"低评分且趋势下降 ({current_score:.1f}, {trend.value})",
                current_score=current_score,
                trend=trend.value,
                recommended_state="deprecated",
            )

        # 规则3: 晋升（高分+上升趋势+已归档）
        if (
            current_score > self.PROMOTE_THRESHOLD
            and trend == HealthTrend.IMPROVING
            and weapon.state.value == "archived"
        ):
            return SelectionDecision(
                weapon_id=weapon_id,
                action="promote",
                reason=f"高评分且趋势上升 ({current_score:.1f}, {trend.value})",
                current_score=current_score,
                trend=trend.value,
                recommended_state="active",
            )

        # 规则4: 不活跃废弃
        if weapon.last_used:
            try:
                last_used_date = datetime.fromisoformat(weapon.last_used)
                days_inactive = (datetime.now() - last_used_date).days
                if days_inactive >= self.INACTIVITY_DAYS:
                    return SelectionDecision(
                        weapon_id=weapon_id,
                        action="deprecate",
                        reason=f"连续{days_inactive}天未使用",
                        current_score=current_score,
                        trend=trend.value,
                        recommended_state="deprecated",
                    )
            except (ValueError, TypeError):
                pass

        # 规则5: 保持
        return SelectionDecision(
            weapon_id=weapon_id,
            action="keep",
            reason="当前状态良好",
            current_score=current_score,
            trend=trend.value,
            recommended_state=weapon.state.value,
        )

    def evaluate_all(
        self, histories: dict[str, HealthHistory] | None = None
    ) -> list[SelectionDecision]:
        """
        评估所有武器，批量返回决策。

        Args:
            histories: {weapon_id: HealthHistory} 映射

        Returns:
            决策列表
        """
        decisions = []
        histories = histories or {}
        for weapon in self.registry.list_all():
            history = histories.get(weapon.id)
            decision = self.evaluate(weapon.id, history)
            decisions.append(decision)
        return decisions

    def get_retirement_candidates(
        self, histories: dict[str, HealthHistory] | None = None
    ) -> list[str]:
        """获取需要退役的武器ID列表"""
        decisions = self.evaluate_all(histories)
        return [d.weapon_id for d in decisions if d.action == "retire"]

    def get_deprecation_candidates(
        self, histories: dict[str, HealthHistory] | None = None
    ) -> list[str]:
        """获取需要废弃的武器ID列表"""
        decisions = self.evaluate_all(histories)
        return [d.weapon_id for d in decisions if d.action == "deprecate"]

    def get_promotion_candidates(
        self, histories: dict[str, HealthHistory] | None = None
    ) -> list[str]:
        """获取可晋升的武器ID列表"""
        decisions = self.evaluate_all(histories)
        return [d.weapon_id for d in decisions if d.action == "promote"]


# ────────────────────────────────────────────────────────────────────────────
# 健康排名器
# ────────────────────────────────────────────────────────────────────────────


class HealthRanker:
    """
    健康排名器——按多维健康指标对武器排序。

    排序维度（按优先级）：
    1. 健康评分（降序）
    2. 使用次数（降序）
    3. 成功率（降序）
    4. 趋势（IMPROVING > STABLE > VOLATILE > DECLINING > NEW）
    """

    TREND_PRIORITY = {
        HealthTrend.IMPROVING: 4,
        HealthTrend.STABLE: 3,
        HealthTrend.VOLATILE: 2,
        HealthTrend.DECLINING: 1,
        HealthTrend.NEW: 0,
    }

    @classmethod
    def rank(
        cls,
        registry,
        weapon_type=None,
        top_k: int = 0,
        histories: dict[str, HealthHistory] | None = None,
    ) -> list[dict]:
        """
        对武器库中的武器进行健康排名。

        Args:
            registry: ArmoryRegistry 实例
            weapon_type: 可选类型过滤
            top_k: 返回前K名（0=全部）
            histories: 健康历史映射

        Returns:
            [{weapon, rank, score, trend}, ...] 排名列表
        """
        weapons = registry.list_all(weapon_type=weapon_type)
        histories = histories or {}

        def sort_key(w):
            trend = histories.get(w.id)
            trend_val = trend.get_trend() if trend else HealthTrend.NEW
            return (
                w.health_score,
                w.usage_count,
                w.success_rate or 0,
                cls.TREND_PRIORITY.get(trend_val, 0),
            )

        weapons.sort(key=sort_key, reverse=True)

        if top_k > 0:
            weapons = weapons[:top_k]

        results = []
        for rank, weapon in enumerate(weapons, 1):
            history = histories.get(weapon.id)
            trend = history.get_trend() if history else HealthTrend.NEW
            results.append(
                {
                    "rank": rank,
                    "weapon_id": weapon.id,
                    "weapon_name": weapon.name,
                    "health_score": weapon.health_score,
                    "usage_count": weapon.usage_count,
                    "success_rate": weapon.success_rate,
                    "trend": trend.value,
                }
            )

        return results

    @classmethod
    def get_top_performers(
        cls, registry, n: int = 5, histories: dict[str, HealthHistory] | None = None
    ) -> list[dict]:
        """获取表现最好的N个武器"""
        return cls.rank(registry, top_k=n, histories=histories)

    @classmethod
    def get_underperformers(
        cls, registry, threshold: float = 30.0, histories: dict[str, HealthHistory] | None = None
    ) -> list[dict]:
        """获取表现不佳的武器（健康评分低于阈值）"""
        all_ranked = cls.rank(registry, histories=histories)
        return [r for r in all_ranked if r["health_score"] < threshold]

    @classmethod
    def get_health_distribution(cls, registry) -> dict[str, int]:
        """获取健康评分分布"""
        weapons = registry.list_all()
        distribution = {
            "excellent (80-100)": 0,
            "good (60-80)": 0,
            "fair (40-60)": 0,
            "poor (20-40)": 0,
            "critical (0-20)": 0,
        }

        for w in weapons:
            score = w.health_score
            if score >= 80:
                distribution["excellent (80-100)"] += 1
            elif score >= 60:
                distribution["good (60-80)"] += 1
            elif score >= 40:
                distribution["fair (40-60)"] += 1
            elif score >= 20:
                distribution["poor (20-40)"] += 1
            else:
                distribution["critical (0-20)"] += 1

        return distribution
