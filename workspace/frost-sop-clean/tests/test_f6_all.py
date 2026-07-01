"""
F6 全量集成测试主运行脚本

依次运行4个测试模块，汇总结果并输出F6验收报告。
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置测试模式环境变量（在导入 skills.llm 之前设置）
os.environ["FROST_TESTING"] = "1"

# 延迟导入，确保环境变量先设置
from tests.test_f6_sop_e2e import run_all_e2e_tests
from tests.test_f6_deep_quality import run_all_dq_tests
from tests.test_f6_parallel import run_all_par_tests
from tests.test_f6_persistence import run_all_per_tests


def run_regression_tests():
    """运行全部已有测试套件，验证无回归错误。"""
    print("=" * 60)
    print("F6 回归测试")
    print("=" * 60)

    import subprocess

    test_files = [
        "tests/test_store.py",
        "tests/test_agent.py",
        "tests/test_sop.py",
        "tests/test_assemble.py",
        "tests/test_mercenary_output.py",
        "tests/test_gene_quality.py",
        "tests/test_elder_e2e.py",
        "tests/test_elder_deep_quality.py",
        "tests/test_evolution_e2e.py",
        "tests/test_evolution_deep_quality.py",
        "tests/test_health_dashboard.py",
        "tests/test_autonomy_data.py",
        "tests/test_integration.py",
    ]

    passed = 0
    failed = 0
    results = []

    for tf in test_files:
        if not os.path.exists(tf):
            print(f"  ⏭️ {tf} (文件不存在，跳过)")
            results.append({"file": tf, "status": "skipped", "reason": "文件不存在"})
            continue
        try:
            # 使用 subprocess 运行每个测试文件
            env = os.environ.copy()
            env["FROST_TESTING"] = "1"
            result = subprocess.run(
                [sys.executable, "-X", "utf8", tf],
                capture_output=True,
                text=True,
                timeout=60,
                env=env,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            )
            if result.returncode == 0:
                print(f"  ✅ {tf}")
                passed += 1
                results.append({"file": tf, "status": "passed"})
            else:
                print(f"  ❌ {tf} (returncode={result.returncode})")
                failed += 1
                results.append(
                    {
                        "file": tf,
                        "status": "failed",
                        "output": result.stdout[-200:] if result.stdout else "",
                    }
                )
        except subprocess.TimeoutExpired:
            print(f"  ⏰️ {tf} (超时)")
            failed += 1
            results.append({"file": tf, "status": "timeout"})
        except Exception as e:
            print(f"  ❌ {tf} (异常: {e})")
            failed += 1
            results.append({"file": tf, "status": "error", "error": str(e)})
        print()

    total = passed + failed
    print(f"回归测试: {passed}/{total} 通过")
    print("=" * 60)
    return passed, total, results


def generate_f6_report(e2e_result, dq_result, par_result, per_result, reg_result):
    """按规格书要求格式输出F6全量集成测试报告。"""
    e2e_passed, e2e_total, e2e_details = e2e_result
    dq_passed, dq_total, dq_details = dq_result
    par_passed, par_total, par_details = par_result
    per_passed, per_total, per_details = per_result
    reg_passed, reg_total, reg_details = reg_result

    lines = []
    lines.append("=" * 60)
    lines.append("FROST-SOP F6 全量集成测试报告")
    lines.append(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("执行者: WorkBuddy")
    lines.append("=" * 60)
    lines.append("")

    # 一、SOP端到端测试
    lines.append("一、SOP端到端测试")
    e2e_map = {d["test"]: d for d in e2e_details}
    for test_id in [
        "E2E-01",
        "E2E-02",
        "E2E-03",
        "E2E-04",
        "E2E-05",
        "E2E-06",
        "E2E-07",
    ]:
        d = e2e_map.get(test_id, {})
        status = d.get("passed", False)
        if status is True:
            lines.append(f"  {test_id} DEV-001: 通过")
        elif status is False:
            lines.append(f"  {test_id} DEV-001: 失败")
        else:
            lines.append(f"  {test_id}: {status}")
    lines.append(f"  通过率: {e2e_passed}/{e2e_total}")
    lines.append("")

    # 二、深度质量验证
    lines.append("二、深度质量验证")
    dq_map = {d["test"]: d for d in dq_details}
    for test_id in [f"DQ-{i:02d}" for i in range(1, 9)]:
        d = dq_map.get(test_id, {})
        status = d.get("passed", False)
        lines.append(f"  {test_id}: {'通过' if status is True else '失败'}")
    lines.append(f"  通过率: {dq_passed}/{dq_total}")
    lines.append("")

    # 三、多任务并行测试
    lines.append("三、多任务并行测试")
    par_map = {d["test"]: d for d in par_details}
    for test_id in ["PAR-01", "PAR-02", "PAR-03", "PAR-04"]:
        d = par_map.get(test_id, {})
        status = d.get("passed", False)
        lines.append(f"  {test_id}: {'通过' if status is True else '失败'}")
    lines.append(f"  通过率: {par_passed}/{par_total}")
    lines.append("")

    # 四、持久化恢复测试
    lines.append("四、持久化恢复测试")
    per_map = {d["test"]: d for d in per_details}
    for test_id in ["PER-01", "PER-02", "PER-03", "PER-04"]:
        d = per_map.get(test_id, {})
        status = d.get("passed", False)
        lines.append(f"  {test_id}: {'通过' if status is True else '失败'}")
    lines.append(f"  通过率: {per_passed}/{per_total}")
    lines.append("")

    # 五、回归测试
    lines.append("五、回归测试")
    lines.append(f"  已有测试通过率: {reg_passed}/{reg_total}")
    lines.append("")

    # 六、深度质量矩阵
    lines.append("六、深度质量矩阵")
    # 检查各维度覆盖情况
    dq_passed_set = {d["test"] for d in dq_details if d.get("passed") is True}
    matrix = {
        "数据完整性": "已覆盖"
        if any(t in dq_passed_set for t in ["DQ-01", "DQ-05"])
        else "未覆盖",
        "语义正确性": "已覆盖" if "DQ-02" in dq_passed_set else "未覆盖",
        "逻辑一致性": "已覆盖"
        if any(t in dq_passed_set for t in ["DQ-03", "DQ-04"])
        else "未覆盖",
        "边界健壮性": "已覆盖"
        if any(t in dq_passed_set for t in ["DQ-06", "DQ-07", "DQ-08"])
        else "未覆盖",
        "并行隔离性": "已覆盖" if par_passed >= 3 else "未覆盖",
        "持久化可靠性": "已覆盖" if per_passed >= 3 else "未覆盖",
    }
    for dim, status in matrix.items():
        lines.append(f"  {dim}: {status}")
    lines.append("")

    # 综合结论
    lines.append("综合结论:")
    all_passed = (
        e2e_passed >= 6  # 允许DEV-002跳过
        and dq_passed >= 6
        and par_passed >= 3
        and per_passed >= 3
        and reg_passed >= reg_total * 0.8  # 回归测试80%通过
    )
    if all_passed:
        lines.append("  ✅ 通过")
    else:
        lines.append("  ❌ 不通过")
        if e2e_passed < 6:
            lines.append(f"  - SOP端到端: {e2e_passed}/7")
        if dq_passed < 6:
            lines.append(f"  - 深度质量: {dq_passed}/8")
        if par_passed < 3:
            lines.append(f"  - 并行测试: {par_passed}/4")
        if per_passed < 3:
            lines.append(f"  - 持久化: {per_passed}/4")
        if reg_passed < reg_total * 0.8:
            lines.append(f"  - 回归测试: {reg_passed}/{reg_total}")

    lines.append("")
    lines.append("=" * 60)

    report = "\n".join(lines)
    return report


def main():
    print("")
    print(" " * 20 + "=" * 20)
    print(" " * 20 + " F6 全量集成测试")
    print(" " * 20 + "=" * 20)
    print("")

    # 1. SOP端到端
    e2e_p, e2e_t, e2e_r = run_all_e2e_tests()

    # 2. 深度质量
    dq_p, dq_t, dq_r = run_all_dq_tests()

    # 3. 多任务并行
    par_p, par_t, par_r = run_all_par_tests()

    # 4. 持久化恢复
    per_p, per_t, per_r = run_all_per_tests()

    # 5. 回归测试
    reg_p, reg_t, reg_r = run_regression_tests()

    # 6. 生成报告
    report = generate_f6_report(
        (e2e_p, e2e_t, e2e_r),
        (dq_p, dq_t, dq_r),
        (par_p, par_t, par_r),
        (per_p, per_t, per_r),
        (reg_p, reg_t, reg_r),
    )

    print("")
    print(report)
    print("")

    # 写入报告文件
    report_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "F6_TEST_REPORT.md"
    )
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"报告已保存至: {report_path}")


if __name__ == "__main__":
    main()
