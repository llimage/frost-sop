"""
FROST-SOP V8.0 — 执行追踪测试

验证：
1. ExecutionTrace 创建和事件记录
2. ProjectManager 在创建项目时自动创建追踪
3. TaskParentAgent 在关键节点写入追踪
4. TraceStore 存储和检索
5. 追踪日志导出
"""

import os
os.environ["FROST_TESTING"] = "1"

import sys
sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

from core.project import Project, ProjectStore
from core.trace import ExecutionTrace, TraceStore, create_trace
from skills.strategy.project_manager import ProjectManager
from agents.task_parent import TaskParentAgent


def test_create_trace():
    """测试追踪创建。"""
    print("\n【测试1】创建追踪")
    trace = create_trace("proj_test_001")
    assert trace.trace_id.startswith("trace_")
    assert trace.project_id == "proj_test_001"
    assert len(trace.events) == 1
    assert trace.events[0]["actor"] == "TraceStore"
    print(f"  ✅ 追踪创建: {trace.trace_id}")
    return True


def test_trace_events():
    """测试事件记录。"""
    print("\n【测试2】事件记录")
    trace = create_trace("proj_test_002")
    trace.add_event("ProjectManager", "project_created", {"raw_input": "test"})
    trace.add_decision("route", "single_active_project", {"project_id": "proj_xxx"})
    trace.add_error("execution", "timeout", "retry_after_5s")

    assert len(trace.events) == 2
    assert len(trace.decisions) == 1
    assert len(trace.errors) == 1
    assert trace.errors[0]["phase"] == "execution"
    print("  ✅ 事件/决策/错误记录正常")
    return True


def test_trace_log_export():
    """测试日志导出。"""
    print("\n【测试3】日志导出")
    trace = create_trace("proj_test_003")
    trace.add_event("Actor1", "action1", {"key": "value"})
    trace.add_event("Actor2", "action2")

    log_text = trace.to_log_text()
    assert "Execution Trace" in log_text
    assert "Actor1: action1" in log_text
    assert "Actor2: action2" in log_text
    assert "key" in log_text
    assert "value" in log_text
    print("  ✅ 日志导出正常")
    return True


def test_trace_store():
    """测试追踪存储。"""
    print("\n【测试4】追踪存储")
    store = TraceStore()
    trace = create_trace("proj_test_004")
    trace.add_event("Test", "test_event")

    store.save(trace)
    loaded = store.load(trace.trace_id)

    assert loaded is not None
    assert loaded.project_id == "proj_test_004"
    assert len(loaded.events) == 2
    print(f"  ✅ 存储/检索: {trace.trace_id}")
    return True


def test_project_manager_creates_trace():
    """测试 ProjectManager 自动创建追踪。"""
    print("\n【测试5】ProjectManager 自动追踪")
    trace_store = TraceStore()
    pm = ProjectManager(trace_store=trace_store)
    result = pm.handle_input("我要做心理健康服务")

    assert "trace_id" in result
    trace_id = result["trace_id"]
    assert trace_id.startswith("trace_")

    # 验证追踪已保存（使用同一个trace_store）
    trace = trace_store.load(trace_id)
    assert trace is not None
    assert trace.project_id == result["project_id"]
    assert any(e["action"] == "project_created" for e in trace.events)
    assert any(e["action"] == "new_task_received" for e in trace.events)
    print(f"  ✅ 自动追踪: {trace_id}")
    return True


def test_task_parent_writes_trace():
    """测试 TaskParentAgent 写入追踪。"""
    print("\n【测试6】TaskParentAgent 追踪写入")
    project = Project(id="proj_test_006", name="测试", raw_input="测试", status="created")
    trace = create_trace("proj_test_006")
    store = ProjectStore()

    parent = TaskParentAgent(project=project, project_store=store, trace=trace)
    parent.handle_new_task("我要做测试任务")

    # 验证愿景对齐事件已记录
    assert any(e["action"] == "vision_aligned" for e in trace.events)

    # 处理用户消息
    parent.handle_user_message("进度怎么样？")
    assert any(e["action"] == "status_query" for e in trace.events)

    parent.handle_user_message("改成大学生用户")
    assert any(e["action"] == "vision_updated" for e in trace.events)

    print(f"  ✅ 追踪写入: {len(trace.events)} 个事件")
    return True


def test_trace_decision_points():
    """测试决策点记录。"""
    print("\n【测试7】决策点记录")
    trace = create_trace("proj_test_007")

    trace.add_decision("create_new_project", "no_active_projects", {})
    trace.add_decision("route_to_project", "single_active_project", {"project_id": "proj_xxx"})

    assert len(trace.decisions) == 2
    assert trace.decisions[0]["decision"] == "create_new_project"
    print("  ✅ 决策点记录正常")
    return True


def test_trace_error_recovery():
    """测试错误和恢复记录。"""
    print("\n【测试8】错误恢复记录")
    trace = create_trace("proj_test_008")

    trace.add_error("vision_alignment", "LLM_timeout", "fallback_to_mock")
    trace.add_error("execution", "footman_crash", "restart_footman")

    assert len(trace.errors) == 2
    assert trace.errors[0]["recovery"] == "fallback_to_mock"

    log = trace.to_log_text()
    assert "LLM_timeout" in log
    assert "fallback_to_mock" in log
    print("  ✅ 错误恢复记录正常")
    return True


# ── 主函数 ──

def main():
    print("=" * 60)
    print("【V8.0 执行追踪测试】")
    print("=" * 60)

    tests = [
        ("创建追踪", test_create_trace),
        ("事件记录", test_trace_events),
        ("日志导出", test_trace_log_export),
        ("追踪存储", test_trace_store),
        ("PM自动追踪", test_project_manager_creates_trace),
        ("TPA追踪写入", test_task_parent_writes_trace),
        ("决策点记录", test_trace_decision_points),
        ("错误恢复记录", test_trace_error_recovery),
    ]

    results = []
    for name, test_fn in tests:
        try:
            results.append((name, test_fn()))
        except Exception as e:
            import traceback
            print(f"  ❌ {name} 失败: {e}")
            traceback.print_exc()
            results.append((name, False))

    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅" if result else "❌"
        print(f"  {status} {name}")

    print(f"\n总计: {total} 项 | 通过: {passed} | 失败: {total - passed}")

    if passed == total:
        print("\n🎉 V8.0 执行追踪验证通过！")
    else:
        print(f"\n⚠️ {total - passed} 项测试失败。")


if __name__ == "__main__":
    main()
