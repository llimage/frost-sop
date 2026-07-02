"""
Targeted tests for mutation testing of modules with low kill rates.

These tests specifically exercise code paths in json_safety.py and
armory_lifecycle.py that are not covered by existing tests, improving
mutation kill rate above the 80% threshold.

Run: python -X utf8 -m pytest tests/test_mutation_targets.py -v -s
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("FROST_TESTING", "1")


# ============================================================
# json_safety.py targeted tests
# ============================================================


class TestJsonSafetyMutations:
    """Tests designed to kill mutations in core/json_safety.py."""

    def test_empty_string_rejected(self):
        """Empty string should be rejected."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse("")
        assert result is None
        assert error is not None
        assert "Empty" in error

    def test_whitespace_only_rejected(self):
        """Whitespace-only string should be rejected."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse("   \n\t  ")
        assert result is None
        assert error is not None

    def test_valid_dict_parsed(self):
        """Valid JSON dict should parse successfully."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"key": "value"}')
        assert result is not None
        assert result == {"key": "value"}
        assert error is None

    def test_oversized_rejected(self):
        """Payload exceeding max_length should be rejected."""
        from core.json_safety import safe_json_parse

        large = '{"x": "' + "A" * 200 + '"}'
        result, error = safe_json_parse(large, max_length=50)
        assert result is None
        assert error is not None

    def test_array_rejected(self):
        """JSON array should be rejected (not a dict)."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse("[1, 2, 3]")
        assert result is None
        assert error is not None

    def test_string_rejected(self):
        """JSON string should be rejected (not a dict)."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('"hello"')
        assert result is None
        assert error is not None

    def test_number_rejected(self):
        """JSON number should be rejected (not a dict)."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse("42")
        assert result is None
        assert error is not None

    def test_deeply_nested_rejected(self):
        """Deeply nested structure should be rejected."""
        from core.json_safety import safe_json_parse

        nested = '{"a": ' * 15 + '"deep"' + "}" * 15
        result, error = safe_json_parse(nested, max_depth=5)
        assert result is None
        assert error is not None

    def test_shallow_nested_accepted(self):
        """Shallow nested dict should be accepted."""
        from core.json_safety import safe_json_parse

        shallow = '{"a": {"b": {"c": 1}}}'
        result, error = safe_json_parse(shallow, max_depth=10)
        assert result is not None
        assert error is None

    def test_nan_rejected(self):
        """NaN should be rejected."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"x": NaN}')
        assert result is None
        assert error is not None

    def test_infinity_rejected(self):
        """Infinity should be rejected."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"x": Infinity}')
        assert result is None
        assert error is not None

    def test_negative_infinity_rejected(self):
        """-Infinity should be rejected."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"x": -Infinity}')
        assert result is None
        assert error is not None

    def test_safe_json_parse_or_default_success(self):
        from core.json_safety import safe_json_parse_or_default

        default = {"fallback": True}
        result = safe_json_parse_or_default('{"key": "value"}', default)
        assert result == {"key": "value"}

    def test_safe_json_parse_or_default_fallback(self):
        from core.json_safety import safe_json_parse_or_default

        default = {"fallback": True}
        result = safe_json_parse_or_default("invalid json", default)
        assert result == default

    def test_safe_json_parse_or_default_empty(self):
        from core.json_safety import safe_json_parse_or_default

        default = {"fallback": True}
        result = safe_json_parse_or_default("", default)
        assert result == default

    def test_float_clamping(self):
        """Large floats should be clamped, not crash."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"x": 1e200}')
        assert result is not None or error is not None

    def test_int_clamping(self):
        """Large ints should be clamped."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse('{"x": 99999999999999999999999999}')
        assert result is not None or error is not None

    def test_get_depth_empty_dict(self):
        """Empty dict should have depth 0."""
        from core.json_safety import _get_depth

        assert _get_depth({}) == 0

    def test_get_depth_empty_list(self):
        """Empty list should have depth 0."""
        from core.json_safety import _get_depth

        assert _get_depth([]) == 0

    def test_get_depth_flat_dict(self):
        """Flat dict should have depth 1."""
        from core.json_safety import _get_depth

        assert _get_depth({"a": 1, "b": 2}) == 1

    def test_get_depth_nested(self):
        """Nested dict should have correct depth."""
        from core.json_safety import _get_depth

        assert _get_depth({"a": {"b": {"c": 1}}}) == 3

    def test_get_depth_nested_list(self):
        """Nested list should have correct depth."""
        from core.json_safety import _get_depth

        assert _get_depth({"a": [1, [2, [3]]]}) == 4

    def test_get_depth_non_dict(self):
        """Non-dict/list should have depth 0."""
        from core.json_safety import _get_depth

        assert _get_depth(42) == 0
        assert _get_depth("hello") == 0
        assert _get_depth(None) == 0

    def test_invalid_json(self):
        """Invalid JSON should return error."""
        from core.json_safety import safe_json_parse

        result, error = safe_json_parse("{invalid}")
        assert result is None
        assert error is not None

    def test_safe_float_nan(self):
        """NaN float should return 0.0."""
        from core.json_safety import _safe_float

        assert _safe_float("nan") == 0.0

    def test_safe_float_normal(self):
        """Normal float should pass through."""
        from core.json_safety import _safe_float

        assert _safe_float("3.14") == 3.14

    def test_safe_float_large(self):
        """Very large float should be clamped."""
        from core.json_safety import SAFE_FLOAT_MAX, _safe_float

        assert _safe_float("1e200") == SAFE_FLOAT_MAX

    def test_safe_float_small(self):
        """Very negative float should be clamped."""
        from core.json_safety import SAFE_FLOAT_MIN, _safe_float

        assert _safe_float("-1e200") == SAFE_FLOAT_MIN

    def test_safe_int_large(self):
        """Very large int should be clamped."""
        from core.json_safety import SAFE_INT_MAX, _safe_int

        assert _safe_int("99999999999999999999999999") == SAFE_INT_MAX

    def test_safe_int_small(self):
        """Very negative int should be clamped."""
        from core.json_safety import SAFE_INT_MIN, _safe_int

        assert _safe_int("-99999999999999999999999999") == SAFE_INT_MIN

    def test_safe_int_normal(self):
        """Normal int should pass through."""
        from core.json_safety import _safe_int

        assert _safe_int("42") == 42

    def test_safe_constant_raises(self):
        """Unsafe constant should raise ValueError."""
        from core.json_safety import _safe_constant

        with pytest.raises(ValueError):
            _safe_constant("NaN")

    def test_valid_nested_within_limit(self):
        """Valid nested dict within depth limit should succeed."""
        from core.json_safety import safe_json_parse

        data = '{"level1": {"level2": {"level3": {"value": 42}}}}'
        result, error = safe_json_parse(data, max_depth=10)
        assert result is not None
        assert error is None


# ============================================================
# armory_lifecycle.py targeted tests
# ============================================================


def _make_registry():
    """Create a real ArmoryRegistry with a mock store."""
    from core.armory import ArmoryRegistry
    from core.store import Store

    store = MagicMock(spec=Store)
    store.save = MagicMock()
    store.load = MagicMock(return_value=None)
    store.delete = MagicMock()
    store.list_keys = MagicMock(return_value=[])

    registry = ArmoryRegistry(store=store)
    return registry


def _make_weapon(weapon_id="test:w1", **kwargs):
    """Create a weapon metadata for testing."""
    from core.armory import WeaponMetadata, WeaponType

    defaults = {
        "id": weapon_id,
        "name": weapon_id,
        "type": WeaponType.SKILL,
    }
    defaults.update(kwargs)
    return WeaponMetadata(**defaults)


class TestWeaponLifecycleMutations:
    """Tests for WeaponLifecycle — designed to kill mutations."""

    def test_transition_nonexistent_weapon(self):
        """Transition for non-existent weapon should fail."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        lifecycle = WeaponLifecycle(registry)

        ok, msg = lifecycle.transition("nonexistent", WeaponState.VALIDATED)
        assert ok is False
        assert "不存在" in msg

    def test_transition_same_state(self):
        """Transition to same state should succeed with 'no change' message."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ACTIVE)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.ACTIVE)
        assert ok is True
        assert "无需转换" in msg

    def test_transition_invalid_path(self):
        """Invalid state transition should be rejected."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.RETIRED)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        # RETIRED → ACTIVE is not valid
        ok, msg = lifecycle.transition("test:w1", WeaponState.ACTIVE)
        assert ok is False
        assert "无效" in msg

    def test_transition_discovered_to_validated(self):
        """Valid transition DISCOVERED → VALIDATED should succeed."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.DISCOVERED)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.VALIDATED)
        assert ok is True

    def test_transition_to_trial_requires_usage(self):
        """Transition to TRIALED should require usage_count >= 1."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.VALIDATED, usage_count=0)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.TRIALED)
        assert ok is False
        assert "试炼" in msg

    def test_transition_to_active_invalid_from_validated(self):
        """Transition from VALIDATED to ACTIVE should be invalid (not in allowed transitions)."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.VALIDATED, usage_count=5)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.ACTIVE)
        assert ok is False
        assert "无效" in msg

    def test_transition_to_active_requires_health_score(self):
        """Transition to ACTIVE should require health_score >= 30."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ARCHIVED, health_score=10)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.ACTIVE)
        assert ok is False
        assert "健康评分" in msg

    def test_transition_to_active_success(self):
        """Valid transition ARCHIVED → ACTIVE should succeed."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ARCHIVED, health_score=50)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.ACTIVE)
        assert ok is True

    def test_transition_to_deprecated_sets_inactive(self):
        """Transition to DEPRECATED should set is_active = False."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ACTIVE, is_active=True)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.DEPRECATED)
        assert ok is True
        assert weapon.is_active is False
        assert weapon.deprecated_at is not None

    def test_transition_to_retired_sets_inactive(self):
        """Transition to RETIRED should set is_active = False."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ACTIVE, is_active=True)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.RETIRED)
        assert ok is True
        assert weapon.is_active is False
        assert weapon.retired_at is not None

    def test_transition_to_archived_sets_timestamp(self):
        """Transition to ARCHIVED should set archived_at."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.TRIALED, usage_count=5)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        ok, msg = lifecycle.transition("test:w1", WeaponState.ARCHIVED)
        assert ok is True
        assert weapon.archived_at is not None

    def test_auto_evaluate_nonexistent(self):
        """Auto-evaluate for non-existent weapon should return RETIRED."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        lifecycle = WeaponLifecycle(registry)

        state, msg = lifecycle.auto_evaluate("nonexistent")
        assert state == WeaponState.RETIRED
        assert "不存在" in msg

    def test_auto_evaluate_preset_skipped(self):
        """Preset weapons should not be auto-evaluated."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ACTIVE, is_preset=True)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        state, msg = lifecycle.auto_evaluate("test:w1")
        assert state == WeaponState.ACTIVE
        assert "预置" in msg

    def test_auto_evaluate_low_health(self):
        """Low health score should recommend RETIRED."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ACTIVE, is_preset=False, health_score=10)
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        state, msg = lifecycle.auto_evaluate("test:w1")
        assert state == WeaponState.RETIRED
        assert "健康评分" in msg

    def test_auto_evaluate_never_used(self):
        """Active weapon with 0 usage should recommend DEPRECATED."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(
            state=WeaponState.ACTIVE,
            is_preset=False,
            health_score=50,
            usage_count=0,
        )
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        state, msg = lifecycle.auto_evaluate("test:w1")
        assert state == WeaponState.DEPRECATED
        assert "从未使用" in msg

    def test_auto_evaluate_high_success_archived(self):
        """Archived weapon with high success rate should recommend ACTIVE."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(
            state=WeaponState.ARCHIVED,
            is_preset=False,
            health_score=50,
            usage_count=15,
            success_count=13,
            failure_count=2,
        )
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        state, msg = lifecycle.auto_evaluate("test:w1")
        assert state == WeaponState.ACTIVE
        assert "激活" in msg

    def test_auto_evaluate_stable(self):
        """Healthy active weapon should stay ACTIVE."""
        from core.armory import WeaponState
        from core.armory_lifecycle import WeaponLifecycle

        registry = _make_registry()
        weapon = _make_weapon(
            state=WeaponState.ACTIVE,
            is_preset=False,
            health_score=50,
            usage_count=10,
        )
        registry.register(weapon)

        lifecycle = WeaponLifecycle(registry)
        state, msg = lifecycle.auto_evaluate("test:w1")
        assert state == WeaponState.ACTIVE
        assert "合适" in msg


class TestWeaponLoaderMutations:
    """Tests for WeaponLoader — designed to kill mutations."""

    def test_load_from_module_no_skills(self):
        """Loading a module with no Skill instances should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        # json module has no Skill instances
        result = loader.load_from_module("json")
        assert result is None

    def test_load_from_module_invalid_module(self):
        """Loading an invalid module should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        result = loader.load_from_module("nonexistent.module.xyz")
        assert result is None

    def test_load_from_sop_yaml_invalid_file(self):
        """Loading non-existent YAML should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        result = loader.load_from_sop_yaml("nonexistent.yaml")
        assert result is None

    def test_load_from_sop_yaml_no_stages(self):
        """YAML without 'stages' key should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        # Write within project dir (safe_open requires containment)
        tmp_dir = Path("tests/_tmp_mutation")
        tmp_dir.mkdir(exist_ok=True)
        yaml_path = tmp_dir / "no_stages.yaml"
        yaml_path.write_text("key: value\nno_stages: true\n", encoding="utf-8")
        result = loader.load_from_sop_yaml(str(yaml_path))
        yaml_path.unlink()
        assert result is None

    def test_load_from_sop_yaml_valid(self):
        """Valid SOP YAML should return WeaponMetadata."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        tmp_dir = Path("tests/_tmp_mutation")
        tmp_dir.mkdir(exist_ok=True)
        yaml_path = tmp_dir / "test_sop.yaml"
        yaml_path.write_text(
            "sop_id: DEV-001\nname: Test SOP\nstages:\n"
            "  - phase_id: phase1\n    skills:\n      - skill_a\n      - skill_b\n",
            encoding="utf-8",
        )
        result = loader.load_from_sop_yaml(str(yaml_path))
        yaml_path.unlink()
        assert result is not None
        assert result.id == "sop:DEV-001"
        assert len(result.applicable_scenarios) > 0

    def test_load_from_skill_card_invalid_file(self):
        """Loading non-existent skill card should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        result = loader.load_from_skill_card("nonexistent.yaml")
        assert result is None

    def test_load_from_skill_card_no_intent(self):
        """Skill card without 'intent' key should return None."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        tmp_dir = Path("tests/_tmp_mutation")
        tmp_dir.mkdir(exist_ok=True)
        yaml_path = tmp_dir / "no_intent.yaml"
        yaml_path.write_text("key: value\nno_intent: true\n", encoding="utf-8")
        result = loader.load_from_skill_card(str(yaml_path))
        yaml_path.unlink()
        assert result is None

    def test_load_from_skill_card_valid(self):
        """Valid skill card should return WeaponMetadata."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        tmp_dir = Path("tests/_tmp_mutation")
        tmp_dir.mkdir(exist_ok=True)
        yaml_path = tmp_dir / "test_card.yaml"
        yaml_path.write_text(
            'intent: "Test skill card"\n'
            'applicable_when: "scenario A, scenario B"\n'
            'not_applicable_when: "scenario C"\n',
            encoding="utf-8",
        )
        result = loader.load_from_skill_card(str(yaml_path))
        yaml_path.unlink()
        assert result is not None
        assert result.id.startswith("gene:")
        assert len(result.applicable_scenarios) >= 1

    def test_load_from_store_no_list_keys(self):
        """Store without list_keys should return empty list."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        store = MagicMock()  # no list_keys attribute
        result = loader.load_from_store(store)
        assert result == []

    def test_load_from_store_empty(self):
        """Store with no matching keys should return empty list."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        store = MagicMock()
        store.list_keys.return_value = []
        result = loader.load_from_store(store)
        assert result == []

    def test_load_from_store_with_genes(self):
        """Store with gene entries should return weapons."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        store = MagicMock()
        store.list_keys.return_value = ["skill_gene:gene1", "skill_gene:gene2", "other:key"]
        store.load.side_effect = lambda k: {
            "skill_gene:gene1": {"applicable_scenarios": ["a", "b"]},
            "skill_gene:gene2": {"applicable_scenarios": []},
            "other:key": None,
        }.get(k)
        result = loader.load_from_store(store)
        assert len(result) == 2
        assert result[0].id == "gene:gene1"

    def test_discover_all_empty(self):
        """discover_all with no sources should return zero stats."""
        from core.armory_lifecycle import WeaponLoader

        registry = _make_registry()
        loader = WeaponLoader(registry)

        stats = loader.discover_all()
        assert stats["total"] == 0
        assert stats["skill"] == 0
        assert stats["sop"] == 0
        assert stats["gene"] == 0


class TestArmoryDispatcherMutations:
    """Tests for ArmoryDispatcher — designed to kill mutations."""

    def test_dispatch_nonexistent(self):
        """Dispatching non-existent weapon should return None."""
        from core.armory_lifecycle import ArmoryDispatcher

        registry = _make_registry()
        dispatcher = ArmoryDispatcher(registry)

        result = dispatcher.dispatch("nonexistent")
        assert result is None

    def test_dispatch_inactive_weapon(self):
        """Dispatching inactive weapon should return None."""
        from core.armory import WeaponState
        from core.armory_lifecycle import ArmoryDispatcher

        registry = _make_registry()
        weapon = _make_weapon(state=WeaponState.ARCHIVED, is_active=False)
        registry.register(weapon)

        dispatcher = ArmoryDispatcher(registry)
        result = dispatcher.dispatch("test:w1")
        assert result is None

    def test_dispatch_sop_nonexistent(self):
        """Dispatching non-existent SOP should return None."""
        from core.armory_lifecycle import ArmoryDispatcher

        registry = _make_registry()
        dispatcher = ArmoryDispatcher(registry)

        result = dispatcher.dispatch_sop("nonexistent")
        assert result is None

    def test_dispatch_sop_inactive(self):
        """Dispatching inactive SOP should return None."""
        from core.armory import WeaponType
        from core.armory_lifecycle import ArmoryDispatcher

        registry = _make_registry()
        weapon = _make_weapon(
            weapon_id="sop:test",
            type=WeaponType.SOP,
            is_active=False,
        )
        registry.register(weapon)

        dispatcher = ArmoryDispatcher(registry)
        result = dispatcher.dispatch_sop("test")
        assert result is None

    def test_dispatch_for_task_empty_registry(self):
        """dispatch_for_task with empty registry should return empty skills."""
        from core.armory_lifecycle import ArmoryDispatcher

        registry = _make_registry()
        dispatcher = ArmoryDispatcher(registry)

        result = dispatcher.dispatch_for_task("test task")
        assert "skills" in result
        assert "sop" in result
        assert "recommended_weapons" in result
        assert "reason" in result
