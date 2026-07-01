"""
FROST-SOP 长老审计端到端验证
验证 audit_family Skill 能正确读取资产Store数据并生成审计报告。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.elder import create_elder
from stores.asset import create_asset_store

# 预置任务数据（修正规格书语法错误：移除最后一个逗号）
PRESET_TASKS = [
    {
        "task_id": "task-001",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "技术设计", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-002",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "技术设计", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-003",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "技术设计", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-004",
        "sop": "DEV-002",
        "status": "failed",
        "stages": [
            {"name": "问题定位", "status": "success"},
            {"name": "修复方案", "status": "failed", "output": "合规校验未通过：缺少审查阶段"},
        ],
    },
    {
        "task_id": "task-005",
        "sop": "DEV-001",
        "status": "failed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "代码实现", "status": "failed", "output": "合规校验失败：包含禁止Skill"},
        ],
    },
]

PRESET_LESSONS = [
    {
        "task_id": "task-004",
        "error_type": "compliance",
        "description": "修复方案缺少审查阶段",
        "solution": "在SOP中增加审查交付阶段",
    },
    {
        "task_id": "task-005",
        "error_type": "compliance",
        "description": "代码实现包含禁止Skill",
        "solution": "替换为合规的替代Skill",
    },
    {
        "task_id": "task-003",
        "error_type": "performance",
        "description": "代码实现耗时过长",
        "solution": "优化生成逻辑，减少LLM调用次数",
    },
]


def test_elder_e2e():
    print("=== 长老审计端到端验证开始 ===")

    # 1. 创建资产Store并预置数据
    asset_store = create_asset_store(backend="memory")
    for task in PRESET_TASKS:
        asset_store.save(f"task:{task['task_id']}", task)
    for lesson in PRESET_LESSONS:
        # 注意：key 格式为 "lesson:task_id:error_type"
        key = f"lesson:{lesson['task_id']}:{lesson['error_type']}"
        asset_store.save(key, lesson)

    print(f"✅ 预置数据完成：{len(PRESET_TASKS)} 条任务，{len(PRESET_LESSONS)} 条错题本")

    # 2. 创建长老Agent
    elder = create_elder("test_elder", asset_store=asset_store)

    # 3. 执行审计
    context = {"_asset_store": asset_store, "_constitution_store": None}
    result = elder.run(["audit_family"], context)

    report = result.get("_audit_report", {})
    if not report:
        print("❌ 审计报告为空")
        return False

    print(f"   审计报告状态：{report.get('status')}")
    print(f"   审计发现：{report.get('findings')}")
    print(f"   审计建议：{report.get('recommendations')}")

    # 4. 验证统计数字（AC-1）
    stats = report.get("statistics", {})
    total_tasks = stats.get("total_tasks")
    successful_tasks = stats.get("successful_tasks")
    failed_tasks = stats.get("failed_tasks")
    total_lessons = stats.get("total_lessons")

    print("\n   统计数字：")
    print(f"     total_tasks = {total_tasks}")
    print(f"     successful_tasks = {successful_tasks}")
    print(f"     failed_tasks = {failed_tasks}")
    print(f"     total_lessons = {total_lessons}")

    # AC-1: total_tasks=5, successful_tasks=3, failed_tasks=2, total_lessons=3
    if total_tasks != 5:
        print(f"❌ AC-1 失败：total_tasks 应为 5，实际为 {total_tasks}")
        return False
    if successful_tasks != 3:
        print(f"❌ AC-1 失败：successful_tasks 应为 3，实际为 {successful_tasks}")
        return False
    if failed_tasks != 2:
        print(f"❌ AC-1 失败：failed_tasks 应为 2，实际为 {failed_tasks}")
        return False
    if total_lessons != 3:
        print(f"❌ AC-1 失败：total_lessons 应为 3，实际为 {total_lessons}")
        return False

    print("✅ AC-1 通过：统计数字正确")

    # 5. 验证发现和建议（AC-2）
    findings = report.get("findings", [])
    recommendations = report.get("recommendations", [])

    print(f"\n   审计发现数：{len(findings)}")
    print(f"   审计建议数：{len(recommendations)}")

    # AC-2: 至少1条发现和至少1条建议
    if len(findings) < 1:
        print(f"❌ AC-2 失败：审计报告应包含至少 1 条发现，实际为 {len(findings)}")
        return False

    # 失败率=2/5=40% > 30%，应触发SOP优化建议
    if len(recommendations) < 1:
        print(f"❌ AC-2 失败：审计报告应包含至少 1 条建议，实际为 {len(recommendations)}")
        return False

    print("✅ AC-2 通过：审计报告包含发现和建议")
    print("\n=== 长老审计端到端验证通过 ✅ ===")
    return True


if __name__ == "__main__":
    success = test_elder_e2e()
    sys.exit(0 if success else 1)
