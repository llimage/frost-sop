"""
F8 验收测试：决策点前端恢复 + 超时提醒

测试内容：
1. DecisionManager 的 pause/resume 逻辑（单元测试）
2. decision_points 表读写（集成测试）
3. 超时通知功能（单元测试）
4. 审计日志集成（集成测试）
"""

import sys
import os
import json
import time
import pytest
from datetime import datetime, timedelta

# 确保项目根目录在路径中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestDecisionManager:
    """测试 DecisionManager 的核心功能"""
    
    def setup_method(self):
        """测试前置设置 — 创建父记录满足外键约束"""
        from core.db import get_db
        from core.decision_manager import DecisionManager
        
        self.db = get_db()
        self.decision_manager = DecisionManager(db=self.db)
        
        # 确保 project 存在（task 的外键）
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, status) "
            "VALUES ('test_project', 'F8测试项目', '用于决策点测试', 'active')"
        )
        # 确保 test agent 存在（decision_points 的外键）
        cursor.execute(
            "INSERT OR IGNORE INTO agents (id, name, agent_type, generation) "
            "VALUES ('test_agent', '测试Agent', 'parent', 1)"
        )
        # 确保 test tasks 存在（decision_points 的外键）
        for tid in ['test_task_001', 'test_task_002', 'test_task_003']:
            cursor.execute(
                "INSERT OR IGNORE INTO tasks (id, title, description, project_id, status) "
                "VALUES (?, ?, ?, 'test_project', 'pending')",
                (tid, f'测试任务-{tid}', f'{tid}的描述')
            )
        conn.commit()
        
        # 清理已有测试决策数据
        cursor.execute("DELETE FROM decision_points WHERE task_id LIKE 'test_%'")
        conn.commit()
    
    def teardown_method(self):
        """测试后置清理 — 注意：不关闭单例连接"""
        if hasattr(self, 'db'):
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM decision_points WHERE task_id LIKE 'test_%'")
            cursor.execute("DELETE FROM audit_log WHERE agent_id = 'test_agent'")
            conn.commit()
            # 关键修复：绝不 conn.close() — DB 是单例模式
    
    def test_pause_decision(self):
        """测试暂停决策功能"""
        decision_id = self.decision_manager.pause_decision(
            task_id="test_task_001",
            stage_id="test_stage_001",
            question="是否需要执行此操作？",
            options=["confirm", "reject", "modify"]
        )
        
        assert decision_id is not None, "decision_id 不应为 None"
        assert isinstance(decision_id, int), "decision_id 应为整数"
        
        # 检查数据库记录
        pending = self.decision_manager.get_pending_decision()
        assert pending is not None, "应该有 pending 决策"
        assert pending["task_id"] == "test_task_001", "task_id 不匹配"
        assert pending["status"] == "pending", "status 应为 pending"
    
    def test_resume_decision(self):
        """测试恢复决策功能"""
        # 先暂停
        decision_id = self.decision_manager.pause_decision(
            task_id="test_task_002",
            stage_id="test_stage_002",
            question="测试问题",
            options=["confirm", "reject"]
        )
        
        # 再恢复
        result = self.decision_manager.resume_decision(
            decision_id=decision_id,
            user_choice="confirm",
            user_note="测试备注"
        )
        
        assert result is True, "resume_decision 应返回 True"
        
        # 检查数据库记录
        pending = self.decision_manager.get_pending_decision()
        assert pending is None, "恢复后不应有 pending 决策"
        
        # 检查决策记录是否更新
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT status, user_decision, user_note FROM decision_points WHERE id = ?", (decision_id,))
        row = cursor.fetchone()
        # 不关闭连接 — DB 是单例模式
        
        assert row is not None, "决策记录应存在"
        assert row["status"] == "resolved", "status 应为 resolved"
        assert row["user_decision"] == "confirm", "user_decision 应为 confirm"
        assert row["user_note"] == "测试备注", "user_note 不匹配"
    
    def test_has_pending_decision(self):
        """测试检查是否有 pending 决策"""
        # 初始状态：没有 pending 决策
        assert not self.decision_manager.has_pending_decision(), "初始状态应无 pending 决策"
        
        # 暂停一个决策
        self.decision_manager.pause_decision(
            task_id="test_task_003",
            stage_id="test_stage_003",
            question="测试问题",
            options=["confirm"]
        )
        
        assert self.decision_manager.has_pending_decision(), "暂停后应有 pending 决策"
        
        # 恢复决策
        pending = self.decision_manager.get_pending_decision()
        self.decision_manager.resume_decision(pending["id"], "confirm")
        
        assert not self.decision_manager.has_pending_decision(), "恢复后应无 pending 决策"


class TestNotifier:
    """测试超时通知功能"""
    
    def test_check_decision_timeout(self):
        """测试超时检查功能"""
        from core.notifier import check_decision_timeout
        from datetime import datetime, timedelta
        
        # 测试1：1小时前创建，1小时超时 → 应超时
        old_time = datetime.now() - timedelta(hours=2)
        assert check_decision_timeout(old_time, timeout_seconds=3600), "2小时前应超时"
        
        # 测试2：30分钟前创建，1小时超时 → 不应超时
        recent_time = datetime.now() - timedelta(minutes=30)
        assert not check_decision_timeout(recent_time, timeout_seconds=3600), "30分钟前不应超时"
        
        # 测试3：字符串时间格式
        old_time_str = (datetime.now() - timedelta(hours=2)).isoformat()
        assert check_decision_timeout(old_time_str, timeout_seconds=3600), "字符串时间格式应正常工作"
    
    def test_send_notification(self):
        """测试发送通知功能（降级模式）"""
        from core.notifier import send_windows_notification
        
        # 注意：这个测试可能会失败，因为测试环境中可能没有通知库
        # 但函数应该能降级为控制台输出
        result = send_windows_notification(
            title="F8 测试通知",
            message="这是一条测试通知",
            duration=1
        )
        
        # 在降级模式下，函数返回 False，但不会抛出异常
        assert isinstance(result, bool), "send_windows_notification 应返回 bool"


class TestAuditIntegration:
    """测试审计日志集成"""
    
    def setup_method(self):
        """测试前置设置 — 使用单例 DB，唯一测试数据"""
        from core.db import get_db
        from core.decision_manager import DecisionManager
        
        self.db = get_db()
        self.decision_manager = DecisionManager(db=self.db)
        
        # 使用唯一 ID 避免与外键冲突
        self.project_id = "test_project_audit_f8"
        self.task_id = "test_task_audit_f8"
        
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, status) "
            "VALUES (?, 'F8审计测试', '审计测试项目', 'active')",
            (self.project_id,)
        )
        cursor.execute(
            "INSERT OR IGNORE INTO agents (id, name, agent_type, generation) "
            "VALUES ('test_agent', '测试Agent', 'parent', 1)"
        )
        cursor.execute(
            "INSERT OR IGNORE INTO tasks (id, title, description, project_id, status) "
            "VALUES (?, '审计测试任务', '审计测试描述', ?, 'pending')",
            (self.task_id, self.project_id)
        )
        conn.commit()
    
    def teardown_method(self):
        """测试后置清理"""
        if hasattr(self, 'db'):
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM decision_points WHERE task_id = ?", (self.task_id,))
            cursor.execute("DELETE FROM audit_log WHERE agent_id = 'founder_f8'")
            conn.commit()
    
    def test_audit_log_after_decision(self):
        """测试决策后审计日志的写入"""
        # 暂停决策
        decision_id = self.decision_manager.pause_decision(
            task_id=self.task_id,
            stage_id="test_stage_audit_f8",
            question="审计测试",
            options=["confirm"]
        )
        
        # 恢复决策
        self.decision_manager.resume_decision(
            decision_id=decision_id,
            user_choice="confirm",
            user_note="审计测试备注"
        )
        
        # 写入审计日志
        audit_id = self.db.log_audit({
            "action": "decision_made",
            "agent_id": "founder_f8",
            "details": json.dumps({
                "decision_id": decision_id,
                "choice": "confirm",
                "note": "审计测试备注"
            }, ensure_ascii=False)
        })
        
        assert audit_id is not None, "审计日志应成功写入"
        
        # 检查审计日志
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT action, agent_id FROM audit_log WHERE id = ?", (audit_id,))
        row = cursor.fetchone()
        
        assert row is not None, "审计日志记录应存在"
        assert row["action"] == "decision_made", "action 不匹配"
        assert row["agent_id"] == "founder_f8", "agent_id 不匹配"


if __name__ == "__main__":
    # 手动运行测试
    print("开始 F8 验收测试...")
    
    # 测试 DecisionManager
    print("\n=== 测试 DecisionManager ===")
    test_dm = TestDecisionManager()
    test_dm.setup_method()
    
    try:
        test_dm.test_pause_decision()
        print("✅ test_pause_decision 通过")
    except Exception as e:
        print(f"❌ test_pause_decision 失败: {e}")
    
    try:
        test_dm.test_resume_decision()
        print("✅ test_resume_decision 通过")
    except Exception as e:
        print(f"❌ test_resume_decision 失败: {e}")
    
    try:
        test_dm.test_has_pending_decision()
        print("✅ test_has_pending_decision 通过")
    except Exception as e:
        print(f"❌ test_has_pending_decision 失败: {e}")
    
    test_dm.teardown_method()
    
    # 测试 Notifier
    print("\n=== 测试 Notifier ===")
    test_nt = TestNotifier()
    
    try:
        test_nt.test_check_decision_timeout()
        print("✅ test_check_decision_timeout 通过")
    except Exception as e:
        print(f"❌ test_check_decision_timeout 失败: {e}")
    
    try:
        test_nt.test_send_notification()
        print("✅ test_send_notification 通过")
    except Exception as e:
        print(f"❌ test_send_notification 失败: {e}")
    
    # 测试审计集成
    print("\n=== 测试审计集成 ===")
    test_audit = TestAuditIntegration()
    test_audit.setup_method()
    
    try:
        test_audit.test_audit_log_after_decision()
        print("✅ test_audit_log_after_decision 通过")
    except Exception as e:
        print(f"❌ test_audit_log_after_decision 失败: {e}")
    
    test_audit.teardown_method()
    
    print("\n=== F8 验收测试完成 ===")
