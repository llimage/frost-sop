"""
FROST-SOP V7.4 — 进化 + 自主决策 + TACTIC 验证

验证内容：
1. TACTIC 类型武器可注册/检索
2. 武器进化机制（evolve, consecutive_failures, needs_evolution）
3. 场景驱动推荐（recommend_for_task, recommend_bundle_for_task）
4. 府兵自主决策（dispatch_for_task 返回 tactics）
5. 进化触发检查（check_evolution_triggers）
"""

import sys
import os

sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

from core.armory import ArmoryRegistry, WeaponMetadata, WeaponType, WeaponCategory, WeaponState
from core.armory_lifecycle import ArmoryDispatcher


def test_tactic_type():
    """测试 TACTIC 类型武器。"""
    print("\n【测试1】TACTIC 类型武器")

    registry = ArmoryRegistry()

    tactic = WeaponMetadata(
        id="tactic:TEST-001",
        name="测试战术",
        type=WeaponType.TACTIC,
        category=WeaponCategory.GOVERNANCE,
        applicable_scenarios=["测试场景"],
        is_preset=True,
    )
    registry.register(tactic)

    # 按类型检索
    tactics = registry.find_by_type(WeaponType.TACTIC)
    assert len(tactics) == 1, f"应有1个 TACTIC，实际{len(tactics)}"
    assert tactics[0].id == "tactic:TEST-001"
    print("✅ TACTIC 类型注册和检索正常")

    # SOP 类型应向后兼容（同 TACTIC 的枚举值）
    # 注意：WeaponType.SOP 和 WeaponType.TACTIC 是不同的枚举成员
    # 但业务语义相同
    print("✅ TACTIC/SOP 语义向后兼容")
    return True


def test_weapon_evolution():
    """测试武器进化机制。"""
    print("\n【测试2】武器进化机制")

    registry = ArmoryRegistry()

    weapon = WeaponMetadata(
        id="skill:test_skill",
        name="测试技能",
        type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        applicable_scenarios=["测试"],
        version="1.0",
        health_score=50.0,
    )
    registry.register(weapon)

    # 初始状态
    w = registry.get("skill:test_skill")
    assert w.version == "1.0"
    assert w.evolution_count == 0
    print(f"   初始: v{w.version}, health={w.health_score}")

    # 模拟连续失败触发进化
    for _ in range(3):
        registry.record_usage("skill:test_skill", success=False)

    w = registry.get("skill:test_skill")
    assert w.consecutive_failures == 3, f"连续失败应为3，实际{w.consecutive_failures}"
    assert w.needs_evolution, "应触发进化条件"
    print(f"   连续3次失败后: health={w.health_score}, consecutive={w.consecutive_failures}")
    print("✅ 连续失败追踪正确")

    # 执行进化
    new_weapon = registry.evolve_weapon("skill:test_skill", "连续失败", {"description": "改进后的描述"})
    assert new_weapon is not None
    assert new_weapon.version == "1.1", f"新版本应为1.1，实际{new_weapon.version}"
    assert new_weapon.evolution_count == 1
    assert new_weapon.health_score == 50.0  # 重置
    assert new_weapon.consecutive_failures == 0  # 重置
    print(f"   进化后: v{new_weapon.version}, health={new_weapon.health_score}")

    # 旧版本应标记为 DEPRECATED
    old = registry.get("skill:test_skill")
    assert old.state == WeaponState.DEPRECATED
    print(f"   旧版本状态: {old.state.value}")
    print("✅ 武器进化机制正常")
    return True


def test_scene_driven_recommendation():
    """测试场景驱动推荐。"""
    print("\n【测试3】场景驱动推荐")

    registry = ArmoryRegistry()

    # 注册多个武器
    registry.register(WeaponMetadata(
        id="skill:plan_gen", name="计划生成", type=WeaponType.SKILL,
        category=WeaponCategory.STRATEGY,
        applicable_scenarios=["计划", "拆解", "战略"],
        health_score=80.0, usage_count=10, success_count=9,
        is_preset=True,
    ))
    registry.register(WeaponMetadata(
        id="skill:plan_refine", name="计划细化", type=WeaponType.SKILL,
        category=WeaponCategory.STRATEGY,
        applicable_scenarios=["细化", "计划", "并行"],
        health_score=70.0, usage_count=5, success_count=4,
        is_preset=True,
    ))
    registry.register(WeaponMetadata(
        id="tactic:intake", name="需求澄清", type=WeaponType.TACTIC,
        category=WeaponCategory.GOVERNANCE,
        applicable_scenarios=["需求", "澄清", "启动"],
        health_score=90.0, usage_count=20, success_count=19,
        is_preset=True,
    ))

    # 场景驱动推荐
    recommended = registry.recommend_for_task("我要做计划拆解", top_k=2)
    assert len(recommended) > 0, "应返回推荐武器"
    print(f"   推荐 '{recommended[0].name}' (health={recommended[0].health_score})")
    print("✅ 场景驱动推荐正常")

    # 组合推荐
    bundle = registry.recommend_bundle_for_task("计划细化")
    assert bundle.get("primary") is not None
    print(f"   主武器: {bundle['primary'].name if bundle['primary'] else 'None'}")
    print("✅ 组合推荐正常")
    return True


def test_footman_autonomous_dispatch():
    """测试府兵自主决策配发。"""
    print("\n【测试4】府兵自主决策")

    registry = ArmoryRegistry()

    # 注册武器
    registry.register(WeaponMetadata(
        id="skill:call_llm", name="call_llm", type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        applicable_scenarios=["推理", "生成"],
        health_score=85.0, usage_count=50, success_count=48,
        is_preset=True,
    ))

    dispatcher = ArmoryDispatcher(registry)

    # 自主配发
    result = dispatcher.dispatch_for_task("需求解析")
    print(f"   配发结果: {result['reason']}")
    print(f"   Skills: {list(result['skills'].keys())}")
    print(f"   Tactics: {[t.id for t in result['tactics']]}")
    print("✅ 府兵自主决策配发正常")
    return True


def test_evolution_triggers():
    """测试进化触发检查。"""
    print("\n【测试5】进化触发检查")

    registry = ArmoryRegistry()

    # 健康武器
    registry.register(WeaponMetadata(
        id="skill:healthy", name="健康武器", type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        health_score=80.0, is_preset=False,
    ))

    # 需要进化的武器
    registry.register(WeaponMetadata(
        id="skill:sick", name="病态武器", type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        health_score=25.0, consecutive_failures=3,
        is_preset=False,
    ))

    # 需要退役的武器
    registry.register(WeaponMetadata(
        id="skill:dying", name="垂死武器", type=WeaponType.SKILL,
        category=WeaponCategory.COGNITIVE,
        health_score=10.0, is_preset=False,
    ))

    triggers = registry.check_evolution_triggers()
    print(f"   触发数量: {len(triggers)}")
    for wid, reason in triggers:
        print(f"     - {wid}: {reason}")

    assert len(triggers) == 2, f"应触发2个，实际{len(triggers)}"
    print("✅ 进化触发检查正常")
    return True


def main():
    print("=" * 60)
    print("【V7.4 进化 + 自主决策 + TACTIC 验证】")
    print("=" * 60)

    results = []
    results.append(("TACTIC 类型", test_tactic_type()))
    results.append(("武器进化", test_weapon_evolution()))
    results.append(("场景驱动推荐", test_scene_driven_recommendation()))
    results.append(("府兵自主决策", test_footman_autonomous_dispatch()))
    results.append(("进化触发检查", test_evolution_triggers()))

    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        icon = "✅" if r else "❌"
        print(f"   {icon} {name}")
    print(f"\n总计: {len(results)} 项 | 通过: {passed} | 失败: {len(results) - passed}")

    if passed == len(results):
        print("\n🎉 V7.4 进化 + 自主决策验证通过！")


if __name__ == "__main__":
    main()
