"""
V4.0 P0-b 验收测试

验证：
- AC-4: 军师分析小组（六个分析Skill可调用，整合Skill生成简报）
- AC-5: 斥候持续狩猎（持续优化搜索可定时触发，预测性搜索可根据军师预测定向搜索）
"""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


class TestAC4Analytics:
    """AC-4: 军师分析小组验证"""
    
    def setup_method(self):
        """每个测试前创建一个Mock Store"""
        self.mock_store = MagicMock()
        self.mock_store.list_keys.return_value = []
        self.mock_store.load.return_value = None
    
    def test_analytics_import(self):
        """测试：六个分析Skill可导入"""
        from skills.analytics import (
            analyze_finance,
            analyze_skill,
            analyze_task,
            analyze_audit,
            analyze_heartbeat,
            analyze_hunt,
            integrate_briefings
        )
        assert callable(analyze_finance)
        assert callable(analyze_skill)
        assert callable(analyze_task)
        assert callable(analyze_audit)
        assert callable(analyze_heartbeat)
        assert callable(analyze_hunt)
        assert callable(integrate_briefings)
    
    def test_analyze_finance_light(self):
        """测试：财务分析（light模式）不调用LLM"""
        from skills.analytics import analyze_finance
        
        context = {
            "_asset_store": self.mock_store,
            "_analysis_depth": "light"
        }
        
        with patch('skills.analytics._call_llm_for_briefing') as mock_llm:
            result_context = analyze_finance(context)
            # light模式不应调用LLM
            mock_llm.assert_not_called()
        
        assert "_analytics_finance" in result_context
        assert result_context["_analytics_finance"]["depth"] == "light"
        assert "briefing" in result_context["_analytics_finance"]
    
    def test_analyze_skill_light(self):
        """测试：Skill分析（light模式）不调用LLM"""
        from skills.analytics import analyze_skill
        
        context = {
            "_asset_store": self.mock_store,
            "_analysis_depth": "light"
        }
        
        with patch('skills.analytics._call_llm_for_briefing') as mock_llm:
            result_context = analyze_skill(context)
            mock_llm.assert_not_called()
        
        assert "_analytics_skill" in result_context
        assert result_context["_analytics_skill"]["depth"] == "light"
    
    def test_analyze_task_light(self):
        """测试：任务分析（light模式）不调用LLM"""
        from skills.analytics import analyze_task
        
        context = {
            "_asset_store": self.mock_store,
            "_analysis_depth": "light"
        }
        
        with patch('skills.analytics._call_llm_for_briefing') as mock_llm:
            result_context = analyze_task(context)
            mock_llm.assert_not_called()
        
        assert "_analytics_task" in result_context
        assert result_context["_analytics_task"]["depth"] == "light"
    
    def test_analyze_audit_light(self):
        """测试：合规分析（light模式）不调用LLM"""
        from skills.analytics import analyze_audit
        
        context = {
            "_asset_store": self.mock_store,
            "_analysis_depth": "light"
        }
        
        with patch('skills.analytics._call_llm_for_briefing') as mock_llm:
            result_context = analyze_audit(context)
            mock_llm.assert_not_called()
        
        assert "_analytics_audit" in result_context
        assert result_context["_analytics_audit"]["depth"] == "light"
    
    def test_analyze_heartbeat_import_only(self):
        """测试：心跳分析可导入（不报错）"""
        from skills.analytics import analyze_heartbeat
        assert callable(analyze_heartbeat)
    
    def test_analyze_hunt_import_only(self):
        """测试：狩猎分析可导入（不报错）"""
        from skills.analytics import analyze_hunt
        assert callable(analyze_hunt)
    
    def test_integrate_briefings_light(self):
        """测试：整合Skill生成简报（light模式）"""
        from skills.analytics import integrate_briefings
        
        context = {
            "_analytics_finance": {"briefing": "财务简报", "depth": "light"},
            "_analytics_skill": {"briefing": "Skill简报", "depth": "light"},
            "_analytics_task": {"briefing": "任务简报", "depth": "light"},
            "_analytics_audit": {"briefing": "合规简报", "depth": "light"},
            "_analytics_heartbeat": {"briefing": "心跳简报", "depth": "light"},
            "_analytics_hunt": {"briefing": "狩猎简报", "depth": "light"},
            "_analysis_depth": "light"
        }
        
        with patch('skills.analytics._call_llm_for_briefing') as mock_llm:
            result_context = integrate_briefings(context)
            mock_llm.assert_not_called()
        
        assert "_integrated_briefing" in result_context
        integrated = result_context["_integrated_briefing"]
        assert "briefings" in integrated
        assert "correlations" in integrated
        assert "integrated_text" in integrated
        assert "suggested_panels" in integrated
    
    def test_integrate_briefings_generates_panels(self):
        """测试：整合Skill根据分析结果生成面板建议"""
        from skills.analytics import integrate_briefings
        
        context = {
            "_analytics_finance": {"briefing": "财务简报", "depth": "light", "budget_usage_rate": 0.85},
            "_analytics_skill": {"briefing": "Skill简报", "depth": "light", "success_rate": 0.95},
            "_analytics_task": {"briefing": "任务简报", "depth": "light", "completion_rate": 0.85},
            "_analytics_audit": {"briefing": "合规简报", "depth": "light", "pass_rate": 0.95},
            "_analytics_heartbeat": {"briefing": "心跳简报", "depth": "light"},
            "_analytics_hunt": {"briefing": "狩猎简报", "depth": "light"},
            "_analysis_depth": "light"
        }
        
        result_context = integrate_briefings(context)
        
        integrated = result_context["_integrated_briefing"]
        # 预算使用率>80%，应建议增加面板
        assert len(integrated["suggested_panels"]) > 0
        assert any(p["title"] == "预算使用率" for p in integrated["suggested_panels"])


class TestAC5Hunt:
    """AC-5: 斥候持续狩猎验证"""
    
    def setup_method(self):
        """每个测试前创建一个Mock Store"""
        self.mock_store = MagicMock()
        self.mock_store.list_keys.return_value = []
        self.mock_store.load.return_value = None
    
    def test_hunt_import(self):
        """测试：三个狩猎Skill可导入"""
        from skills.hunt import (
            search_external,
            compare_skill,
            absorb_skill,
            hunt_sop,
            trigger_continuous_hunt,
            trigger_predictive_hunt
        )
        assert callable(search_external)
        assert callable(compare_skill)
        assert callable(absorb_skill)
        assert callable(hunt_sop)
        assert callable(trigger_continuous_hunt)
        assert callable(trigger_predictive_hunt)
    
    def test_search_external(self):
        """测试：search_external 可调用"""
        from skills.hunt import search_external
        
        context = {
            "_asset_store": self.mock_store,
            "_hunt_target_skill_id": "test_skill"
        }
        
        result_context = search_external(context)
        
        assert "_hunt_search_result" in result_context
        assert "found" in result_context["_hunt_search_result"]
        assert "candidates" in result_context["_hunt_search_result"]
    
    def test_compare_skill_no_candidates(self):
        """测试：compare_skill 无候选者时跳过"""
        from skills.hunt import compare_skill
        
        context = {
            "_asset_store": self.mock_store,
            "_hunt_search_result": {"found": False, "candidates": []},
            "_hunt_target_skill_id": "test_skill"
        }
        
        result_context = compare_skill(context)
        
        assert "_hunt_compare_result" in result_context
        assert result_context["_hunt_compare_result"]["action"] == "skip"
    
    def test_absorb_skill_no_absorb(self):
        """测试：absorb_skill 无需吸收时跳过"""
        from skills.hunt import absorb_skill
        
        context = {
            "_asset_store": self.mock_store,
            "_hunt_compare_result": {"should_absorb": False, "reason": "health_not_improved"},
            "_hunt_search_result": {"found": False},
            "_hunt_target_skill_id": "test_skill"
        }
        
        result_context = absorb_skill(context)
        
        assert "_hunt_absorb_result" in result_context
        assert result_context["_hunt_absorb_result"]["action"] == "rejected"
    
    def test_hunt_sop_no_targets(self):
        """测试：hunt_sop 无目标时退出"""
        from skills.hunt import hunt_sop
        
        context = {
            "_asset_store": self.mock_store,
            "_hunt_targets": []
        }
        
        result_context = hunt_sop(context)
        
        assert "_hunt_sop_result" in result_context
        assert result_context["_hunt_sop_result"]["status"] == "no_targets"
    
    @patch('skills.hunt._load_target_list')
    def test_trigger_continuous_hunt(self, mock_load):
        """测试：trigger_continuous_hunt 可触发（简化版）"""
        from skills.hunt import trigger_continuous_hunt
        
        # Mock 返回空目标列表
        mock_load.return_value = []
        
        context = {
            "_asset_store": self.mock_store
        }
        
        result_context = trigger_continuous_hunt(context)
        
        assert "_hunt_trigger_result" in result_context
        assert result_context["_hunt_trigger_result"]["trigger_type"] == "continuous"
    
    def test_trigger_predictive_hunt_no_gaps(self):
        """测试：trigger_predictive_hunt 无能力缺口时跳过"""
        from skills.hunt import trigger_predictive_hunt
        
        context = {
            "_asset_store": self.mock_store,
            "_integrated_briefing": {"briefings": {}, "correlations": []}
        }
        
        result_context = trigger_predictive_hunt(context)
        
        assert "_hunt_trigger_result" in result_context
        assert result_context["_hunt_trigger_result"]["trigger_type"] == "predictive"
        assert result_context["_hunt_trigger_result"]["status"] == "no_gaps"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
