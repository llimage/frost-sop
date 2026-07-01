"""
F5 深度质量测试 - 长老审计端到端
ELDER-01 至 ELDER-06 共6个深度测试用例
"""

import os
import sys

# 把 frost-sop/ 目录加入 sys.path
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _PROJECT_ROOT)

from agents.elder import create_elder
from stores.asset import create_asset_store


# ================================================================
# 辅助函数
# ================================================================
def _create_elder_context(asset_store):
    """创建长老审计的 context"""
    return {
        "_asset_store": asset_store,
        "_constitution_store": None,
    }


def _run_audit(asset_store):
    """运行长老审计，返回报告和 context"""
    elder = create_elder("test_elder", asset_store=asset_store)
    context = _create_elder_context(asset_store)
    result = elder.run(["audit_family"], context)
    report = result.get("_audit_report", {})
    return report, result


# ================================================================
# ELDER-01: 数据完整性
# 预置5条任务数据（包含完整 stages 列表），长老执行审计
# 预期：statistics 中 total_tasks=5，successful_tasks+failed_tasks=5，
#        total_lessons 等于预置的错题本数量
# ================================================================
def test_elder_01_data_integrity():
    print("  [ELDER-01] 数据完整性...", end=" ")

    asset_store = create_asset_store(backend="memory")

    # 预置5条任务（3成功2失败），包含完整 stages
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
                {"name": "修复", "status": "failed", "output": "合规校验未通过"},
            ],
        },
        {
            "task_id": "t05",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "failed", "output": "合规校验失败"},
            ],
        },
    ]
    for t in tasks:
        asset_store.save(f"task:{t['task_id']}", t)

    # 预置3条错题本
    lessons = [
        {"task_id": "t04", "error_type": "compliance", "description": "修复方案缺少审查阶段"},
        {"task_id": "t05", "error_type": "compliance", "description": "代码实现包含禁止Skill"},
        {"task_id": "t03", "error_type": "performance", "description": "耗时过长"},
    ]
    for i, l in enumerate(lessons):
        asset_store.save(f"lesson:{l['task_id']}:{l['error_type']}", l)

    report, _ = _run_audit(asset_store)
    stats = report.get("statistics", {})

    # 验证
    assert stats.get("total_tasks") == 5, f"total_tasks 应为5，实际为 {stats.get('total_tasks')}"
    assert stats.get("successful_tasks") == 3, (
        f"successful_tasks 应为3，实际为 {stats.get('successful_tasks')}"
    )
    assert stats.get("failed_tasks") == 2, f"failed_tasks 应为2，实际为 {stats.get('failed_tasks')}"
    assert stats.get("successful_tasks") + stats.get("failed_tasks") == 5, (
        "successful+failed 应等于5"
    )
    assert stats.get("total_lessons") == 3, (
        f"total_lessons 应为3，实际为 {stats.get('total_lessons')}"
    )

    # 同时验证顶层字段（兼容）
    assert report.get("total_tasks") == 5, "顶层字段 total_tasks 也应等于5"
    assert report.get("total_lessons") == 3, "顶层字段 total_lessons 也应等于3"

    print("✅ PASS")
    return True


# ================================================================
# ELDER-02: 语义正确性
# 预置2条失败任务的 output 中包含"合规校验未通过"字样
# 预期：审计报告的 findings 中应包含关于合规失败的描述，
#        recommendations 中应包含 SOP 优化建议
# ================================================================
def test_elder_02_semantic_correctness():
    print("  [ELDER-02] 语义正确性...", end=" ")

    asset_store = create_asset_store(backend="memory")

    # 5条任务：2失败3成功（失败率40% > 30%，且任务数>=5，应触发建议）
    tasks = [
        {
            "task_id": "t01",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "failed", "output": "合规校验未通过：缺少审查阶段"},
            ],
        },
        {
            "task_id": "t02",
            "sop": "DEV-001",
            "status": "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "failed", "output": "合规校验失败：包含禁止Skill"},
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
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
        {
            "task_id": "t05",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        },
    ]
    for t in tasks:
        asset_store.save(f"task:{t['task_id']}", t)

    report, _ = _run_audit(asset_store)

    findings = report.get("findings", [])
    recommendations = report.get("recommendations", [])

    # 验证：findings 中应提及任务执行情况
    assert len(findings) >= 1, "findings 应至少包含1条发现"
    finding_text = " ".join(findings)
    assert "失败" in finding_text or "执行" in finding_text, "findings 应包含关于失败的描述"

    # 验证：失败率 100% > 30%，应触发建议
    assert len(recommendations) >= 1, "失败率100%应触发至少1条建议"
    rec_text = " ".join(recommendations)
    assert "失败率" in rec_text or "优化" in rec_text, "recommendations 应包含失败率或优化相关描述"

    print("✅ PASS")
    return True


# ================================================================
# ELDER-03: 逻辑一致性
# 预置失败率40%（2/5），刚好超过30%阈值
# 预期：审计报告的 recommendations 中必须包含至少1条建议
# ================================================================
def test_elder_03_logic_consistency():
    print("  [ELDER-03] 逻辑一致性（失败率40%>30%）...", end=" ")

    asset_store = create_asset_store(backend="memory")

    # 5条任务，2条失败（失败率40%）
    tasks = [
        {
            "task_id": f"t{i:02d}",
            "sop": "DEV-001",
            "status": "completed" if i < 3 else "failed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success" if i < 3 else "failed"},
            ],
        }
        for i in range(5)
    ]
    # 修复第4、5条任务的 stage output
    tasks[3]["stages"][1]["output"] = "合规校验未通过"
    tasks[4]["stages"][1]["output"] = "合规校验失败"

    for t in tasks:
        asset_store.save(f"task:{t['task_id']}", t)

    report, _ = _run_audit(asset_store)

    stats = report.get("statistics", {})
    recommendations = report.get("recommendations", [])

    # 验证统计数字
    assert stats.get("total_tasks") == 5
    assert stats.get("failed_tasks") == 2
    failure_rate = stats.get("failed_tasks") / max(stats.get("total_tasks"), 1)
    assert failure_rate > 0.3, f"失败率应>30%，实际为 {failure_rate:.0%}"

    # 验证：失败率>30% 且任务数>=5，应触发建议
    assert len(recommendations) >= 1, (
        f"失败率{failure_rate:.0%}>30%应触发建议，但 recommendations 为空"
    )
    print("✅ PASS")
    return True


# ================================================================
# ELDER-04: 逻辑一致性
# 预置成功率100%（5/5）
# 预期：审计报告的 recommendations 中应提示"家族运行状态良好"或无建议
# ================================================================
def test_elder_04_logic_consistency_full_success():
    print("  [ELDER-04] 逻辑一致性（成功率100%）...", end=" ")

    asset_store = create_asset_store(backend="memory")

    # 5条任务，全部成功
    tasks = [
        {
            "task_id": f"t{i:02d}",
            "sop": "DEV-001",
            "status": "completed",
            "stages": [
                {"name": "需求", "status": "success"},
                {"name": "编码", "status": "success"},
            ],
        }
        for i in range(5)
    ]
    for t in tasks:
        asset_store.save(f"task:{t['task_id']}", t)

    report, _ = _run_audit(asset_store)

    stats = report.get("statistics", {})
    recommendations = report.get("recommendations", [])

    # 验证统计数字
    assert stats.get("total_tasks") == 5
    assert stats.get("successful_tasks") == 5
    assert stats.get("failed_tasks") == 0

    # 验证：成功率100%，失败率0% < 30%，不应触发失败率建议
    failure_rate_triggered = any("失败率" in rec for rec in recommendations)
    assert not failure_rate_triggered, "成功率100%不应触发失败率建议"

    # 允许 recommendations 为空，或包含"运行状态良好"类提示（当前实现中无此提示，所以为空是正常的）
    print("✅ PASS")
    return True


# ================================================================
# ELDER-05: 边界健壮性
# 资产Store中无任何任务数据（空Store）
# 预期：审计报告 statistics.total_tasks=0，
#        findings 中包含"家族尚未执行任何任务"或类似提示，不崩溃
# ================================================================
def test_elder_05_empty_store():
    print("  [ELDER-05] 边界健壮性（空Store）...", end=" ")

    asset_store = create_asset_store(backend="memory")
    # 不预置任何数据

    report, _ = _run_audit(asset_store)

    stats = report.get("statistics", {})

    # 验证统计数字
    assert stats.get("total_tasks") == 0, (
        f"空Store时 total_tasks 应为0，实际为 {stats.get('total_tasks')}"
    )
    assert stats.get("successful_tasks") == 0
    assert stats.get("failed_tasks") == 0
    assert stats.get("total_lessons") == 0

    # 验证：findings 应包含关于空家族的提示
    findings = report.get("findings", [])
    assert len(findings) >= 1, "空Store时 findings 应至少包含1条"
    finding_text = " ".join(findings)
    assert "尚未执行" in finding_text or "无任务" in finding_text or "0个" in finding_text, (
        f"findings 应提示无任务，实际为: {findings}"
    )

    print("✅ PASS")
    return True


# ================================================================
# ELDER-06: 边界健壮性
# 资产Store不存在（context 中无 _asset_store）
# 预期：返回错误报告（status: error），不抛出异常
# ================================================================
def test_elder_06_no_asset_store():
    print("  [ELDER-06] 边界健壮性（无Asset Store）...", end=" ")

    # 不传入 _asset_store
    elder = create_elder("test_elder")
    context = {"_constitution_store": None}
    result = elder.run(["audit_family"], context)

    report = result.get("_audit_report", {})

    # 验证：应返回错误报告，而不是崩溃
    assert report is not None, "无Asset Store时应返回报告，不应返回None"
    assert report.get("status") == "error", (
        f"无Asset Store时 status 应为 'error'，实际为 {report.get('status')}"
    )
    assert "无资产" in report.get("reason", ""), (
        f"reason 应提及无资产Store，实际为: {report.get('reason')}"
    )

    print("✅ PASS")
    return True


# ================================================================
# 主函数
# ================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("F5 深度质量测试 - 长老审计端到端")
    print("=" * 60)

    tests = [
        ("ELDER-01", test_elder_01_data_integrity),
        ("ELDER-02", test_elder_02_semantic_correctness),
        ("ELDER-03", test_elder_03_logic_consistency),
        ("ELDER-04", test_elder_04_logic_consistency_full_success),
        ("ELDER-05", test_elder_05_empty_store),
        ("ELDER-06", test_elder_06_no_asset_store),
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
