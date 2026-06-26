import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import Store
from core.skill import Skill
from core.agent import Agent


def test_agent_run():
    """Test basic Agent run operation."""
    store = Store()
    skill = Skill("echo", lambda ctx: {**ctx, "_result": ctx.get("msg")})
    agent = Agent("test", store, {"echo": skill})
    result = agent.run(["echo"], {"msg": "hello"})
    assert result["_result"] == "hello"
    print("[PASS] test_agent_run")


def test_agent_spawn_generation_limit():
    """Test Agent spawn with generation limit."""
    ancestor = Agent("ancestor", generation=0, max_spawn_generation=1)
    parent = ancestor.spawn("parent")
    assert parent.generation == 1
    assert parent.max_spawn_generation == 0  # Key: parent cannot spawn further
    try:
        parent.spawn("child")  # parent tries to spawn child, should fail
        assert False, "Should raise PermissionError"
    except PermissionError:
        pass
    print("[PASS] test_agent_spawn_generation_limit")


def test_agent_teach_and_internalize():
    """Test Agent teach and internalize operations."""
    store = Store()
    parent = Agent("parent", store)
    child = Agent("child", Store(), {})
    parent.teach(child, ["step1", "step2"])
    child.internalize()
    assert child._sop_steps == ["step1", "step2"]
    print("[PASS] test_agent_teach_and_internalize")


def test_agent_execution_history():
    """Test Agent execution history recording."""
    store = Store()
    skill = Skill("ok", lambda ctx: ctx)
    agent = Agent("historian", store, {"ok": skill})
    agent.run(["ok"], {})
    agent.run(["ok"], {})
    history = agent.get_history()
    assert len(history) == 2
    assert history[0]["overall_success"] is True
    print("[PASS] test_agent_execution_history")


if __name__ == "__main__":
    test_agent_run()
    test_agent_spawn_generation_limit()
    test_agent_teach_and_internalize()
    test_agent_execution_history()
    print("\n[ALL PASS] All Agent tests passed!")
