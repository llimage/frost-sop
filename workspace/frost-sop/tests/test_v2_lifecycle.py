"""
V2.0 阶段二验收测试：瞬态生命周期管理

验收标准：
1. Agent 执行完后 _status == "destroyed"
2. _destroyed_at 时间戳被设置
3. destroy() 是幂等的（多次调用不报错）
4. agent_status 表有 "running" 和 "destroyed" 记录
5. 回归：测试数不减少
"""

import os
import pytest

# 启用 mock 模式，跳过真实 LLM
os.environ['FROST_TESTING'] = '1'

from core.agent import Agent
from core.skill import Skill


def make_noop_skill(name="noop"):
    """创建一个什么都不做的 Skill，直接返回 context"""
    def noop(context: dict) -> dict:
        context["_noop_ran"] = True
        return context
    return Skill(name, noop)


class TestAgentLifecycle:
    """V2.0 瞬态生命周期测试"""

    def test_v2_01_initial_status_is_idle(self):
        """Agent 初始化后 status 为 idle"""
        agent = Agent(name="test_v2_idle")
        assert agent._status == "idle"
        assert agent._created_at is not None
        assert agent._destroyed_at is None

    def test_v2_02_status_after_run_is_destroyed(self):
        """Agent.run() 完成后 status 应为 destroyed"""
        agent = Agent(
            name="test_v2_run",
            skills={"noop": make_noop_skill()},
        )
        assert agent._status == "idle"
        agent.run(["noop"])
        # 执行完后应被销毁
        assert agent._status == "destroyed"
        assert agent._destroyed_at is not None

    def test_v2_03_destroyed_at_timestamp_set(self):
        """destroy() 后 _destroyed_at 时间戳被设置"""
        from datetime import datetime
        agent = Agent(name="test_v2_ts", skills={"noop": make_noop_skill()})
        before = datetime.now()
        agent.run(["noop"])
        after = datetime.now()
        assert agent._destroyed_at is not None
        assert before <= agent._destroyed_at <= after

    def test_v2_04_destroy_is_idempotent(self):
        """destroy() 多次调用不报错（幂等）"""
        agent = Agent(name="test_v2_idem", skills={"noop": make_noop_skill()})
        agent.run(["noop"])
        assert agent._status == "destroyed"
        # 再次调用不应报错
        agent.destroy()
        agent.destroy()
        assert agent._status == "destroyed"

    def test_v2_05_status_destroyed_on_exception(self):
        """即使 run() 内部抛异常，destroy() 也会被调用"""
        def failing_skill(context: dict) -> dict:
            raise RuntimeError("intentional failure")

        agent = Agent(
            name="test_v2_fail",
            skills={"fail": Skill("fail", failing_skill)},
        )
        with pytest.raises(RuntimeError):
            agent.run(["fail"])

        # 即使失败，状态也应被销毁
        assert agent._status == "destroyed"
        assert agent._destroyed_at is not None

    def test_v2_06_cleanup_clears_pending_sop(self):
        """_cleanup() 清空 _pending_sop"""
        agent = Agent(name="test_v2_cleanup")
        agent._pending_sop = ["step1", "step2"]
        agent._cleanup()
        assert agent._pending_sop == []

    def test_v2_07_cleanup_clears_parent_ref(self):
        """_cleanup() 释放父辈引用"""
        parent = Agent(name="test_v2_parent")
        child = Agent(name="test_v2_child_cleanup")
        child._parent = parent
        child._cleanup()
        assert child._parent is None

    def test_v2_08_db_agent_status_recorded(self):
        """执行后 agent_status 表有 destroyed 记录"""
        # 需要隔离 DB（使用内存或测试 DB）
        import tempfile

        # 使用临时数据库避免污染主库
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            tmp_db = f.name

        try:
            # 重置 DB 单例使用临时路径
            import core.db as db_module
            old_instance = db_module.DBManager._instance
            old_conn = db_module.DBManager._connection
            old_global = db_module._db_manager

            db_module.DBManager._instance = None
            db_module.DBManager._connection = None
            db_module._db_manager = None

            try:
                # 初始化临时 DB
                db_module.DBManager._instance = None
                test_db = db_module.DBManager(db_path=tmp_db)
                db_module._db_manager = test_db

                # 执行 Agent
                agent = Agent(
                    name="test_v2_db_lifecycle",
                    skills={"noop": make_noop_skill()},
                )
                agent.run(["noop"])

                # 验证 agent_status 表有记录
                status_row = test_db.select_one("agent_status", "agent_id", "test_v2_db_lifecycle")
                assert status_row is not None, "agent_status 表应有记录"
                assert status_row["status"] == "destroyed", f"状态应为 destroyed，实际: {status_row['status']}"

            finally:
                # 恢复 DB 单例
                db_module.DBManager._instance = old_instance
                db_module.DBManager._connection = old_conn
                db_module._db_manager = old_global

        finally:
            import os as _os
            try:
                _os.unlink(tmp_db)
            except Exception:
                pass

    def test_v2_09_execution_history_preserved_after_destroy(self):
        """destroy() 不清除 _execution_history（保留审计轨迹）"""
        agent = Agent(name="test_v2_hist", skills={"noop": make_noop_skill()})
        agent.run(["noop"])
        assert agent._status == "destroyed"
        # 执行历史应被保留
        assert len(agent._execution_history) == 1
        assert agent._execution_history[0]["overall_success"] is True
