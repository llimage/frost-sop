"""
FROST-SOP V7.3 — 计划生成器（支持并行组）

将业务需求拆解为结构化计划（JSON），支持并行阶段。

PHILOSOPHY: 拆解不是自由发挥，是标准化流程。
并行不是可选优化，是必要能力（如交付+库存并行查询）。
"""

import json
import logging
import uuid

from core.skill import Skill
from skills.llm import call_llm

logger = logging.getLogger(__name__)


_PLAN_GENERATOR_PROMPT = """你是一名系统架构师，将以下任务需求拆解为可执行的阶段计划。

任务描述：{task}
业务类型：{business_type}
月度预算：¥{budget}
约束条件：{constraints}

## 拆解原则（必须遵守）

1. 每个阶段必须包含明确的 SOP 模板ID（假设存在）
2. 依赖关系不能形成循环
3. 当前版本所有 trigger 必须是 "immediate"
4. 阶段之间可以并行执行的，必须标记相同的 parallel_group

## 并行组 (parallel_group) 规则

- 同 parallel_group 的阶段 = 并行执行（多个府兵同时工作）
- 无 parallel_group 的阶段 = 串行执行（独占一组）
- 一个阶段可以依赖多个前置阶段（depends_on 为列表）
- 并行组内的阶段之间不能有相互依赖

## 并行场景示例

例1（自行车定制）：
  phase_1: 需求解析 → 无 parallel_group
  phase_2a: 交付拆解 → parallel_group: "parallel_1", depends_on: ["phase_1"]
  phase_2b: 库存查询 → parallel_group: "parallel_1", depends_on: ["phase_1"]
  phase_3: 报价生成 → 无 parallel_group, depends_on: ["phase_2a", "phase_2b"]

例2（商业闭环）：
  phase_1: 市场调研 → 无 parallel_group
  phase_2a: 产品设计 → parallel_group: "parallel_1", depends_on: ["phase_1"]
  phase_2b: 竞品分析 → parallel_group: "parallel_1", depends_on: ["phase_1"]
  phase_3: 定价策略 → 无 parallel_group, depends_on: ["phase_2a", "phase_2b"]

## 输出格式（严格 JSON）

```json
{{
  "plan_id": "plan_xxx",
  "name": "任务名称",
  "phases": [
    {{
      "phase_id": "phase_1",
      "module": "需求解析",
      "sop_id": "SOP-REQ-001",
      "trigger": "immediate",
      "inputs": {{"task_description": "..."}},
      "outputs": {{}},
      "depends_on": []
    }},
    {{
      "phase_id": "phase_2a",
      "module": "交付拆解",
      "sop_id": "SOP-DEL-001",
      "trigger": "immediate",
      "parallel_group": "parallel_1",
      "inputs": {{"requirements": "{{phase_1.outputs.requirements}}"}},
      "outputs": {{}},
      "depends_on": ["phase_1"]
    }},
    {{
      "phase_id": "phase_2b",
      "module": "库存查询",
      "sop_id": "SOP-INV-001",
      "trigger": "immediate",
      "parallel_group": "parallel_1",
      "inputs": {{"requirements": "{{phase_1.outputs.requirements}}"}},
      "outputs": {{}},
      "depends_on": ["phase_1"]
    }},
    {{
      "phase_id": "phase_3",
      "module": "报价生成",
      "sop_id": "SOP-QUO-001",
      "trigger": "immediate",
      "inputs": {{
        "parts_list": "{{phase_2a.outputs.parts_list}}",
        "inventory_status": "{{phase_2b.outputs.inventory_status}}"
      }},
      "outputs": {{}},
      "depends_on": ["phase_2a", "phase_2b"]
    }}
  ]
}}
```

## 注意事项

- module 名称自由定义，描述该阶段做什么即可
- 输入参数中的模板变量（如 {{phase_1.outputs.requirements}}）由府兵运行时替换
- parallel_group 命名建议：parallel_1, parallel_2, ... 或语义化名称
- 直接输出 JSON，不要任何其他说明文字
"""


def generate_plan(context: dict) -> dict:
    """
    将任务描述拆解为结构化计划（支持并行组）。

    输入 context:
        _task_description: str — 任务描述（必须）
        _business_type: str — 业务类型（默认：一人公司）
        _budget_cny: float — 月度预算（默认：1000）
        _constraints: list — 约束条件（可选）

    输出 context:
        _plan: dict — 结构化计划
        _plan_id: str — 计划ID
        _plan_name: str — 计划名称
    """
    task = context.get("_task_description", "")
    if not task:
        context["_plan_error"] = "缺少必需输入: _task_description"
        return context

    business_type = context.get("_business_type", "一人公司")
    budget = context.get("_budget_cny", 1000)
    constraints = context.get("_constraints", [])
    constraints_str = "\n".join(f"- {c}" for c in constraints) if constraints else "无"

    prompt = _PLAN_GENERATOR_PROMPT.format(
        task=task,
        business_type=business_type,
        budget=budget,
        constraints=constraints_str,
    )

    # 调用 LLM
    llm_context = call_llm({
        "_prompt": prompt,
        "_llm_profile": "execute",
        "_max_tokens": 2500,
    })

    response = llm_context.get("_llm_response", "").strip()
    tokens = llm_context.get("_llm_tokens", {})

    # 解析 JSON
    plan = _parse_plan_json(response)
    if plan is None:
        context["_plan_error"] = "JSON 解析失败"
        context["_plan_raw_response"] = response
        context["_plan_llm_tokens"] = tokens
        return context

    # 验证计划结构
    validation_error = _validate_plan(plan)
    if validation_error:
        context["_plan_error"] = validation_error
        context["_plan_raw_response"] = response
        context["_plan_llm_tokens"] = tokens
        return context

    # 生成 plan_id（如果 LLM 没生成）
    plan_id = plan.get("plan_id", f"plan_{uuid.uuid4().hex[:8]}")
    plan["plan_id"] = plan_id

    # 输出
    context["_plan"] = plan
    context["_plan_id"] = plan_id
    context["_plan_name"] = plan.get("name", "未命名计划")
    context["_plan_llm_tokens"] = tokens

    # 统计并行组
    groups = set()
    for p in plan.get("phases", []):
        if "parallel_group" in p:
            groups.add(p["parallel_group"])

    logger.info(
        "计划生成成功: %s (%s), %d 阶段, %d 并行组, tokens=%s",
        plan_id, context["_plan_name"], len(plan.get("phases", [])), len(groups), tokens,
    )

    return context


def _parse_plan_json(response: str) -> dict | None:
    """从 LLM 响应中提取 JSON 计划。"""
    # 尝试提取 ```json ... ``` 块
    json_start = response.find("```json")
    if json_start >= 0:
        json_start = response.find("{", json_start)
        json_end = response.find("```", json_start)
        if json_end > json_start:
            json_str = response[json_start:json_end].strip()
            try:
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass

    # 尝试直接找第一个 {
    json_start = response.find("{")
    json_end = response.rfind("}") + 1
    if json_start >= 0 and json_end > json_start:
        json_str = response[json_start:json_end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 尝试直接解析整个响应
    try:
        return json.loads(response)
    except json.JSONDecodeError:
        pass

    return None


def _validate_plan(plan: dict) -> str | None:
    """验证计划结构。返回错误信息或 None。"""
    if not isinstance(plan, dict):
        return "计划不是 dict 类型"

    if "phases" not in plan:
        return "缺少 phases 字段"

    phases = plan.get("phases", [])
    if not isinstance(phases, list):
        return "phases 必须是列表"

    if len(phases) == 0:
        return "phases 为空"

    phase_ids = set()
    dependencies = set()
    group_phases = {}  # parallel_group -> [phase_ids]

    for i, phase in enumerate(phases):
        if not isinstance(phase, dict):
            return f"阶段 {i} 不是 dict"

        pid = phase.get("phase_id")
        if not pid:
            return f"阶段 {i} 缺少 phase_id"

        if pid in phase_ids:
            return f"重复的 phase_id: {pid}"
        phase_ids.add(pid)

        module = phase.get("module")
        if not module or not isinstance(module, str):
            return f"阶段 {pid} 的 module 无效"

        trigger = phase.get("trigger", "")
        if trigger != "immediate":
            if not trigger.startswith("cron:"):
                return f"阶段 {pid} 的 trigger 无效: {trigger}"

        # 收集并行组
        pg = phase.get("parallel_group")
        if pg:
            if pg not in group_phases:
                group_phases[pg] = []
            group_phases[pg].append(pid)

        # 收集依赖
        deps = phase.get("depends_on", [])
        if isinstance(deps, list):
            for dep in deps:
                dependencies.add((pid, dep))

    # 检查依赖是否存在
    for pid, dep in dependencies:
        if dep not in phase_ids:
            return f"阶段 {pid} 依赖不存在的阶段: {dep}"

    # 检查循环依赖（简化：只检查是否有自依赖）
    for pid, dep in dependencies:
        if pid == dep:
            return f"阶段 {pid} 自依赖"

    # 检查并行组内是否有相互依赖
    for gid, pids in group_phases.items():
        for pid in pids:
            for dep_pid, dep in dependencies:
                if dep_pid == pid and dep in pids and dep != pid:
                    return f"并行组 '{gid}' 内阶段 {pid} 依赖同组阶段 {dep}（并行组内不能有依赖）"

    return None


plan_generator_skill = Skill(
    "plan_generator",
    generate_plan,
    required_keys=["_task_description"],
    output_schema={"_plan": dict, "_plan_id": str},
    timeout_seconds=120,
)
