"""
F6 SOP端到端测试

验证7个SOP（DEV-001, DEV-002, STR-002, MT-001, OPS-001, OPS-006, STR-001）
完整执行链路，所有阶段均能正确完成。
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.test_f6_mock_llm import patch_openai
from core.sop import SOP
from stores.asset import create_asset_store
from agents.parent import create_parent
from core.store import Store


SOP_SPECS = [
    {"id": "DEV-001", "name": "新功能开发", "stages": 5, "exists": True},
    {"id": "DEV-002", "name": "Bug修复",    "stages": 4, "exists": False},
    {"id": "STR-002", "name": "自进化验证", "stages": 4, "exists": True},
    {"id": "MT-001",  "name": "内容发布",   "stages": 4, "exists": True, "note": "规格书称MKT-001"},
    {"id": "OPS-001", "name": "财务月结",   "stages": 3, "exists": True},
    {"id": "OPS-006", "name": "知识资产管理", "stages": 4, "exists": True},
    {"id": "STR-001", "name": "项目立项",   "stages": 5, "exists": True},
]


def _run_sop(sop_id: str, task_description: str) -> dict:
    """
    端到端执行一个SOP，返回执行结果摘要。
    调用方需使用 with patch_openai(): 包裹本函数。
    """
    sop = SOP.load_from_yaml(f"sops/templates/{sop_id}.yaml")
    asset_store = create_asset_store(backend="memory")
    coord_store = Store()
    parent = create_parent(f"parent_{sop_id}", coord_store)

    # 内化SOP
    context = {
        "_sop_to_internalize": {
            "sop_id": sop.sop_id,
            "name": sop.name,
            "stages": sop.stages,
        },
        "_asset_store": asset_store,
        "_parent_agent": parent,
    }
    context = parent.run(["internalize_sop"], context)

    # 依次执行每个阶段
    stage_results = []
    for stage in sop.stages:
        sc = {
            "_current_stage": stage,
            "_parent_agent": parent,
            "_asset_store": asset_store,
            "_stage_results": stage_results,
            "_output_type": stage.get("output_type", "document"),
        }
        try:
            sc = parent.run(["execute_stage"], sc)
            stage_results = sc.get("_stage_results", stage_results)
        except Exception as e:
            stage_results.append({
                "stage": stage.get("name"),
                "status": "failed",
                "output": f"执行异常: {e}",
            })

    completed = sum(1 for r in stage_results if r.get("status") == "completed")
    failed    = sum(1 for r in stage_results if r.get("status") == "failed")

    return {
        "sop_id": sop_id,
        "sop_name": sop.name,
        "total_stages": len(sop.stages),
        "completed": completed,
        "failed": failed,
        "all_passed": completed == len(sop.stages) and failed == 0,
        "stage_results": stage_results,
    }


def test_e2e_dev001():
    """E2E-01: DEV-001 新功能开发"""
    print("  E2E-01: DEV-001 新功能开发 ... ", end="")
    with patch_openai():
        result = _run_sop("DEV-001", "用户认证功能")
    ok = result["all_passed"] and result["completed"] == 5
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/5)")
    return ok, result


def test_e2e_dev002():
    """E2E-02: DEV-002 Bug修复"""
    print("  E2E-02: DEV-002 Bug修复 ... ", end="")
    with patch_openai():
        result = _run_sop("DEV-002", "登录页面样式错乱")
    ok = result["all_passed"] and result["completed"] == 4
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/4)")
    return ok, result


def test_e2e_str002():
    """E2E-03: STR-002 自进化验证"""
    print("  E2E-03: STR-002 自进化验证 ... ", end="")
    asset_store = create_asset_store(backend="memory")
    for i in range(5):
        asset_store.save(f"task:task-{i:03d}", {
            "task_id": f"task-{i:003d}",
            "sop": "DEV-001",
            "status": "completed" if i < 3 else "failed",
            "stage_results": [{"name": f"阶段{j}", "status": "success" if i < 3 else "failed"} for j in range(5)],
        })
    with patch_openai():
        result = _run_sop("STR-002", "分析历史任务数据")
    has_suggestions = any(
        "建议" in r.get("output", "") or "suggestion" in r.get("output", "").lower()
        for r in result["stage_results"]
    )
    ok = result["all_passed"] and result["completed"] == 4 and has_suggestions
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/4, 有建议={has_suggestions})")
    return ok, result


def test_e2e_mkt001():
    """E2E-04: MT-001 内容发布"""
    print("  E2E-04: MT-001 内容发布 ... ", end="")
    with patch_openai():
        result = _run_sop("MT-001", "FROST框架推广文案")
    ok = result["all_passed"] and result["completed"] == 4
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/4)")
    return ok, result


def test_e2e_ops001():
    """E2E-05: OPS-001 财务月结"""
    print("  E2E-05: OPS-001 财务月结 ... ", end="")
    with patch_openai():
        result = _run_sop("OPS-001", "本月财务数据汇总")
    ok = result["all_passed"] and result["completed"] == 3
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/3)")
    return ok, result


def test_e2e_ops006():
    """E2E-06: OPS-006 知识资产管理"""
    print("  E2E-06: OPS-006 知识资产管理 ... ", end="")
    with patch_openai():
        result = _run_sop("OPS-006", "整理本周知识资产")
    ok = result["all_passed"] and result["completed"] == 4
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/4)")
    return ok, result


def test_e2e_str001():
    """E2E-07: STR-001 项目立项"""
    print("  E2E-07: STR-001 项目立项 ... ", end="")
    with patch_openai():
        result = _run_sop("STR-001", "心域探险新功能立项")
    ok = result["all_passed"] and result["completed"] == 5
    print("✅ 通过" if ok else f"❌ 失败 (完成{result['completed']}/5)")
    return ok, result


def run_all_e2e_tests():
    print("=" * 60)
    print("F6 SOP端到端测试开始")
    print("=" * 60)

    results = []
    passed = 0
    total  = 7

    for test_fn, desc in [
        (test_e2e_dev001, "E2E-01"),
        (test_e2e_dev002, "E2E-02"),
        (test_e2e_str002, "E2E-03"),
        (test_e2e_mkt001, "E2E-04"),
        (test_e2e_ops001, "E2E-05"),
        (test_e2e_ops006, "E2E-06"),
        (test_e2e_str001, "E2E-07"),
    ]:
        ok, info = test_fn()
        results.append({"test": desc, "passed": ok if ok is not None else "skipped", "info": info})
        if ok is True:
            passed += 1
        print()

    print("=" * 60)
    print(
        f"E2E测试完成: {passed}/{total} 通过 (跳过{sum(1 for r in results if r['passed'] == 'skipped')}个)")
    print("=" * 60)
    return passed, total, results


if __name__ == "__main__":
    p, t, r = run_all_e2e_tests()
    sys.exit(0 if p == t else 1)
