"""
F6 多任务并行测试（v3）

验证4个PAR用例。
不使用 patch_openai()（会导致多线程死锁），
改为依赖 FROST_TESTING=1 环境变量（在进程启动前设置，所有线程共享）。
"""

import sys
import os
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# DEFECT-002修复：不再导入 patch_openai，改为依赖 FROST_TESTING 环境变量
# from tests.test_f6_mock_llm import patch_openai

from core.sop import SOP
from stores.asset import create_asset_store
from agents.parent import create_parent
from core.store import Store


def _run_sop_task(
    sop_id: str, task_description: str, results: list, lock: threading.Lock
):
    """在线程中执行一个SOP任务（依赖 FROST_TESTING=1 环境变量）"""
    try:
        asset_store = create_asset_store(backend="memory")
        coord_store = Store()
        parent = create_parent(f"parent_{sop_id}_{threading.get_ident()}", coord_store)
        sop = SOP.load_from_yaml(f"sops/templates/{sop_id}.yaml")
        stage_results = []
        for stage in sop.stages:
            sc = {
                "_current_stage": stage,
                "_parent_agent": parent,
                "_asset_store": asset_store,
                "_stage_results": stage_results,
                "_output_type": stage.get("output_type", "document"),
            }
            sc = parent.run(["execute_stage"], sc)
            stage_results = sc.get("_stage_results", stage_results)

        completed = sum(1 for r in stage_results if r.get("status") == "completed")
        with lock:
            results.append(
                {
                    "sop_id": sop_id,
                    "total_stages": len(sop.stages),
                    "completed": completed,
                    "success": completed == len(sop.stages),
                }
            )
    except Exception as e:
        with lock:
            results.append({"sop_id": sop_id, "error": str(e), "success": False})


# ─────────────────────────────────────────────
# PAR-01: 同时启动2个DEV-001任务
# ─────────────────────────────────────────────
def test_par01_two_dev001():
    print("  PAR-01: 2个DEV-001并行 ... ", end="")
    results = []
    lock = threading.Lock()
    t1 = threading.Thread(
        target=_run_sop_task, args=("DEV-001", "用户认证功能", results, lock)
    )
    t2 = threading.Thread(
        target=_run_sop_task, args=("DEV-001", "数据导出功能", results, lock)
    )
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    if t1.is_alive() or t2.is_alive():
        print("❌ 失败 (线程超时)")
        return False, {"error": "线程超时(60s)"}

    ok = len(results) == 2 and all(r.get("success") for r in results)
    if ok:
        print("✅ 通过 (2个任务均完成)")
    else:
        failed = [r for r in results if not r.get("success")]
        print(
            f"❌ 失败 (success={sum(r.get('success', False) for r in results)}/2, failed={failed})"
        )
    return ok, results


# ─────────────────────────────────────────────
# PAR-02: DEV-001 + MT-001 并行
# ─────────────────────────────────────────────
def test_par02_mixed_types():
    print("  PAR-02: DEV-001 + MT-001 并行 ... ", end="")
    results = []
    lock = threading.Lock()
    t1 = threading.Thread(
        target=_run_sop_task, args=("DEV-001", "用户认证功能", results, lock)
    )
    t2 = threading.Thread(
        target=_run_sop_task, args=("MT-001", "FROST框架推广文案", results, lock)
    )
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=60)

    if t1.is_alive() or t2.is_alive():
        print("❌ 失败 (线程超时)")
        return False, {"error": "线程超时(60s)"}

    ok = len(results) == 2 and all(r.get("success") for r in results)
    if ok:
        print("✅ 通过 (2个任务均完成)")
    else:
        print(f"❌ 失败 (results={results})")
    return ok, results


# ─────────────────────────────────────────────
# PAR-03: 3个不同类型SOP并行
# ─────────────────────────────────────────────
def test_par03_three_mixed():
    print("  PAR-03: 3个不同类型SOP并行 ... ", end="")
    results = []
    lock = threading.Lock()
    threads = [
        threading.Thread(
            target=_run_sop_task, args=("DEV-001", "用户认证", results, lock)
        ),
        threading.Thread(
            target=_run_sop_task, args=("MT-001", "推广文案", results, lock)
        ),
        threading.Thread(
            target=_run_sop_task, args=("OPS-001", "财务月结", results, lock)
        ),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=90)

    if any(t.is_alive() for t in threads):
        print("❌ 失败 (线程超时)")
        return False, {"error": "线程超时(90s)"}

    ok = len(results) == 3 and all(r.get("success") for r in results)
    if ok:
        print("✅ 通过 (3个任务均完成)")
    else:
        print(f"❌ 失败 (results={results})")
    return ok, results


# ─────────────────────────────────────────────
# PAR-04: 任务失败隔离
# ─────────────────────────────────────────────
def _run_failing_task(sop_id: str, results: list, lock: threading.Lock):
    """执行一个会失败的任务（用不存在的SOP）"""
    try:
        sop = SOP.load_from_yaml(f"sops/templates/{sop_id}.yaml")
        asset_store = create_asset_store(backend="memory")
        coord_store = Store()
        parent = create_parent("parent_fail", coord_store)
        stage_results = []
        for stage in sop.stages:
            sc = {
                "_current_stage": stage,
                "_parent_agent": parent,
                "_asset_store": asset_store,
                "_stage_results": stage_results,
                "_output_type": "document",
            }
            sc = parent.run(["execute_stage"], sc)
            stage_results = sc.get("_stage_results", stage_results)
    except Exception as e:
        with lock:
            results.append(
                {"sop_id": sop_id, "expected_failure": True, "error": str(e)}
            )


def test_par04_failure_isolation():
    print("  PAR-04: 任务失败隔离 ... ", end="")
    results = []
    lock = threading.Lock()
    # 任务1：正常
    t1 = threading.Thread(
        target=_run_sop_task, args=("DEV-001", "正常任务", results, lock)
    )
    # 任务2：会失败（用DEV-999不存在的SOP，在 load_from_yaml 时报错）
    t2 = threading.Thread(target=_run_failing_task, args=("DEV-999", results, lock))
    t1.start()
    t2.start()
    t1.join(timeout=60)
    t2.join(timeout=10)

    if t1.is_alive():
        print("❌ 失败 (正常任务线程超时)")
        return False, {"error": "正常任务线程超时(60s)"}

    success_results = [r for r in results if r.get("success")]
    ok = len(success_results) >= 1
    if ok:
        print(f"✅ 通过 (成功={len(success_results)}, 有预期失败)")
    else:
        print(f"❌ 失败 (results={results})")
    return ok, results


# ─────────────────────────────────────────────
# 运行全部PAR测试
# ─────────────────────────────────────────────
def run_all_par_tests():
    print("=" * 60)
    print("F6 多任务并行测试")
    print("=" * 60)

    tests = [
        ("PAR-01", test_par01_two_dev001),
        ("PAR-02", test_par02_mixed_types),
        ("PAR-03", test_par03_three_mixed),
        ("PAR-04", test_par04_failure_isolation),
    ]

    results = []
    passed = 0
    for test_id, test_fn in tests:
        ok, info = test_fn()
        results.append({"test": test_id, "passed": ok, "info": info})
        if ok:
            passed += 1
        print()

    print("=" * 60)
    print(f"PAR测试: {passed}/{len(tests)} 通过")
    print("=" * 60)
    return passed, len(tests), results


if __name__ == "__main__":
    p, t, r = run_all_par_tests()
    sys.exit(0 if p == t else 1)
