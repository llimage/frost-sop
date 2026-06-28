"""
FROST-SOP V3.1 测试覆盖率补充: skills/orchestration.py
覆盖 internalize_sop, spawn, emit, validate_sop, merge_from, finalize_task
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skill import Skill
from core.agent import Agent
from core.store import Store
from skills.orchestration import (
    internalize_sop, spawn, emit, validate_sop, merge_from, finalize_task,
)


# ============================================================
# internalize_sop 测试
# ============================================================

def test_internalize_sop_with_stages():
    """内化有阶段的SOP模板"""
    ctx = {"_sop_to_internalize": {
        "sop_id": "TEST-001",
        "stages": [
            {"name": "需求分析", "agent": "analyst", "skills": ["analyze"]},
            {"name": "开发", "agent": "dev", "skills": ["code"]},
            {"name": "测试", "agent": "tester", "skills": ["test"]},
        ]
    }}
    result = internalize_sop(ctx)
    steps = result.get("_internalized_steps", [])
    assert len(steps) == 3
    assert steps[0] == "execute_stage:需求分析"
    assert steps[1] == "execute_stage:开发"
    assert steps[2] == "execute_stage:测试"
    assert result.get("_reason", "").startswith("内化成功")


def test_internalize_sop_empty_stages():
    """内化无阶段的SOP模板"""
    ctx = {"_sop_to_internalize": {"stages": []}}
    result = internalize_sop(ctx)
    assert result.get("_internalized_steps") == []
    assert "无阶段定义" in result.get("_reason", "")


def test_internalize_sop_no_data():
    """内化不提供SOP数据"""
    ctx = {}
    result = internalize_sop(ctx)
    assert result.get("_internalized_steps") == []
    assert "无阶段定义" in result.get("_reason", "")


# ============================================================
# spawn 测试
# ============================================================

def test_spawn_no_spec():
    """spawn无规格时跳过"""
    ctx = {}
    result = spawn(ctx)
    assert result is ctx


def test_spawn_no_template():
    """spawn无模板Agent时跳过"""
    ctx = {"_spawn_spec": {"agent_id": "child_1"}}
    result = spawn(ctx)
    assert result is ctx
    assert "_children_results" not in result


def test_spawn_with_template():
    """spawn有模板Agent时创建子Agent"""
    template = Agent(name="template_agent", store=Store(),
        skills={"test_skill": Skill("test_skill", lambda c: c)},
        sop_steps=["test_skill"])
    ctx = {
        "_spawn_spec": {
            "agent_id": "child_agent",
            "template_agent": template,
            "initial_context": {"_test_key": "test_value"},
        }
    }
    result = spawn(ctx)
    children = result.get("_children_results", [])
    assert len(children) == 1
    assert children[0]["agent_id"] == "child_agent"


# ============================================================
# emit 测试
# ============================================================

def test_emit_default_keys():
    """emit默认导出_result键"""
    ctx = {"_result": "test_data", "other": "ignored"}
    result = emit(ctx)
    assert "_result" in result
    assert result["_result"].get("_result") == "test_data"


def test_emit_custom_keys():
    """emit自定义导出键"""
    ctx = {"a": 1, "b": 2, "c": 3, "_emit_keys": ["a", "c"]}
    result = emit(ctx)
    assert result["_result"] == {"a": 1, "c": 3}


# ============================================================
# validate_sop 测试
# ============================================================

def test_validate_sop_no_sop():
    """validate_sop无SOP时返回错误"""
    ctx = {}
    result = validate_sop(ctx)
    validation = result.get("_validation_result", {})
    assert validation.get("valid") is False


# ============================================================
# merge_from 测试
# ============================================================

def test_merge_from_basic():
    """merge_from基本合并"""
    child_store = Store()
    child_store.save("output", "hello world")
    child_store.save("status", "done")
    parent_store = Store()
    ctx = {
        "_child_store": child_store,
        "_store": parent_store,
        "_merge_keys": ["output", "status"],
    }
    result = merge_from(ctx)
    assert parent_store.load("output") == "hello world"
    assert parent_store.load("status") == "done"


def test_merge_from_no_stores():
    """merge_from无Store时跳过"""
    ctx = {"_merge_keys": ["key1"]}
    result = merge_from(ctx)
    assert result is ctx


def test_merge_from_missing_key():
    """merge_from合并不存在的键"""
    child_store = Store()
    parent_store = Store()
    ctx = {
        "_child_store": child_store,
        "_store": parent_store,
        "_merge_keys": ["nonexistent"],
    }
    result = merge_from(ctx)
    assert parent_store.load("nonexistent") is None


# ============================================================
# finalize_task 测试
# ============================================================

def test_finalize_task_no_task_id():
    """finalize_task无task_id时跳过审计"""
    ctx = {"_task_id": "unknown"}
    result = finalize_task(ctx)
    assert result.get("_elder_audit_triggered") is False


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            print(f"Running {name}...")
            func()
            print(f"  ✅ {name} passed")
    print("\n✅ 所有 orchestration 覆盖率测试通过")
