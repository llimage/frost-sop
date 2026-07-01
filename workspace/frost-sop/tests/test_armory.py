"""
V5.0 P0 武器注册表 — 验收测试

测试范围：
  1. Weapon（WeaponMetadata别名）数据类：创建、health_score、is_ready
  2. ArmoryRegistry V5.0 新增方法：list_active, search_by_tags, search_by_domain,
     update_status, record_usage, count
  3. 类型别名兼容性：Weapon=WeaponMetadata, WeaponStatus=WeaponState, FunctionDomain=WeaponCategory
  4. migrate_skill_registry_to_armory 迁移工具
  5. V4.0 向后兼容：现有方法不被破坏

运行方式：
  cd workspace/frost-sop
  python -X utf8 -c "import os; os.environ['FROST_TESTING']='1'; import subprocess; subprocess.run(['python','-m','pytest','tests/test_armory_v5.py','-v','--capture=no'])"
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.armory import (
    ArmoryRegistry,
    FunctionDomain,
    Weapon,
    WeaponCategory,
    WeaponMetadata,
    WeaponState,
    WeaponStatus,
    WeaponType,
    migrate_skill_registry_to_armory,
)

# ────────────────────────────────────────────────────────────────────────────
# 测试组 1：类型别名与枚举
# ────────────────────────────────────────────────────────────────────────────


class TestTypeAliases:
    """V5.0 类型别名兼容性"""

    def test_weapon_alias(self):
        """Weapon 是 WeaponMetadata 的别名"""
        assert Weapon is WeaponMetadata

    def test_weapon_status_alias(self):
        """WeaponStatus 是 WeaponState 的别名"""
        assert WeaponStatus is WeaponState

    def test_function_domain_alias(self):
        """FunctionDomain 是 WeaponCategory 的别名"""
        assert FunctionDomain is WeaponCategory

    def test_weapon_type_values(self):
        """WeaponType 包含 V5.0 定义的 6 种类型"""
        assert WeaponType.SKILL.value == "skill"
        assert WeaponType.SOP.value == "sop"
        assert WeaponType.INTEL.value == "intel"
        assert WeaponType.IMMUN.value == "immun"
        assert WeaponType.BIND.value == "bind"
        assert WeaponType.GENE.value == "gene"

    def test_weapon_status_values(self):
        """WeaponStatus 包含 V5.0 定义的 7 种状态"""
        assert WeaponStatus.DISCOVERED.value == "discovered"
        assert WeaponStatus.VALIDATED.value == "validated"
        assert WeaponStatus.TRIALED.value == "trialed"
        assert WeaponStatus.ARCHIVED.value == "archived"
        assert WeaponStatus.ACTIVE.value == "active"
        assert WeaponStatus.DEPRECATED.value == "deprecated"
        assert WeaponStatus.RETIRED.value == "retired"


# ────────────────────────────────────────────────────────────────────────────
# 测试组 2：Weapon 数据类
# ────────────────────────────────────────────────────────────────────────────


class TestWeapon:
    """V5.0 Weapon 数据类测试"""

    def test_create_weapon(self):
        """创建武器——基本字段正确"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
        )
        assert w.id == "skill:test"
        assert w.name == "test"
        assert w.type == WeaponType.SKILL
        assert w.category == FunctionDomain.COGNITIVE

    def test_new_weapon_health_score(self):
        """新武器健康评分为 50.0（V4.0 默认值，0-100 量表）"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
        )
        assert w.health_score == 50.0

    def test_weapon_tags_default_empty(self):
        """新武器 tags 默认为空列表"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
        )
        assert w.tags == []

    def test_weapon_description_default_empty(self):
        """新武器 description 默认为空字符串"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
        )
        assert w.description == ""

    def test_is_ready_active_and_healthy(self):
        """is_ready: ACTIVE 状态 + 健康评分 >= 30 → True"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.ACTIVE,
            health_score=80.0,
        )
        assert w.is_ready is True

    def test_is_ready_not_active(self):
        """is_ready: 非 ACTIVE 状态 → False"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.DISCOVERED,
            health_score=80.0,
        )
        assert w.is_ready is False

    def test_is_ready_low_health(self):
        """is_ready: ACTIVE 但健康评分 < 30 → False"""
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.ACTIVE,
            health_score=15.0,
        )
        assert w.is_ready is False


# ────────────────────────────────────────────────────────────────────────────
# 测试组 3：ArmoryRegistry V5.0 新增方法
# ────────────────────────────────────────────────────────────────────────────


class TestArmoryRegistryV5:
    """V5.0 ArmoryRegistry 新增方法测试"""

    def test_register_and_get(self):
        """注册武器后可通过 get 获取"""
        r = ArmoryRegistry()
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
        )
        r.register(w)
        assert r.get("skill:test") is w

    def test_count(self):
        """count() 返回武器总数"""
        r = ArmoryRegistry()
        assert r.count() == 0
        r.register(
            Weapon(id="skill:a", name="a", type=WeaponType.SKILL, category=FunctionDomain.COGNITIVE)
        )
        r.register(
            Weapon(id="skill:b", name="b", type=WeaponType.SKILL, category=FunctionDomain.COGNITIVE)
        )
        assert r.count() == 2

    def test_list_active(self):
        """list_active() 只返回 is_ready 为 True 的武器"""
        r = ArmoryRegistry()
        w1 = Weapon(
            id="skill:a",
            name="a",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.ACTIVE,
            health_score=80.0,
        )
        w2 = Weapon(
            id="skill:b",
            name="b",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.DISCOVERED,
            health_score=50.0,
        )
        r.register(w1)
        r.register(w2)
        active = r.list_active()
        assert len(active) == 1
        assert active[0].id == "skill:a"

    def test_search_by_tags(self):
        """search_by_tags() 按标签搜索（任一匹配）"""
        r = ArmoryRegistry()
        w1 = Weapon(
            id="skill:a",
            name="a",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            tags=["llm", "text"],
        )
        w2 = Weapon(
            id="skill:b",
            name="b",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            tags=["image"],
        )
        r.register(w1)
        r.register(w2)
        assert len(r.search_by_tags(["llm"])) == 1
        assert len(r.search_by_tags(["text", "image"])) == 2
        assert len(r.search_by_tags(["nonexistent"])) == 0

    def test_search_by_domain(self):
        """search_by_domain() 按功能域搜索"""
        r = ArmoryRegistry()
        w1 = Weapon(
            id="skill:a", name="a", type=WeaponType.SKILL, category=FunctionDomain.COGNITIVE
        )
        w2 = Weapon(id="immun:b", name="b", type=WeaponType.IMMUN, category=FunctionDomain.IMMUNE)
        r.register(w1)
        r.register(w2)
        assert len(r.search_by_domain(FunctionDomain.COGNITIVE)) == 1
        assert len(r.search_by_domain(FunctionDomain.IMMUNE)) == 1

    def test_update_status(self):
        """update_status() 直接更新武器状态"""
        r = ArmoryRegistry()
        w = Weapon(
            id="skill:test",
            name="test",
            type=WeaponType.SKILL,
            category=FunctionDomain.COGNITIVE,
            state=WeaponStatus.DISCOVERED,
            health_score=80.0,
        )
        r.register(w)
        r.update_status("skill:test", WeaponStatus.ACTIVE)
        assert r.get("skill:test").state == WeaponStatus.ACTIVE
        assert r.get("skill:test").activated_at is not None

    def test_update_status_nonexistent_raises(self):
        """update_status() 对不存在的武器抛出 ValueError"""
        r = ArmoryRegistry()
        try:
            r.update_status("nonexistent", WeaponStatus.ACTIVE)
            assert False, "应抛出 ValueError"
        except ValueError:
            pass

    def test_record_usage(self):
        """record_usage() 记录使用（成功和失败）"""
        r = ArmoryRegistry()
        w = Weapon(
            id="skill:test", name="test", type=WeaponType.SKILL, category=FunctionDomain.COGNITIVE
        )
        r.register(w)
        r.record_usage("skill:test", True)
        r.record_usage("skill:test", False)
        weapon = r.get("skill:test")
        assert weapon.usage_count == 2
        assert weapon.success_count == 1
        assert weapon.failure_count == 1


# ────────────────────────────────────────────────────────────────────────────
# 测试组 4：迁移工具
# ────────────────────────────────────────────────────────────────────────────


class TestMigration:
    """V5.0 迁移函数测试"""

    def test_migrate_skill_registry_to_armory(self):
        """migrate_skill_registry_to_armory 正确迁移技能"""

        # 创建模拟 SkillRegistry（frost-sop 没有 SkillRegistry，用 mock 对象）
        class MockSkillRegistry:
            def __init__(self):
                self._catalog = {
                    "call_llm": {"name": "call_llm", "description": "LLM 调用技能", "func": None},
                    "assemble_agent": {
                        "name": "assemble_agent",
                        "description": "Agent 组装",
                        "func": None,
                    },
                }

        sr = MockSkillRegistry()
        armory = ArmoryRegistry()
        count = migrate_skill_registry_to_armory(sr, armory)

        assert count == 2
        assert armory.count() == 2
        assert armory.get("skill:call_llm") is not None
        assert armory.get("skill:assemble_agent") is not None
        # 验证迁移后的武器属性
        w = armory.get("skill:call_llm")
        assert w.type == WeaponType.SKILL
        assert w.state == WeaponStatus.ACTIVE
        assert w.description == "LLM 调用技能"

    def test_migrate_empty_registry(self):
        """迁移空 SkillRegistry 返回 0"""

        class MockSkillRegistry:
            def __init__(self):
                self._catalog = {}

        sr = MockSkillRegistry()
        armory = ArmoryRegistry()
        count = migrate_skill_registry_to_armory(sr, armory)
        assert count == 0
        assert armory.count() == 0


# ────────────────────────────────────────────────────────────────────────────
# 测试组 5：V4.0 向后兼容
# ────────────────────────────────────────────────────────────────────────────


class TestV4BackwardCompat:
    """V5.0 新增功能不破坏 V4.0 已有功能"""

    def test_v4_find_by_category_still_works(self):
        """V4.0 find_by_category() 仍然可用"""
        r = ArmoryRegistry()
        w = Weapon(id="skill:a", name="a", type=WeaponType.SKILL, category=WeaponCategory.COGNITIVE)
        r.register(w)
        results = r.find_by_category(WeaponCategory.COGNITIVE)
        assert len(results) == 1

    def test_v4_list_all_still_works(self):
        """V4.0 list_all() 仍然可用"""
        r = ArmoryRegistry()
        r.register(
            Weapon(id="skill:a", name="a", type=WeaponType.SKILL, category=WeaponCategory.COGNITIVE)
        )
        r.register(
            Weapon(id="sop:b", name="b", type=WeaponType.SOP, category=WeaponCategory.EXECUTION)
        )
        assert len(r.list_all()) == 2
        assert len(r.list_all(weapon_type=WeaponType.SOP)) == 1
