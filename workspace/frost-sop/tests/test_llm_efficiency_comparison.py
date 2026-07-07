"""
LLM效率控制对比测试脚本
对比修改前（temperature=0.7，无格式约束）和修改后（temperature=0.1，有格式约束）的输出质量。

用法: cd workspace/frost-sop && python -X utf8 tests/test_llm_efficiency_comparison.py
"""

import json
import os
import sys
import time
from datetime import datetime

# 确保项目根目录在 sys.path 中
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from skills.llm import call_llm

# ── 测试用例 ──────────────────────────────────────────────────────────
# 模拟OPS-007阶段1的prompt

BASELINE_PROMPT = """对"长上下文记忆管理"进行深度调研，收集：
1. 英文技术文章（Medium、Dev.to、官方博客）
2. 中文技术文章（知乎、CSDN、技术博客）
3. GitHub开源项目（star > 100）
4. 最新论文（arXiv、Google Scholar）

输出：结构化信息列表（包含标题、URL、核心观点）"""

CONSTRAINED_PROMPT = """对"长上下文记忆管理"进行深度调研，收集：
1. 英文技术文章（Medium、Dev.to、官方博客）
2. 中文技术文章（知乎、CSDN、技术博客）
3. GitHub开源项目（star > 100）
4. 最新论文（arXiv、Google Scholar）

输出要求：必须严格按照以下格式输出，不要添加任何解释或说明：

## 信息列表

### [文章/项目1标题]
- URL: [完整链接]
- 核心观点: [100字以内摘要]
- 来源类型: [技术文章/GitHub项目/论文]

### [文章/项目2标题]
- URL: [完整链接]
- 核心观点: [100字以内摘要]
- 来源类型: [技术文章/GitHub项目/论文]

（继续列出所有收集到的信息）

重要：只输出以上内容，不要有以下内容：
- 不要开头说明（如"好的，我来收集信息..."）
- 不要结尾总结（如"综上所述..."）
- 不要元说明（如"这是一个结构化列表..."）"""


def run_test(label: str, prompt: str, temperature: float, runs: int = 3) -> list:
    """运行多次测试，返回结果列表。"""
    results = []
    for i in range(runs):
        print(f"\n{'=' * 60}")
        print(f"[{label}] 第 {i + 1}/{runs} 次运行 (temperature={temperature})")
        print(f"{'=' * 60}")

        start_time = time.time()
        context = {
            "_prompt": prompt,
            "_system_prompt": "你是一个专业的AI助手。请根据要求生成内容。",
            "_temperature": temperature,
            "_max_tokens": 2048,
            "_agent_id": f"test_{label}_{i + 1}",
        }

        try:
            result = call_llm(context)
            elapsed = time.time() - start_time
            response = result.get("_llm_response", "")
            tokens = result.get("_llm_tokens", {})
            backend = result.get("_llm_backend", "unknown")

            result_data = {
                "label": label,
                "run": i + 1,
                "temperature": temperature,
                "elapsed_seconds": round(elapsed, 2),
                "response_length": len(response),
                "response_preview": response[:500],
                "response_full": response,
                "tokens": tokens,
                "backend": backend,
                "success": True,
            }
            print(f"  耗时: {elapsed:.1f}s")
            print(f"  输出长度: {len(response)} 字符")
            print(f"  Token: {tokens.get('total', 'N/A')}")
            print(f"  前200字: {response[:200]}...")

        except Exception as e:
            elapsed = time.time() - start_time
            result_data = {
                "label": label,
                "run": i + 1,
                "temperature": temperature,
                "elapsed_seconds": round(elapsed, 2),
                "error": str(e),
                "success": False,
            }
            print(f"  失败: {e}")

        results.append(result_data)
        time.sleep(1)  # 避免API限速

    return results


def check_format_compliance(text: str, label: str) -> dict:
    """检查输出是否符合格式要求。"""
    checks = {
        "has_info_header": "## 信息列表" in text or "信息列表" in text,
        "has_url": "URL:" in text or "URL：" in text or "http" in text,
        "has_core_viewpoint": "核心观点" in text or "核心" in text,
        "has_source_type": "来源类型" in text or "来源" in text,
        "no_greeting": not any(g in text[:50] for g in ["好的", "我来", "你好", "当然"]),
        "no_closing": not any(c in text[-100:] for c in ["综上", "总的来说", "希望对你"]),
        "no_meta_explanation": "这是一个" not in text[:100] and "以下是" not in text[:30],
    }

    if label == "baseline":
        # 基线测试不要求格式约束，只检查基本内容
        relevant_checks = ["has_url", "has_core_viewpoint"]
    else:
        # 改进测试检查所有格式要求
        relevant_checks = list(checks.keys())

    passed = sum(1 for k in relevant_checks if checks[k])
    total = len(relevant_checks)
    rate = passed / total if total > 0 else 0

    return {
        "checks": {k: checks[k] for k in relevant_checks},
        "passed": passed,
        "total": total,
        "compliance_rate": round(rate, 2),
    }


def main():
    print("=" * 60)
    print("LLM效率控制对比测试")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # ── 第1步：基线测试（temperature=0.7，无格式约束）──
    print("\n" + "=" * 60)
    print("第1步：基线测试（修改前 - temperature=0.7，无格式约束）")
    print("=" * 60)
    baseline_results = run_test("baseline", BASELINE_PROMPT, temperature=0.7, runs=3)

    # ── 第2步：改进测试（temperature=0.1，有格式约束）──
    print("\n" + "=" * 60)
    print("第2步：改进测试（修改后 - temperature=0.1，有格式约束）")
    print("=" * 60)
    improved_results = run_test("improved", CONSTRAINED_PROMPT, temperature=0.1, runs=3)

    # ── 第3步：格式合规率对比 ──
    print("\n" + "=" * 60)
    print("第3步：格式合规率对比")
    print("=" * 60)

    for label, results in [("baseline", baseline_results), ("improved", improved_results)]:
        print(f"\n--- {label.upper()} ---")
        for r in results:
            if r["success"]:
                compliance = check_format_compliance(r["response_full"], label)
                r["compliance"] = compliance
                print(
                    f"  Run {r['run']}: 合规率 {compliance['compliance_rate']:.0%} "
                    f"({compliance['passed']}/{compliance['total']})"
                )
            else:
                print(f"  Run {r['run']}: 失败")

    # ── 第4步：汇总对比 ──
    print("\n" + "=" * 60)
    print("第4步：汇总对比")
    print("=" * 60)

    def avg(lst, key):
        vals = [x.get(key) for x in lst if x.get("success") and x.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0

    def avg_compliance(lst):
        vals = [x.get("compliance", {}).get("compliance_rate", 0) for x in lst if x.get("success")]
        return sum(vals) / len(vals) if vals else 0

    summary = {
        "test_time": datetime.now().isoformat(),
        "baseline": {
            "avg_elapsed": round(avg(baseline_results, "elapsed_seconds"), 2),
            "avg_length": round(avg(baseline_results, "response_length")),
            "avg_tokens": round(
                avg([r.get("tokens", {}) for r in baseline_results if r.get("success")], "total")
            ),
            "avg_compliance": round(avg_compliance(baseline_results), 2),
        },
        "improved": {
            "avg_elapsed": round(avg(improved_results, "elapsed_seconds"), 2),
            "avg_length": round(avg(improved_results, "response_length")),
            "avg_tokens": round(
                avg([r.get("tokens", {}) for r in improved_results if r.get("success")], "total")
            ),
            "avg_compliance": round(avg_compliance(improved_results), 2),
        },
    }

    print(f"\n{'指标':<20} {'基线(0.7)':<20} {'改进(0.1)':<20} {'变化':<20}")
    print("-" * 80)
    print(
        f"{'平均耗时(s)':<20} {summary['baseline']['avg_elapsed']:<20} {summary['improved']['avg_elapsed']:<20} {summary['improved']['avg_elapsed'] - summary['baseline']['avg_elapsed']:+.2f}"
    )
    print(
        f"{'平均输出长度':<20} {summary['baseline']['avg_length']:<20} {summary['improved']['avg_length']:<20} {summary['improved']['avg_length'] - summary['baseline']['avg_length']:+.0f}"
    )
    print(
        f"{'平均Token':<20} {summary['baseline']['avg_tokens']:<20} {summary['improved']['avg_tokens']:<20} {summary['improved']['avg_tokens'] - summary['baseline']['avg_tokens']:+.0f}"
    )
    print(
        f"{'格式合规率':<20} {summary['baseline']['avg_compliance']:.0%}{'':<14} {summary['improved']['avg_compliance']:.0%}{'':<14} {summary['improved']['avg_compliance'] - summary['baseline']['avg_compliance']:+.0%}"
    )

    # ── 保存完整结果 ──
    output_dir = os.path.join(project_root, "output")
    os.makedirs(output_dir, exist_ok=True)

    report_path = os.path.join(output_dir, "llm_efficiency_comparison_report.json")
    full_report = {
        "summary": summary,
        "baseline_results": baseline_results,
        "improved_results": improved_results,
    }

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(full_report, f, ensure_ascii=False, indent=2)

    print(f"\n完整报告已保存到: {report_path}")

    # ── 结论 ──
    print("\n" + "=" * 60)
    print("结论")
    print("=" * 60)

    token_change = summary["improved"]["avg_tokens"] - summary["baseline"]["avg_tokens"]
    compliance_change = (
        summary["improved"]["avg_compliance"] - summary["baseline"]["avg_compliance"]
    )

    if compliance_change > 0:
        print(f"✅ 格式合规率提升: {compliance_change:+.0%}")
    else:
        print(f"⚠️ 格式合规率未提升: {compliance_change:+.0%}")

    if token_change < 0:
        print(
            f"✅ Token消耗降低: {abs(token_change):.0f} tokens ({token_change / summary['baseline']['avg_tokens']:.0%})"
        )
    else:
        print(f"⚠️ Token消耗增加: {token_change:+.0f} tokens")

    print("\n建议:")
    if compliance_change > 0 and token_change <= 0:
        print("  → 改进有效！格式合规率提升且Token未增加，建议推广到其他SOP模板")
    elif compliance_change > 0 and token_change > 0:
        print("  → 格式合规率提升但Token略增，权衡后建议推广（格式正确比省Token更重要）")
    else:
        print("  → 改进效果不明显，需要调整prompt约束方式")


if __name__ == "__main__":
    main()
