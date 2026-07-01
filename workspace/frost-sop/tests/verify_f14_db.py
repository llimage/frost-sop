"""F14 Acceptance: Database verification script.
Usage: python tests/verify_f14_db.py [--search STR]
If --search is provided, filters by task description containing that string.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from core.db import get_db


def main(search_term=None):
    db = get_db()

    # Build WHERE clause for filtering
    if search_term:
        task_filter = f"WHERE description LIKE '%{search_term}%'"
    else:
        task_filter = ""

    print("=" * 60)
    print("F14 持久化验收 - 数据库验证")
    print("=" * 60)

    # Step 3: tasks table
    print("\n[Step 3] tasks 表最新记录:")
    rows = db.query(
        f"SELECT id, project_id, sop_id, description, status, created_at FROM tasks {task_filter} ORDER BY created_at DESC LIMIT 3"
    )
    for r in rows:
        print(
            f"  id={r['id']}, project={r['project_id']}, status={r['status']}, created={r['created_at']}"
        )
        print(f"  desc={r['description'][:80]}")
    print(f"  => 匹配任务数: {len(rows)}")

    if rows:
        task_id = rows[0]["id"]
    else:
        print("  ❌ 未找到匹配任务！")
        return False

    # Step 4: task_stages
    print(f"\n[Step 4] task_stages (task_id={task_id}):")
    stages = db.query(
        f"SELECT stage_name, stage_order, status, started_at, completed_at FROM task_stages WHERE task_id='{task_id}' ORDER BY stage_order"
    )
    for s in stages:
        print(f"  [{s['status']}] stage {s['stage_order']}: {s['stage_name']}")
    print(f"  => 共 {len(stages)} 条阶段记录")
    if len(stages) < 3:
        print("  ⚠️ 阶段数少于预期（至少应有3个阶段）")

    # Step 5: agents (孙辈)
    print("\n[Step 5] agents 表孙辈记录 (最近):")
    agents = db.query(
        "SELECT name, agent_type, generation, status, created_at FROM agents ORDER BY created_at DESC LIMIT 10"
    )
    gen2_count = 0
    for a in agents:
        print(f"  [{a['generation']}] {a['name']} ({a['agent_type']}) - {a['status']}")
        if a["generation"] == 2:
            gen2_count += 1
    print(f"  => 最近孙辈(generation=2) Agent 数: {gen2_count}")

    # Step 6: cost_log
    print(f"\n[Step 6] cost_log (task_id={task_id}):")
    costs = db.query(
        f"SELECT agent_id, task_id, model, tokens, cost FROM cost_log WHERE task_id='{task_id}' LIMIT 5"
    )
    valid_count = 0
    for c in costs:
        is_valid = c["agent_id"] not in ("unknown", None, "") and c["cost"] > 0
        if is_valid:
            valid_count += 1
        print(
            f"  agent={c['agent_id']}, model={c['model']}, tokens={c['tokens']}, cost={c['cost']:.4f} {'✅' if is_valid else '❌'}"
        )
    print(f"  => 有效 cost_log 记录数: {valid_count}/{len(costs)}")

    # Step 7: sop_executions
    print(f"\n[Step 7] sop_executions (task_id={task_id}):")
    execs = db.query(
        f"SELECT task_id, sop_id, sop_template_id, status, started_at, completed_at, total_stages, completed_stages FROM sop_executions WHERE task_id='{task_id}'"
    )
    for e in execs:
        print(
            f"  sop={e.get('sop_id') or e.get('sop_template_id')}, status={e['status']}, stages={e['completed_stages']}/{e['total_stages']}"
        )
    print(f"  => 共 {len(execs)} 条执行记录")

    # Summary
    print("\n" + "=" * 60)
    print("验收总结:")
    checks = {
        "Tasks 表有新记录": len(rows) > 0,
        "Task Stages >= 3": len(stages) >= 3,
        "孙辈 Agent (gen2) >= 1": gen2_count >= 1,
        "Cost Log 有效": valid_count > 0,
        "SOP Execution 记录": len(execs) > 0,
    }
    for check, passed in checks.items():
        print(f"  {'✅' if passed else '❌'} {check}")

    all_passed = all(checks.values())
    print(f"\n{'全部通过!' if all_passed else '存在问题，请检查!'}")
    return all_passed


if __name__ == "__main__":
    search = None
    if len(sys.argv) > 2 and sys.argv[1] == "--search":
        search = sys.argv[2]
    main(search_term=search)
