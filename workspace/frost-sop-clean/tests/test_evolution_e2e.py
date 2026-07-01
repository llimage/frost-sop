"""
FROST-SOP STR-002 自进化端到端验证
验证父辈能基于历史任务数据生成 SOP 优化建议。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stores.asset import create_asset_store
from agents.parent import create_parent
from core.store import Store


# 预置任务数据（与规格书一致）
PRESET_TASKS = [
    {
        "task_id": "task-001",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-002",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-003",
        "sop": "DEV-001",
        "status": "completed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "代码实现", "status": "success"},
        ],
    },
    {
        "task_id": "task-004",
        "sop": "DEV-002",
        "status": "failed",
        "stages": [
            {"name": "问题定位", "status": "success"},
            {"name": "修复方案", "status": "failed", "output": "合规校验未通过"},
        ],
    },
    {
        "task_id": "task-005",
        "sop": "DEV-001",
        "status": "failed",
        "stages": [
            {"name": "需求分析", "status": "success"},
            {"name": "代码实现", "status": "failed", "output": "合规校验失败"},
        ],
    },
]


def test_evolution_e2e():
    print("=== STR-002 自进化端到端验证开始 ===")

    # 1. 预置数据
    asset_store = create_asset_store(backend="memory")
    for task in PRESET_TASKS:
        asset_store.save(f"task:{task['task_id']}", task)

    print(f"✅ 预置数据完成：{len(PRESET_TASKS)} 条任务")

    # 2. 创建父辈
    parent = create_parent("evolution_parent", Store())

    # 3. 执行自进化 SOP（直接调用 Skill，不依赖 STR-002.yaml）
    context = {
        "_asset_store": asset_store,
        "_history_limit": 20,
    }

    print("   执行 Step 1/4: load_task_history...")
    result = parent.run(["load_task_history"], context)
    task_history = result.get("_task_history", [])
    print(f"   ✅ 加载历史：{len(task_history)} 条记录")

    print("   执行 Step 2/4: analyze_trends...")
    result = parent.run(["analyze_trends"], result)
    trends = result.get("_trends", {})
    print(f"   ✅ 趋势分析：成功率 {trends.get('success_rate', 0):.0%}")
    print(f"   洞察：{trends.get('insights', [])}")

    print("   执行 Step 3/4: generate_suggestions...")
    result = parent.run(["generate_suggestions"], result)
    suggestions = result.get("_suggestions", [])
    print(f"   ✅ 生成建议：{len(suggestions)} 条")
    for i, s in enumerate(suggestions, 1):
        print(f"   - 建议{i}：{s['type']}（优先级：{s['priority']}）")

    print("   执行 Step 4/4: present_for_approval...")
    result = parent.run(["present_for_approval"], result)
    report = result.get("_approval_report", "")
    print(f"   ✅ 确认报告已生成（长度：{len(report)} 字符）")

    # 4. 验证（AC-3 ~ AC-6）
    # AC-3: task_history 包含5条记录
    if len(task_history) != 5:
        print(f"❌ AC-3 失败：task_history 应包含 5 条记录，实际为 {len(task_history)}")
        return False
    print("✅ AC-3 通过：task_history 包含 5 条记录")

    # AC-4: trends 统计数字正确
    if trends.get("total") != 5:
        print(f"❌ AC-4 失败：total 应为 5，实际为 {trends.get('total')}")
        return False
    if trends.get("successful") != 3:
        print(f"❌ AC-4 失败：successful 应为 3，实际为 {trends.get('successful')}")
        return False
    if trends.get("failed") != 2:
        print(f"❌ AC-4 失败：failed 应为 2，实际为 {trends.get('failed')}")
        return False
    print("✅ AC-4 通过：trends 统计数字正确")

    # AC-5: suggestions 包含至少1条优化建议
    if len(suggestions) < 1:
        print(
            f"❌ AC-5 失败：suggestions 应包含至少 1 条建议，实际为 {len(suggestions)}"
        )
        return False
    print("✅ AC-5 通过：suggestions 包含至少 1 条优化建议")

    # AC-6: approval_report 包含"家族自进化报告"和"优化建议"
    if "家族自进化报告" not in report:
        print("❌ AC-6 失败：approval_report 应包含 '家族自进化报告'")
        return False
    if "优化建议" not in report:
        print("❌ AC-6 失败：approval_report 应包含 '优化建议'")
        return False
    print("✅ AC-6 通过：approval_report 包含必要内容")

    print("\n=== STR-002 自进化端到端验证通过 ✅ ===")
    return True


if __name__ == "__main__":
    success = test_evolution_e2e()
    sys.exit(0 if success else 1)
