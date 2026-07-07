"""
FROST-SOP V7.4 — 父辈 Agent（ParentAgent）

父辈是战术规划者。

职责：
1. 接收祖辈的战略拆解（粗粒度计划）
2. 细化为可执行计划（识别哪些子任务可以并行）
3. 标记 parallel_group，定义阶段依赖
4. 将细化后的计划存入 Store，供府兵执行

PHILOSOPHY: 祖辈出方向，父辈出方案，府兵出执行。
三代同堂，各安其位。

祖辈（Grandparent）= 战略：做什么、为什么做
父辈（Parent）    = 战术：怎么做、谁来做、何时并行
府兵（Footman）   = 执行：做、报告、协同
"""

import json
import logging
import uuid

from core.skill import Skill
from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.store import Store
from skills.llm import call_llm

logger = logging.getLogger(__name__)


_PARENT_PLAN_REFINER_PROMPT = """你是一名战术规划专家。将以下战略级计划细化为可执行计划。

## 战略计划（祖辈拆解）

{grandparent_plan}

## 细化要求

1. 每个阶段必须有明确的 SOP ID（引用武器库中的已有武器）
2. 识别可以并行执行的阶段，标记相同的 parallel_group
3. 并行规则：
   - 同一 parallel_group 的阶段之间不能有依赖
   - 并行阶段各自产出独立结果，后续阶段合并使用
4. 输入参数使用模板语法：{{phase_id.outputs.key}}
5. 输出完整的可执行计划 JSON

## 输出格式

```json
{{
  "plan_id": "plan_xxx",
  "name": "计划名称",
  "refined_from": "祖辈计划ID",
  "phases": [
    {{
      "phase_id": "phase_1",
      "module": "模块名称",
      "sop_id": "SOP-XXX-001",
      "trigger": "immediate",
      "parallel_group": "可选：并行组ID",
      "inputs": {{}},
      "outputs": {{}},
      "depends_on": []
    }}
  ]
}}
```

## 并行场景示例

输入："自行车定制"
输出：
- phase_1: 需求解析（串行）
- phase_2a: 零部件拆解（parallel_group: "assembly"）
- phase_2b: 库存查询（parallel_group: "assembly"）
- phase_3: 报价生成（串行，依赖 2a 和 2b）

直接输出 JSON，不要其他说明。
"""


class ParentAgent:
    """
    父辈 Agent。

    不是硬编码的调度器，而是武器库中的一个"角色"。
    父辈本身也是府兵的一种，执行"计划细化"任务。

    使用方式：
        parent = ParentAgent(daemon, store)
        parent.refine_plan(grandparent_plan)  # 细化为可执行计划
        parent.start_execution(plan_id)       # 启动并行编排（调用 Skill）
    """

    def __init__(self, daemon: EventBusDaemon = None, store: Store = None):
        self.daemon = daemon or EventBusDaemon()
        self.store = store or Store()
        self._orchestrator_skill = parallel_orchestrator_skill

    def refine_plan(self, grandparent_plan: dict, context: dict = None) -> dict:
        """
        将祖辈的战略计划细化为可执行计划。

        这是父辈的核心能力：战术级拆解 + 并行识别。

        Args:
            grandparent_plan: 祖辈生成的粗粒度计划
            context: 额外上下文（预算、约束等）

        Returns:
            细化后的可执行计划
        """
        plan_json = json.dumps(grandparent_plan, ensure_ascii=False, indent=2)

        prompt = _PARENT_PLAN_REFINER_PROMPT.format(
            grandparent_plan=plan_json,
        )

        llm_context = call_llm({
            "_prompt": prompt,
            "_llm_profile": "execute",
            "_max_tokens": 2500,
        })

        response = llm_context.get("_llm_response", "").strip()

        # 解析 JSON
        refined_plan = _parse_refined_plan(response)
        if refined_plan is None:
            logger.error("[ParentAgent] 计划细化失败，无法解析 LLM 输出")
            return None

        # 生成 plan_id
        plan_id = refined_plan.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}")
        refined_plan["plan_id"] = plan_id
        refined_plan["_refined_by"] = "parent_agent"
        refined_plan["_llm_tokens"] = llm_context.get("_llm_tokens", {})

        # 存入 Store
        self.store.save(f"plan:{plan_id}", refined_plan)

        logger.info(
            "[ParentAgent] 计划细化完成: %s, %d 阶段",
            plan_id, len(refined_plan.get("phases", [])),
        )

        # 发布计划生成事件
        if self.daemon.is_running():
            self.daemon.publish(Event(
                event_type=EventType.PLAN_GENERATED,
                source="parent_agent",
                data={"plan_id": plan_id, "phases_count": len(refined_plan.get("phases", []))},
            ))

        return refined_plan

    def start_execution(self, plan_id: str):
        """
        启动计划执行。

        父辈不直接调度府兵，而是调用武器库中的并行编排 Skill。
        这符合"武器库统一配发"的哲学。

        Args:
            plan_id: 计划ID
        """
        plan = self.store.load(f"plan:{plan_id}")
        if not plan:
            logger.error("[ParentAgent] 计划不存在: %s", plan_id)
            return

        # 调用并行编排 Skill（武器库配发）
        logger.info("[ParentAgent] 启动执行: %s，调用并行编排器", plan_id)

        context = {
            "_plan": plan,
            "_plan_id": plan_id,
        }

        # 执行编排（这会触发事件总线上的阶段调度）
        self._orchestrator_skill.execute(context)

    def get_plan(self, plan_id: str) -> dict | None:
        """从 Store 读取计划。"""
        return self.store.load(f"plan:{plan_id}")


def _parse_refined_plan(response: str) -> dict | None:
    """解析 LLM 输出的细化计划。"""
    # 尝试提取 ```json ... ``` 块
    json_start = response.find("```json")
    if json_start >= 0:
        json_start = response.find("{", json_start)
        json_end = response.find("```", json_start)
        if json_end > json_start:
            try:
                return json.loads(response[json_start:json_end].strip())
            except json.JSONDecodeError:
                pass

    # 尝试直接找第一个 {
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        try:
            return json.loads(response[json_start:json_end])
        except json.JSONDecodeError:
            pass

    return None


def refine_plan_skill_fn(context: dict) -> dict:
    """
    Skill 入口：计划细化。

    输入 context:
        _grandparent_plan: dict — 祖辈的战略计划
        _constraints: list — 约束条件（可选）

    输出 context:
        _refined_plan: dict — 细化后的可执行计划
        _plan_id: str — 计划ID
    """
    grandparent_plan = context.get("_grandparent_plan")
    if not grandparent_plan:
        context["_refine_error"] = "缺少 _grandparent_plan"
        return context

    parent = ParentAgent()
    refined = parent.refine_plan(grandparent_plan, context)

    if refined:
        context["_refined_plan"] = refined
        context["_plan_id"] = refined["plan_id"]
    else:
        context["_refine_error"] = "计划细化失败"

    return context


# ──────────────────────────────────────────
# 武器库注册
# ──────────────────────────────────────────

plan_refiner_skill = Skill(
    "plan_refiner",
    refine_plan_skill_fn,
    required_keys=["_grandparent_plan"],
    output_schema={"_refined_plan": dict, "_plan_id": str},
    timeout_seconds=120,
)


# 并行编排 Skill（将 core/coordinator.py 的核心逻辑武器化）
def parallel_orchestrate_fn(context: dict) -> dict:
    """
    并行编排 Skill。

    武器库中的武器，负责解析 parallel_group 并调度事件。

    输入 context:
        _plan: dict — 细化后的计划（含 parallel_group）
        _plan_id: str — 计划ID

    输出 context:
        _execution_groups: dict — 执行组解析结果
    """
    plan = context.get("_plan")
    plan_id = context.get("_plan_id")
    if not plan or not plan_id:
        context["_orchestrate_error"] = "缺少 _plan 或 _plan_id"
        return context

    from core.coordinator import ParallelCoordinator

    # V7.4: ParallelCoordinator 是库，不是核心组件
    # 编排 Skill 自己管理事件总线
    daemon = EventBusDaemon()
    if not daemon.is_running():
        daemon.start()

    coordinator = ParallelCoordinator(store=Store())
    coordinator.load_plan(plan)

    # 触发入口组
    entry_groups = coordinator.get_entry_groups()
    for gid in entry_groups:
        group = coordinator.get_group(gid)
        # 为组内每个阶段发布触发事件
        for phase in group.phases:
            daemon.publish(Event(
                event_type=EventType.SCHEDULED_EXECUTED,
                source="parallel_orchestrator",
                data={
                    "plan_id": plan_id,
                    "phase_id": phase["phase_id"],
                    "inputs": {},
                    "coordinated": True,
                },
            ))

    # 订阅阶段完成事件，驱动后续组
    def _on_phase_completed(event: Event):
        if event.data.get("plan_id") != plan_id:
            return
        phase_id = event.data.get("phase_id")
        outputs = event.data.get("outputs", {})

        # 标记阶段完成，检查整组是否完成
        group_completed = coordinator.mark_group_phase_completed(phase_id, outputs)

        if group_completed:
            gid = coordinator.get_group_for_phase(phase_id)
            # 检查并触发后续组
            ready_groups = coordinator.get_ready_dependent_groups(gid)
            for ready_gid in ready_groups:
                ready_group = coordinator.get_group(ready_gid)
                group_inputs = coordinator.collect_group_inputs(ready_gid)
                for phase in ready_group.phases:
                    daemon.publish(Event(
                        event_type=EventType.SCHEDULED_EXECUTED,
                        source="parallel_orchestrator",
                        data={
                            "plan_id": plan_id,
                            "phase_id": phase["phase_id"],
                            "inputs": group_inputs,
                            "coordinated": True,
                        },
                    ))

    EventBus().subscribe(EventType.STAGE_COMPLETED, _on_phase_completed)

    context["_execution_groups"] = {
        gid: {
            "phases": [p["phase_id"] for p in g.phases],
            "depends_on": g.depends_on_groups,
        }
        for gid, g in coordinator._groups.items()
    }

    logger.info("[parallel_orchestrator] 计划 %s 已开始执行", plan_id)
    return context
    """
    并行编排 Skill。

    武器库中的武器，负责解析 parallel_group 并调度事件。

    输入 context:
        _plan: dict — 细化后的计划（含 parallel_group）
        _plan_id: str — 计划ID

    输出 context:
        _execution_groups: dict — 执行组解析结果
    """
    plan = context.get("_plan")
    plan_id = context.get("_plan_id")
    if not plan or not plan_id:
        context["_orchestrate_error"] = "缺少 _plan 或 _plan_id"
        return context

    from core.coordinator import ParallelCoordinator

    daemon = EventBusDaemon()
    if not daemon.is_running():
        daemon.start()

    coordinator = ParallelCoordinator(daemon=daemon)
    coordinator.load_plan(plan)
    coordinator.start_execution()

    context["_execution_groups"] = {
        gid: {
            "phases": [p["phase_id"] for p in g.phases],
            "depends_on": g.depends_on_groups,
        }
        for gid, g in coordinator._groups.items()
    }

    logger.info("[parallel_orchestrator] 计划 %s 已开始执行", plan_id)
    return context


parallel_orchestrator_skill = Skill(
    "parallel_orchestrator",
    parallel_orchestrate_fn,
    required_keys=["_plan", "_plan_id"],
    output_schema={"_execution_groups": dict},
    timeout_seconds=60,
)
