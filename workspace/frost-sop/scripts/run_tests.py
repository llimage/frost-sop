#!/usr/bin/env python
"""
FROST-SOP 高效测试运行器
输出干净的单行摘要，避免输出数万行测试日志污染上下文

用法:
  python scripts/run_tests.py              # 全量测试 + coverage
  python scripts/run_tests.py --no-cov     # 全量测试，不跑coverage
  python scripts/run_tests.py tests/test_xxx.py  # 指定测试文件
  python scripts/run_tests.py --quick      # 只跑快速测试（跳过慢测试）
"""

import json
import os
import re
import subprocess
import sys


def main():
    args = sys.argv[1:]
    no_cov = "--no-cov" in args
    quick = "--quick" in args
    target_args = [a for a in args if not a.startswith("--")]

    # 构建pytest命令
    cmd = [
        sys.executable,
        "-X",
        "utf8",
        "-m",
        "pytest",
        "--tb=short",  # 只显示失败摘要
        "-q",  # 安静模式
        "--no-header",  # 不显示header
        "-p",
        "no:warnings",  # 禁用warnings
    ]

    if quick:
        cmd.extend(["-m", "not slow"])

    if not no_cov:
        cmd.extend(
            [
                "--cov=core",
                "--cov=skills",
                "--cov=api",
                "--cov=stores",
                "--cov=config",
                "--cov-report=term",  # 只term，不要term-missing
            ]
        )

    # 目标测试文件
    if target_args:
        cmd.extend(target_args)
    else:
        cmd.append("tests/")

    # 设置环境
    env = os.environ.copy()
    env["FROST_TESTING"] = "1"

    # 运行并捕获输出
    print("Running tests...", flush=True)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=env,
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        timeout=600,
    )

    output = result.stdout + "\n" + result.stderr

    # 解析测试结果
    passed = 0
    failed = 0
    skipped = 0
    errors = 0

    # 尝试从输出中提取摘要
    # pytest summary line format: "===== N passed, N failed, N skipped in N.NNs ====="
    summary_match = re.search(
        r"(\d+) passed.*?(\d+ failed)?.*?(\d+ skipped)?.*?(\d+ error)?", output
    )
    if summary_match:
        passed = int(summary_match.group(1))
        failed = int(summary_match.group(2) or 0)
        skipped = int(summary_match.group(3) or 0)
        errors = int(summary_match.group(4) or 0)

    # 提取coverage
    coverage = "N/A"
    if not no_cov:
        cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        if cov_match:
            coverage = cov_match.group(1) + "%"

    # 提取失败的测试名称（如果有）
    failed_tests = []
    if failed > 0 or errors > 0:
        for line in output.split("\n"):
            if line.startswith("FAILED") or line.startswith("ERROR"):
                failed_tests.append(line.strip())

    # 提取执行时间
    duration_match = re.search(r"in ([\d.]+)s", output)
    duration = duration_match.group(1) + "s" if duration_match else "N/A"

    # 输出干净的单行摘要
    status = "PASS" if (failed == 0 and errors == 0) else "FAIL"
    print(f"\n{'=' * 60}")
    print(f"RESULT: {status}")
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors:  {errors}")
    print(f"  Coverage: {coverage}")
    print(f"  Duration: {duration}")

    if failed_tests:
        print("\n  Failed tests:")
        for t in failed_tests[:20]:
            print(f"    {t}")

    print(f"{'=' * 60}")

    # 同时写入文件供后续读取
    summary = {
        "status": status,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "errors": errors,
        "coverage": coverage,
        "duration": duration,
        "failed_tests": failed_tests[:20],
    }
    summary_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_result_summary.json"
    )
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # exit code
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()
