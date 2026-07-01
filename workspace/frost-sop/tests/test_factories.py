"""
测试数据工厂验证测试

验证 factories.py 中所有工厂都能正确生成数据，
确保边界场景被覆盖。
"""

import pytest

# 导入项目路径
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FROST_TESTING", "1")

from tests.factories import (
    TaskConfigFactory,
    AgentConfigFactory,
    SOPTemplateFactory,
    SkillConfigFactory,
    EventFactory,
    StoreEntryFactory,
    create_batch,
    create_edge_case_task_configs,
    create_edge_case_skill_configs,
    create_edge_case_store_entries,
)


class TestTaskConfigFactory:
    """测试 TaskConfigFactory"""

    def test_creates_default(self):
        config = TaskConfigFactory()
        assert config["task_id"].startswith("task:")
        assert len(config["task_input"]) > 0
        assert config["status"] == "pending"

    def test_creates_batch(self):
        configs = TaskConfigFactory.create_batch(50)
        assert len(configs) == 50
        ids = {c["task_id"] for c in configs}
        assert len(ids) == 50, "All task IDs should be unique"

    def test_edge_case_minimal(self):
        config = TaskConfigFactory(as_minimal=True)
        assert len(config["task_input"]) == 1

    def test_edge_case_verbose(self):
        config = TaskConfigFactory(as_verbose=True)
        assert len(config["task_input"]) > 100

    def test_edge_case_unicode(self):
        config = TaskConfigFactory(as_unicode=True)
        assert "🚀" in config["task_input"]

    def test_edge_case_empty(self):
        config = TaskConfigFactory(as_empty=True)
        assert config["task_input"].strip() == ""

    def test_edge_case_covered_by_utility(self):
        configs = create_edge_case_task_configs()
        assert len(configs) == 7
        statuses = {c["status"] for c in configs}
        assert "completed" in statuses
        assert "failed" in statuses


class TestAgentConfigFactory:
    """测试 AgentConfigFactory"""

    def test_creates_default(self):
        config = AgentConfigFactory()
        assert config["agent_id"].startswith("agent_")
        assert len(config["assigned_skills"]) >= 1
        assert 0.0 <= config["temperature"] <= 1.0

    def test_minimal(self):
        config = AgentConfigFactory(as_minimal=True)
        assert len(config["assigned_skills"]) == 1

    def test_maximal(self):
        config = AgentConfigFactory(as_maximal=True)
        assert len(config["assigned_skills"]) == 20


class TestSOPTemplateFactory:
    """测试 SOPTemplateFactory"""

    def test_creates_default(self):
        sop = SOPTemplateFactory()
        assert sop["sop_id"].startswith(("DEV-", "OPS-", "STR-", "MT-"))
        assert len(sop["phases"]) >= 3

    def test_5_phase_variant(self):
        sop = SOPTemplateFactory(as_5_phase=True)
        assert len(sop["phases"]) == 5

    def test_single_phase(self):
        sop = SOPTemplateFactory(as_single_phase=True)
        assert len(sop["phases"]) == 1

    def test_phases_have_skills(self):
        sop = SOPTemplateFactory()
        for phase in sop["phases"]:
            assert "skill" in phase
            assert len(phase["inputs"]) == 3
            assert len(phase["outputs"]) == 2


class TestSkillConfigFactory:
    """测试 SkillConfigFactory"""

    def test_creates_default(self):
        skill = SkillConfigFactory()
        assert skill["name"].startswith("skill_gene:")
        assert skill["status"] in ("draft", "active", "rejected")

    def test_edge_cases_covered(self):
        skills = create_edge_case_skill_configs()
        statuses = {s["status"] for s in skills}
        assert "active" in statuses
        assert "draft" in statuses
        assert "rejected" in statuses


class TestEventFactory:
    """测试 EventFactory"""

    def test_creates_default(self):
        event = EventFactory()
        assert event["event_id"].startswith("evt_")
        assert "payload" in event

    def test_error_event(self):
        event = EventFactory(as_error_event=True)
        assert "error" in event["payload"]
        assert "code" in event["payload"]

    def test_complex_payload(self):
        event = EventFactory(as_complex_payload=True)
        assert "nested" in event["payload"]


class TestStoreEntryFactory:
    """测试 StoreEntryFactory"""

    def test_creates_default(self):
        entry = StoreEntryFactory()
        assert ":" in entry["key"]
        assert isinstance(entry["value"], dict)

    def test_edge_cases_covered(self):
        entries = create_edge_case_store_entries()
        assert len(entries) == 5
        keys = {e["key"] for e in entries}
        assert any("constitution" in k for k in keys)
        assert any("unicode" in k for k in keys)


class TestCreateBatch:
    """测试 create_batch 便利函数"""

    def test_batch_size(self):
        items = create_batch(TaskConfigFactory, size=25)
        assert len(items) == 25

    def test_batch_uniqueness(self):
        items = create_batch(EventFactory, size=100)
        event_ids = {e["event_id"] for e in items}
        assert len(event_ids) == 100
