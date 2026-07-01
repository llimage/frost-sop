"""
core/cost.py 单元测试

测试 CostTracker 成本预算控制器。
通过 mock get_db() 实现纯内存测试。
"""

import sys
import os
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FROST_TESTING", "1")

import pytest
from datetime import date


class TestCostTracker:
    """测试 CostTracker"""

    @pytest.fixture
    def mock_db(self):
        """Mock DBManager"""
        db = MagicMock()
        db.insert = MagicMock(return_value=True)
        db.get_monthly_cost = MagicMock(return_value=0.0)
        return db

    @pytest.fixture
    def tracker(self, mock_db):
        """创建 CostTracker（mock 的 DB）"""
        with patch("core.cost.get_db", return_value=mock_db):
            from core.cost import CostTracker

            return CostTracker(monthly_budget=100.0, alert_ratio=0.8)

    def test_track_cost_writes_to_db(self, tracker, mock_db):
        cost = tracker.track_cost(
            agent_id="agent_01", tokens=5000, model="gpt-4", task_id="task:abc"
        )
        assert cost > 0
        mock_db.insert.assert_called_once()
        # 验证 cost_log 表名
        args = mock_db.insert.call_args[0]
        assert args[0] == "cost_log"

    def test_track_cost_calculation(self, tracker):
        """成本 = tokens/1000 * 0.001"""
        cost = tracker.track_cost(agent_id="a", tokens=10000)
        # 10000/1000 = 10, 10 * 0.001 = 0.01
        # 实际上这是粗略成本估算
        assert cost == 0.01

    def test_check_budget_normal(self, tracker, mock_db):
        mock_db.get_monthly_cost.return_value = 30.0
        result = tracker.check_budget()
        assert result["status"] == "normal"
        assert result["usage_ratio"] == 0.3
        assert result["remaining"] == 70.0

    def test_check_budget_warning(self, tracker, mock_db):
        mock_db.get_monthly_cost.return_value = 85.0
        result = tracker.check_budget()
        assert result["status"] == "warning"

    def test_check_budget_exceeded(self, tracker, mock_db):
        mock_db.get_monthly_cost.return_value = 110.0
        result = tracker.check_budget()
        assert result["status"] == "exceeded"
        assert result["remaining"] < 0

    def test_check_budget_edge_alert_ratio(self, tracker, mock_db):
        """恰好 80% 是 warning 边界"""
        mock_db.get_monthly_cost.return_value = 80.0
        result = tracker.check_budget()
        assert result["status"] == "warning"

    def test_check_and_throw_exceeded(self, tracker, mock_db):
        from core.cost import BudgetExceededError

        mock_db.get_monthly_cost.return_value = 150.0
        with pytest.raises(BudgetExceededError):
            tracker.check_and_throw(agent_id="a", tokens=100)

    def test_check_and_throw_no_exceeded(self, tracker, mock_db):
        mock_db.get_monthly_cost.return_value = 50.0
        # 不应抛出异常
        tracker.check_and_throw(agent_id="a", tokens=100)

    def test_update_budget_config(self, tracker, mock_db):
        tracker.update_budget_config(monthly_budget=200.0, alert_ratio=0.5)
        assert tracker.monthly_budget == 200.0
        assert tracker.alert_ratio == 0.5

    def test_global_singleton(self):
        with patch("core.cost.get_db"):
            from core.cost import get_cost_tracker

            c1 = get_cost_tracker()
            c2 = get_cost_tracker()
            assert c1 is c2


class TestBudgetExceededError:
    """测试自定义异常"""

    def test_is_exception(self):
        from core.cost import BudgetExceededError

        assert issubclass(BudgetExceededError, Exception)

    def test_message(self):
        from core.cost import BudgetExceededError

        e = BudgetExceededError("预算已超支 50 元")
        assert "50" in str(e)
