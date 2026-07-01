"""
V5.0 P3: 健康元数据层测试
测试 HealthHistory / NaturalSelectionEngine / HealthRanker
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta

from core.armory import (
    ArmoryRegistry,
    WeaponCategory,
    WeaponMetadata,
    WeaponState,
    WeaponType,
)
from core.health_meta import (
    HealthHistory,
    HealthRanker,
    HealthSnapshot,
    HealthTrend,
    NaturalSelectionEngine,
    SelectionDecision,
)

# ── 辅助函数 ──────────────────────────────────────────────────────────────────


def make_weapon(
    weapon_id="skill:test",
    score=50.0,
    usage=0,
    success=0,
    failure=0,
    state=WeaponState.ACTIVE,
    preset=False,
    last_used=None,
):
    """创建测试武器"""
    w = WeaponMetadata(
        id=weapon_id,
        name=weapon_id,
        type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        health_score=score,
        usage_count=usage,
        success_count=success,
        failure_count=failure,
        state=state,
        is_active=(state == WeaponState.ACTIVE),
        is_preset=preset,
        last_used=last_used,
    )
    return w


def make_history(scores):
    """创建有指定评分历史的 HealthHistory"""
    h = HealthHistory()
    for s in scores:
        h.record(health_score=s, usage_count=10, success_count=8, failure_count=2)
    return h


# ── HealthSnapshot 测试 ───────────────────────────────────────────────────────


class TestHealthSnapshot:
    def test_create(self):
        s = HealthSnapshot(
            timestamp="2026-06-29T00:00:00",
            health_score=75.5,
            usage_count=100,
            success_count=90,
            failure_count=10,
            weapon_state="active",
        )
        assert s.health_score == 75.5
        assert s.usage_count == 100
        assert s.weapon_state == "active"

    def test_to_dict(self):
        s = HealthSnapshot(
            timestamp="2026-06-29T00:00:00",
            health_score=50.0,
            usage_count=10,
            success_count=8,
            failure_count=2,
            weapon_state="active",
        )
        d = s.to_dict()
        assert d["health_score"] == 50.0
        assert d["usage_count"] == 10
        assert d["weapon_state"] == "active"


# ── HealthHistory 测试 ────────────────────────────────────────────────────────


class TestHealthHistory:
    def test_empty_history(self):
        h = HealthHistory()
        assert h.count() == 0
        assert h.get_trend() == HealthTrend.NEW
        assert h.get_average_score() == 0.0

    def test_record_snapshot(self):
        h = HealthHistory()
        h.record(health_score=50.0)
        assert h.count() == 1
        assert h.get_average_score() == 50.0

    def test_record_multiple(self):
        h = HealthHistory()
        for score in [40, 50, 60, 70, 80]:
            h.record(health_score=score)
        assert h.count() == 5
        assert h.get_average_score() == 60.0

    def test_trend_improving(self):
        h = make_history([30, 40, 50, 60, 70])
        assert h.get_trend() == HealthTrend.IMPROVING

    def test_trend_declining(self):
        h = make_history([70, 60, 50, 40, 30])
        assert h.get_trend() == HealthTrend.DECLINING

    def test_trend_stable(self):
        h = make_history([50, 51, 50, 51, 50])
        assert h.get_trend() == HealthTrend.STABLE

    def test_trend_new(self):
        h = make_history([50, 55])
        assert h.get_trend() == HealthTrend.NEW

    def test_trend_volatile(self):
        h = make_history([10, 90, 10, 90, 10])
        assert h.get_trend() == HealthTrend.VOLATILE

    def test_max_snapshots(self):
        h = HealthHistory()
        for i in range(150):
            h.record(health_score=float(i))
        assert h.count() == 100  # maxlen=100

    def test_get_recent(self):
        h = HealthHistory()
        for i in range(20):
            h.record(health_score=float(i))
        recent = h.get_recent(5)
        assert len(recent) == 5
        assert recent[-1].health_score == 19.0

    def test_get_score_range(self):
        h = make_history([30, 50, 70, 90])
        min_s, max_s = h.get_score_range()
        assert min_s == 30
        assert max_s == 90

    def test_to_dict(self):
        h = HealthHistory()
        h.record(health_score=50.0)
        d = h.to_dict()
        assert len(d) == 1
        assert d[0]["health_score"] == 50.0


# ── NaturalSelectionEngine 测试 ───────────────────────────────────────────────


class TestNaturalSelectionEngine:
    def test_retire_low_score(self):
        """低分武器应被退役"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:low", score=15.0))
        engine = NaturalSelectionEngine(r)
        decision = engine.evaluate("skill:low")
        assert decision.action == "retire"
        assert decision.recommended_state == "retired"

    def test_deprecate_declining(self):
        """低分+下降趋势应被废弃"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:declining", score=25.0))
        engine = NaturalSelectionEngine(r)
        history = make_history([50, 40, 30, 25, 20])
        decision = engine.evaluate("skill:declining", history)
        assert decision.action == "deprecate"

    def test_promote_improving(self):
        """高分+上升趋势+已归档应被晋升"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:rising", score=85.0, state=WeaponState.ARCHIVED))
        engine = NaturalSelectionEngine(r)
        history = make_history([60, 70, 75, 80, 85])
        decision = engine.evaluate("skill:rising", history)
        assert decision.action == "promote"
        assert decision.recommended_state == "active"

    def test_keep_good_weapon(self):
        """健康武器保持现状"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:good", score=70.0, usage=100, success=90))
        engine = NaturalSelectionEngine(r)
        decision = engine.evaluate("skill:good")
        assert decision.action == "keep"

    def test_preset_weapon_not_retired(self):
        """预置武器不被自动退役"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:preset", score=10.0, preset=True))
        engine = NaturalSelectionEngine(r)
        decision = engine.evaluate("skill:preset")
        assert decision.action == "keep"
        assert "预置" in decision.reason

    def test_deprecate_inactive(self):
        """不活跃武器应被废弃"""
        r = ArmoryRegistry()
        old_date = (datetime.now() - timedelta(days=35)).isoformat()
        r.register(make_weapon("skill:inactive", score=50.0, last_used=old_date))
        engine = NaturalSelectionEngine(r)
        decision = engine.evaluate("skill:inactive")
        assert decision.action == "deprecate"
        assert "未使用" in decision.reason

    def test_nonexistent_weapon(self):
        r = ArmoryRegistry()
        engine = NaturalSelectionEngine(r)
        decision = engine.evaluate("skill:nonexistent")
        assert decision.action == "keep"
        assert "不存在" in decision.reason

    def test_evaluate_all(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:good", score=70.0))
        r.register(make_weapon("skill:bad", score=10.0))
        engine = NaturalSelectionEngine(r)
        decisions = engine.evaluate_all()
        assert len(decisions) == 2
        actions = {d.weapon_id: d.action for d in decisions}
        assert actions["skill:bad"] == "retire"
        assert actions["skill:good"] == "keep"

    def test_retirement_candidates(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=15.0))
        r.register(make_weapon("skill:b", score=50.0))
        r.register(make_weapon("skill:c", score=10.0))
        engine = NaturalSelectionEngine(r)
        candidates = engine.get_retirement_candidates()
        assert "skill:a" in candidates
        assert "skill:c" in candidates
        assert "skill:b" not in candidates

    def test_promotion_candidates(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=85.0, state=WeaponState.ARCHIVED))
        r.register(make_weapon("skill:b", score=50.0))
        engine = NaturalSelectionEngine(r)
        histories = {"skill:a": make_history([60, 70, 75, 80, 85])}
        candidates = engine.get_promotion_candidates(histories)
        assert "skill:a" in candidates


# ── HealthRanker 测试 ─────────────────────────────────────────────────────────


class TestHealthRanker:
    def test_rank_basic(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=80.0, usage=100, success=90))
        r.register(make_weapon("skill:b", score=50.0, usage=50, success=40))
        r.register(make_weapon("skill:c", score=90.0, usage=200, success=180))

        ranked = HealthRanker.rank(r)
        assert len(ranked) == 3
        assert ranked[0]["weapon_id"] == "skill:c"  # 最高分
        assert ranked[0]["rank"] == 1
        assert ranked[1]["weapon_id"] == "skill:a"
        assert ranked[2]["weapon_id"] == "skill:b"

    def test_rank_top_k(self):
        r = ArmoryRegistry()
        for i in range(10):
            r.register(make_weapon(f"skill:{i}", score=float(i * 10)))
        ranked = HealthRanker.rank(r, top_k=3)
        assert len(ranked) == 3

    def test_rank_by_type(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=80.0))
        r.register(
            WeaponMetadata(
                id="sop:DEV-001",
                name="DEV-001",
                type=WeaponType.SOP,
                category=WeaponCategory.EXECUTION,
                health_score=90.0,
            )
        )
        ranked = HealthRanker.rank(r, weapon_type=WeaponType.SOP)
        assert len(ranked) == 1
        assert ranked[0]["weapon_id"] == "sop:DEV-001"

    def test_get_top_performers(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=90.0))
        r.register(make_weapon("skill:b", score=80.0))
        r.register(make_weapon("skill:c", score=70.0))
        top = HealthRanker.get_top_performers(r, n=2)
        assert len(top) == 2
        assert top[0]["weapon_id"] == "skill:a"

    def test_get_underperformers(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:good", score=80.0))
        r.register(make_weapon("skill:bad", score=15.0))
        r.register(make_weapon("skill:mid", score=25.0))
        under = HealthRanker.get_underperformers(r, threshold=30.0)
        assert len(under) == 2
        ids = [u["weapon_id"] for u in under]
        assert "skill:bad" in ids
        assert "skill:mid" in ids

    def test_health_distribution(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=90.0))
        r.register(make_weapon("skill:b", score=70.0))
        r.register(make_weapon("skill:c", score=50.0))
        r.register(make_weapon("skill:d", score=25.0))
        r.register(make_weapon("skill:e", score=10.0))
        dist = HealthRanker.get_health_distribution(r)
        assert dist["excellent (80-100)"] == 1
        assert dist["good (60-80)"] == 1
        assert dist["fair (40-60)"] == 1
        assert dist["poor (20-40)"] == 1
        assert dist["critical (0-20)"] == 1

    def test_rank_with_trend(self):
        """带趋势的排名"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", score=70.0))
        r.register(make_weapon("skill:b", score=70.0))
        histories = {
            "skill:a": make_history([50, 55, 60, 65, 70]),  # IMPROVING
            "skill:b": make_history([90, 80, 75, 72, 70]),  # DECLINING
        }
        ranked = HealthRanker.rank(r, histories=histories)
        # 同分但A趋势更好，应排第一
        assert ranked[0]["weapon_id"] == "skill:a"
        assert ranked[0]["trend"] == "improving"
        assert ranked[1]["trend"] == "declining"

    def test_empty_registry_rank(self):
        r = ArmoryRegistry()
        ranked = HealthRanker.rank(r)
        assert ranked == []

    def test_selection_decision_to_dict(self):
        d = SelectionDecision(
            weapon_id="test",
            action="keep",
            reason="OK",
            current_score=50.0,
            trend="stable",
            recommended_state="active",
        )
        result = d.to_dict()
        assert result["weapon_id"] == "test"
        assert result["action"] == "keep"
        assert result["current_score"] == 50.0
