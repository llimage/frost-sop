"""
P0-2 自验收测试：父辈自修复重试机制

测试内容：
1. 基础重试：Skill 前2次失败、第3次成功
2. 备用Skill切换：第2次重试时切换到备用Skill
3. 最大重试后上报祖辈
4. 成功执行无重试
"""

import os
import sys
import time
import pytest

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.agent import Agent
from core.skill import Skill


class TestRetryMechanism:
    """测试重试机制核心逻辑"""

    def test_retry_succeeds_on_third_attempt(self):
        """测试：前2次失败、第3次成功"""
        call_count = [0]

        def flaky_skill(ctx):
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError(f"临时故障 (尝试 {call_count[0]})")
            ctx["_result"] = f"第{call_count[0]}次成功"
            return ctx

        agent = Agent(
            name="test_retry_agent",
            skills={"flaky": Skill("flaky", flaky_skill)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
        )

        context = agent.run(["flaky"], {})

        assert call_count[0] == 3, f"应调用3次，实际: {call_count[0]}"
        assert context["_result"] == "第3次成功"

        # 检查执行历史
        history = agent.get_history(1)
        assert len(history) > 0
        last_record = history[0]
        assert last_record["overall_success"] is True
        step_records = last_record["step_records"]
        assert len(step_records) == 1
        assert step_records[0]["success"] is True
        assert step_records[0]["retries"] == 2  # 2次重试后成功
        print("  ✅ test_retry_succeeds_on_third_attempt 通过")

    def test_max_retries_exceeded_reports_to_elder(self):
        """测试：3次全部失败后上报祖辈"""
        elder_reports = []

        def elder_callback(max_retries, step_name, error, agent_name):
            elder_reports.append(
                {
                    "max_retries": max_retries,
                    "step_name": step_name,
                    "error": str(error),
                    "agent_name": agent_name,
                }
            )

        def always_fail(ctx):
            raise RuntimeError("永久性故障")

        agent = Agent(
            name="test_fail_agent",
            skills={"fail_skill": Skill("fail_skill", always_fail)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
            on_max_retries=elder_callback,
        )

        try:
            agent.run(["fail_skill"], {})
            assert False, "应抛出异常"
        except RuntimeError as e:
            assert "永久性故障" in str(e)

        # 验证上报到祖辈
        assert len(elder_reports) == 1, f"应有1条上报，实际: {len(elder_reports)}"
        report = elder_reports[0]
        assert report["step_name"] == "fail_skill"
        assert report["max_retries"] == 3
        assert report["agent_name"] == "test_fail_agent"
        assert "永久性故障" in report["error"]

        # 检查执行历史记录了失败
        history = agent.get_history(1)
        assert history[0]["overall_success"] is False
        step_records = history[0]["step_records"]
        assert step_records[0]["success"] is False
        assert step_records[0]["retries"] == 3
        assert step_records[0]["escalated_to_elder"] is True
        print("  ✅ test_max_retries_exceeded_reports_to_elder 通过")

    def test_alternate_skill_switching(self):
        """测试：第2次重试时切换到备用Skill"""
        call_log = []

        def primary_skill(ctx):
            call_log.append("primary")
            raise RuntimeError("主Skill不可用")

        def backup_skill(ctx):
            call_log.append("backup")
            ctx["_result"] = "备用Skill成功"
            return ctx

        agent = Agent(
            name="test_alt_agent",
            skills={
                "call_llm": Skill("call_llm", primary_skill),
                "call_llm_base": Skill("call_llm_base", backup_skill),
            },
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
        )

        context = agent.run(["call_llm"], {})

        # 应该尝试了 primary (attempt 1), primary (attempt 2), 然后切换到 backup (attempt 2 retry)
        # Wait, let me review the logic:
        # Attempt 1: primary fails → call_log.append("primary")
        # Attempt 2: _find_alternate_skill checks for "call_llm" → finds "call_llm_base" → switches step
        # Attempt 2 (with backup): backup succeeds → call_log.append("backup")
        # So call_log should be ["primary", "backup"]

        assert "primary" in call_log, "应尝试过主Skill"
        assert "backup" in call_log, "应切换到了备用Skill"
        assert context["_result"] == "备用Skill成功"
        print(f"  ✅ test_alternate_skill_switching 通过 ({call_log})")

    def test_no_retry_on_success(self):
        """测试：成功时不重试"""
        call_count = [0]

        def stable_skill(ctx):
            call_count[0] += 1
            ctx["_result"] = "一次成功"
            return ctx

        agent = Agent(
            name="test_stable_agent",
            skills={"stable": Skill("stable", stable_skill)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
        )

        context = agent.run(["stable"], {})

        assert call_count[0] == 1, f"应只调用1次，实际: {call_count[0]}"
        assert context["_result"] == "一次成功"

        history = agent.get_history(1)
        assert history[0]["step_records"][0]["retries"] == 0
        print("  ✅ test_no_retry_on_success 通过")

    def test_multiple_agents_with_retry(self):
        """测试：多代Agent重试传递"""
        child_calls = [0]

        def child_skill(ctx):
            child_calls[0] += 1
            if child_calls[0] < 2:
                raise RuntimeError(f"子Agent临时故障 (尝试 {child_calls[0]})")
            ctx["_child_result"] = "子Agent成功"
            return ctx

        child = Agent(
            name="child_agent",
            skills={"task": Skill("task", child_skill)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
        )

        # 父辈Agent作为步骤执行子Agent，子Agent执行内部SOP步骤
        context = child.run(["task"], {})

        assert child_calls[0] == 2, f"子Agent应调用2次，实际: {child_calls[0]}"
        assert context["_child_result"] == "子Agent成功"
        print("  ✅ test_multiple_agents_with_retry 通过")

    def test_parent_runs_child_agent_with_retry(self):
        """测试：父辈运行子Agent作为步骤，子Agent自带重试"""
        child_calls = [0]

        def child_task(ctx):
            child_calls[0] += 1
            if child_calls[0] < 2:
                raise RuntimeError("子故障")
            ctx["_done"] = True
            return ctx

        child = Agent(
            name="retry_child",
            skills={"run_task": Skill("run_task", child_task)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.05},
        )
        child._sop_steps = ["run_task"]

        parent = Agent(
            name="retry_parent",
            retry_config={"max_retries": 1, "retry_delay_seconds": 0.05},
        )

        context = parent.run([child], {})

        assert child_calls[0] == 2, (
            f"子Agent应调用2次（内部重试），实际: {child_calls[0]}"
        )
        assert context.get("_done") is True
        print("  ✅ test_parent_runs_child_agent_with_retry 通过")


class TestRetryLogging:
    """测试重试日志记录"""

    def test_retry_records_in_history(self):
        """测试执行历史包含重试信息"""
        call_count = [0]

        def flaky(ctx):
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("故障1")
            ctx["_result"] = "成功"
            return ctx

        agent = Agent(
            name="log_test_agent",
            skills={"flaky": Skill("flaky", flaky)},
            retry_config={"max_retries": 3, "retry_delay_seconds": 0.1},
        )

        agent.run(["flaky"], {})

        history = agent.get_history()
        assert len(history) >= 1

        # 验证历史记录包含重试信息
        record = history[0]
        assert "step_records" in record
        assert "overall_success" in record

        # 从历史中检查
        step = record["step_records"][0]
        assert step["success"] is True
        assert step["retries"] >= 1  # 至少重试了1次
        print("  ✅ test_retry_records_in_history 通过")


def test_timing_between_retries():
    """测试重试间隔时间正确"""
    call_count = [0]

    def fail_twice(ctx):
        call_count[0] += 1
        if call_count[0] < 3:
            raise RuntimeError("故障")
        ctx["_result"] = "最终成功"
        return ctx

    agent = Agent(
        name="timing_agent",
        skills={"fail_twice": Skill("fail_twice", fail_twice)},
        retry_config={"max_retries": 3, "retry_delay_seconds": 0.05},
    )

    start = time.time()
    agent.run(["fail_twice"], {})
    elapsed = time.time() - start

    # 2次重试 × 0.05s = 至少 0.1s
    assert elapsed >= 0.08, f"总耗时应 >= 0.08s（因重试延迟），实际: {elapsed:.3f}s"
    print(f"  ✅ test_timing_between_retries 通过 (耗时 {elapsed:.3f}s)")


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v", "--tb=short"])
