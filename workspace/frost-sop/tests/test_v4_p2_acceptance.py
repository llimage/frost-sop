"""
V4.0 P2 验收测试（AC-9: 治理系统）

验证：
- AC-9: 治理系统数据驱动修订
  - 规则效果追踪
  - 修订建议生成
  - 分级修订权限
"""
import unittest
from unittest.mock import MagicMock, patch
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAC9GovernanceSystem(unittest.TestCase):
    """AC-9: 治理系统数据驱动修订"""

    def test_track_rule_effects(self):
        """测试规则效果追踪"""
        from agents.elder import track_rule_effects
        
        # 创建 Mock Store
        mock_constitution_store = MagicMock()
        mock_constitution_store.load.return_value = [
            {"id": "rule_001", "text": "预算预警比例 80%"},
            {"id": "rule_002", "text": "合规检查必须执行"},
        ]
        
        mock_asset_store = MagicMock()
        mock_asset_store.list_keys.return_value = [
            "task:task_001",
            "task:task_002",
            "task:task_003",
        ]
        
        # 模拟任务数据
        def mock_load(key):
            if key == "task:task_001":
                return {"status": "completed", "triggered_rules": ["rule_001"]}
            elif key == "task:task_002":
                return {"status": "failed", "triggered_rules": ["rule_001", "rule_002"]}
            elif key == "task:task_003":
                return {"status": "failed", "triggered_rules": ["rule_001"]}
            return None
        
        mock_asset_store.load.side_effect = mock_load
        
        context = {
            "_constitution_store": mock_constitution_store,
            "_asset_store": mock_asset_store,
        }
        
        result = track_rule_effects(context)
        
        # 验证规则效果被追踪
        rule_effects = result.get("_rule_effects", {})
        self.assertIn("rule_001", rule_effects)
        self.assertIn("rule_002", rule_effects)
        
        # rule_001: 触发3次，成功1次，失败2次
        self.assertEqual(rule_effects["rule_001"]["trigger_count"], 3)
        self.assertEqual(rule_effects["rule_001"]["success_count"], 1)
        self.assertEqual(rule_effects["rule_001"]["failure_count"], 2)
        self.assertAlmostEqual(rule_effects["rule_001"]["failure_rate"], 2/3)
        
        # rule_002: 触发1次，失败1次
        self.assertEqual(rule_effects["rule_002"]["trigger_count"], 1)
        self.assertEqual(rule_effects["rule_002"]["failure_count"], 1)
        self.assertAlmostEqual(rule_effects["rule_002"]["failure_rate"], 1.0)
        
        print("✅ test_track_rule_effects passed")
    
    def test_generate_revision_suggestions(self):
        """测试修订建议生成"""
        from agents.elder import generate_revision_suggestions
        
        # 模拟规则效果（失败率 > 30%）
        rule_effects = {
            "rule_001": {
                "rule_id": "rule_001",
                "rule_text": "预算预警比例 80%",
                "trigger_count": 10,
                "success_count": 6,
                "failure_count": 4,
                "failure_rate": 0.4,  # > 30%
                "complaint_count": 0,
                "complaint_rate": 0.0,
            },
            "rule_002": {
                "rule_id": "rule_002",
                "rule_text": "合规检查必须执行",
                "trigger_count": 10,
                "success_count": 9,
                "failure_count": 1,
                "failure_rate": 0.1,  # < 30%
                "complaint_count": 0,
                "complaint_rate": 0.0,
            },
        }
        
        context = {
            "_rule_effects": rule_effects,
            "_rules_need_revision": ["rule_001"],  # rule_001 需要修订
            "_constitution_store": MagicMock(),
        }
        
        result = generate_revision_suggestions(context)
        
        # 验证修订建议生成
        suggestions = result.get("_revision_suggestions", [])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["rule_id"], "rule_001")
        self.assertIn("失败率", suggestions[0]["problem"])
        self.assertTrue(len(suggestions[0]["suggestion"]) > 0)  # 有建议内容
        
        print("✅ test_generate_revision_suggestions passed")
    
    def test_generate_revision_suggestions_high_failure_rate(self):
        """测试高失败率规则的修订建议"""
        from agents.elder import generate_revision_suggestions
        
        # 模拟高失败率规则（> 50%）
        rule_effects = {
            "rule_003": {
                "rule_id": "rule_003",
                "rule_text": "严格执行代码审查",
                "trigger_count": 10,
                "success_count": 3,
                "failure_count": 7,
                "failure_rate": 0.7,  # > 50%
                "complaint_count": 0,
                "complaint_rate": 0.0,
            },
        }
        
        context = {
            "_rule_effects": rule_effects,
            "_rules_need_revision": ["rule_003"],
            "_constitution_store": MagicMock(),
        }
        
        result = generate_revision_suggestions(context)
        
        suggestions = result.get("_revision_suggestions", [])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["risk_level"], "high")  # 高风险
        self.assertFalse(suggestions[0]["auto_apply"])  # 需要审批
        
        print("✅ test_generate_revision_suggestions_high_failure_rate passed")
    
    def test_generate_revision_suggestions_low_risk_auto_apply(self):
        """测试低风险调整自动生效"""
        from agents.elder import generate_revision_suggestions
        
        # 模拟低风险规则（预算相关，失败率 30-50%）
        rule_effects = {
            "rule_004": {
                "rule_id": "rule_004",
                "rule_text": "预算预警比例 80%",
                "trigger_count": 10,
                "success_count": 6,
                "failure_count": 4,
                "failure_rate": 0.4,  # 30-50%
                "complaint_count": 0,
                "complaint_rate": 0.0,
            },
        }
        
        context = {
            "_rule_effects": rule_effects,
            "_rules_need_revision": ["rule_004"],
            "_constitution_store": MagicMock(),
        }
        
        result = generate_revision_suggestions(context)
        
        suggestions = result.get("_revision_suggestions", [])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["risk_level"], "medium")
        self.assertTrue(suggestions[0]["auto_apply"])  # 预算相关，自动生效
        
        print("✅ test_generate_revision_suggestions_low_risk_auto_apply passed")
    
    def test_apply_revision_auto(self):
        """测试自动生效的修订"""
        from agents.elder import apply_revision
        
        suggestions = [
            {
                "rule_id": "rule_001",
                "rule_text": "预算预警比例 80%",
                "problem": "失败率 40%",
                "suggestion": "预算预警比例调整为 85%",
                "failure_rate": 0.4,
                "complaint_rate": 0.0,
                "risk_level": "medium",
                "auto_apply": True,  # 自动生效
                "created_at": "2026-06-28T10:00:00",
            },
        ]
        
        mock_constitution_store = MagicMock()
        mock_constitution_store.load.return_value = [
            {"id": "rule_001", "text": "预算预警比例 80%"},
        ]
        
        context = {
            "_revision_suggestions": suggestions,
            "_monarch_approved": [],
            "_constitution_store": mock_constitution_store,
        }
        
        result = apply_revision(context)
        
        # 验证自动生效
        applied = result.get("_applied_revisions", [])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["rule_id"], "rule_001")
        self.assertEqual(applied[0]["applied_by"], "auto")
        
        # 验证 pending 为空
        pending = result.get("_pending_approvals", [])
        self.assertEqual(len(pending), 0)
        
        print("✅ test_apply_revision_auto passed")
    
    def test_apply_revision_pending_approval(self):
        """测试需要审批的修订"""
        from agents.elder import apply_revision
        
        suggestions = [
            {
                "rule_id": "rule_003",
                "rule_text": "严格执行代码审查",
                "problem": "失败率 70%",
                "suggestion": "放宽代码审查标准",
                "failure_rate": 0.7,
                "complaint_rate": 0.0,
                "risk_level": "high",
                "auto_apply": False,  # 需要审批
                "created_at": "2026-06-28T10:00:00",
            },
        ]
        
        context = {
            "_revision_suggestions": suggestions,
            "_monarch_approved": [],  # 未批准
            "_constitution_store": MagicMock(),
        }
        
        result = apply_revision(context)
        
        # 验证未生效，进入 pending
        applied = result.get("_applied_revisions", [])
        self.assertEqual(len(applied), 0)
        
        pending = result.get("_pending_approvals", [])
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["rule_id"], "rule_003")
        
        print("✅ test_apply_revision_pending_approval passed")
    
    def test_apply_revision_monarch_approved(self):
        """测试君主批准后生效"""
        from agents.elder import apply_revision
        
        suggestions = [
            {
                "rule_id": "rule_003",
                "rule_text": "严格执行代码审查",
                "problem": "失败率 70%",
                "suggestion": "放宽代码审查标准",
                "failure_rate": 0.7,
                "complaint_rate": 0.0,
                "risk_level": "high",
                "auto_apply": False,  # 需要审批
                "created_at": "2026-06-28T10:00:00",
            },
        ]
        
        context = {
            "_revision_suggestions": suggestions,
            "_monarch_approved": ["rule_003"],  # 已批准
            "_constitution_store": MagicMock(),
        }
        
        result = apply_revision(context)
        
        # 验证已生效
        applied = result.get("_applied_revisions", [])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["rule_id"], "rule_003")
        self.assertEqual(applied[0]["applied_by"], "monarch")
        
        # 验证 pending 为空
        pending = result.get("_pending_approvals", [])
        self.assertEqual(len(pending), 0)
        
        print("✅ test_apply_revision_monarch_approved passed")
    
    def test_governance_workflow(self):
        """测试完整治理工作流：追踪 → 生成建议 → 应用修订"""
        from agents.elder import track_rule_effects, generate_revision_suggestions, apply_revision
        
        # 1. 模拟规则效果（失败率 > 30%）
        mock_constitution_store = MagicMock()
        mock_constitution_store.load.return_value = [
            {"id": "rule_001", "text": "预算预警比例 80%"},
        ]
        
        mock_asset_store = MagicMock()
        mock_asset_store.list_keys.return_value = [
            "task:task_001",
            "task:task_002",
            "task:task_003",
            "task:task_004",
            "task:task_005",
        ]
        
        # 模拟任务数据（rule_001 触发5次，失败2次，失败率 40%）
        def mock_load(key):
            if key == "task:task_001":
                return {"status": "completed", "triggered_rules": ["rule_001"]}
            elif key.startswith("task:"):
                return {"status": "failed", "triggered_rules": ["rule_001"]}
            return None
        
        mock_asset_store.load.side_effect = mock_load
        
        context = {
            "_constitution_store": mock_constitution_store,
            "_asset_store": mock_asset_store,
        }
        
        # 2. 追踪规则效果
        context = track_rule_effects(context)
        self.assertIn("rule_001", context["_rule_effects"])
        self.assertIn("rule_001", context["_rules_need_revision"])
        
        # 3. 生成修订建议
        context = generate_revision_suggestions(context)
        suggestions = context.get("_revision_suggestions", [])
        self.assertEqual(len(suggestions), 1)
        self.assertEqual(suggestions[0]["rule_id"], "rule_001")
        
        # 4. 应用修订（自动生效）
        suggestions[0]["auto_apply"] = True  # 模拟低风险
        context["_revision_suggestions"] = suggestions
        context = apply_revision(context)
        
        applied = context.get("_applied_revisions", [])
        self.assertEqual(len(applied), 1)
        self.assertEqual(applied[0]["rule_id"], "rule_001")
        
        print("✅ test_governance_workflow passed")


if __name__ == "__main__":
    unittest.main()
