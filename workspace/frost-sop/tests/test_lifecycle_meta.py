"""
V5.0 P4: 生命周期元数据层测试
测试 LifecycleEventLog / TransitionGuard / BatchLifecycleManager
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.armory import (
    WeaponMetadata, WeaponType, WeaponState, WeaponCategory, ArmoryRegistry,
)
from core.lifecycle_meta import (
    LifecycleEvent, LifecycleEventType, LifecycleEventLog,
    TransitionGuard, GuardResult,
    BatchLifecycleManager, BatchResult,
)


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def make_weapon(weapon_id="skill:test", state=WeaponState.ACTIVE, score=50.0,
                preset=False, usage=10):
    """创建测试武器"""
    return WeaponMetadata(
        id=weapon_id, name=weapon_id, type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        state=state, is_active=(state == WeaponState.ACTIVE),
        is_preset=preset, health_score=score, usage_count=usage,
    )


def make_registry_with_states():
    """创建含不同状态武器的注册表"""
    r = ArmoryRegistry()
    r.register(make_weapon("skill:discovered", state=WeaponState.DISCOVERED, usage=0))
    r.register(make_weapon("skill:validated", state=WeaponState.VALIDATED, usage=1))
    r.register(make_weapon("skill:trialed", state=WeaponState.TRIALED, usage=5))
    r.register(make_weapon("skill:archived", state=WeaponState.ARCHIVED, score=60.0))
    r.register(make_weapon("skill:active", state=WeaponState.ACTIVE, score=70.0, usage=50))
    r.register(make_weapon("skill:deprecated", state=WeaponState.DEPRECATED, score=40.0))
    r.register(make_weapon("skill:retired", state=WeaponState.RETIRED, score=10.0))
    return r


# ── LifecycleEvent 测试 ───────────────────────────────────────────────────────

class TestLifecycleEvent:
    def test_create(self):
        e = LifecycleEvent(
            event_id="evt_001", weapon_id="skill:test",
            event_type=LifecycleEventType.STATE_TRANSITION,
            timestamp="2026-06-29T00:00:00",
            from_state="active", to_state="deprecated",
            reason="low usage", operator="system",
        )
        assert e.event_id == "evt_001"
        assert e.from_state == "active"
        assert e.to_state == "deprecated"

    def test_to_dict(self):
        e = LifecycleEvent(
            event_id="evt_001", weapon_id="skill:test",
            event_type=LifecycleEventType.REGISTERED,
            timestamp="2026-06-29T00:00:00",
        )
        d = e.to_dict()
        assert d["event_id"] == "evt_001"
        assert d["event_type"] == "registered"
        assert d["weapon_id"] == "skill:test"


# ── LifecycleEventLog 测试 ────────────────────────────────────────────────────

class TestLifecycleEventLog:
    def test_empty_log(self):
        log = LifecycleEventLog()
        assert log.count() == 0
        assert log.get_by_weapon("skill:test") == []

    def test_log_event(self):
        log = LifecycleEventLog()
        event = log.log(
            weapon_id="skill:test",
            event_type=LifecycleEventType.REGISTERED,
        )
        assert log.count() == 1
        assert event.weapon_id == "skill:test"
        assert event.event_type == LifecycleEventType.REGISTERED

    def test_log_multiple(self):
        log = LifecycleEventLog()
        for i in range(10):
            log.log(weapon_id=f"skill:{i}", event_type=LifecycleEventType.REGISTERED)
        assert log.count() == 10

    def test_get_by_weapon(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.REGISTERED)
        log.log(weapon_id="skill:b", event_type=LifecycleEventType.REGISTERED)
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.STATE_TRANSITION,
                from_state="discovered", to_state="validated")
        events = log.get_by_weapon("skill:a")
        assert len(events) == 2

    def test_get_by_type(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.REGISTERED)
        log.log(weapon_id="skill:b", event_type=LifecycleEventType.STATE_TRANSITION)
        log.log(weapon_id="skill:c", event_type=LifecycleEventType.REGISTERED)
        registered = log.get_by_type(LifecycleEventType.REGISTERED)
        assert len(registered) == 2

    def test_get_recent(self):
        log = LifecycleEventLog()
        for i in range(20):
            log.log(weapon_id=f"skill:{i}", event_type=LifecycleEventType.REGISTERED)
        recent = log.get_recent(5)
        assert len(recent) == 5
        assert recent[-1].weapon_id == "skill:19"

    def test_get_timeline(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.REGISTERED)
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.STATE_TRANSITION,
                from_state="discovered", to_state="validated")
        timeline = log.get_timeline("skill:a")
        assert len(timeline) == 2
        assert timeline[0]["event_type"] == "registered"

    def test_get_state_history(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.STATE_TRANSITION,
                from_state="discovered", to_state="validated")
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.STATE_TRANSITION,
                from_state="validated", to_state="trialed")
        history = log.get_state_history("skill:a")
        assert len(history) == 2
        assert history[0] == (history[0][0], "discovered", "validated")

    def test_max_events(self):
        log = LifecycleEventLog()
        for i in range(1500):
            log.log(weapon_id=f"skill:{i}", event_type=LifecycleEventType.REGISTERED)
        assert log.count() == 1000  # maxlen=1000

    def test_clear(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.REGISTERED)
        log.clear()
        assert log.count() == 0

    def test_count_by_weapon(self):
        log = LifecycleEventLog()
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.REGISTERED)
        log.log(weapon_id="skill:a", event_type=LifecycleEventType.USAGE_RECORDED)
        log.log(weapon_id="skill:b", event_type=LifecycleEventType.REGISTERED)
        assert log.count_by_weapon("skill:a") == 2
        assert log.count_by_weapon("skill:b") == 1

    def test_unique_event_ids(self):
        log = LifecycleEventLog()
        ids = set()
        for i in range(100):
            e = log.log(weapon_id=f"skill:{i}", event_type=LifecycleEventType.REGISTERED)
            ids.add(e.event_id)
        assert len(ids) == 100  # 全部唯一


# ── TransitionGuard 测试 ──────────────────────────────────────────────────────

class TestTransitionGuard:
    def test_valid_transition(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:discovered", "validated")
        assert result.allowed is True

    def test_invalid_transition(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:active", "discovered")
        assert result.allowed is False
        assert "无效转换" in result.reason

    def test_same_state(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:active", "active")
        assert result.allowed is True
        assert "无需转换" in result.reason

    def test_preset_weapon_not_retired(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:preset", state=WeaponState.ACTIVE, preset=True))
        guard = TransitionGuard(r)
        result = guard.check("skill:preset", "retired")
        assert result.allowed is False
        assert "预置" in result.reason

    def test_retired_is_terminal(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:retired", "active")
        assert result.allowed is False

    def test_activate_low_health(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:low", state=WeaponState.ARCHIVED, score=20.0))
        guard = TransitionGuard(r)
        result = guard.check("skill:low", "active")
        assert result.allowed is False
        assert "健康评分" in result.reason

    def test_warnings_on_retire(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:active", "retired")
        assert result.allowed is True
        assert any("不可逆" in w for w in result.warnings)

    def test_warning_on_revive(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:deprecated", "active")
        assert result.allowed is True
        assert any("复活" in w for w in result.warnings)

    def test_nonexistent_weapon(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        result = guard.check("skill:nonexistent", "active")
        assert result.allowed is False
        assert "不存在" in result.reason

    def test_get_allowed_transitions(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        allowed = guard.get_allowed_transitions("skill:active")
        assert "deprecated" in allowed
        assert "retired" in allowed
        assert "discovered" not in allowed

    def test_get_allowed_transitions_preset(self):
        """预置武器的允许转换不包含 retired"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:preset", state=WeaponState.ACTIVE, preset=True))
        guard = TransitionGuard(r)
        allowed = guard.get_allowed_transitions("skill:preset")
        assert "retired" not in allowed
        assert "deprecated" in allowed

    def test_is_terminal_state(self):
        guard = TransitionGuard(ArmoryRegistry())
        assert guard.is_terminal_state("retired") is True
        assert guard.is_terminal_state("active") is False

    def test_check_batch(self):
        r = make_registry_with_states()
        guard = TransitionGuard(r)
        results = guard.check_batch([
            ("skill:discovered", "validated"),
            ("skill:active", "discovered"),  # invalid
            ("skill:retired", "active"),     # terminal
        ])
        assert len(results) == 3
        assert results["skill:discovered"].allowed is True
        assert results["skill:active"].allowed is False

    def test_guard_result_to_dict(self):
        result = GuardResult(allowed=True, reason="OK", warnings=["warn"])
        d = result.to_dict()
        assert d["allowed"] is True
        assert d["reason"] == "OK"
        assert d["warnings"] == ["warn"]


# ── BatchLifecycleManager 测试 ────────────────────────────────────────────────

class TestBatchLifecycleManager:
    def test_batch_transition_success(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", state=WeaponState.ARCHIVED, score=60.0))
        r.register(make_weapon("skill:b", state=WeaponState.ARCHIVED, score=70.0))
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_transition(["skill:a", "skill:b"], "active")
        assert result.succeeded == 2
        assert result.failed == 0

    def test_batch_transition_partial_failure(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:ok", state=WeaponState.ARCHIVED, score=60.0))
        r.register(make_weapon("skill:bad", state=WeaponState.ACTIVE, score=70.0))
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_transition(["skill:ok", "skill:bad", "skill:nonexistent"], "active")
        # skill:ok: archived→active OK
        # skill:bad: active→active same state, allowed
        # skill:nonexistent: skipped
        assert result.succeeded == 2
        assert result.skipped == 1

    def test_batch_transition_too_large(self):
        r = ArmoryRegistry()
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_transition(["skill:x"] * 100, "active")
        assert result.succeeded == 0
        assert "超过限制" in result.details[0]["error"]

    def test_batch_transition_invalid_state(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", state=WeaponState.ACTIVE))
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_transition(["skill:a"], "invalid_state")
        assert result.skipped == 1

    def test_batch_retire_low_health(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:low1", state=WeaponState.ACTIVE, score=15.0))
        r.register(make_weapon("skill:low2", state=WeaponState.ACTIVE, score=10.0))
        r.register(make_weapon("skill:ok", state=WeaponState.ACTIVE, score=50.0))
        r.register(make_weapon("skill:preset_low", state=WeaponState.ACTIVE, score=5.0, preset=True))
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_retire_low_health(threshold=20.0)
        # low1 and low2 are retired (non-preset, score < 20)
        # preset_low is filtered out by batch_retire_low_health (is_preset check)
        # ok is not a candidate (score >= 20)
        assert result.succeeded == 2  # low1 and low2

    def test_batch_activate_archived(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:arch1", state=WeaponState.ARCHIVED, score=60.0))
        r.register(make_weapon("skill:arch2", state=WeaponState.ARCHIVED, score=70.0))
        r.register(make_weapon("skill:arch_low", state=WeaponState.ARCHIVED, score=20.0))
        mgr = BatchLifecycleManager(r)
        result = mgr.batch_activate_archived()
        # arch1 and arch2 activated (health >= 30)
        # arch_low filtered out by batch_activate_archived (health < 30)
        assert result.succeeded == 2  # arch1 and arch2
        assert result.total == 2      # arch_low not in candidates

    def test_batch_logs_events(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", state=WeaponState.ARCHIVED, score=60.0))
        mgr = BatchLifecycleManager(r)
        mgr.batch_transition(["skill:a"], "active")
        events = mgr.event_log.get_by_weapon("skill:a")
        assert len(events) == 1
        assert events[0].event_type == LifecycleEventType.STATE_TRANSITION

    def test_get_lifecycle_report(self):
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", state=WeaponState.ACTIVE, score=70.0, usage=50))
        mgr = BatchLifecycleManager(r)
        mgr.batch_transition(["skill:a"], "deprecated", reason="test")
        report = mgr.get_lifecycle_report("skill:a")
        assert report["weapon_id"] == "skill:a"
        assert report["current_state"] == "deprecated"
        assert report["event_count"] >= 1
        assert report["state_change_count"] >= 1
        assert "active" in report["allowed_transitions"]  # deprecated → active allowed

    def test_get_lifecycle_report_nonexistent(self):
        r = ArmoryRegistry()
        mgr = BatchLifecycleManager(r)
        report = mgr.get_lifecycle_report("skill:nonexistent")
        assert "error" in report

    def test_batch_result_to_dict(self):
        result = BatchResult(
            operation="test", total=10, succeeded=8, failed=1, skipped=1,
            details=[{"weapon_id": "skill:a", "status": "succeeded"}]
        )
        d = result.to_dict()
        assert d["operation"] == "test"
        assert d["total"] == 10
        assert d["succeeded"] == 8
        assert d["failed"] == 1
        assert d["skipped"] == 1
