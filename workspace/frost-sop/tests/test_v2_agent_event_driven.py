"""
V2.0 子阶段 4.3 验收测试：Agent 类事件驱动改造

验收标准：
1. event_driven=False（默认）不发布任何事件（向后兼容）
2. event_driven=True 时，步骤完成后发布 STEP_COMPLETED 事件
3. event_driven=True 时，初始化发布 AGENT_CREATED，销毁发布 AGENT_DESTROYED
4. 直接调用模式（旧代码）仍然可用
5. 订阅者能收到事件并响应
6. 回归：所有原有测试不受影响
"""

import os

import pytest

os.environ["FROST_TESTING"] = "1"

from core.agent import Agent
from core.event_bus import EventBus, EventType, get_event_bus
from core.skill import Skill


def make_noop():
    def noop(ctx):
        ctx["_ran"] = True
        return ctx

    return Skill("noop", noop)


class TestAgentEventDriven:
    """V2.0 子阶段 4.3: Agent 事件驱动测试"""

    def setup_method(self):
        """每个测试前重置 EventBus"""
        EventBus.reset()

    def teardown_method(self):
        EventBus.reset()

    # ----------------------------------------------------------
    # 向后兼容：event_driven=False（默认）
    # ----------------------------------------------------------

    def test_v2_43_01_default_no_events_published(self):
        """默认 event_driven=False，不发布任何事件"""
        bus = get_event_bus()
        collected = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: collected.append(e))
        bus.subscribe(EventType.AGENT_CREATED, lambda e: collected.append(e))
        bus.subscribe(EventType.AGENT_DESTROYED, lambda e: collected.append(e))

        agent = Agent(name="test_compat", skills={"noop": make_noop()})
        agent.run(["noop"])

        assert len(collected) == 0, "默认模式不应发布事件"

    def test_v2_43_02_direct_call_still_works(self):
        """直接调用模式（V1.0）仍然正常工作"""
        agent = Agent(name="test_direct", skills={"noop": make_noop()})
        ctx = agent.run(["noop"])
        assert ctx.get("_ran") is True

    # ----------------------------------------------------------
    # event_driven=True 模式
    # ----------------------------------------------------------

    def test_v2_43_03_event_driven_agent_created(self):
        """event_driven=True 时，初始化发布 AGENT_CREATED 事件"""
        bus = get_event_bus()
        created_events = []
        bus.subscribe(EventType.AGENT_CREATED, lambda e: created_events.append(e))

        Agent(name="test_ev_create", skills={"noop": make_noop()}, event_driven=True)

        assert len(created_events) == 1
        assert created_events[0].source == "test_ev_create"
        assert created_events[0].data["agent_name"] == "test_ev_create"

    def test_v2_43_04_event_driven_step_completed(self):
        """event_driven=True 时，每个步骤完成后发布 STEP_COMPLETED 事件"""
        bus = get_event_bus()
        step_events = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: step_events.append(e))

        def skill_a(ctx):
            ctx["_a"] = 1
            return ctx

        def skill_b(ctx):
            ctx["_b"] = 2
            return ctx

        agent = Agent(
            name="test_ev_steps",
            skills={
                "skill_a": Skill("skill_a", skill_a),
                "skill_b": Skill("skill_b", skill_b),
            },
            event_driven=True,
        )
        agent.run(["skill_a", "skill_b"])

        assert len(step_events) == 2
        step_names = [e.data["step_name"] for e in step_events]
        assert "skill_a" in step_names
        assert "skill_b" in step_names

    def test_v2_43_05_event_driven_agent_destroyed(self):
        """event_driven=True 时，destroy() 发布 AGENT_DESTROYED 事件"""
        bus = get_event_bus()
        destroyed_events = []
        bus.subscribe(EventType.AGENT_DESTROYED, lambda e: destroyed_events.append(e))

        # 订阅 AGENT_CREATED 不干扰
        agent = Agent(name="test_ev_destroy", skills={"noop": make_noop()}, event_driven=True)
        # 清空 AGENT_CREATED 缓存（只关心 DESTROYED）
        destroyed_events.clear()

        agent.run(["noop"])

        assert len(destroyed_events) == 1
        assert destroyed_events[0].source == "test_ev_destroy"
        assert destroyed_events[0].data["agent_name"] == "test_ev_destroy"

    def test_v2_43_06_event_driven_step_data_contains_task_id(self):
        """STEP_COMPLETED 事件 data 包含 task_id"""
        bus = get_event_bus()
        step_events = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: step_events.append(e))

        agent = Agent(name="test_ev_task_id", skills={"noop": make_noop()}, event_driven=True)
        agent.run(["noop"], initial_context={"_task_id": "task_abc123"})

        assert len(step_events) == 1
        assert step_events[0].data.get("task_id") == "task_abc123"

    def test_v2_43_07_subscriber_receives_events_in_order(self):
        """订阅者按步骤顺序收到 STEP_COMPLETED 事件"""
        bus = get_event_bus()
        order = []

        def track(e):
            order.append(e.data["step_name"])

        bus.subscribe(EventType.STEP_COMPLETED, track)

        def s1(ctx):
            ctx["s1"] = 1
            return ctx

        def s2(ctx):
            ctx["s2"] = 2
            return ctx

        def s3(ctx):
            ctx["s3"] = 3
            return ctx

        agent = Agent(
            name="test_ev_order",
            skills={
                "s1": Skill("s1", s1),
                "s2": Skill("s2", s2),
                "s3": Skill("s3", s3),
            },
            event_driven=True,
        )
        agent.run(["s1", "s2", "s3"])

        assert order == ["s1", "s2", "s3"]

    def test_v2_43_08_no_step_event_on_failure(self):
        """步骤失败时不发布 STEP_COMPLETED 事件（只有成功步骤发布）"""
        bus = get_event_bus()
        step_events = []
        bus.subscribe(EventType.STEP_COMPLETED, lambda e: step_events.append(e))

        def ok_skill(ctx):
            ctx["ok"] = True
            return ctx

        def fail_skill(ctx):
            raise RuntimeError("故意失败")

        agent = Agent(
            name="test_ev_fail",
            skills={
                "ok": Skill("ok", ok_skill),
                "fail": Skill("fail", fail_skill),
            },
            event_driven=True,
            retry_config={"max_retries": 1, "retry_delay_seconds": 0},
        )

        with pytest.raises(RuntimeError):
            agent.run(["ok", "fail"])

        # ok 步骤成功发布了事件，fail 步骤没有
        step_names = [e.data["step_name"] for e in step_events]
        assert "ok" in step_names
        assert "fail" not in step_names

    def test_v2_43_09_event_driven_field_accessible(self):
        """_event_driven 字段可以访问，默认为 False"""
        a1 = Agent(name="test_ev_field_false")
        assert a1._event_driven is False

        a2 = Agent(name="test_ev_field_true", event_driven=True)
        assert a2._event_driven is True
