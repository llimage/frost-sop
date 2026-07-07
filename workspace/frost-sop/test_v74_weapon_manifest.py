"""
FROST-SOP V7.4 — 全量武器清单验证

验证所有武器：
1. 可注册到武器库
2. 可按类别/场景检索
3. 可配发给府兵执行
4. 武器健康评分机制有效
"""

import sys
import os
import time

sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

env_path = r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop\.env'
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key] = val

os.environ.pop('FROST_TESTING', None)

from core.armory import ArmoryRegistry, WeaponType, WeaponCategory, WeaponState
from core.weapon_manifest import register_all_weapons, get_weapon_manifest, ALL_WEAPONS
from core.event_bus import EventBus, EventType
from core.event_bus_daemon import EventBusDaemon
from core.store import Store
from agents.footman import FootmanAgent
from agents.auditor import AuditorAgent
from agents.parent import ParentAgent
from skills.strategy.plan_generator import plan_generator_skill
from skills.strategy.ceo_assessment import ceo_assessment_skill
from skills.strategy.lesson_archivist import lesson_archivist_skill
from skills.llm import call_llm


def test_weapon_manifest_registration():
    """测试武器清单注册。"""
    print("\n【测试1】武器清单注册")

    registry = ArmoryRegistry()
    count = register_all_weapons(registry)

    assert count > 0, "没有武器被注册"
    print(f"✅ 已注册 {count} 件武器")

    # 验证每个武器都可检索
    for weapon in ALL_WEAPONS:
        found = registry.get(weapon.id)
        assert found is not None, f"武器 {weapon.id} 未找到"
        assert found.name == weapon.name
        print(f"   ✅ {weapon.id}: {weapon.name}")

    return True


def test_weapon_retrieval_by_category():
    """测试按类别检索武器。"""
    print("\n【测试2】按类别检索武器")

    registry = ArmoryRegistry()
    register_all_weapons(registry)

    # 战略层
    strategy = registry.find_by_category(WeaponCategory.STRATEGY)
    assert len(strategy) >= 2, f"战略层武器不足: {len(strategy)}"
    print(f"   战略层: {len(strategy)} 件")

    # 治理层
    governance = registry.find_by_category(WeaponCategory.GOVERNANCE)
    assert len(governance) >= 2, f"治理层武器不足: {len(governance)}"
    print(f"   治理层: {len(governance)} 件")

    # 编排层
    orchestrate = registry.find_by_category(WeaponCategory.ORCHESTRATE)
    assert len(orchestrate) >= 1, f"编排层武器不足: {len(orchestrate)}"
    print(f"   编排层: {len(orchestrate)} 件")

    # SOP
    sops = registry.find_by_type(WeaponType.SOP)
    assert len(sops) >= 2, f"SOP 不足: {len(sops)}"
    print(f"   SOP: {len(sops)} 件")

    return True


def test_weapon_retrieval_by_scenario():
    """测试按场景检索武器。"""
    print("\n【测试3】按场景检索武器")

    registry = ArmoryRegistry()
    register_all_weapons(registry)

    # 计划相关场景
    planning = registry.find_by_scenario("计划细化")
    assert len(planning) >= 1, "未找到计划细化武器"
    print(f"   计划细化: {len(planning)} 件")

    # 审计相关场景
    audit = registry.find_by_scenario("计划审计")
    assert len(audit) >= 1, "未找到审计武器"
    print(f"   计划审计: {len(audit)} 件")

    # 并行相关场景
    parallel = registry.find_by_scenario("并行执行")
    assert len(parallel) >= 1, "未找到并行武器"
    print(f"   并行执行: {len(parallel)} 件")

    return True


def test_weapon_health_score():
    """测试武器健康评分。"""
    print("\n【测试4】武器健康评分")

    registry = ArmoryRegistry()
    register_all_weapons(registry)

    weapon = registry.get("skill:plan_generator")
    assert weapon is not None
    assert weapon.health_score == 50.0, f"初始健康评分应为 50.0，实际 {weapon.health_score}"

    # 模拟成功使用
    registry.record_usage("skill:plan_generator", success=True)
    weapon = registry.get("skill:plan_generator")
    assert weapon.health_score > 50.0, f"使用后健康评分应上升，实际 {weapon.health_score}"
    print(f"   使用后健康评分: {weapon.health_score}")

    # 模拟失败使用
    registry.record_usage("skill:plan_generator", success=False)
    weapon = registry.get("skill:plan_generator")
    print(f"   失败后健康评分: {weapon.health_score}")

    # 检查统计
    stats = registry.get_stats()
    assert stats["total_weapons"] > 0
    print(f"   武器库统计: {stats}")

    return True


def test_skill_weapon_execution():
    """测试 Skill 武器可执行。"""
    print("\n【测试5】Skill 武器可执行")

    # 测试计划生成器
    print("   ▶ 测试 plan_generator...")
    context = {
        "_task_description": "我要做轻量化心理健康服务",
        "_business_type": "一人公司",
        "_budget_cny": 1000,
        "_constraints": ["社恐，不做1V1"],
    }
    result = plan_generator_skill.execute(context)
    assert result.get("_plan") is not None, "计划生成失败"
    assert result.get("_plan_id") is not None
    print(f"   ✅ plan_generator: {result['_plan_id']}")

    # 测试 CEO 评估
    print("   ▶ 测试 ceo_assessment...")
    plan = result["_plan"]
    plan_id = result["_plan_id"]
    eval_ctx = {
        "_plan": plan,
        "_plan_id": plan_id,
        "_intake_answers": {"Q1": "有稳定主业收入", "Q2": "心理咨询师"},
        "_budget_cny": 1000,
    }
    eval_result = ceo_assessment_skill.execute(eval_ctx)
    assert eval_result.get("_assessment") is not None, "CEO评估失败"
    print(f"   ✅ ceo_assessment: {eval_result['_go_no_go']}")

    # 测试教训归档
    print("   ▶ 测试 lesson_archivist...")
    lesson_ctx = {
        "_plan_id": plan_id,
        "_phase_id": "phase_1",
        "_module": "计划",
        "_sop_id": "SOP-PLAN-001",
        "_execution_status": "failed",
        "_error": "SOP 不存在",
    }
    lesson_result = lesson_archivist_skill.execute(lesson_ctx)
    assert lesson_result.get("_lesson") is not None, "教训归档失败"
    print(f"   ✅ lesson_archivist: {lesson_result['_lesson_id']}")

    return True


def test_agent_as_weapon():
    """测试 Agent 作为武器可配发。"""
    print("\n【测试6】Agent 作为武器")

    registry = ArmoryRegistry()
    register_all_weapons(registry)

    # 审计武器
    auditor_weapon = registry.get("skill:auditor")
    assert auditor_weapon is not None
    assert auditor_weapon.category == WeaponCategory.GOVERNANCE
    print(f"   ✅ 审计武器: {auditor_weapon.name} ({auditor_weapon.category.value})")

    # 父辈武器
    parent_weapon = registry.get("skill:plan_refiner")
    assert parent_weapon is not None
    assert parent_weapon.category == WeaponCategory.STRATEGY
    print(f"   ✅ 父辈武器: {parent_weapon.name} ({parent_weapon.category.value})")

    return True


def test_weapon_manifest_summary():
    """测试武器清单摘要。"""
    print("\n【测试7】武器清单摘要")

    manifest = get_weapon_manifest()
    assert len(manifest) > 0, "武器清单为空"

    total = sum(len(v) for v in manifest.values())
    print(f"   总计: {total} 件武器")
    for category, weapons in manifest.items():
        print(f"   [{category}] {len(weapons)} 件")
        for w in weapons:
            print(f"      - {w['id']}: {w['name']}")

    return True


def main():
    print("=" * 60)
    print("【V7.4 全量武器清单验证】")
    print("=" * 60)

    results = []
    results.append(("武器清单注册", test_weapon_manifest_registration()))
    results.append(("按类别检索", test_weapon_retrieval_by_category()))
    results.append(("按场景检索", test_weapon_retrieval_by_scenario()))
    results.append(("健康评分", test_weapon_health_score()))
    results.append(("Skill 可执行", test_skill_weapon_execution()))
    results.append(("Agent 武器化", test_agent_as_weapon()))
    results.append(("清单摘要", test_weapon_manifest_summary()))

    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        icon = "✅" if r else "❌"
        print(f"   {icon} {name}")
    print(f"\n总计: {len(results)} 项 | 通过: {passed} | 失败: {len(results) - passed}")

    if passed == len(results):
        print("\n🎉 全量武器化验证通过！")
        print("所有能力已武器化：Skill + SOP + Store + Armory")


if __name__ == "__main__":
    main()
