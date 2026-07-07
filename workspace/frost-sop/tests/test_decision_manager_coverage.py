"""
V7 阶段3 覆盖率补测试 — core/decision_manager.py (57% → 85%+)
决策管理器：暂停/恢复/拒绝决策点
"""

import os
import sys

import pytest

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import DBManager
from core.decision_manager import DecisionManager, get_decision_manager


@pytest.fixture
def fresh_dm(tmp_path):
    """每个测试用独立DB和DecisionManager"""
    db = DBManager(db_path=str(tmp_path / "test_decision.db"))
    dm = DecisionManager(db=db)
    return dm


class TestPauseDecision:
    """暂停决策测试"""

    def test_pause_returns_decision_id(self, fresh_dm):
        id = fresh_dm.pause_decision("task-001", "stage-1", "是否继续？", ["confirm", "reject"])
        assert isinstance(id, int)
        assert id > 0

    def test_pause_invalid_task_id(self, fresh_dm):
        id = fresh_dm.pause_decision("unknown", "stage-1", "问题？", ["confirm"])
        assert id == -1

    def test_pause_empty_task_id(self, fresh_dm):
        id = fresh_dm.pause_decision("", "stage-1", "问题？", ["confirm"])
        assert id == -1

    def test_pause_with_options(self, fresh_dm):
        id = fresh_dm.pause_decision("task-002", "stage-2", "选择方案", ["方案A", "方案B", "方案C"])
        assert id > 0


class TestResumeDecision:
    """恢复决策测试"""

    def test_resume_success(self, fresh_dm):
        id = fresh_dm.pause_decision("task-003", "stage-3", "确认？", ["yes", "no"])
        result = fresh_dm.resume_decision(id, "yes", "用户确认执行")
        assert result is True

    def test_resume_nonexistent_decision(self, fresh_dm):
        result = fresh_dm.resume_decision(9999, "confirm")
        assert result is False

    def test_resume_with_note(self, fresh_dm):
        id = fresh_dm.pause_decision("task-004", "stage-4", "问题", ["ok"])
        result = fresh_dm.resume_decision(id, "ok", "备注信息")
        assert result is True


class TestRejectDecision:
    """拒绝决策测试"""

    def test_reject_success(self, fresh_dm):
        id = fresh_dm.pause_decision("task-005", "stage-5", "问题", ["ok", "no"])
        result = fresh_dm.reject_decision(id, "不符合要求")
        assert result is True

    def test_reject_nonexistent(self, fresh_dm):
        result = fresh_dm.reject_decision(9999, "不存在")
        assert result is False


class TestGetPendingDecision:
    """获取待处理决策测试"""

    def test_get_pending_returns_latest(self, fresh_dm):
        fresh_dm.pause_decision("task-006", "stage-6", "问题1", ["a", "b"])
        decision = fresh_dm.get_pending_decision()
        assert decision is not None
        assert decision["status"] == "pending"

    def test_get_pending_none_when_all_resolved(self, fresh_dm):
        id = fresh_dm.pause_decision("task-007", "stage-7", "问题", ["ok"])
        fresh_dm.resume_decision(id, "ok")
        decision = fresh_dm.get_pending_decision()
        assert decision is None

    def test_has_pending_decision(self, fresh_dm):
        fresh_dm.pause_decision("task-008", "stage-8", "问题", ["ok"])
        assert fresh_dm.has_pending_decision() is True

    def test_has_no_pending(self, fresh_dm):
        assert fresh_dm.has_pending_decision() is False


class TestGetDecisionById:
    """按ID获取决策测试"""

    def test_get_by_id_success(self, fresh_dm):
        id = fresh_dm.pause_decision("task-009", "stage-9", "问题", ["a", "b"])
        decision = fresh_dm.get_decision_by_id(id)
        assert decision is not None
        assert decision["question"] == "问题"
        assert decision["options"] == ["a", "b"]

    def test_get_by_id_nonexistent(self, fresh_dm):
        decision = fresh_dm.get_decision_by_id(9999)
        assert decision is None


class TestGetDecisionsByTask:
    """按任务ID获取决策列表"""

    def test_get_by_task_multiple(self, fresh_dm):
        fresh_dm.pause_decision("task-010", "stage-1", "问题1", ["a"])
        fresh_dm.pause_decision("task-010", "stage-2", "问题2", ["b"])
        decisions = fresh_dm.get_decisions_by_task("task-010")
        assert len(decisions) == 2

    def test_get_by_task_empty(self, fresh_dm):
        decisions = fresh_dm.get_decisions_by_task("nonexistent")
        assert decisions == []


class TestGetDecisionManager:
    """全局单例测试"""

    def test_singleton(self):
        dm1 = get_decision_manager()
        dm2 = get_decision_manager()
        assert dm1 is dm2
