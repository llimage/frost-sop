"""
V7 阶段3 覆盖率补测试 — skills/succession.py (63% → 85%+)
交棒机制：propose_succession, execute_succession
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.succession import (
    execute_succession,
    execute_succession_skill,
    propose_succession,
    propose_succession_skill,
)


class MockStore:
    """模拟资产Store"""

    def __init__(self):
        self._data = {}

    def save(self, key, value):
        self._data[key] = value

    def load(self, key):
        return self._data.get(key)

    def list_keys(self):
        return list(self._data.keys())


class TestProposeSuccession:
    """交棒提案测试"""

    def test_no_store_rejects(self):
        ctx = {"_asset_store": None}
        result = propose_succession(ctx)
        assert result["_succession_proposal"]["recommend"] is False
        assert "无资产Store" in result["_succession_proposal"]["reason"]

    def test_few_tasks_rejects(self):
        store = MockStore()
        for i in range(3):
            store.save(f"task:t{i}", {"stage_results": []})
        ctx = {"_asset_store": store}
        result = propose_succession(ctx)
        assert result["_succession_proposal"]["recommend"] is False
        assert "不足" in result["_succession_proposal"]["reason"]

    def test_enough_tasks_low_failure(self):
        store = MockStore()
        for i in range(10):
            store.save(f"task:t{i}", {"stage_results": [{"status": "success", "output": "完成"}]})
        ctx = {"_asset_store": store}
        result = propose_succession(ctx)
        assert result["_succession_proposal"]["recommend"] is False

    def test_enough_tasks_high_compliance_failure(self):
        store = MockStore()
        for i in range(10):
            store.save(
                f"task:t{i}",
                {
                    "stage_results": [
                        {"status": "failed", "output": "合规检查不通过"},
                        {"status": "success", "output": "完成"},
                    ]
                },
            )
        ctx = {"_asset_store": store, "_succession_threshold": 0.3}
        result = propose_succession(ctx)
        assert result["_succession_proposal"]["recommend"] is True

    def test_custom_threshold(self):
        store = MockStore()
        for i in range(10):
            store.save(f"task:t{i}", {"stage_results": [{"status": "failed", "output": "合规"}]})
        ctx = {"_asset_store": store, "_succession_threshold": 0.5}
        result = propose_succession(ctx)
        assert result["_succession_proposal"]["recommend"] is True

    def test_skill_instance(self):
        assert propose_succession_skill.name == "propose_succession"


class MockAgent:
    """模拟Agent"""

    def __init__(self, name="test_agent"):
        self.name = name
        self.generation = 2
        self.max_spawn_generation = 3
        self.store = None


class TestExecuteSuccession:
    """执行交棒测试"""

    def test_execute_success_missing_params(self):
        ctx = {"_old_ancestor": None, "_new_ancestor": None, "_constitution_store": None}
        result = execute_succession(ctx)
        assert result["_succession_result"]["success"] is False

    def test_execute_succession_success(self):
        old = MockAgent("old_elder")
        new = MockAgent("new_leader")
        store = MockStore()
        ctx = {"_old_ancestor": old, "_new_ancestor": new, "_constitution_store": store}
        result = execute_succession(ctx)
        assert result["_succession_result"]["success"] is True
        assert new.generation == 0
        assert old.name == "elder_old_elder"
        # 验证交棒记录已保存
        record = store.load("family:succession_history")
        assert record is not None
        assert record["event"] == "succession"

    def test_skill_instance(self):
        assert execute_succession_skill.name == "execute_succession"
