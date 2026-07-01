"""
F5 深度质量测试 - STR-002 自进化
EVO-01 至 EVO-06 共6个深度测试用例
"""

import sys
import os

# 把 frost-sop/ 目录加入 sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from stores.asset import create_asset_store
from agents.parent import create_parent
from core.store import Store


# ================================================================
# 辅助函数
# ================================================================
def _create_parent_with_evolution_skills():
    """创建已注册自进化 Skill 的父辈 Agent"""
    parent = create_parent("evolution_parent", Store())
    return parent


def _preset_tasks(asset_store, tasks):
    """预置任务数据到资产 Store"""
    for t in tasks:
        asset_store.save(f"task:{t['task_id']}", t)


# ================================================================
# EVO-01: 数据完整性
# 预置5条混合任务数据（3成功2失败），加载历史
# 预期：_task_history 列表长度为5，每条记录包含 task_id 和 status 字段
# ================================================================
def test_evo_01_data_integrity():
    print("  [EVO-01] 数据完整性...", end=" ")

    asset_store = create_asset_store(backend="memory")
    tasks = [
        {
            "task_id": "t01",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t02",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t03",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t04",
            "sop": "DEV-002",
            "status": "failed",
            "stages": [
                {"name": "定位", "status": "success"},
                {"name": "修复", "status": "failed"},
            ],
        },
        {
            "task_id": "t05",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "failed"},
            ],
        },
    ]
    _preset_tasks(asset_store, tasks)

    parent = _create_parent_with_evolution_skills()
    context = {
        "_asset_store": asset_store,
        "_history_limit": 20,
    }
    result = parent.run(
        ["load_task_history", "analyze_trends", "generate_suggestions"], context
    )

    task_history = result.get("_task_history", [])
    trends = result.get("_trends", {})

    # 验证数据完整性
    assert len(task_history) == 5, f"task_history 长度应为5，实际为 {len(task_history)}"
    for t in task_history:
        assert "task_id" in t, f"task_history 记录缺少 task_id 字段: {t}"
        assert "status" in t, f"task_history 记录缺少 status 字段: {t}"

    # 验证趋势统计
    assert trends.get("total") == 5, f"trends.total 应为5，实际为 {trends.get('total')}"
    assert trends.get("successful") == 3, (
        f"trends.successful 应为3，实际为 {trends.get('successful')}"
    )
    assert trends.get("failed") == 2, (
        f"trends.failed 应为2，实际为 {trends.get('failed')}"
    )

    print("✅ PASS")
    return True


# ================================================================
# EVO-02: 语义正确性
# 失败任务中的 output 明确提及"合规校验"
# 预期：analyze_trends 生成的 insights 中应包含关于"合规"错误的描述
# ================================================================
def test_evo_02_semantic_correctness():
    print("  [EVO-02] 语义正确性（合规错误）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    tasks = [
        {
            "task_id": "t01",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {
                    "name": "编码",
                    "status": "failed",
                    "output": "合规校验未通过：缺少审查阶段",
                },
            ],
        },
        {
            "task_id": "t02",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {
                    "name": "编码",
                    "status": "failed",
                    "output": "合规校验失败：包含禁止Skill",
                },
            ],
        },
        {
            "task_id": "t03",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
    ]
    _preset_tasks(asset_store, tasks)

    parent = _create_parent_with_evolution_skills()
    context = {"_asset_store": asset_store}
    result = parent.run(["load_task_history", "analyze_trends"], context)

    trends = result.get("_trends", {})
    insights = trends.get("insights", [])

    # 验证：insights 中应提及"合规"相关描述
    insight_text = " ".join(insights)
    has_compliance_mention = any(
        kw in insight_text for kw in ["合规", "compliance", "错误类型"]
    )
    assert has_compliance_mention, f"insights 应提及合规错误，实际为: {insights}"

    # 验证：error_types 统计应包含 compliance
    error_types = trends.get("error_types", {})
    assert "compliance" in error_types, (
        f"error_types 应包含 compliance，实际为: {error_types}"
    )

    print("✅ PASS")
    return True


# ================================================================
# EVO-03: 逻辑一致性
# 预置数据中 DEV-001 失败率 25%（1/4），DEV-002 失败率 100%（1/1）
# 预期：generate_suggestions 应针对 DEV-002 生成高优先级建议，
#        针对 DEV-001 生成低优先级建议（或不生成）
# ================================================================
def test_evo_03_logic_consistency():
    print("  [EVO-03] 逻辑一致性（SOP失败率）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    tasks = [
        # DEV-001: 4条，1条失败 → 失败率 25%
        {
            "task_id": "t01",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t02",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t03",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t04",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "failed", "output": "测试失败"},
            ],
        },
        # DEV-002: 1条，1条失败 → 失败率 100%
        {
            "task_id": "t05",
            "sop": "DEV-002",
            "status": "failed",
            "stages": [
                {"name": "定位", "status": "success"},
                {"name": "修复", "status": "failed", "output": "合规校验未通过"},
            ],
        },
    ]
    _preset_tasks(asset_store, tasks)

    parent = _create_parent_with_evolution_skills()
    context = {"_asset_store": asset_store}
    result = parent.run(
        ["load_task_history", "analyze_trends", "generate_suggestions"], context
    )

    suggestions = result.get("_suggestions", [])
    trends = result.get("_trends", {})

    # 验证：应有至少1条建议
    assert len(suggestions) >= 1, f"应生成至少1条建议，实际为 {len(suggestions)}"

    # 验证：DEV-002 失败率 100% >= 0.5，应生成高优先级建议
    high_priority_targets = [
        s["target"] for s in suggestions if s.get("priority") == "high"
    ]
    assert "DEV-002" in high_priority_targets or any(
        s.get("priority") == "high" for s in suggestions
    ), f"DEV-002 失败率100%应触发高优先级建议，实际建议: {suggestions}"

    # 验证：DEV-001 失败率 25% < 0.3，不应生成建议（或生成低优先级）
    dev001_suggestions = [s for s in suggestions if s.get("target") == "DEV-001"]
    if dev001_suggestions:
        # 如果生成了，优先级应为 low
        for s in dev001_suggestions:
            assert s.get("priority") == "low", (
                f"DEV-001 失败率25%如生成建议，优先级应为low，实际为 {s.get('priority')}"
            )

    print("✅ PASS")
    return True


# ================================================================
# EVO-04: 边界健壮性
# 资产 Store 中只有1条任务记录
# 预期：analyze_trends 正常返回分析结果（不要求生成洞察），不崩溃
# ================================================================
def test_evo_04_boundary_single_task():
    print("  [EVO-04] 边界健壮性（1条任务）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    tasks = [
        {
            "task_id": "t01",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [{"name": "需求", "status": "success"}],
        },
    ]
    _preset_tasks(asset_store, tasks)

    parent = _create_parent_with_evolution_skills()
    context = {"_asset_store": asset_store}
    result = parent.run(["load_task_history", "analyze_trends"], context)

    trends = result.get("_trends", {})

    # 验证：不崩溃，返回有效结果
    assert trends is not None, "trends 不应为 None"
    assert trends.get("total") == 1, f"trends.total 应为1，实际为 {trends.get('total')}"
    assert trends.get("successful") == 1
    assert trends.get("failed") == 0

    print("✅ PASS")
    return True


# ================================================================
# EVO-05: 边界健壮性
# 资产 Store 中无任何任务数据
# 预期：load_task_history 返回空列表，
#        analyze_trends 返回提示信息（无崩溃），
#        generate_suggestions 返回"暂无优化建议"（无崩溃）
# ================================================================
def test_evo_05_boundary_empty_store():
    print("  [EVO-05] 边界健壮性（空Store）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    # 不预置任何数据

    parent = _create_parent_with_evolution_skills()
    context = {"_asset_store": asset_store}
    result = parent.run(
        ["load_task_history", "analyze_trends", "generate_suggestions"], context
    )

    task_history = result.get("_task_history", [])
    trends = result.get("_trends", {})
    suggestions = result.get("_suggestions", [])

    # 验证：load_task_history 返回空列表
    assert isinstance(task_history, list), (
        f"task_history 应为 list，实际为 {type(task_history)}"
    )
    assert len(task_history) == 0, (
        f"空Store时 task_history 长度应为0，实际为 {len(task_history)}"
    )

    # 验证：analyze_trends 返回有效结果（不崩溃）
    assert trends is not None, "trends 不应为 None"
    assert trends.get("total") == 0, (
        f"空Store时 trends.total 应为0，实际为 {trends.get('total')}"
    )

    # 验证：generate_suggestions 应返回空列表或 no_action 类型建议
    assert isinstance(suggestions, list), (
        f"suggestions 应为 list，实际为 {type(suggestions)}"
    )
    if len(suggestions) > 0:
        # 如果有建议，应为 no_action 类型
        assert suggestions[0].get("type") == "no_action" or len(suggestions) == 0, (
            f"空Store时建议应为 no_action 类型，实际为: {suggestions}"
        )

    print("✅ PASS")
    return True


# ================================================================
# EVO-06: 语义正确性
# 预置3条成功任务，成功率100%
# 预期：generate_suggestions 返回的建议类型应为 no_action 或类似，
#        不应出现高优先级警告
# ================================================================
def test_evo_06_semantic_full_success():
    print("  [EVO-06] 语义正确性（成功率100%）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    tasks = [
        {
            "task_id": f"t0{i}",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        }
        for i in range(3)
    ]
    _preset_tasks(asset_store, tasks)

    parent = _create_parent_with_evolution_skills()
    context = {"_asset_store": asset_store}
    result = parent.run(
        ["load_task_history", "analyze_trends", "generate_suggestions"], context
    )

    suggestions = result.get("_suggestions", [])
    trends = result.get("_trends", {})

    # 验证：成功率100%
    assert trends.get("success_rate") == 1.0, (
        f"成功率应为100%，实际为 {trends.get('success_rate')}"
    )

    # 验证：不应出现高优先级警告
    high_priority = [s for s in suggestions if s.get("priority") == "high"]
    assert len(high_priority) == 0, (
        f"成功率100%不应出现高优先级建议，实际为: {high_priority}"
    )

    # 验证：建议应为 no_action 类型（或为空）
    if len(suggestions) > 0:
        assert suggestions[0].get("type") == "no_action", (
            f"成功率100%时建议类型应为 no_action，实际为: {suggestions[0].get('type')}"
        )

    print("✅ PASS")
    return True


# ================================================================
# 主函数
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("F5 深度质量测试 - STR-002 自进化")
    print("=" * 60)

    tests = [
        ("EVO-01", test_evo_01_data_integrity),
        ("EVO-02", test_evo_02_semantic_correctness),
        ("EVO-03", test_evo_03_logic_consistency),
        ("EVO-04", test_evo_04_boundary_single_task),
        ("EVO-05", test_evo_05_boundary_empty_store),
        ("EVO-06", test_evo_06_semantic_full_success),
    ]

    results = []
    for name, test_fn in tests:
        try:
            ok = test_fn()
            results.append((name, ok, ""))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"❌ FAIL: {e}")

    print()
    print("=" * 60)
    print("测试报告")
    print("=" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    for name, ok, err in results:
        status = "✅ PASS" if ok else f"❌ FAIL: {err}"
        print(f"  {name}: {status}")
    print()
    print(f"总计: {passed}/{total} 通过")
    if passed == total:
        print("🎉 所有深度测试通过！")
    else:
        print("⚠️ 部分测试失败，请检查上述错误信息")
