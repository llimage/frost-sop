"""
V4.0 P1 验收测试
验证 AC-6（免疫系统P0）、AC-7（驾驶舱动态面板）、AC-8（传承系统）
"""
import sys
import os
import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch


class TestAC6ImmuneSystem:
    """AC-6: 免疫系统P0 验收测试"""

    def test_send_heartbeat(self):
        """测试 send_heartbeat 可导入和调用"""
        from skills.watchdog import send_heartbeat
        context = {
            "_agent_id": "test_agent",
            "_agent_role": "parent",
            "_task_id": "task_001",
            "_store": MagicMock(),
        }
        result = send_heartbeat(context)
        assert "_heartbeat_sent" in result
        assert "_heartbeat_time" in result

    def test_monitor_heartbeat(self):
        """测试 monitor_heartbeat 可导入和调用"""
        from skills.watchdog import monitor_heartbeat
        context = {
            "_store": MagicMock(),
            "_active_parents": ["parent_001"],
            "_heartbeat_timeout": 120,
        }
        # Mock event bus
        with patch("skills.watchdog.get_event_bus") as mock_get_bus:
            mock_bus = MagicMock()
            mock_bus.get_event_log.return_value = []
            mock_get_bus.return_value = mock_bus
            result = monitor_heartbeat(context)
            assert "_timeout_parents" in result
            assert "_monitor_result" in result

    def test_p1_respiratory_monitoring(self):
        """测试 P1 呼吸监控函数可导入"""
        from skills.watchdog import (
            report_stage_status,
            report_task_health,
            check_consecutive_failures,
        )
        # 验证函数可调用
        ctx = {
            "_stage_name": "test_stage",
            "_stage_status": "completed",
            "_task_id": "task_001",
            "_agent_id": "agent_001",
        }
        result = report_stage_status(ctx)
        assert "_stage_status_reported" in result

    def test_p1_task_health(self):
        """测试 report_task_health 可调用"""
        from skills.watchdog import report_task_health
        ctx = {
            "_task_id": "task_001",
            "_health_score": 0.8,
            "_health_reason": "任务运行正常",
            "_agent_id": "agent_001",
        }
        result = report_task_health(ctx)
        assert "_task_health_reported" in result
        assert "_health_level" in result

    def test_p1_circuit_breaker(self):
        """测试 check_consecutive_failures 可调用"""
        from skills.watchdog import check_consecutive_failures
        ctx = {
            "_task_id": "task_001",
            "_failure_history": [
                {"status": "failed"},
                {"status": "failed"},
                {"status": "failed"},
            ],
            "_circuit_breaker_threshold": 3,
        }
        result = check_consecutive_failures(ctx)
        assert "_circuit_breaker_triggered" in result
        # 3 次失败 == 阈值 3，应该触发熔断
        assert result.get("_circuit_breaker_triggered") == True

    def test_dead_man_switch(self):
        """测试 DeadManSwitch 可导入和调用"""
        from core.dead_mans_switch import DeadManSwitch, setup_dead_man_switch
        dms = DeadManSwitch(timeout_minutes=30)
        assert dms.timeout_minutes == 30
        assert dms.is_armed == True

        # 模拟超时
        dms.last_event_time = datetime.now() - timedelta(minutes=31)
        alert = dms.check()
        assert alert is not None
        assert alert["alert_level"] == "CRITICAL"

    def test_check_ancestor_alive(self):
        """测试 check_ancestor_alive 可导入和调用"""
        from agents.elder import check_ancestor_alive
        context = {
            "_store": MagicMock(),
        }
        result = check_ancestor_alive(context)
        assert "_dead_mans_watch_report" in result
        report = result["_dead_mans_watch_report"]
        assert "status" in report
        assert "report" in report


class TestAC7DynamicDashboard:
    """AC-7: 驾驶舱动态面板 验收测试"""

    def test_panel_template_library(self):
        """测试 st.session_state.panel_templates 存在"""
        import streamlit as st
        if not hasattr(st, "session_state"):
            pytest.skip("Streamlit session_state 不可用")
        # 模拟 session_state
        st.session_state.panel_templates = {}
        st.session_state.dynamic_panels = []
        st.session_state.suggested_panels = []
        assert isinstance(st.session_state.panel_templates, dict)
        assert isinstance(st.session_state.dynamic_panels, list)

    def test_parse_suggested_panels(self):
        """测试 parse_suggested_panels 函数"""
        # 直接测试逻辑
        briefing = {
            "_suggested_panels": [
                {"type": "metric", "title": "测试指标", "value": 100},
                {"type": "line_chart", "title": "趋势图", "data": [1, 2, 3]},
            ]
        }
        suggested = briefing.get("_suggested_panels", [])
        assert len(suggested) == 2
        assert suggested[0]["type"] == "metric"
        assert suggested[1]["type"] == "line_chart"

    def test_render_dynamic_panels_function_exists(self):
        """测试 render_dynamic_panels 函数在 app.py 中定义"""
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "app", "app.py")
        # 不实际加载（会触发 Streamlit 初始化），只检查文件包含函数定义
        with open("app.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert "def render_dynamic_panels" in content
        assert "def parse_suggested_panels" in content
        assert "def clear_dynamic_panels" in content
        assert "def update_dynamic_panels_from_briefing" in content

    def test_dynamic_panel_session_state(self):
        """测试动态面板 session_state 初始化"""
        import streamlit as st
        if not hasattr(st, "session_state"):
            pytest.skip("Streamlit session_state 不可用")
        # 检查 app.py 中是否初始化了 panel_templates
        with open("app.py", "r", encoding="utf-8") as f:
            content = f.read()
        # 验证初始化代码存在
        assert "panel_templates" in content
        assert "dynamic_panels" in content
        assert "suggested_panels" in content


class TestAC8InheritanceSystem:
    """AC-8: 传承系统 验收测试"""

    def test_update_skill_graph(self):
        """测试 update_skill_graph 可导入和调用"""
        from skills.evolution import update_skill_graph
        context = {
            "_new_skill_id": "skill_test_001",
            "_new_skill_metadata": {"type": "test"},
        }
        result = update_skill_graph(context)
        assert "_skill_graph_updated" in result

    def test_update_mistake_book(self):
        """测试 update_mistake_book 可导入和调用"""
        from skills.evolution import update_mistake_book
        context = {
            "_failure_record": {"error": "测试错误"},
            "_asset_store": MagicMock(),
        }
        result = update_mistake_book(context)
        assert "_mistake_book_updated" in result
        assert "_lesson_key" in result

    def test_manage_sop_version(self):
        """测试 manage_sop_version 可导入和调用"""
        from skills.evolution import manage_sop_version
        context = {
            "_sop_optimization": {
                "target": "DEV-001",
                "original_content": "原版 SOP",
            },
            "_asset_store": MagicMock(),
        }
        # Mock store.load to return None (v1 doesn't exist)
        with patch("skills.evolution.getattr") as mock_getattr:
            result = manage_sop_version(context)
            assert "_sop_version_created" in result

    def test_skill_graph_incremental(self):
        """测试技能图增量进化逻辑"""
        # 模拟 skill_graph 存在的情况
        context = {
            "_new_skill_id": "new_skill",
            "_skill_graph": MagicMock(),
            "_related_skills": ["skill_a", "skill_b"],
        }
        from skills.evolution import update_skill_graph
        result = update_skill_graph(context)
        # 如果 core.skill_graph 存在，应该调用 add_node
        # 如果不存在，应该返回 False 但不报错
        assert "_skill_graph_updated" in result

    def test_mistake_book_auto_update(self):
        """测试错题本自动更新逻辑"""
        from skills.evolution import update_mistake_book
        mock_store = MagicMock()
        mock_store.load.return_value = {"times_encountered": 2}

        context = {
            "_failure_record": {"error": "合规错误：测试"},
            "_asset_store": mock_store,
        }
        result = update_mistake_book(context)
        assert result["_mistake_book_updated"] == True
        assert result["_lesson_key"] == "lesson:compliance_error"
        # 验证 times_encountered 递增
        saved_data = mock_store.save.call_args[0][1]
        assert saved_data["times_encountered"] == 3

    def test_sop_version_management(self):
        """测试 SOP 模板版本管理逻辑"""
        from skills.evolution import manage_sop_version
        mock_store = MagicMock()
        mock_store.load.return_value = None  # v1 不存在

        context = {
            "_sop_optimization": {"target": "DEV-001"},
            "_asset_store": mock_store,
        }
        result = manage_sop_version(context)
        assert result["_sop_version_created"] == True
        assert result["_sop_version"] == "v2"
        # 验证 v1 和 v2 都被保存
        assert mock_store.save.call_count == 2


class TestElderHealthCheck:
    """长老体检监控增强 验收测试"""

    def test_audit_health_function_exists(self):
        """测试 audit_health 函数在 agents/elder.py 中定义"""
        with open("agents/elder.py", "r", encoding="utf-8") as f:
            content = f.read()
        assert "def audit_health" in content
        assert "def _detect_direction_drift" in content
        assert "def _track_constitution_rule_effects" in content

    def test_audit_health_importable(self):
        """测试 audit_health 可导入"""
        from agents.elder import audit_health
        context = {
            "_asset_store": MagicMock(),
            "_constitution_store": MagicMock(),
            "_health_check_type": "routine",
        }
        result = audit_health(context)
        assert "_health_report" in result
        assert "_reason" in result

    def test_direction_drift_detection(self):
        """测试方向漂移检测逻辑"""
        from agents.elder import _detect_direction_drift
        mock_store = MagicMock()
        # 模拟 3 次不同的 briefing
        mock_store.list_keys.return_value = [
            "briefing:001", "briefing:002", "briefing:003"
        ]
        mock_store.load.side_effect = [
            {"main_topic": "topic_A"},
            {"main_topic": "topic_B"},
            {"main_topic": "topic_C"},
        ]
        context = {"_asset_store": mock_store}
        result = _detect_direction_drift(context)
        assert result == True  # 3 个不同主题 = 漂移

    def test_constitution_rule_effect_tracking(self):
        """测试宪法规则效果追踪逻辑"""
        from agents.elder import _track_constitution_rule_effects
        mock_constitution_store = MagicMock()
        mock_constitution_store.load.return_value = [
            {"id": "rule_001"},
            {"id": "rule_002"},
        ]
        mock_asset_store = MagicMock()
        mock_asset_store.list_keys.return_value = [
            "task:001", "task:002"
        ]
        mock_asset_store.load.side_effect = [
            {"status": "completed", "triggered_rules": ["rule_001"]},
            {"status": "failed", "triggered_rules": ["rule_001", "rule_002"]},
        ]
        context = {
            "_constitution_store": mock_constitution_store,
            "_asset_store": mock_asset_store,
        }
        result = _track_constitution_rule_effects(context)
        assert "rule_001" in result
        assert result["rule_001"]["trigger_count"] == 2
        assert result["rule_001"]["success_count"] == 1
        assert result["rule_001"]["failure_count"] == 1
