"""
FROST-SOP V3.1 测试覆盖率补充: skills/evolution.py
覆盖 load_task_history, analyze_trends, generate_suggestions, present_for_approval
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import Store
from skills.evolution import (
    load_task_history, analyze_trends, generate_suggestions,
    present_for_approval,
)


# ============================================================
# load_task_history 测试
# ============================================================

def test_load_task_history_no_store():
    """无资产Store时返回空列表"""
    ctx = {}
    result = load_task_history(ctx)
    assert result.get("_task_history") == []
    assert "无资产" in result.get("_reason", "")


def test_load_task_history_with_tasks():
    """有任务记录时正确加载"""
    store = Store()
    store.save("task:001", {"id": "001", "name": "test1",
        "status": "completed", "timestamp": "2026-06-01"})
    store.save("task:002", {"id": "002", "name": "test2",
        "status": "failed", "timestamp": "2026-06-05"})
    store.save("task:003", {"id": "003", "name": "test3",
        "status": "completed", "timestamp": "2026-06-10"})
    # 添加一个非task数据
    store.save("lesson:001", {"id": "lesson1"})
    ctx = {"_asset_store": store}
    result = load_task_history(ctx)
    tasks = result.get("_task_history", [])
    assert len(tasks) == 3
    # 验证按时间倒序排列
    assert tasks[0]["timestamp"] == "2026-06-10"


def test_load_task_history_with_limit():
    """limit限制正确生效"""
    store = Store()
    for i in range(30):
        store.save(f"task:{i:03d}", {"id": str(i),
            "status": "completed", "timestamp": f"2026-06-{i:02d}"})
    ctx = {"_asset_store": store, "_history_limit": 5}
    result = load_task_history(ctx)
    assert len(result.get("_task_history", [])) == 5


# ============================================================
# analyze_trends 测试
# ============================================================

def test_analyze_trends_empty():
    """空历史数据"""
    ctx = {"_task_history": []}
    result = analyze_trends(ctx)
    trends = result.get("_trends", {})
    assert trends.get("total") == 0


def test_analyze_trends_mixed():
    """混合成功/失败数据"""
    tasks = [
        {"status": "completed", "sop": "DEV-001", "stages": []},
        {"status": "completed", "sop": "DEV-001", "stages": []},
        {"status": "failed", "sop": "DEV-001", "stages": [
            {"status": "failed", "output": "合规检查失败"}]},
        {"status": "completed", "sop": "OPS-001", "stages": []},
        {"status": "failed", "sop": "OPS-001", "stages": [
            {"status": "error", "output": "执行错误"}]},
    ]
    ctx = {"_task_history": tasks}
    result = analyze_trends(ctx)
    trends = result.get("_trends", {})
    assert trends.get("total") == 5
    assert trends.get("successful") == 3
    assert trends.get("failed") == 2
    assert trends.get("success_rate") == 0.6
    # SOP统计
    assert "DEV-001" in trends["sop_stats"]
    assert trends["sop_stats"]["DEV-001"]["failed"] == 1
    # 错误类型
    assert "compliance" in trends.get("error_types", {})


def test_analyze_trends_all_success():
    """全部成功的趋势分析"""
    tasks = [
        {"status": "success", "sop": "DEV-001", "stages": []},
        {"status": "completed", "sop": "DEV-001", "stages": []},
    ]
    ctx = {"_task_history": tasks}
    result = analyze_trends(ctx)
    trends = result.get("_trends", {})
    assert trends.get("success_rate") == 1.0
    assert "运行状态良好" in trends.get("insights", "")[0]


def test_analyze_trends_high_failure():
    """高失败率的趋势分析"""
    tasks = [
        {"status": "failed", "sop": "DEV-001", "stages": []},
        {"status": "failed", "sop": "DEV-001", "stages": []},
        {"status": "completed", "sop": "DEV-001", "stages": []},
    ]
    ctx = {"_task_history": tasks}
    result = analyze_trends(ctx)
    insights = result.get("_trends", {}).get("insights", [])
    assert any("需要重点关注" in i for i in insights)


# ============================================================
# generate_suggestions 测试
# ============================================================

def test_generate_suggestions_no_trends():
    """无趋势数据时返回空"""
    ctx = {"_trends": {"total": 0}}
    result = generate_suggestions(ctx)
    assert result.get("_suggestions") == []
    assert "无趋势数据" in result.get("_reason", "")


def test_generate_suggestions_high_failure_sop():
    """高失败SOP生成优化建议"""
    trends = {
        "total": 10,
        "success_rate": 0.4,
        "sop_stats": {
            "DEV-001": {"total": 10, "success": 4, "failed": 6},
        },
        "error_types": {"compliance": 3},
    }
    ctx = {"_trends": trends}
    result = generate_suggestions(ctx)
    suggestions = result.get("_suggestions", [])
    assert len(suggestions) >= 2
    # 应该有SOP优化建议和整体审查建议
    sop_suggestions = [s for s in suggestions
        if s["type"] in ("sop_optimization", "urgent_review")]
    assert len(sop_suggestions) >= 1


def test_generate_suggestions_healthy():
    """健康状态返回no_action建议"""
    trends = {
        "total": 10,
        "success_rate": 0.9,
        "sop_stats": {},
        "error_types": {},
    }
    ctx = {"_trends": trends}
    result = generate_suggestions(ctx)
    suggestions = result.get("_suggestions", [])
    assert any(s["type"] == "no_action" for s in suggestions)


# ============================================================
# present_for_approval 测试
# ============================================================

def test_present_for_approval_basic():
    """生成审批报告"""
    ctx = {
        "_trends": {
            "total": 5, "success_rate": 0.8,
            "successful": 4, "failed": 1,
            "insights": ["家族整体成功率 80%，运行状态良好"],
        },
        "_suggestions": [
            {"type": "sop_review", "target": "DEV-001",
             "reason": "失败率较高", "priority": "low"},
        ],
    }
    result = present_for_approval(ctx)
    report = result.get("_approval_report", "")
    assert "家族自进化报告" in report
    assert "数据概览" in report
    assert "优化建议" in report
    assert "创始人决策" in report
    assert report == result.get("_result", "")


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            print(f"Running {name}...")
            func()
            print(f"  ✅ {name} passed")
    print("\n✅ 所有 evolution 覆盖率测试通过")
