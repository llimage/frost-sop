"""
FROST-SOP V1.0 - Family AI Command Platform
Main entry point for the FROST-SOP system.
"""

import json
import uuid
import asyncio
import logging
import argparse
from datetime import datetime
from stores.constitution import create_constitution_store
from stores.asset import create_asset_store
from agents.ancestor import create_ancestor
from agents.parent import create_parent
from agents.elder import create_elder, subscribe_elder_to_events
from core.store import Store
from core.db import get_db

logger = logging.getLogger(__name__)


def main(task_input=None, sop_id=None):
    """Main execution flow."""
    if task_input is None:
        task_input = "Add user authentication feature to the project"
    if sop_id is None:
        sop_id = "DEV-001"

    sop_file = f"sops/templates/{sop_id}.yaml"

    print("=" * 60)
    print("FROST-SOP V1.0 - Family AI Command Platform")
    print("=" * 60)

    # 1. Create Stores
    print("\n[1] Initializing family Stores...")
    constitution_store = create_constitution_store()
    asset_store = create_asset_store()
    print("   Constitution Store created")
    print("   Asset Store created")

    # 2. Create Ancestor Agent
    print("\n[2] Creating Ancestor Agent...")
    ancestor = create_ancestor(constitution_store, asset_store)
    print("   Ancestor Agent ready")

    # V2.0: 创建长老并订阅事件总线（fail-safe，EventBus 不可用时优雅跳过）
    logger.info("[2.1] V2.0 Initializing Elder event subscription...")
    elder = create_elder("elder_main", asset_store=asset_store)
    if subscribe_elder_to_events(elder):
        logger.info("  [V2.0] 长老已订阅 TASK_COMPLETED 事件，审计将自动触发")
    else:
        logger.info("  [V2.0] 长老事件订阅跳过（EventBus 不可用，不影响主流程）")

    # 3. Receive task input
    print(f"\n[3] Task: {task_input}")
    print(f"   SOP: {sop_id}")

    # F14: Persist task to database
    db = get_db()
    task_id = f"task_{uuid.uuid4().hex[:12]}"

    # Ensure default project exists (required by FK constraint)
    existing_project = db.select_one("projects", "id", "default")
    if not existing_project:
        db.insert("projects", {
            "id": "default",
            "name": "默认项目",
            "status": "active",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        print("   [DB] Default project created")

    db.insert("tasks", {
        "id": task_id,
        "title": task_input[:100],
        "description": task_input,
        "project_id": "default",
        "status": "running",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    })
    print(f"   [DB] Task persisted: {task_id}")

    # 4. Ancestor LLM decomposes task
    print(f"\n[4] Ancestor decomposing task: {task_input}")
    context = ancestor.run(
        sop_steps=["call_llm"],
        initial_context={
            "_prompt": f"Analyze the following task, decompose into 1-3 parent agents, return JSON: {task_input}"
        }
    )
    llm_response = context.get("_llm_response", "")
    print(f"   Decomposition result: {llm_response}")

    # 5. Create parent and execute DEV-001
    print("\n[5] Creating Parent Agent and executing DEV-001 SOP...")
    coordination_store = Store()
    parent = create_parent("parent_dev", coordination_store)

    # 5.1 Load SOP template
    from core.sop import SOP
    sop = SOP.load_from_yaml(sop_file)
    print(f"   Loaded SOP: {sop.name} v{sop.version}")

    # F14: Ensure SOP template exists in DB (FK prerequisite for sop_executions)
    existing_sop_tpl = db.select_one("sop_templates", "id", sop.sop_id)
    if not existing_sop_tpl:
        db.insert("sop_templates", {
            "id": sop.sop_id,
            "sop_id": sop.sop_id,
            "name": sop.name,
            "version": sop.version,
            "content": json.dumps({"stages": sop.stages, "required_stages": sop.required_stages, "forbidden_skills": sop.forbidden_skills}),
            "is_preset": 1,
            "is_validated": 1,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        })
        print(f"   [DB] SOP template persisted: {sop.sop_id}")

    # F14: Log SOP execution start
    sop_exec_id = db.insert("sop_executions", {
        "task_id": task_id,
        "sop_template_id": sop.sop_id,
        "started_at": datetime.now().isoformat(),
        "status": "running",
        "total_stages": len(sop.stages),
        "completed_stages": 0,
    })
    print(f"   [DB] SOP execution logged: id={sop_exec_id}")

    # 5.2 Compliance validation (on preset SOP)
    compliance_rules = {
        "required_stages": ["审查交付"],
        "forbidden_skills": ["direct_db_write"],
        "max_budget": 300,
    }
    context = ancestor.run(
        sop_steps=["validate_sop"],
        initial_context={
            "_sop_to_validate": sop,
            "_compliance_rules": compliance_rules,
        }
    )
    validation = context.get("_validation_result", {})
    if validation.get("valid"):
        print(f"   Compliance check: [PASS] Passed")
    else:
        print(f"   Compliance check: [FAIL] Failed - {validation.get('errors', [])}")
        return

    # 5.4 父辈搜索替代SOP模板（验证外部探索能力）
    print("\n[5.4] 父辈搜索替代SOP模板...")
    from skills.search import search_sop_skill
    search_ctx = search_sop_skill.execute({
        "_search_query": sop_id,
        "_asset_store": asset_store,
        "_search_external": True,
    })
    search_results = search_ctx.get("_search_results", [])
    print(f"   搜索结果: 找到 {len(search_results)} 个SOP模板")
    for r in search_results:
        print(f"   - 来源: {r['source']}, SOP: {r.get('name', r.get('sop_id'))}")

    # 5.5 对外部搜索到的SOP进行合规校验
    if search_results and search_results[0]["source"] == "web":
        print("\n[5.5] 对外部搜索到的SOP进行合规校验...")
        from core.sop import SOP
        ext_data = search_results[0].get("content", {})
        if ext_data:
            external_sop = SOP(
                sop_id=ext_data.get("sop_id", "external_001"),
                name=ext_data.get("name", "外部SOP"),
                version=ext_data.get("version", "1.0"),
                stages=ext_data.get("stages", []),
                required_stages=ext_data.get("required_stages", []),
                forbidden_skills=ext_data.get("forbidden_skills", []),
            )
            from skills.orchestration import validate_sop_skill
            val_ctx = validate_sop_skill.execute({
                "_sop_to_validate": external_sop,
                "_compliance_rules": compliance_rules,
            })
            ext_val = val_ctx.get("_validation_result", {})
            if ext_val.get("valid"):
                print(f"   外部SOP合规校验: [PASS] 通过（可以加载使用）")
            else:
                print(f"   外部SOP合规校验: [FAIL] 失败 - {ext_val.get('errors', [])}")
                print(f"   拒绝加载，使用家族资产Store中的预置模板")

    # ================================================================
    # 5.3 父辈内化外部搜索到的 SOP（P3 核心验证）
    # ================================================================
    print("\n[5.3] 父辈内化搜索到的 SOP...")

    # 5.3.1 确定要内化的 SOP：优先使用外部搜索结果，否则用预置模板
    sop_to_internalize = None
    if search_results:
        external_result = search_results[0]
        print(
            f"   使用外部搜索结果: 来源={external_result['source']}, SOP={external_result.get('name', external_result.get('sop_id'))}")
        sop_to_internalize = external_result.get("content", {})

    if not sop_to_internalize or not sop_to_internalize.get("stages"):
        print(f"   外部搜索无有效结果，使用预置 {sop_id} 模板")
        sop_to_internalize = {
            "sop_id": sop_id,
            "name": sop.name,
            "version": sop.version,
            "stages": sop.stages,
            "required_stages": sop.required_stages,
            "forbidden_skills": sop.forbidden_skills,
        }

    # 5.3.2 调用 internalize_sop Skill
    int_context = parent.run(
        sop_steps=["internalize_sop"],
        initial_context={"_sop_to_internalize": sop_to_internalize}
    )
    internalized_steps = int_context.get("_internalized_steps", [])
    sop_stages_detail = int_context.get("_sop_stages", [])
    print(f"   内化结果: {len(internalized_steps)} 个阶段")
    for step in internalized_steps:
        print(f"   - {step}")

    # V2.0 P1-6: 发布 TASK_DECOMPOSED 事件（SOP 内化完成 = 任务分解完成）
    try:
        from core.event_bus import get_event_bus, Event, EventType
        bus = get_event_bus()
        bus.publish(Event(
            event_type=EventType.TASK_DECOMPOSED,
            source="main:task_decomposer",
            data={
                "task_id": task_id,
                "task_description": task_input,
                "sop_id": sop_id,
                "stage_count": len(sop_stages_detail),
                "stages": [s.get("name", f"阶段{i+1}") for i, s in enumerate(sop_stages_detail)],
            },
        ))
        logger.info("  📡 [V2.0] TASK_DECOMPOSED 事件已发布（%s个阶段）", len(sop_stages_detail))
    except Exception as e:
        logger.warning("  [V2.0] TASK_DECOMPOSED 发布失败（不影响流程）: %s", e)

    # ================================================================
    # 5.4 父辈按内化后的 SOP 真实执行各阶段（孙辈Agent执行）
    # ================================================================
    print("\n[5.4] 父辈按内化SOP执行各阶段（创建孙辈Agent）...")

    stage_context = {"_stage_results": [], "_parent_agent": parent, "_task_id": task_id}

    for i, stage in enumerate(sop_stages_detail):
        stage_name = stage.get("name", f"阶段{i+1}")
        stage_order = i + 1
        print(f"\n   --- 阶段 {stage_order}/{len(sop_stages_detail)}: {stage_name} ---")

        # F14: Record stage start in DB
        stage_db_id = db.insert("task_stages", {
            "task_id": task_id,
            "stage_name": stage_name,
            "stage_order": stage_order,
            "status": "running",
            "started_at": datetime.now().isoformat(),
        })

        stage_context["_current_stage"] = stage

        stage_context = parent.run(
            sop_steps=["execute_stage"],
            initial_context=stage_context
        )

        result = stage_context.get("_current_stage_result", {})
        child_gen = result.get("child_generation", "?")
        stage_status = result.get("status", "unknown")
        stage_output = str(result.get("output", ""))[:500]
        print(f"   孙辈Agent(gen={child_gen}): {result.get('agent', '未知')}")
        print(f"   状态: {stage_status}")
        print(f"   产出: {stage_output[:80]}...")

        # F14: Update stage result in DB
        db.update("task_stages", "id", stage_db_id, {
            "status": stage_status,
            "output": stage_output,
            "completed_at": datetime.now().isoformat(),
        })

        # F14: Update SOP execution progress
        db.update("sop_executions", "id", sop_exec_id, {
            "completed_stages": stage_order,
        })

        # 收割孙辈Store数据到父辈Store
        child_data = stage_context.get("_child_store_data", {})
        if child_data:
            for key, value in child_data.items():
                coordination_store.save(f"child_{stage_name}_{key}", value)

    # ================================================================
    # 5.5 父辈收割产出到资产Store
    # ================================================================
    print("\n[5.5] 父辈收割产出...")

    all_results = stage_context.get("_stage_results", [])
    asset_store.save("task:latest", {
        "task": task_input,
        "sop_source": search_results[0]["source"] if search_results else "preset",
        "sop_name": sop_to_internalize.get("name", "未知"),
        "stages_completed": len(all_results),
        "stage_results": all_results,
        "total_stages": len(sop_stages_detail),
    })
    print(f"   已收割 {len(all_results)} 个阶段的产出到资产Store")

    # F14: Mark task and SOP execution as completed in DB
    db.update("tasks", "id", task_id, {
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "result_summary": f"完成 {len(all_results)}/{len(sop_stages_detail)} 个阶段",
    })
    db.update("sop_executions", "id", sop_exec_id, {
        "status": "completed",
        "completed_at": datetime.now().isoformat(),
    })
    print(f"   [DB] Task {task_id} completed, all results persisted")

    # V2.0 阶段三：任务完成后触发长老自动审计（后台非阻塞）
    print("\n[5.6] V2.0 触发长老自动审计...")
    finalize_context = parent.run(
        sop_steps=["finalize_task"],
        initial_context={
            "_task_id": task_id,
            "_asset_store": asset_store,
            "_constitution_store": constitution_store,
            "_stage_results": all_results,
        }
    )
    if finalize_context.get("_elder_audit_triggered"):
        print(f"   [V2.0] 长老审计后台线程已启动")
    else:
        print(f"   [V2.0] 长老审计未触发: {finalize_context.get('_reason', '未知')}")

    # 6. Completion
    print("\n" + "=" * 60)
    print("FROST-SOP V1.0 Task Execution Complete")
    print("=" * 60)


# ============================================================
# V3.0: 异步事件驱动入口
# ============================================================

async def main_async(task_input: str = None, sop_id: str = None, timeout: int = 600):
    """
    V3.0 异步事件驱动入口。

    流程：
    1. 创建所有组件（ancestor/parent/elder）
    2. 注册所有事件订阅
    3. 发布 TASK_CREATED 事件
    4. 进入事件循环，等待 TASK_COMPLETED / TASK_FAILED / TASK_TIMEOUT

    Args:
        task_input: 任务描述
        sop_id: SOP 模板 ID
        timeout: 超时时间（秒，默认 600）
    """
    import asyncio
    from core.event_bus import get_async_event_bus, Event, EventType
    from agents.ancestor import create_ancestor
    from agents.parent import create_parent
    from agents.elder import create_elder, subscribe_elder_to_events
    from skills.orchestration import register_stage_executor

    if task_input is None:
        task_input = "Add user authentication feature to the project"
    if sop_id is None:
        sop_id = "DEV-001"

    logger.info("=" * 60)
    logger.info("FROST-SOP V3.0 - Async Event-Driven Mode")
    logger.info("=" * 60)

    # 1. 创建 Stores
    constitution_store = create_constitution_store()
    asset_store = create_asset_store()

    # 2. 获取 AsyncEventBus（不 reset，由调用方负责清理）
    bus = get_async_event_bus()

    # 3. 创建组件（event_driven=True）
    ancestor = create_ancestor(constitution_store, asset_store, event_driven=True)
    parent = create_parent("parent_v3", Store(), event_driven=True,
                           asset_store=asset_store, sop_id=sop_id)
    elder = create_elder("elder_v3", asset_store=asset_store)
    # V2.0 长老订阅（使用同步 EventBus，fail-safe）
    subscribe_elder_to_events(elder)

    # 4. 注册 execute_stage 事件订阅
    register_stage_executor(parent, asset_store)

    # 5. 等待终止事件
    task_done = asyncio.Event()
    final_status = {"status": None, "event": None}

    async def on_task_completed(event: Event):
        final_status["status"] = "completed"
        final_status["event"] = event
        task_done.set()

    async def on_task_failed(event: Event):
        final_status["status"] = "failed"
        final_status["event"] = event
        task_done.set()

    async def on_task_timeout(event: Event):
        final_status["status"] = "timeout"
        final_status["event"] = event
        task_done.set()

    bus.subscribe_async(EventType.TASK_COMPLETED, on_task_completed)
    bus.subscribe_async(EventType.TASK_FAILED, on_task_failed)
    bus.subscribe_async(EventType.TASK_TIMEOUT, on_task_timeout)

    # 6. 发布 TASK_CREATED
    task_id = f"task_v3_{uuid.uuid4().hex[:8]}"
    logger.info("[V3.0] 发布 TASK_CREATED: %s", task_id)

    await bus.publish(Event(
        event_type=EventType.TASK_CREATED,
        source="main:async_entry",
        data={
            "task_id": task_id,
            "task_description": task_input,
            "sop_id": sop_id,
        },
    ))

    # 7. 等待任务完成或超时
    try:
        await asyncio.wait_for(task_done.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        # 超时 → 发布 TASK_TIMEOUT（非 TASK_FAILED）
        logger.warning("[V3.0] 任务超时（%s秒），发布 TASK_TIMEOUT", timeout)
        await bus.publish(Event(
            event_type=EventType.TASK_TIMEOUT,
            source="main:async_entry",
            data={
                "task_id": task_id,
                "timeout_seconds": timeout,
            },
        ))
        final_status["status"] = "timeout"

    # 8. 输出结果
    logger.info("=" * 60)
    if final_status["status"] == "completed":
        event = final_status["event"]
        logger.info("[V3.0] 任务完成: %s (阶段: %s/%s)",
                    task_id,
                    event.data.get("stages_completed", "?"),
                    event.data.get("total_stages", "?"))
    elif final_status["status"] == "failed":
        event = final_status["event"]
        logger.error("[V3.0] 任务失败: %s — %s",
                     task_id, event.data.get("error", "unknown"))
    elif final_status["status"] == "timeout":
        logger.warning("[V3.0] 任务超时: %s (%s秒)", task_id, timeout)
    logger.info("=" * 60)

    return final_status["status"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FROST-SOP CLI")
    parser.add_argument("--task", type=str, default=None, help="Task description")
    parser.add_argument("--sop", type=str, default=None, help="SOP template ID (e.g. DEV-001)")
    parser.add_argument("--async-mode", action="store_true",
                        help="Use V3.0 async event-driven mode")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (async mode)")
    args = parser.parse_args()

    # 日志配置（覆盖同步和异步两种模式）
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

    if args.async_mode:
        # V3.0 异步事件驱动模式
        # CLI 入口负责重置 AsyncEventBus，确保干净状态
        from core.event_bus import AsyncEventBus
        AsyncEventBus.reset()
        asyncio.run(main_async(
            task_input=args.task,
            sop_id=args.sop,
            timeout=args.timeout,
        ))
    else:
        # V2.0 同步管道模式（默认）
        main(task_input=args.task, sop_id=args.sop)
