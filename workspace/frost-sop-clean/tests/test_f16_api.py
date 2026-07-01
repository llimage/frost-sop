"""F16 FastAPI 端点验证脚本"""

import json
import urllib.request
import urllib.error

BASE = "http://localhost:8000/api"
passed = 0
failed = 0


def test(name, method="GET", path="", body=None):
    global passed, failed
    try:
        url = f"{BASE}{path}"
        data = json.dumps(body).encode("utf-8") if body else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json") if body else None
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read().decode())
        status = resp.status
        print(f"  PASS  [{name}] status={status}")
        passed += 1
        return result
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  FAIL  [{name}] HTTP {e.code}: {body[:200]}")
        failed += 1
        return None
    except Exception as e:
        print(f"  FAIL  [{name}] {e}")
        failed += 1
        return None


print("=" * 50)
print("F16 FastAPI Endpoint Verification")
print("=" * 50)

# 1. Health check
r = test("1. GET /api/health", path="/health")

# 2. List projects
r = test("2. GET /api/projects", path="/projects")
if r:
    print(f"     → {len(r)} projects")

# 3. Get single project
r = test("3. GET /api/projects/default", path="/projects/default")

# 4. Create and run task
r = test(
    "4. POST /api/tasks",
    method="POST",
    path="/tasks",
    body={
        "description": "F16 API测试任务",
        "sop_id": "DEV-001",
        "project_id": "default",
        "use_real_llm": False,
    },
)
task_id = r.get("task_id") if r else None
if r:
    print(
        f"     → task_id={task_id} status={r.get('status')} stages={len(r.get('stages', []))}"
    )

# 5. List tasks
r = test("5. GET /api/tasks", path="/tasks?limit=5")

# 6. Task stages
if task_id:
    test(f"6. GET /api/tasks/{task_id}/stages", path=f"/tasks/{task_id}/stages")
else:
    print("  SKIP  [6. task stages] no task_id")

# 7. Costs
r = test("7. GET /api/costs", path="/costs?month=2026-06")
if r:
    print(f"     → monthly_total={r.get('monthly_total')}")

# 8. Agents
r = test("8. GET /api/agents", path="/agents")

# 9. Chat
test(
    "9. POST /api/chat",
    method="POST",
    path="/chat",
    body={"message": "项目进展如何？请用中文回复", "use_real_llm": False},
)

# 10. Skills
r = test("10. GET /api/skills", path="/skills")

# 11. List schedules
r = test("11. GET /api/schedule", path="/schedule")

# 12. Create schedule
r = test(
    "12. POST /api/schedule",
    method="POST",
    path="/schedule",
    body={
        "title": "F16测试日程",
        "start_time": "2026-06-25T09:00:00",
        "end_time": "2026-06-25T10:00:00",
        "description": "API验证测试",
    },
)
if r:
    print(f"     → id={r.get('id')} title={r.get('title')}")

print()
print(f"{'=' * 50}")
print(f"RESULTS: {passed} passed / {failed} failed / {12} total")
print(f"{'=' * 50}")
