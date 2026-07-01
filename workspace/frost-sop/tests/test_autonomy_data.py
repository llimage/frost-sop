"""
FROST-SOP 深度质量验证 - 验证五：家族自治机制数据真实性

AC-5: 验证长老审计报告和交棒评估的数据是否真实来自资产Store
"""

import os
import sys
from datetime import datetime
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.elder import create_elder
from core.store import Store
from skills.succession import propose_succession_skill
from stores.asset import create_asset_store

# ============ 预置数据 ============


def create_test_data(store: Store, num_tasks: int = 5):
    """
    在Store中预置任务记录

    每个任务记录包含：
    - task_id: 任务ID
    - title: 任务标题
    - stages: 阶段列表，每个阶段包含name和status
    - created_at: 创建时间
    """
    print(f"  📝 预置{num_tasks}条任务记录...")

    for i in range(num_tasks):
        task_id = f"test-task-{i + 1:03d}"

        # 前3个任务成功，后2个任务失败
        if i < 3:
            stages = [
                {"name": "需求分析", "status": "success"},
                {"name": "设计", "status": "success"},
                {"name": "开发", "status": "success"},
                {"name": "测试", "status": "success"},
            ]
            status = "completed"
        else:
            stages = [
                {"name": "需求分析", "status": "success"},
                {"name": "设计", "status": "failed"},
                {"name": "开发", "status": "pending"},
            ]
            status = "failed"

        task_record = {
            "task_id": task_id,
            "title": f"测试任务{i + 1}",
            "stages": stages,
            "status": status,
            "created_at": (datetime.now().replace(day=i + 1)).isoformat(),
        }

        # 存储到Store
        store.save(f"task:{task_id}", task_record)

    print(f"  ✅ 预置完成: {num_tasks}条任务记录")


# ============ 验证函数 ============


def verify_audit_report(report: dict[str, Any], expected_num_tasks: int) -> dict[str, Any]:
    """
    验证审计报告的数据真实性

    Returns:
        {"passed": bool, "checks": list}
    """
    checks = []

    # 检查1：total_tasks是否等于预置数量
    total_tasks = report.get("total_tasks", 0)
    if total_tasks == expected_num_tasks:
        checks.append(
            {
                "name": "total_tasks匹配",
                "passed": True,
                "detail": f"报告中的total_tasks={total_tasks}, 预置数量={expected_num_tasks}",
            }
        )
    else:
        checks.append(
            {
                "name": "total_tasks匹配",
                "passed": False,
                "detail": f"报告中的total_tasks={total_tasks}, 预置数量={expected_num_tasks}",
            }
        )

    # 检查2：successful_tasks是否等于3（前3个任务成功）
    successful_tasks = report.get("successful_tasks", 0)
    if successful_tasks == 3:
        checks.append(
            {
                "name": "successful_tasks匹配",
                "passed": True,
                "detail": f"报告中的successful_tasks={successful_tasks}, 预期=3",
            }
        )
    else:
        checks.append(
            {
                "name": "successful_tasks匹配",
                "passed": False,
                "detail": f"报告中的successful_tasks={successful_tasks}, 预期=3",
            }
        )

    # 检查3：failed_tasks是否等于2（后2个任务失败）
    failed_tasks = report.get("failed_tasks", 0)
    if failed_tasks == 2:
        checks.append(
            {
                "name": "failed_tasks匹配",
                "passed": True,
                "detail": f"报告中的failed_tasks={failed_tasks}, 预期=2",
            }
        )
    else:
        checks.append(
            {
                "name": "failed_tasks匹配",
                "passed": False,
                "detail": f"报告中的failed_tasks={failed_tasks}, 预期=2",
            }
        )

    # 检查4：findings是否非空（审计报告应该包含发现）
    findings = report.get("findings", [])
    if len(findings) > 0:
        checks.append(
            {"name": "findings非空", "passed": True, "detail": f"报告包含{len(findings)}个发现"}
        )
    else:
        checks.append({"name": "findings非空", "passed": False, "detail": "报告不包含任何发现"})

    passed = all(check["passed"] for check in checks)

    return {"passed": passed, "checks": checks, "report": report}


def verify_succession_proposal(proposal: dict[str, Any], expected_num_tasks: int) -> dict[str, Any]:
    """
    验证交棒评估的数据真实性

    Returns:
        {"passed": bool, "checks": list}
    """
    checks = []

    # 检查1：total_tasks_analyzed是否等于预置数量
    total_tasks = proposal.get("total_tasks_analyzed", 0)
    if total_tasks == expected_num_tasks:
        checks.append(
            {
                "name": "total_tasks_analyzed匹配",
                "passed": True,
                "detail": f"评估中的total_tasks_analyzed={total_tasks}, 预置数量={expected_num_tasks}",
            }
        )
    else:
        checks.append(
            {
                "name": "total_tasks_analyzed匹配",
                "passed": False,
                "detail": f"评估中的total_tasks_analyzed={total_tasks}, 预置数量={expected_num_tasks}",
            }
        )

    # 检查2：proposal是否包含必要字段
    required_fields = ["recommend", "reason", "failure_rate", "total_tasks_analyzed"]
    missing_fields = [f for f in required_fields if f not in proposal]
    if not missing_fields:
        checks.append(
            {"name": "proposal字段完整", "passed": True, "detail": f"包含字段: {required_fields}"}
        )
    else:
        checks.append(
            {"name": "proposal字段完整", "passed": False, "detail": f"缺少字段: {missing_fields}"}
        )

    passed = all(check["passed"] for check in checks)

    return {"passed": passed, "checks": checks, "proposal": proposal}


def test_autonomy_data():
    """AC-5: 验证家族自治机制数据真实性"""
    print("=" * 60)
    print("验证五：家族自治机制数据真实性 (AC-5)")
    print("=" * 60)

    # 创建临时资产Store（使用内存后端，不污染真实资产Store）
    print("\n📂 创建临时资产Store...")
    temp_store = create_asset_store(backend="memory")

    # 预置测试数据
    print("\n📝 预置测试数据...")
    create_test_data(temp_store, num_tasks=5)

    # 验证预置数据
    print("\n🔍 验证预置数据...")
    task_keys = [k for k in temp_store.list_keys() if k.startswith("task:")]
    print(f"  预置的任务记录数: {len(task_keys)}")

    if len(task_keys) != 5:
        print(f"  ❌ 预置数据失败: 期望5条, 实际{len(task_keys)}条")
        return {"passed": False, "reason": f"预置数据失败: 期望5条, 实际{len(task_keys)}条"}

    # 创建长老Agent
    print("\n🤖 创建长老Agent...")
    elder = create_elder("test_elder")

    # 验证1：长老审计报告
    print("\n" + "-" * 60)
    print("验证1：长老审计报告数据真实性")
    print("-" * 60)

    print("\n  🔄 调用audit_family Skill...")
    try:
        # 准备context
        context = {"_asset_store": temp_store, "_elder_agent": elder}

        # 调用audit_family Skill
        # 注意：audit_family是elder的一个Skill
        audit_skill = elder.skills.get("audit_family")
        if audit_skill is None:
            print("  ❌ 长老Agent缺少audit_family Skill")
            audit_result = {"passed": False, "reason": "长老Agent缺少audit_family Skill"}
        else:
            result_ctx = audit_skill.execute(context)
            report = result_ctx.get("_audit_report", {})

            print("  ✅ 审计完成")
            print(f"     报告摘要: {report.get('summary', '无摘要')[:100]}...")

            # 验证报告数据真实性
            print("\n  🔍 验证报告数据真实性...")
            audit_result = verify_audit_report(report, expected_num_tasks=5)

            if audit_result["passed"]:
                print("  ✅ 验证通过")
            else:
                print("  ❌ 验证失败:")
                for check in audit_result["checks"]:
                    if not check["passed"]:
                        print(f"      - {check['name']}: {check['detail']}")

    except Exception as e:
        print(f"  ❌ 执行异常: {type(e).__name__}: {e}")
        audit_result = {"passed": False, "reason": f"执行异常: {e}"}

    # 验证2：交棒评估数据真实性
    print("\n" + "-" * 60)
    print("验证2：交棒评估数据真实性")
    print("-" * 60)

    print("\n  🔄 调用propose_succession Skill...")
    try:
        # 准备context
        context = {"_asset_store": temp_store}

        # 调用propose_succession Skill
        result_ctx = propose_succession_skill.execute(context)
        proposal = result_ctx.get("_succession_proposal", {})

        print("  ✅ 评估完成")
        print(f"     交棒建议: {proposal.get('recommend', '未知')}")

        # 验证评估数据真实性
        print("\n  🔍 验证评估数据真实性...")
        succession_result = verify_succession_proposal(proposal, expected_num_tasks=5)

        if succession_result["passed"]:
            print("  ✅ 验证通过")
        else:
            print("  ❌ 验证失败:")
            for check in succession_result["checks"]:
                if not check["passed"]:
                    print(f"      - {check['name']}: {check['detail']}")

    except Exception as e:
        print(f"  ❌ 执行异常: {type(e).__name__}: {e}")
        succession_result = {"passed": False, "reason": f"执行异常: {e}"}

    # 汇总结果
    print("\n" + "=" * 60)
    print("AC-5 验证结果汇总")
    print("=" * 60)

    all_passed = audit_result.get("passed", False) and succession_result.get("passed", False)

    print(f"\n长老审计报告: {'✅ 通过' if audit_result.get('passed', False) else '❌ 失败'}")
    print(f"交棒评估: {'✅ 通过' if succession_result.get('passed', False) else '❌ 失败'}")

    print(f"\n{'✅' if all_passed else '❌'} AC-5 验证结果: {'通过' if all_passed else '不通过'}")
    print("  要求: 审计报告和交棒评估引用真实数据")
    print(f"  实际: {'全部通过' if all_passed else '有失败项'}")

    return {
        "audit_result": audit_result,
        "succession_result": succession_result,
        "passed": all_passed,
    }


if __name__ == "__main__":
    result = test_autonomy_data()

    print("\n" + "=" * 60)
    print("AC-5 验证完成")
    print("=" * 60)
