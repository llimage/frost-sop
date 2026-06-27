"""
调试：audit_family 数据读取问题
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import Store, HierarchicalStore
from agents.elder import audit_family_skill

# 创建测试数据
own_store = Store()
own_store.save("task:test-001", {"status": "completed", "stage_results": []})
own_store.save("task:test-002", {"status": "failed", "stage_results": [{"status": "failed"}]})
own_store.save("lesson:test-001", {"error_type": "test"})

parent_store = Store()
parent_store.save("task:test-003", {"status": "completed", "stage_results": []})

# 测试1：普通Store
print("=" * 60)
print("测试1：普通Store")
store1 = Store()
store1.save("task:t1", {"status": "completed", "stage_results": []})
store1.save("task:t2", {"status": "completed", "stage_results": []})
context1 = {"_asset_store": store1}
result1 = audit_family_skill.execute(context1)
report1 = result1.get("_audit_report", {})
print(f"total_tasks: {report1.get('statistics', {}).get('total_tasks', 'N/A')}")

# 测试2：HierarchicalStore
print("=" * 60)
print("测试2：HierarchicalStore")
h_store = HierarchicalStore(own_store=own_store, parent=parent_store)
context2 = {"_asset_store": h_store}
result2 = audit_family_skill.execute(context2)
report2 = result2.get("_audit_report", {})
print(f"total_tasks: {report2.get('statistics', {}).get('total_tasks', 'N/A')}")
print(f"own_store keys: {own_store.list_keys()}")
print(f"parent_store keys: {parent_store.list_keys()}")
print(f"h_store.list_keys(): {h_store.list_keys()}")

# 测试3：验证list_keys行为
print("=" * 60)
print("测试3：直接调用list_keys")
print(f"store1.list_keys(): {store1.list_keys()}")
print(f"  task: 前缀键数: {len([k for k in store1.list_keys() if k.startswith('task:')])}")
