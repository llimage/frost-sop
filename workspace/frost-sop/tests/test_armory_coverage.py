"""
armory.py 全面补测 — 补充 test_armory.py 未覆盖的分支。

覆盖目标：
  - WeaponMetadata: record_usage(execution_time), to_dict, from_dict, hash/eq, success_rate, post_init
  - ArmoryRegistry: _compare_version, register升级, unregister, find_by_*全套, recommend,
    recommend_bundle, get_stats, update_status全分支, _load_from_store, _persist_to_store,
    find_similar, list_all过滤
  - 便捷函数: get_armory_registry单例, get_armory_dispatcher, get_weapon_lifecycle, get_weapon_loader
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.armory import (
    ArmoryRegistry,
    WeaponCategory,
    WeaponMetadata,
    WeaponState,
    WeaponType,
    get_armory_dispatcher,
    get_armory_registry,
    get_weapon_lifecycle,
    get_weapon_loader,
)

# ────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────────────────────


def _make_weapon(weapon_id="skill:test", name="test", **kwargs):
    """快速创建 WeaponMetadata"""
    defaults = {
        "id": weapon_id,
        "name": name,
        "type": WeaponType.SKILL,
        "category": WeaponCategory.COGNITIVE,
    }
    defaults.update(kwargs)
    return WeaponMetadata(**defaults)


# =============================================================================
# Part 1: WeaponMetadata 数据类
# =============================================================================


class TestWeaponRecordUsage:
    """record_usage() 方法全分支"""

    def test_record_usage_success_updates_stats(self):
        w = _make_weapon()
        w.record_usage(success=True)
        assert w.usage_count == 1
        assert w.success_count == 1
        assert w.failure_count == 0
        assert w.last_used is not None

    def test_record_usage_failure_updates_stats(self):
        w = _make_weapon()
        w.record_usage(success=False)
        assert w.usage_count == 1
        assert w.success_count == 0
        assert w.failure_count == 1

    def test_record_usage_updates_health_score(self):
        w = _make_weapon()
        original = w.health_score
        w.record_usage(success=True)
        # 健康评分应该变化（不会等于初始50.0）
        assert w.health_score != original

    def test_record_usage_multiple_calls(self):
        w = _make_weapon()
        for _ in range(10):
            w.record_usage(success=True)
        assert w.usage_count == 10
        assert w.success_count == 10

    def test_record_usage_with_execution_time_first_time(self):
        """首次记录执行时间 — avg_execution_time 直接设置"""
        w = _make_weapon()
        w.record_usage(success=True, execution_time=2.5)
        assert w.avg_execution_time == 2.5

    def test_record_usage_with_execution_time_subsequent(self):
        """第二次记录执行时间 — 加权平均"""
        w = _make_weapon()
        w.record_usage(success=True, execution_time=2.0)
        w.record_usage(success=True, execution_time=4.0)
        # avg = (2.0 * 1 + 4.0) / 2 = 3.0
        assert w.avg_execution_time == 3.0

    def test_record_usage_with_execution_time_multiple(self):
        """多次记录执行时间 — 加权平均"""
        w = _make_weapon()
        w.record_usage(success=True, execution_time=1.0)
        w.record_usage(success=True, execution_time=2.0)
        w.record_usage(success=True, execution_time=3.0)
        # avg after 2: (1*1 + 2)/2 = 1.5
        # avg after 3: (1.5*2 + 3)/3 = (3+3)/3 = 2.0
        assert w.avg_execution_time == 2.0

    def test_record_usage_updates_updated_at(self):
        w = _make_weapon()
        old_updated = w.updated_at
        w.record_usage(success=True)
        assert w.updated_at != old_updated


class TestWeaponSuccessRate:
    """success_rate 属性"""

    def test_success_rate_no_usage(self):
        w = _make_weapon()
        assert w.success_rate is None

    def test_success_rate_all_success(self):
        w = _make_weapon(success_count=5, failure_count=0)
        assert w.success_rate == 1.0

    def test_success_rate_all_failure(self):
        w = _make_weapon(success_count=0, failure_count=5)
        assert w.success_rate == 0.0

    def test_success_rate_partial(self):
        w = _make_weapon(success_count=3, failure_count=2)
        assert w.success_rate == 0.6

    def test_post_init_calculates_success_rate(self):
        """__post_init__ 自动计算 _success_rate"""
        w = _make_weapon(success_count=4, failure_count=1)
        # 内部 _success_rate 被计算，通过 success_rate 属性也可获取
        total = w.success_count + w.failure_count
        assert total == 5
        # 验证属性
        assert w.success_rate == 0.8


class TestWeaponToDict:
    """to_dict() 方法"""

    def test_to_dict_basic(self):
        w = _make_weapon()
        d = w.to_dict()
        assert d["id"] == "skill:test"
        assert d["name"] == "test"
        assert d["type"] == "skill"
        assert d["category"] == "cognitive"
        assert d["state"] == "active"

    def test_to_dict_removes_runtime_instances(self):
        w = _make_weapon()
        d = w.to_dict()
        assert "_skill_instance" not in d
        assert "_sop_instance" not in d

    def test_to_dict_with_scenarios(self):
        w = _make_weapon(applicable_scenarios=["代码生成", "测试"])
        d = w.to_dict()
        assert "代码生成" in d["applicable_scenarios"]

    def test_to_dict_with_card(self):
        from core.skill_graph import SkillCard

        card = SkillCard(
            intent="测试技能卡",
            applicable_when="需要测试时",
        )
        w = _make_weapon(card=card)
        d = w.to_dict()
        assert "card" in d


class TestWeaponFromDict:
    """from_dict() 类方法"""

    def test_from_dict_basic(self):
        data = {
            "id": "skill:test",
            "name": "test",
            "type": "skill",
            "category": "cognitive",
            "state": "active",
        }
        w = WeaponMetadata.from_dict(data)
        assert w.id == "skill:test"
        assert w.type == WeaponType.SKILL
        assert w.category == WeaponCategory.COGNITIVE
        assert w.state == WeaponState.ACTIVE

    def test_from_dict_defaults_category(self):
        data = {"id": "skill:x", "name": "x", "type": "skill", "state": "active"}
        w = WeaponMetadata.from_dict(data)
        assert w.category == WeaponCategory.UNKNOWN

    def test_from_dict_defaults_state(self):
        data = {"id": "skill:x", "name": "x", "type": "skill", "category": "cognitive"}
        w = WeaponMetadata.from_dict(data)
        assert w.state == WeaponState.ACTIVE

    def test_from_dict_with_card(self):
        data = {
            "id": "skill:test",
            "name": "test",
            "type": "skill",
            "category": "cognitive",
            "state": "active",
            "card": {"card_id": "card_001", "name": "test_card"},
        }
        w = WeaponMetadata.from_dict(data)
        # card 字段存在但反序列化简化了
        assert w is not None
        assert w.id == "skill:test"

    def test_from_dict_removes_private_fields(self):
        data = {
            "id": "skill:test",
            "name": "test",
            "type": "skill",
            "category": "cognitive",
            "state": "active",
            "_skill_instance": "should_be_removed",
            "_sop_instance": "should_be_removed",
        }
        w = WeaponMetadata.from_dict(data)
        assert w.id == "skill:test"


class TestWeaponHashEq:
    """__hash__ 和 __eq__ 方法"""

    def test_hash_same_id(self):
        w1 = _make_weapon("skill:a")
        w2 = _make_weapon("skill:a")
        assert hash(w1) == hash(w2)

    def test_hash_different_id(self):
        w1 = _make_weapon("skill:a")
        w2 = _make_weapon("skill:b")
        assert hash(w1) != hash(w2)

    def test_eq_same_id(self):
        w1 = _make_weapon("skill:a")
        w2 = _make_weapon("skill:a")
        assert w1 == w2

    def test_eq_different_id(self):
        w1 = _make_weapon("skill:a")
        w2 = _make_weapon("skill:b")
        assert w1 != w2

    def test_eq_non_weapon(self):
        w = _make_weapon()
        assert w != "not a weapon"
        assert w != 42
        assert w != WeaponMetadata  # 类本身不是实例

    def test_eq_weapon_instance(self):
        """isinstance 检查通过"""
        w1 = _make_weapon("skill:a")
        w2 = _make_weapon("skill:a")
        assert w1 == w2


# =============================================================================
# Part 2: ArmoryRegistry 版本比较
# =============================================================================


class TestCompareVersion:
    """_compare_version() 方法"""

    def test_v1_greater_than_v2(self):
        assert ArmoryRegistry._compare_version("2.0", "1.0") > 0

    def test_v1_less_than_v2(self):
        assert ArmoryRegistry._compare_version("1.0", "2.0") < 0

    def test_equal_versions(self):
        assert ArmoryRegistry._compare_version("1.0", "1.0") == 0

    def test_v1_longer_patch(self):
        """2.0.1 > 2.0"""
        assert ArmoryRegistry._compare_version("2.0.1", "2.0") > 0

    def test_v2_longer_patch(self):
        """1.0 < 1.0.1"""
        assert ArmoryRegistry._compare_version("1.0", "1.0.1") < 0

    def test_different_major(self):
        assert ArmoryRegistry._compare_version("5.0.0", "4.9.9") > 0

    def test_same_major_different_minor(self):
        assert ArmoryRegistry._compare_version("1.5.0", "1.4.0") > 0


# =============================================================================
# Part 3: ArmoryRegistry 注册与注销
# =============================================================================


class TestRegisterEdgeCases:
    """register() 边界情况"""

    def test_register_new_weapon(self):
        r = ArmoryRegistry()
        w = _make_weapon("skill:a")
        assert r.register(w) is True
        assert r.count() == 1

    def test_register_duplicate_same_version(self):
        """已存在且版本相同 → 不覆盖，返回False"""
        r = ArmoryRegistry()
        w1 = _make_weapon("skill:a", name="original", version="1.0")
        w2 = _make_weapon("skill:a", name="updated", version="1.0")
        assert r.register(w1) is True
        assert r.register(w2) is False
        assert r.get("skill:a").name == "original"  # 保持原值

    def test_register_duplicate_lower_version(self):
        """已存在且新版本更低 → 不覆盖"""
        r = ArmoryRegistry()
        w1 = _make_weapon("skill:a", version="2.0")
        w2 = _make_weapon("skill:a", version="1.0", name="lower")
        r.register(w1)
        assert r.register(w2) is False
        assert r.get("skill:a").version == "2.0"

    def test_register_duplicate_higher_version(self):
        """已存在但新版本更高 → 覆盖"""
        r = ArmoryRegistry()
        w1 = _make_weapon("skill:a", version="1.0", name="old")
        w2 = _make_weapon("skill:a", version="2.0", name="new")
        r.register(w1)
        assert r.register(w2) is True
        assert r.get("skill:a").name == "new"
        assert r.get("skill:a").version == "2.0"


class TestUnregister:
    """unregister() 方法"""

    def test_unregister_normal(self):
        r = ArmoryRegistry()
        w = _make_weapon("skill:a", is_preset=False)
        r.register(w)
        assert r.unregister("skill:a") is True
        assert r.count() == 0
        assert r.get("skill:a") is None

    def test_unregister_preset_weapon_fails(self):
        """预置武器不可删除"""
        r = ArmoryRegistry()
        w = _make_weapon("skill:a", is_preset=True)
        r.register(w)
        assert r.unregister("skill:a") is False
        assert r.count() == 1

    def test_unregister_nonexistent(self):
        r = ArmoryRegistry()
        assert r.unregister("nonexistent") is False


# =============================================================================
# Part 4: ArmoryRegistry 检索方法
# =============================================================================


class TestFindByType:
    """find_by_type()"""

    def test_find_by_type_skill(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL))
        r.register(_make_weapon("sop:b", type=WeaponType.SOP))
        results = r.find_by_type(WeaponType.SKILL)
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_find_by_type_no_match(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL))
        results = r.find_by_type(WeaponType.BIND)
        assert results == []

    def test_find_by_type_with_state_filter(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL, state=WeaponState.ACTIVE))
        r.register(_make_weapon("skill:b", type=WeaponType.SKILL, state=WeaponState.DISCOVERED))
        results = r.find_by_type(WeaponType.SKILL, state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"


class TestFindByCategoryWithState:
    """find_by_category() 带状态过滤"""

    def test_find_by_category_with_state_filter(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon("skill:a", category=WeaponCategory.COGNITIVE, state=WeaponState.ACTIVE)
        )
        r.register(
            _make_weapon("skill:b", category=WeaponCategory.COGNITIVE, state=WeaponState.RETIRED)
        )
        results = r.find_by_category(WeaponCategory.COGNITIVE, state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"


class TestFindByScenario:
    """find_by_scenario()"""

    def test_find_by_scenario_match(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成"]))
        r.register(_make_weapon("skill:b", applicable_scenarios=["文档分析"]))
        results = r.find_by_scenario("代码生成")
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_find_by_scenario_no_match(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成"]))
        results = r.find_by_scenario("nonexistent")
        assert results == []

    def test_find_by_scenario_with_state(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon("skill:a", applicable_scenarios=["代码生成"], state=WeaponState.ACTIVE)
        )
        r.register(
            _make_weapon("skill:b", applicable_scenarios=["代码生成"], state=WeaponState.RETIRED)
        )
        results = r.find_by_scenario("代码生成", state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_find_by_scenario_empty_registry(self):
        r = ArmoryRegistry()
        results = r.find_by_scenario("anything")
        assert results == []


class TestFindByScenarios:
    """find_by_scenarios()"""

    def test_match_any(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成"]))
        r.register(_make_weapon("skill:b", applicable_scenarios=["文档分析"]))
        r.register(_make_weapon("skill:c", applicable_scenarios=["测试"]))
        results = r.find_by_scenarios(["代码生成", "文档分析"], match_all=False)
        assert len(results) == 2

    def test_match_all(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成", "文档分析"]))
        r.register(_make_weapon("skill:b", applicable_scenarios=["代码生成"]))
        results = r.find_by_scenarios(["代码生成", "文档分析"], match_all=True)
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_empty_scenarios(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a"))
        results = r.find_by_scenarios([])
        assert results == []

    def test_match_all_no_results(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成"]))
        results = r.find_by_scenarios(["代码生成", "文档分析"], match_all=True)
        assert results == []

    def test_with_state_filter(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:a",
                applicable_scenarios=["代码生成"],
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:b",
                applicable_scenarios=["代码生成"],
                state=WeaponState.RETIRED,
            )
        )
        results = r.find_by_scenarios(["代码生成"], state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"


class TestFindByKeyword:
    """find_by_keyword()"""

    def test_match_name(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", name="LLM调用引擎"))
        r.register(_make_weapon("skill:b", name="文件处理"))
        results = r.find_by_keyword("llm")
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_match_scenario(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", applicable_scenarios=["代码生成"]))
        r.register(_make_weapon("skill:b", applicable_scenarios=["文档分析"]))
        results = r.find_by_keyword("代码")
        assert len(results) == 1

    def test_match_id(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:code_gen"))
        r.register(_make_weapon("skill:doc_analysis"))
        results = r.find_by_keyword("code_gen")
        assert len(results) == 1

    def test_no_match(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a"))
        results = r.find_by_keyword("zzzzzzz")
        assert results == []

    def test_with_state_filter(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", name="LLM引擎", state=WeaponState.ACTIVE))
        r.register(_make_weapon("skill:b", name="LLM工具", state=WeaponState.RETIRED))
        results = r.find_by_keyword("llm", state=WeaponState.ACTIVE)
        assert len(results) == 1

    def test_case_insensitive(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", name="LLM Engine"))
        results = r.find_by_keyword("llm")
        assert len(results) == 1


class TestFindDependents:
    """find_dependents()"""

    def test_with_dependents(self):
        r = ArmoryRegistry()
        w = _make_weapon("skill:base", dependencies=[])
        w2 = _make_weapon("skill:high", dependencies=["skill:base"])
        r.register(w)
        r.register(w2)
        dependents = r.find_dependents("skill:base")
        assert len(dependents) == 1
        assert dependents[0].id == "skill:high"

    def test_no_dependents(self):
        r = ArmoryRegistry()
        w = _make_weapon("skill:solo", dependencies=[])
        r.register(w)
        dependents = r.find_dependents("skill:solo")
        assert dependents == []

    def test_nonexistent_weapon(self):
        r = ArmoryRegistry()
        dependents = r.find_dependents("nonexistent")
        assert dependents == []


class TestFindByHealthScore:
    """find_by_health_score()"""

    def test_all_weapons(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", health_score=30.0))
        r.register(_make_weapon("skill:b", health_score=80.0))
        results = r.find_by_health_score()
        assert len(results) == 2

    def test_min_score(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", health_score=30.0))
        r.register(_make_weapon("skill:b", health_score=80.0))
        results = r.find_by_health_score(min_score=50.0)
        assert len(results) == 1
        assert results[0].id == "skill:b"

    def test_max_score(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", health_score=30.0))
        r.register(_make_weapon("skill:b", health_score=80.0))
        results = r.find_by_health_score(max_score=40.0)
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_range(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", health_score=10.0))
        r.register(_make_weapon("skill:b", health_score=50.0))
        r.register(_make_weapon("skill:c", health_score=90.0))
        results = r.find_by_health_score(min_score=30.0, max_score=70.0)
        assert len(results) == 1
        assert results[0].id == "skill:b"

    def test_with_type_filter(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL, health_score=50.0))
        r.register(_make_weapon("sop:b", type=WeaponType.SOP, health_score=50.0))
        results = r.find_by_health_score(weapon_type=WeaponType.SOP)
        assert len(results) == 1
        assert results[0].id == "sop:b"

    def test_no_results(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", health_score=30.0))
        results = r.find_by_health_score(min_score=90.0)
        assert results == []


# =============================================================================
# Part 5: ArmoryRegistry 推荐与统计
# =============================================================================


class TestRecommend:
    """recommend() 方法"""

    def test_recommend_basic(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:llm",
                name="LLM引擎",
                applicable_scenarios=["AI推理"],
                health_score=90.0,
                usage_count=100,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:file",
                name="文件处理",
                applicable_scenarios=["文件操作"],
                health_score=50.0,
                usage_count=10,
                state=WeaponState.ACTIVE,
            )
        )
        results = r.recommend("AI")
        assert len(results) >= 1

    def test_recommend_filters_low_health(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:good",
                name="LLM引擎",
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:bad",
                name="LLM工具",
                health_score=10.0,
                state=WeaponState.ACTIVE,
            )
        )
        results = r.recommend("LLM")
        assert len(results) == 1
        assert results[0].id == "skill:good"

    def test_recommend_filters_non_active(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:active",
                name="LLM引擎",
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:retired",
                name="LLM旧版",
                health_score=90.0,
                state=WeaponState.RETIRED,
            )
        )
        results = r.recommend("LLM")
        assert len(results) == 1
        assert results[0].id == "skill:active"

    def test_recommend_with_type_filter(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:a",
                name="LLM SKILL",
                type=WeaponType.SKILL,
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "sop:b",
                name="LLM SOP",
                type=WeaponType.SOP,
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        results = r.recommend("LLM", weapon_type=WeaponType.SKILL)
        assert len(results) == 1
        assert results[0].type == WeaponType.SKILL

    def test_recommend_top_k(self):
        r = ArmoryRegistry()
        for i in range(10):
            r.register(
                _make_weapon(
                    f"skill:{i}",
                    name=f"引擎{i}",
                    health_score=50.0 + i,
                    state=WeaponState.ACTIVE,
                )
            )
        results = r.recommend("引擎", top_k=3)
        assert len(results) == 3

    def test_recommend_sorted_by_health(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:low",
                name="LLM引擎",
                health_score=40.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:high",
                name="LLM引擎",
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:mid",
                name="LLM引擎",
                health_score=60.0,
                state=WeaponState.ACTIVE,
            )
        )
        results = r.recommend("LLM")
        # 按健康评分降序
        assert results[0].id == "skill:high"
        assert results[1].id == "skill:mid"


class TestRecommendBundle:
    """recommend_bundle() 方法"""

    def test_recommend_bundle_default_categories(self):
        r = ArmoryRegistry()
        for cat in WeaponCategory:
            r.register(
                _make_weapon(
                    f"skill:{cat.value}",
                    name=f"{cat.value}_weapon",
                    category=cat,
                    health_score=80.0,
                    state=WeaponState.ACTIVE,
                )
            )
        bundle = r.recommend_bundle("test")
        assert isinstance(bundle, dict)
        # 每个类别都应出现在结果中
        for cat in WeaponCategory:
            assert cat.value in bundle

    def test_recommend_bundle_specific_categories(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:a",
                category=WeaponCategory.COGNITIVE,
                health_score=80.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:b",
                category=WeaponCategory.IMMUNE,
                health_score=80.0,
                state=WeaponState.ACTIVE,
            )
        )
        bundle = r.recommend_bundle("test", required_categories=[WeaponCategory.COGNITIVE])
        assert len(bundle) == 1
        assert "cognitive" in bundle

    def test_recommend_bundle_empty_registry(self):
        r = ArmoryRegistry()
        bundle = r.recommend_bundle("test", required_categories=[WeaponCategory.COGNITIVE])
        assert bundle["cognitive"] == []

    def test_recommend_bundle_filters_low_health(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:good",
                category=WeaponCategory.COGNITIVE,
                health_score=90.0,
                state=WeaponState.ACTIVE,
            )
        )
        r.register(
            _make_weapon(
                "skill:bad",
                category=WeaponCategory.COGNITIVE,
                health_score=10.0,
                state=WeaponState.ACTIVE,
            )
        )
        bundle = r.recommend_bundle("test", required_categories=[WeaponCategory.COGNITIVE])
        assert len(bundle["cognitive"]) == 1
        assert bundle["cognitive"][0].id == "skill:good"


class TestGetStats:
    """get_stats() 方法"""

    def test_get_stats_empty(self):
        r = ArmoryRegistry()
        stats = r.get_stats()
        assert stats["total_weapons"] == 0
        assert stats["avg_health_score"] == 0.0
        assert stats["top_weapons"] == []

    def test_get_stats_with_weapons(self):
        r = ArmoryRegistry()
        r.register(
            _make_weapon(
                "skill:a",
                type=WeaponType.SKILL,
                category=WeaponCategory.COGNITIVE,
                state=WeaponState.ACTIVE,
                health_score=80.0,
            )
        )
        r.register(
            _make_weapon(
                "sop:b",
                type=WeaponType.SOP,
                category=WeaponCategory.EXECUTION,
                state=WeaponState.DISCOVERED,
                health_score=40.0,
            )
        )
        stats = r.get_stats()
        assert stats["total_weapons"] == 2
        assert stats["by_type"]["skill"] == 1
        assert stats["by_type"]["sop"] == 1
        assert stats["by_category"]["cognitive"] == 1
        assert stats["by_state"]["active"] == 1
        assert stats["by_state"]["discovered"] == 1
        assert stats["avg_health_score"] == 60.0
        assert len(stats["top_weapons"]) == 2  # 只有2个武器

    def test_get_stats_top_weapons_limited_to_5(self):
        r = ArmoryRegistry()
        for i in range(10):
            r.register(
                _make_weapon(
                    f"skill:{i}",
                    health_score=float(i * 10),
                    state=WeaponState.ACTIVE,
                )
            )
        stats = r.get_stats()
        assert len(stats["top_weapons"]) == 5


class TestListAllWithFilters:
    """list_all() 带过滤参数"""

    def test_list_all_no_filters(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a"))
        r.register(_make_weapon("sop:b", type=WeaponType.SOP))
        assert len(r.list_all()) == 2

    def test_list_all_type_filter(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL))
        r.register(_make_weapon("sop:b", type=WeaponType.SOP))
        results = r.list_all(weapon_type=WeaponType.SOP)
        assert len(results) == 1
        assert results[0].id == "sop:b"

    def test_list_all_state_filter(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", state=WeaponState.ACTIVE))
        r.register(_make_weapon("skill:b", state=WeaponState.RETIRED))
        results = r.list_all(state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"

    def test_list_all_both_filters(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", type=WeaponType.SKILL, state=WeaponState.ACTIVE))
        r.register(_make_weapon("sop:b", type=WeaponType.SOP, state=WeaponState.ACTIVE))
        r.register(_make_weapon("skill:c", type=WeaponType.SKILL, state=WeaponState.RETIRED))
        results = r.list_all(weapon_type=WeaponType.SKILL, state=WeaponState.ACTIVE)
        assert len(results) == 1
        assert results[0].id == "skill:a"


# =============================================================================
# Part 6: ArmoryRegistry update_status 全分支
# =============================================================================


class TestUpdateStatusAllBranches:
    """update_status() — ACTIVE, RETIRED, DEPRECATED, 异常"""

    def test_update_to_active(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", state=WeaponState.DISCOVERED, is_active=False))
        r.update_status("skill:a", WeaponState.ACTIVE)
        w = r.get("skill:a")
        assert w.state == WeaponState.ACTIVE
        assert w.is_active is True
        assert w.activated_at is not None

    def test_update_to_retired(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", state=WeaponState.ACTIVE, is_active=True))
        r.update_status("skill:a", WeaponState.RETIRED)
        w = r.get("skill:a")
        assert w.state == WeaponState.RETIRED
        assert w.is_active is False
        assert w.retired_at is not None

    def test_update_to_deprecated(self):
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", state=WeaponState.ACTIVE, is_active=True))
        r.update_status("skill:a", WeaponState.DEPRECATED)
        w = r.get("skill:a")
        assert w.state == WeaponState.DEPRECATED
        assert w.is_active is False
        assert w.deprecated_at is not None

    def test_update_to_discovered(self):
        """非ACTIVE/RETIRED/DEPRECATED的状态变更 — updated_at 更新"""
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a", state=WeaponState.TRIALED, health_score=50.0))
        old_updated = r.get("skill:a").updated_at
        r.update_status("skill:a", WeaponState.DISCOVERED)
        w = r.get("skill:a")
        assert w.state == WeaponState.DISCOVERED
        # is_active 不变（原状态不是 RETIRED/DEPRECATED，DISCOVERED 也不设 is_active=False）
        # 但武器从 TRIALED -> DISCOVERED，updated_at 应该更新
        assert w.updated_at != old_updated


# =============================================================================
# Part 7: ArmoryRegistry Store 集成
# =============================================================================


class TestLoadFromStore:
    """_load_from_store() 和 _persist_to_store()"""

    def test_load_from_store_no_store(self):
        """无 Store 时 _load_from_store 安全返回"""
        r = ArmoryRegistry(store=None)
        assert r.count() == 0

    def test_load_from_store_empty_data(self):
        """Store 有数据但为空"""
        mock_store = MagicMock()
        mock_store.load.return_value = {}
        r = ArmoryRegistry(store=mock_store)
        assert r.count() == 0

    def test_load_from_store_with_data(self):
        """Store 中有武器数据，正确加载"""
        w = _make_weapon("skill:loaded", name="loaded_weapon")
        mock_store = MagicMock()
        mock_store.load.return_value = {"skill:loaded": w.to_dict()}
        r = ArmoryRegistry(store=mock_store)
        assert r.count() == 1
        assert r.get("skill:loaded") is not None

    def test_load_from_store_corrupted_data(self):
        """Store 中有损坏数据 — 忽略，不崩溃"""
        mock_store = MagicMock()
        mock_store.load.return_value = {
            "skill:good": _make_weapon("skill:good").to_dict(),
            "skill:bad": {"corrupted": True, "missing_fields": True},
        }
        r = ArmoryRegistry(store=mock_store)
        # 损坏数据被忽略，但好的数据加载了
        assert r.count() >= 1
        assert r.get("skill:good") is not None

    def test_persist_to_store_no_store(self):
        """无 Store 时 _persist 安全返回"""
        r = ArmoryRegistry(store=None)
        r.register(_make_weapon("skill:a"))
        # 不应崩溃

    def test_persist_to_store_called_on_register(self):
        """注册时自动持久化"""
        mock_store = MagicMock()
        r = ArmoryRegistry(store=mock_store)
        r.register(_make_weapon("skill:a"))
        # save 应该被调用
        assert mock_store.save.called

    def test_persist_to_store_called_on_unregister(self):
        """注销时自动持久化"""
        mock_store = MagicMock()
        r = ArmoryRegistry(store=mock_store)
        r.register(_make_weapon("skill:a", is_preset=False))
        mock_store.save.reset_mock()
        r.unregister("skill:a")
        assert mock_store.save.called

    def test_persist_to_store_called_on_update_status(self):
        """update_status 时自动持久化"""
        mock_store = MagicMock()
        r = ArmoryRegistry(store=mock_store)
        r.register(_make_weapon("skill:a"))
        mock_store.save.reset_mock()
        r.update_status("skill:a", WeaponState.RETIRED)
        assert mock_store.save.called

    def test_persist_to_store_called_on_record_usage(self):
        """record_usage 时自动持久化"""
        mock_store = MagicMock()
        r = ArmoryRegistry(store=mock_store)
        r.register(_make_weapon("skill:a"))
        mock_store.save.reset_mock()
        r.record_usage("skill:a", True)
        assert mock_store.save.called


class TestFindSimilar:
    """find_similar() 方法"""

    @patch("core.capability_meta.CapabilityComparator")
    def test_find_similar_delegates(self, mock_comp):
        """验证 find_similar 委托给 CapabilityComparator"""
        mock_comp.find_similar.return_value = [
            (_make_weapon("skill:a"), 0.9),
            (_make_weapon("skill:b"), 0.8),
        ]
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a"))
        r.register(_make_weapon("skill:b"))

        results = r.find_similar("skill:a", top_k=3, min_similarity=0.1)
        assert len(results) == 2

    @patch("core.capability_meta.CapabilityComparator")
    def test_find_similar_empty(self, mock_comp):
        mock_comp.find_similar.return_value = []
        r = ArmoryRegistry()
        results = r.find_similar("skill:a")
        assert results == []


# =============================================================================
# Part 8: 便捷函数
# =============================================================================


class TestGetArmoryRegistry:
    """get_armory_registry() 单例"""

    def test_singleton_behavior(self):
        """多次调用返回同一实例"""
        r1 = get_armory_registry()
        r2 = get_armory_registry()
        assert r1 is r2

    def test_with_store(self):
        """带 store 参数调用"""
        mock_store = MagicMock()
        mock_store.load.return_value = None
        r = get_armory_registry(store=mock_store)
        assert r is not None


class TestGetArmoryDispatcher:
    """get_armory_dispatcher()"""

    @patch("core.armory_lifecycle.ArmoryDispatcher")
    def test_get_dispatcher(self, mock_disp):
        mock_disp.return_value = MagicMock()
        d = get_armory_dispatcher()
        assert d is not None
        mock_disp.assert_called_once()


class TestGetWeaponLifecycle:
    """get_weapon_lifecycle()"""

    @patch("core.armory_lifecycle.WeaponLifecycle")
    def test_get_lifecycle(self, mock_lc):
        mock_lc.return_value = MagicMock()
        lc = get_weapon_lifecycle()
        assert lc is not None
        mock_lc.assert_called_once()


class TestGetWeaponLoader:
    """get_weapon_loader()"""

    @patch("core.armory_lifecycle.WeaponLoader")
    def test_get_loader(self, mock_loader):
        mock_loader.return_value = MagicMock()
        loader = get_weapon_loader()
        assert loader is not None
        mock_loader.assert_called_once()


# =============================================================================
# Part 9: 边界覆盖（未覆盖行专项）
# =============================================================================


class TestEdgeCoverage:
    """针对剩余未覆盖行的专项测试"""

    def test_remove_from_indexes_with_scenarios_and_deps(self):
        """覆盖 _remove_from_indexes 中 scenario/dep 清理逻辑 (L315, L317)"""
        r = ArmoryRegistry()
        w = _make_weapon(
            "skill:a",
            applicable_scenarios=["代码生成", "测试"],
            dependencies=["skill:base"],
            is_preset=False,
        )
        r.register(w)
        assert len(r.find_by_scenario("代码生成")) == 1
        assert len(r.find_dependents("skill:base")) == 1
        # 注销触发 _remove_from_indexes — 覆盖 L315, L317
        r.unregister("skill:a")
        assert len(r.find_by_scenario("代码生成")) == 0
        assert len(r.find_dependents("skill:base")) == 0

    def test_record_usage_nonexistent_weapon(self):
        """覆盖 record_usage 对不存在的武器抛出 ValueError (L616)"""
        r = ArmoryRegistry()
        try:
            r.record_usage("nonexistent", True)
            assert False, "应该抛出 ValueError"
        except ValueError:
            pass

    def test_record_usage_with_execution_time_via_registry(self):
        """registry.record_usage 通过委托触发武器级别的 record_usage"""
        r = ArmoryRegistry()
        r.register(_make_weapon("skill:a"))
        r.record_usage("skill:a", True)
        w = r.get("skill:a")
        assert w.usage_count == 1
        assert w.success_count == 1
