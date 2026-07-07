"""
测试脚本：府兵 Agent 端到端测试

验证府兵 Agent 的完整流程：
1. 读取计划
2. 从武器库配发武器
3. 执行武器
4. 发布阶段完成事件
"""

import sys
import time
import os

sys.path.insert(0, r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop')

# 加载 API Key（府兵执行 Skill 可能需要）
env_path = r'D:\my_ai\Solo-Ops-Platform\workspace\frost-sop\.env'
if os.path.exists(env_path):
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, val = line.split('=', 1)
                os.environ[key] = val

os.environ.pop('FROST_TESTING', None)

from core.store import Store
from core.armory import ArmoryRegistry
from core.armory_lifecycle import WeaponLoader, ArmoryDispatcher
from core.event_bus_daemon import EventBusDaemon
from core.event_bus import EventBus, EventType, Event
from agents.footman import FootmanAgent

print("=" * 60)
print("【阶段2测试】府兵 Agent 端到端")
print("=" * 60)

# 1. 创建 Store 并放入 mock 计划
store = Store()
mock_plan = {
    "plan_id": "test_plan_001",
    "name": "轻量化心理健康服务",
    "phases": [
        {
            "phase_id": "phase_1",
            "module": "计划",
            "inputs": {"task_description": "我要做轻量化心理健康服务"},
            "outputs": {},
        },
        {
            "phase_id": "phase_2",
            "module": "营销",
            "inputs": {"topic": "小红书获客"},
            "outputs": {},
        }
    ]
}
store.save("plan:test_plan_001", mock_plan)
print(f"\n[1] Mock 计划已保存: {mock_plan['plan_id']}, {len(mock_plan['phases'])} 个阶段")

# 2. 创建武器库，加载现有武器
registry = ArmoryRegistry(store=store)
loader = WeaponLoader(registry)

# 加载 skills 模块
loaded_modules = [
    ("skills.llm", "cognitive", ["LLM推理"]),
    ("skills.search", "search", ["搜索"]),
    ("skills.web_fetcher", "execution", ["网页抓取"]),
]

for module_name, category, scenarios in loaded_modules:
    from core.armory import WeaponCategory
    wc = getattr(WeaponCategory, category.upper(), WeaponCategory.UNKNOWN)
    weapon = loader.load_from_module(module_name, category=wc, scenarios=scenarios)
    if weapon:
        registry.register(weapon)
        print(f"   加载武器: {weapon.id} ({weapon.name})")
    else:
        print(f"   加载失败: {module_name}")

print(f"\n[2] 武器库: {len(registry._weapons)} 个武器")

# 3. 启动事件总线守护线程
print("\n[3] 启动 EventBusDaemon...")
daemon = EventBusDaemon()
daemon.start()
time.sleep(0.5)
print(f"   守护线程: running={daemon.is_running()}")

# 4. 订阅完成事件（验证府兵是否发布完成事件）
completed_events = []

def on_complete(event):
    completed_events.append(event.data)
    print(f"   [测试订阅者] 阶段完成: plan={event.data.get('plan_id')} phase={event.data.get('phase_id')}")

bus = EventBus()
bus.subscribe(EventType.STAGE_COMPLETED, on_complete)

# 5. 创建并启动府兵
print("\n[4] 启动 FootmanAgent...")
footman = FootmanAgent(registry, store, daemon)
footman.start()

# 6. 发布阶段触发事件（phase_1）
print("\n[5] 发布阶段触发: plan=test_plan_001 phase=phase_1...")
event = Event(
    event_type=EventType.SCHEDULED_EXECUTED,
    source="test",
    data={
        "job_type": "plan_phase",
        "plan_id": "test_plan_001",
        "phase_id": "phase_1",
        "immediate": True,
    }
)
daemon.publish(event)

time.sleep(2)

print(f"\n[6] 完成事件数: {len(completed_events)}")
for e in completed_events:
    print(f"   plan={e.get('plan_id')} phase={e.get('phase_id')}")
    outputs = e.get('outputs', {})
    print(f"   outputs keys: {list(outputs.keys())[:5]}")

# 7. 测试 phase_2（营销模块）
print("\n[7] 发布阶段触发: plan=test_plan_001 phase=phase_2...")
event2 = Event(
    event_type=EventType.SCHEDULED_EXECUTED,
    source="test",
    data={
        "job_type": "plan_phase",
        "plan_id": "test_plan_001",
        "phase_id": "phase_2",
        "immediate": True,
    }
)
daemon.publish(event2)

time.sleep(2)

print(f"\n[8] 总完成事件数: {len(completed_events)}")

# 8. 停止
print("\n[9] 停止...")
daemon.stop()
print(f"   守护线程: running={daemon.is_running()}")

# 结论
all_pass = (
    len(completed_events) == 2 and
    completed_events[0].get('plan_id') == 'test_plan_001' and
    completed_events[0].get('phase_id') == 'phase_1' and
    completed_events[1].get('phase_id') == 'phase_2'
)

print(f"\n{'='*60}")
print("【阶段2测试结论】")
print(f"{'='*60}")

if all_pass:
    print("✅ 全部通过:")
    print("   - 府兵读取计划成功")
    print("   - 从武器库配发武器成功")
    print("   - 执行武器（Skill + SOP）成功")
    print("   - 发布阶段完成事件成功")
    print("   - 两个阶段连续执行正常")
else:
    print("❌ 部分失败:")
    print(f"   完成事件数: {len(completed_events)}/2")
    if completed_events:
        for i, e in enumerate(completed_events):
            print(f"   事件{i}: plan={e.get('plan_id')} phase={e.get('phase_id')}")

print(f"\n武器库健康评分:")
for wid, w in registry._weapons.items():
    print(f"   {wid}: usage={w.usage_count} success={w.success_count} health={w.health_score}")

print(f"\n{'='*60}")
