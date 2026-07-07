"""
V7 阶段3 覆盖率补测试 — core/cost.py (69.62% → 85%+)
成本追踪：CostTracker, BudgetExceededError
"""

import os
import sys

import pytest

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.cost import BudgetExceededError, CostTracker, get_cost_tracker


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """每个测试用独立数据库"""
    from core.db import DBManager

    db_path = str(tmp_path / "test_cost.db")
    db = DBManager(db_path=db_path)
    import core.db as db_mod

    old = db_mod._db_manager
    db_mod._db_manager = db
    yield db
    db_mod._db_manager = old


class TestCostTracker:
    """成本追踪测试"""

    def test_track_cost_returns_value(self, _fresh_db):
        tracker = CostTracker(monthly_budget=300.0)
        cost = tracker.track_cost("agent-1", 1000, "test_model")
        assert cost > 0
        assert cost == 0.001  # 1K tokens * 0.001/1K

    def test_track_cost_with_task(self, _fresh_db):
        tracker = CostTracker()
        # 先创建project和task以满足外键约束
        db = _fresh_db
        db.insert("projects", {"id": "p1", "name": "test", "description": "", "status": "active"})
        db.insert(
            "tasks",
            {
                "id": "task-001",
                "title": "test",
                "description": "",
                "project_id": "p1",
                "status": "pending",
            },
        )
        cost = tracker.track_cost("agent-1", 500, "deepseek", task_id="task-001")
        assert cost == 0.0005

    def test_track_cost_with_tokens_breakdown(self, _fresh_db):
        tracker = CostTracker()
        cost = tracker.track_cost("agent-1", 2000, "deepseek", input_tokens=1500, output_tokens=500)
        assert cost == 0.002

    def test_check_budget_normal(self, _fresh_db):
        tracker = CostTracker(monthly_budget=300.0)
        info = tracker.check_budget()
        assert info["status"] == "normal"
        assert info["monthly_budget"] == 300.0
        assert info["total_cost"] == 0.0

    def test_check_budget_warning(self, _fresh_db):
        tracker = CostTracker(monthly_budget=0.01, alert_ratio=0.8)
        tracker.track_cost("a1", 10000)  # cost = 0.01
        info = tracker.check_budget()
        assert info["status"] in ("warning", "exceeded")

    def test_check_budget_exceeded(self, _fresh_db):
        tracker = CostTracker(monthly_budget=0.001, alert_ratio=0.8)
        tracker.track_cost("a1", 2000)  # cost = 0.002 > budget
        info = tracker.check_budget()
        assert info["status"] == "exceeded"

    def test_check_and_throw_raises(self, _fresh_db):
        tracker = CostTracker(monthly_budget=0.001)
        tracker.track_cost("a1", 2000)
        with pytest.raises(BudgetExceededError):
            tracker.check_and_throw("a1", 100)

    def test_check_and_throw_passes(self, _fresh_db):
        tracker = CostTracker(monthly_budget=300.0)
        tracker.check_and_throw("a1", 100)  # 不应抛异常

    def test_update_budget_config(self, _fresh_db):
        tracker = CostTracker(monthly_budget=300.0)
        tracker.update_budget_config(monthly_budget=500.0, alert_ratio=0.9)
        assert tracker.monthly_budget == 500.0
        assert tracker.alert_ratio == 0.9

    def test_update_budget_partial(self, _fresh_db):
        tracker = CostTracker(monthly_budget=300.0, alert_ratio=0.8)
        tracker.update_budget_config(monthly_budget=500.0)  # 只更新预算
        assert tracker.monthly_budget == 500.0
        assert tracker.alert_ratio == 0.8


class TestGetCostTracker:
    """单例获取测试"""

    def test_singleton(self):
        t1 = get_cost_tracker()
        t2 = get_cost_tracker()
        assert t1 is t2

    def test_budget_exceeded_error_type(self):
        assert issubclass(BudgetExceededError, Exception)
