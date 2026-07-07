"""
FROST-SOP V7.3 — 并行协调器验证（自行车定制）
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

from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.coordinator import ParallelCoordinator
from core.store import Store


def run_test():
    print("=" * 60)
    print("【V7.3 并行协调器验证】自行车定制场景")
    print("=" * 60)

    # ── 测试1: 组解析 ──
    print("\n【测试1】计划解析为执行组")
    plan = {
        "plan_id": "plan_bike_001",
        "phases": [
            {"phase_id": "phase_1", "module": "需求解析", "depends_on": []},
            {"phase_id": "phase_2a", "module": "交付拆解", "parallel_group": "parallel_1", "depends_on": ["phase_1"]},
            {"phase_id": "phase_2b", "module": "库存查询", "parallel_group": "parallel_1", "depends_on": ["phase_1"]},
            {"phase_id": "phase_3", "module": "报价生成", "depends_on": ["phase_2a", "phase_2b"]},
        ],
    }
    coordinator = ParallelCoordinator()
    coordinator.load_plan(plan)
    assert len(coordinator._groups) == 3
    g1 = next(g for g in coordinator._groups.values() if "phase_2a" in [p["phase_id"] for p in g.phases])
    assert len(g1.phases) == 2
    assert "group_phase_1" in g1.depends_on_groups
    print("✅ 3组解析正确，并行组依赖关系正确")

    # ── 测试2: 输入合并 ──
    print("\n【测试2】组输出合并")
    g0 = next(g for g in coordinator._groups.values() if "phase_1" in [p["phase_id"] for p in g.phases])
    g0.mark_phase_completed("phase_1", {"requirements": "身高175, 红色"})
    g0.status = "completed"

    g1.mark_phase_completed("phase_2a", {"parts_list": ["车架A"]})
    g1.mark_phase_completed("phase_2b", {"inventory_status": {"车架A": 5}})
    g1.status = "completed"

    g2 = next(g for g in coordinator._groups.values() if "phase_3" in [p["phase_id"] for p in g.phases])
    inputs = coordinator._collect_group_inputs(g2.group_id)
    assert inputs["parts_list"] == ["车架A"]
    assert inputs["inventory_status"]["车架A"] == 5
    print("✅ 前置组合并输出正确传递给后续组")

    # ── 测试3: 端到端事件流 ──
    print("\n【测试3】端到端事件流")
    print(f"  EventBus._instance before reset: {EventBus._instance}")
    EventBus.reset()
    print(f"  EventBus._instance after reset: {EventBus._instance}")

    print(f"  EventBusDaemon._instance before create: {EventBusDaemon._instance}")
    daemon = EventBusDaemon()
    print(f"  EventBusDaemon._instance after create: {id(EventBusDaemon._instance)}")
    print(f"  daemon._running: {daemon._running}")

    daemon.start()
    time.sleep(0.5)
    print(f"  daemon.is_running(): {daemon.is_running()}")
    print(f"  daemon._bus id: {id(daemon._bus)}")

    received = []
    def capture(event):
        if event.event_type == EventType.SCHEDULED_EXECUTED:
            print(f"    [CAPTURED] {event.data.get('phase_id')}")
            received.append(event.data)

    bus = EventBus()
    print(f"  EventBus id: {id(bus)}")
    bus.subscribe(EventType.SCHEDULED_EXECUTED, capture)
    print(f"  Subscribers: {bus.get_subscriber_count(EventType.SCHEDULED_EXECUTED)}")

    store = Store()
    coordinator = ParallelCoordinator(daemon=daemon, store=store)
    coordinator.load_plan(plan)
    print(f"  Coordinator daemon id: {id(coordinator.daemon)}")
    print(f"  Coordinator daemon running: {coordinator.daemon.is_running()}")

    coordinator.start_execution()
    print(f"  After start_execution, queue size: {daemon.get_queue_size()}")

    time.sleep(2.0)
    print(f"  After sleep, received count: {len(received)}")
    for e in received:
        print(f"    - {e.get('phase_id')}")

    phase1_count = len([e for e in received if e.get("phase_id") == "phase_1"])
    print(f"  phase_1 events: {phase1_count}")

    if phase1_count != 1:
        print("  ❌ 测试失败，退出")
        return False

    print("✅ phase_1 被触发")

    # 模拟 phase_1 完成
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test",
        data={"plan_id": "plan_bike_001", "phase_id": "phase_1", "outputs": {"requirements": "身高175"}},
    ))
    time.sleep(2.0)

    p2a = [e for e in received if e.get("phase_id") == "phase_2a"]
    p2b = [e for e in received if e.get("phase_id") == "phase_2b"]
    assert len(p2a) == 1 and len(p2b) == 1
    assert p2a[0].get("inputs", {}).get("requirements") == "身高175"
    print("✅ phase_2a + phase_2b 并行触发（含前置输入）")

    # 模拟并行组完成
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test",
        data={"plan_id": "plan_bike_001", "phase_id": "phase_2a", "outputs": {"parts_list": ["A"]}},
    ))
    time.sleep(0.5)
    daemon.publish(Event(
        event_type=EventType.STAGE_COMPLETED,
        source="test",
        data={"plan_id": "plan_bike_001", "phase_id": "phase_2b", "outputs": {"inventory_status": {"A": 5}}},
    ))
    time.sleep(2.0)

    p3 = [e for e in received if e.get("phase_id") == "phase_3"]
    assert len(p3) == 1
    assert p3[0].get("inputs", {}).get("parts_list") == ["A"]
    assert p3[0].get("inputs", {}).get("inventory_status") == {"A": 5}
    print("✅ phase_3 被触发（合并并行组输出）")

    daemon.stop()
    EventBus.reset()

    print("\n" + "=" * 60)
    print("【最终结论】")
    print("=" * 60)
    print("✅ 组解析: PASS")
    print("✅ 输入合并: PASS")
    print("✅ 端到端事件流: PASS")
    print("\nV7.3 并行协调器验证通过！")
    return True


if __name__ == "__main__":
    run_test()
