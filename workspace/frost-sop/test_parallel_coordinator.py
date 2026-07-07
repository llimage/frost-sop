"""
FROST-SOP V7.3 — 并行协调器测试（自行车定制场景）

验证核心能力：
1. 计划解析为并行组
2. 组内阶段并行触发
3. 组输出合并为下一组输入
4. 府兵接收前置组合并输出
"""

import sys
import os
import time

sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

env_path = r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop\.env'
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key] = val

os.environ.pop('FROST_TESTING', None)

from core.event_bus import EventBus, EventType
from core.event_bus_daemon import EventBusDaemon
from core.coordinator import ParallelCoordinator, ExecutionGroup
from core.store import Store


def test_group_parsing():
    """测试计划解析为执行组。"""
    print("\n" + "=" * 60)
    print("【测试1】自行车定制计划 → 执行组解析")
    print("=" * 60)

    plan = {
        "plan_id": "plan_bike_001",
        "name": "自行车定制",
        "phases": [
            {"phase_id": "phase_1", "module": "需求解析", "sop_id": "SOP-REQ-001", "trigger": "immediate", "inputs": {"customer_data": "身高175, 颜色偏好红色"}, "outputs": {}, "depends_on": []},
            {"phase_id": "phase_2a", "module": "交付拆解", "sop_id": "SOP-DEL-001", "trigger": "immediate", "parallel_group": "parallel_1", "inputs": {"requirements": "{{phase_1.outputs.requirements}}"}, "outputs": {}, "depends_on": ["phase_1"]},
            {"phase_id": "phase_2b", "module": "库存查询", "sop_id": "SOP-INV-001", "trigger": "immediate", "parallel_group": "parallel_1", "inputs": {"requirements": "{{phase_1.outputs.requirements}}"}, "outputs": {}, "depends_on": ["phase_1"]},
            {"phase_id": "phase_3", "module": "报价生成", "sop_id": "SOP-QUO-001", "trigger": "immediate", "inputs": {"parts_list": "{{phase_2a.outputs.parts_list}}", "inventory_status": "{{phase_2b.outputs.inventory_status}}"}, "outputs": {}, "depends_on": ["phase_2a", "phase_2b"]},
        ],
    }

    coordinator = ParallelCoordinator()
    coordinator.load_plan(plan)

    assert len(coordinator._groups) == 3, f"应有3组，实际{len(coordinator._groups)}"
    print("✅ 组数量正确: 3")

    # phase_1 独占一组
    g0 = next(g for g in coordinator._groups.values() if "phase_1" in [p["phase_id"] for p in g.phases])
    assert len(g0.phases) == 1
    assert g0.depends_on_groups == []
    print("✅ phase_1 独占一组，无依赖")

    # phase_2a + phase_2b 同组
    g1 = next(g for g in coordinator._groups.values() if "phase_2a" in [p["phase_id"] for p in g.phases])
    assert len(g1.phases) == 2
    assert "group_phase_1" in g1.depends_on_groups
    print("✅ phase_2a + phase_2b 同组并行，依赖 phase_1")

    # phase_3 依赖并行组
    g2 = next(g for g in coordinator._groups.values() if "phase_3" in [p["phase_id"] for p in g.phases])
    assert g1.group_id in g2.depends_on_groups
    print("✅ phase_3 独占一组，依赖并行组")

    print("\n【测试1结论】✅ PASS")
    return True


def test_group_input_collection():
    """测试组输出合并为下一组输入。"""
    print("\n" + "=" * 60)
    print("【测试2】组输出合并 → 下一组输入")
    print("=" * 60)

    plan = {
        "plan_id": "plan_bike_002",
        "phases": [
            {"phase_id": "phase_1", "module": "需求解析", "depends_on": []},
            {"phase_id": "phase_2a", "module": "交付拆解", "parallel_group": "parallel_1", "depends_on": ["phase_1"]},
            {"phase_id": "phase_2b", "module": "库存查询", "parallel_group": "parallel_1", "depends_on": ["phase_1"]},
            {"phase_id": "phase_3", "module": "报价生成", "depends_on": ["phase_2a", "phase_2b"]},
        ],
    }

    coordinator = ParallelCoordinator()
    coordinator.load_plan(plan)

    # 模拟 group_0 完成
    g0 = next(g for g in coordinator._groups.values() if "phase_1" in [p["phase_id"] for p in g.phases])
    g0.mark_phase_completed("phase_1", {"requirements": "身高175, 红色, 山地车"})
    g0.status = "completed"

    # 收集 group_1 输入
    g1 = next(g for g in coordinator._groups.values() if "phase_2a" in [p["phase_id"] for p in g.phases])
    inputs = coordinator._collect_group_inputs(g1.group_id)
    assert inputs["requirements"] == "身高175, 红色, 山地车"
    print("✅ group_1 输入正确包含 phase_1 的输出")

    # 模拟 group_1 完成
    g1.mark_phase_completed("phase_2a", {"parts_list": ["车架A", "轮组B", "变速C"]})
    g1.mark_phase_completed("phase_2b", {"inventory_status": {"车架A": 5, "轮组B": 0, "变速C": 12}})
    g1.status = "completed"

    # 收集 group_2 输入
    g2 = next(g for g in coordinator._groups.values() if "phase_3" in [p["phase_id"] for p in g.phases])
    inputs = coordinator._collect_group_inputs(g2.group_id)
    assert "parts_list" in inputs
    assert "inventory_status" in inputs
    assert "_group_outputs" in inputs
    print("✅ group_2 输入正确合并 phase_2a + phase_2b 的输出")
    print(f"   parts_list: {inputs['parts_list']}")
    print(f"   inventory_status: {inputs['inventory_status']}")

    print("\n【测试2结论】✅ PASS")
    return True


def test_end_to_end_event_flow():
    """测试端到端事件流。"""
    print("\n" + "=" * 60)
    print("【测试3】端到端事件流（模拟）")
    print("=" * 60)

    EventBus.reset()
    daemon = EventBusDaemon()
    daemon.start()
    time.sleep(0.5)

    received_events = []
    def _capture(event):
        if event.event_type == EventType.SCHEDULED_EXECUTED:
            received_events.append(event.data)

    EventBus().subscribe(EventType.SCHEDULED_EXECUTED, _capture)

    store = Store()
    plan = {
        "plan_id": "plan_bike_003",
        "phases": [
            {"phase_id": "phase_1", "module": "需求解析", "sop_id": "SOP-REQ-001", "trigger": "immediate", "inputs": {}, "outputs": {}, "depends_on": []},
            {"phase_id": "phase_2a", "module": "交付拆解", "sop_id": "SOP-DEL-001", "trigger": "immediate", "parallel_group": "parallel_1", "inputs": {}, "outputs": {}, "depends_on": ["phase_1"]},
            {"phase_id": "phase_2b", "module": "库存查询", "sop_id": "SOP-INV-001", "trigger": "immediate", "parallel_group": "parallel_1", "inputs": {}, "outputs": {}, "depends_on": ["phase_1"]},
            {"phase_id": "phase_3", "module": "报价生成", "sop_id": "SOP-QUO-001", "trigger": "immediate", "inputs": {}, "outputs": {}, "depends_on": ["phase_2a", "phase_2b"]},
        ],
    }

    coordinator = ParallelCoordinator(daemon=daemon, store=store)
    coordinator.load_plan(plan)
    coordinator.start_execution()
    time.sleep(2.0)

    # 验证 phase_1 被触发
    phase1 = [e for e in received_events if e.get("phase_id") == "phase_1"]
    assert len(phase1) == 1, f"应触发1次 phase_1，实际{len(phase1)}"
    print("✅ phase_1 被触发（入口组）")

    # 模拟 phase_1 完成
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test_footman",
        data={"plan_id": "plan_bike_003", "phase_id": "phase_1", "outputs": {"requirements": "身高175"}},
    ))
    time.sleep(2.0)

    # 验证并行组被触发
    p2a = [e for e in received_events if e.get("phase_id") == "phase_2a"]
    p2b = [e for e in received_events if e.get("phase_id") == "phase_2b"]
    assert len(p2a) == 1, f"应触发1次 phase_2a，实际{len(p2a)}"
    assert len(p2b) == 1, f"应触发1次 phase_2b，实际{len(p2b)}"
    assert p2a[0].get("coordinated") == True
    assert p2a[0].get("inputs", {}).get("requirements") == "身高175"
    print("✅ phase_2a + phase_2b 被并行触发（含 phase_1 输出）")

    # 模拟并行组完成
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test_footman",
        data={"plan_id": "plan_bike_003", "phase_id": "phase_2a", "outputs": {"parts_list": ["A", "B"]}},
    ))
    time.sleep(0.5)
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test_footman",
        data={"plan_id": "plan_bike_003", "phase_id": "phase_2b", "outputs": {"inventory_status": {"A": 5}}},
    ))
    time.sleep(2.0)

    # 验证 phase_3 被触发（合并输入）
    p3 = [e for e in received_events if e.get("phase_id") == "phase_3"]
    assert len(p3) == 1, f"应触发1次 phase_3，实际{len(p3)}"
    assert p3[0].get("inputs", {}).get("parts_list") == ["A", "B"]
    assert p3[0].get("inputs", {}).get("inventory_status") == {"A": 5}
    print("✅ phase_3 被触发（合并 phase_2a + phase_2b 输出）")

    print(f"✅ 整体进度: {coordinator.get_overall_progress():.0%}")

    daemon.stop()
    EventBus.reset()

    print("\n【测试3结论】✅ PASS")
    return True


def main():
    print("=" * 60)
    print("【V7.3 并行协调器测试】自行车定制场景")
    print("=" * 60)

    results = []
    results.append(("组解析", test_group_parsing()))
    results.append(("输入合并", test_group_input_collection()))
    results.append(("端到端事件流", test_end_to_end_event_flow()))

    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)
    passed = sum(1 for _, r in results if r)
    for name, r in results:
        icon = "✅" if r else "❌"
        print(f"   {icon} {name}")
    print(f"\n总计: {len(results)} 项 | 通过: {passed} | 失败: {len(results) - passed}")


if __name__ == "__main__":
    main()
