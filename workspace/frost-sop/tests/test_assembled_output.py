"""
FROST-SOP 深度质量验证 - 验证四：府兵组装产出质量

AC-4: 验证基于教练模板组装的府兵，执行任务后产出的内容是否专业
"""

import os
import sys
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.parent import create_parent
from skills.assemble import assemble_agent_skill
from stores.asset import create_asset_store

# 测试用例
TEST_CASES = [
    {
        "id": 1,
        "name": "前端开发",
        "requirement": "需要一个开发登录页面的人",
        "task": "写一个HTML登录表单，包含用户名、密码输入框和提交按钮",
        "quality_checks": {"contains_tags": ["<form", "<input", "<button"], "min_length": 50},
    },
    {
        "id": 2,
        "name": "内容创作",
        "requirement": "需要一个写小红书文案的人",
        "task": "写一篇关于FROST框架的介绍，面向技术人员",
        "quality_checks": {
            "contains_keywords": ["FROST", "Agent", "分形", "框架"],
            "min_length": 100,
        },
    },
    {
        "id": 3,
        "name": "数据分析",
        "requirement": "需要一个分析数据的人",
        "task": "分析以下数据：[1, 2, 3, 4, 5]，给出统计信息",
        "quality_checks": {"contains_keywords": ["平均", "总和", "统计", "数据"], "min_length": 50},
    },
]


def check_quality(output: str, checks: dict[str, Any]) -> dict[str, Any]:
    """
    检查产出是否满足质量检查点

    Returns:
        {"passed": bool, "failed_checks": list}
    """
    failed_checks = []

    # 检查包含标签
    if "contains_tags" in checks:
        for tag in checks["contains_tags"]:
            if tag not in output:
                failed_checks.append(f"未包含标签: {tag}")

    # 检查包含关键词
    if "contains_keywords" in checks:
        matched_keywords = []
        for keyword in checks["contains_keywords"]:
            if keyword in output:
                matched_keywords.append(keyword)

        if len(matched_keywords) == 0:
            failed_checks.append(f"未包含任何期望关键词: {checks['contains_keywords']}")

    # 检查最小长度
    if "min_length" in checks:
        if len(output) < checks["min_length"]:
            failed_checks.append(
                f"长度不足: 期望至少{checks['min_length']}字符, 实际{len(output)}字符"
            )

    passed = len(failed_checks) == 0

    return {
        "passed": passed,
        "failed_checks": failed_checks,
        "matched_keywords": matched_keywords if "contains_keywords" in checks else [],
    }


def test_assembled_output():
    """AC-4: 验证府兵组装产出质量"""
    print("=" * 60)
    print("验证四：府兵组装产出质量 (AC-4)")
    print("=" * 60)

    # 加载资产Store
    print("\n📂 加载资产Store...")
    asset_store = create_asset_store(backend="file", path="data/assets.json")

    # 创建父辈Agent
    print("🤖 创建父辈Agent...")
    parent = create_parent("test_parent", asset_store)

    # 统计结果
    passed_count = 0
    results = []

    # 遍历测试用例
    for test_case in TEST_CASES:
        print(f"\n{'-' * 60}")
        print(f"测试用例 {test_case['id']}: {test_case['name']}")
        print(f"{'-' * 60}")
        print(f"  需求: {test_case['requirement']}")
        print(f"  任务: {test_case['task']}")

        # 步骤1：组装府兵
        print("\n  🔧 步骤1：组装府兵...")
        context = {
            "_agent_requirement": test_case["requirement"],
            "_asset_store": asset_store,
            "_parent_agent": parent,
        }

        try:
            result_ctx = assemble_agent_skill.execute(context)
            assembled_agent = result_ctx.get("_assembled_agent")

            if assembled_agent is None:
                print(f"  ❌ 组装失败: {result_ctx.get('_reason', '未知错误')}")
                results.append(
                    {
                        "id": test_case["id"],
                        "name": test_case["name"],
                        "passed": False,
                        "reason": f"组装失败: {result_ctx.get('_reason', '未知错误')}",
                    }
                )
                continue

            print(f"  ✅ 组装成功: {assembled_agent.name}")
            print(f"     技能数: {len(assembled_agent.skills)}")

            # 步骤2：府兵执行任务
            print("\n  🚀 步骤2：府兵执行任务...")

            # 获取府兵的SOP步骤列表
            sop_steps = assembled_agent._sop_steps

            if not sop_steps:
                print("  ⚠️  警告: 府兵的SOP步骤列表为空")
                results.append(
                    {
                        "id": test_case["id"],
                        "name": test_case["name"],
                        "passed": False,
                        "reason": "府兵的SOP步骤列表为空",
                    }
                )
                continue

            print(f"     府兵SOP步骤数: {len(sop_steps)}")

            # 准备任务context
            task_context = {"_task_description": test_case["task"], "_output_type": "text"}

            # 调用府兵的run方法
            # 注意：run()方法接受两个位置参数：sop_steps和initial_context
            try:
                output_ctx = assembled_agent.run(sop_steps, task_context)
                output = output_ctx.get("_result", "")

                if not output:
                    output = output_ctx.get("_generated_content", "")

                print("  ✅ 执行完成")
                print(f"     产出长度: {len(output)} 字符")
                print(f"     产出预览: {output[:200]}...")  # 只显示前200个字符

                # 步骤3：检查产出质量
                print("\n  🔍 步骤3：检查产出质量...")
                quality_result = check_quality(output, test_case["quality_checks"])

                if quality_result["passed"]:
                    print("  ✅ 质量检查通过")
                    passed_count += 1
                    results.append(
                        {
                            "id": test_case["id"],
                            "name": test_case["name"],
                            "passed": True,
                            "output_length": len(output),
                            "matched_keywords": quality_result.get("matched_keywords", []),
                        }
                    )
                else:
                    print("  ❌ 质量检查失败:")
                    for check in quality_result["failed_checks"]:
                        print(f"      - {check}")

                    results.append(
                        {
                            "id": test_case["id"],
                            "name": test_case["name"],
                            "passed": False,
                            "reason": f"质量检查失败: {quality_result['failed_checks']}",
                            "output_length": len(output),
                        }
                    )

            except Exception as e:
                print(f"  ❌ 执行异常: {type(e).__name__}: {e}")
                results.append(
                    {
                        "id": test_case["id"],
                        "name": test_case["name"],
                        "passed": False,
                        "reason": f"执行异常: {e}",
                    }
                )

        except Exception as e:
            print(f"  ❌ 组装异常: {type(e).__name__}: {e}")
            results.append(
                {
                    "id": test_case["id"],
                    "name": test_case["name"],
                    "passed": False,
                    "reason": f"组装异常: {e}",
                }
            )

    # 输出汇总
    print(f"\n{'=' * 60}")
    print("AC-4 验证结果汇总")
    print(f"{'=' * 60}")
    print(f"总测试用例: {len(TEST_CASES)}")
    print(f"通过: {passed_count}")
    print(f"失败: {len(TEST_CASES) - passed_count}")
    print(f"通过率: {passed_count / len(TEST_CASES) * 100:.1f}%")

    # 判断是否通过
    passed = passed_count >= 2  # 要求：3个用例中至少2个满足质量点

    print(f"\n{'✅' if passed else '❌'} AC-4 验证结果: {'通过' if passed else '不通过'}")
    print("  要求: 3个用例中至少2个满足质量点")
    print(f"  实际: {passed_count}个用例满足质量点")

    return {
        "total": len(TEST_CASES),
        "passed": passed_count,
        "pass_rate": passed_count / len(TEST_CASES) * 100,
        "passed": passed,
        "results": results,
    }


if __name__ == "__main__":
    result = test_assembled_output()

    print("\n" + "=" * 60)
    print("AC-4 验证完成")
    print("=" * 60)
