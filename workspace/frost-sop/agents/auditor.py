"""
FROST-SOP V7.2 — 审计 Agent（Devil's Advocate）

在计划执行前，作为 "反派" 角色检查计划的漏洞：
- 逻辑矛盾（如依赖不存在）
- 资源冲突（如时间/预算超支）
- 风险遗漏（如未考虑法规风险）
- 假设错误（如 "用户会自动来"）

PHILOSOPHY: 审计不是找茬，是防止失败。最好的失败是在纸上失败。
"""

import json
import logging

from core.event_bus import Event, EventType
from core.event_bus import EventBus
from core.skill import Skill
from skills.llm import call_llm

logger = logging.getLogger(__name__)


_AUDITOR_PROMPT = """你是一名无情的产品审计师（Devil's Advocate）。
你的任务：找出以下商业计划中的致命漏洞，并给出致命性评级。

## 审计对象

计划ID: {plan_id}
计划名称: {plan_name}

## 计划阶段

{phases_text}

## CEO评估结果

风险等级: {risk_level}
GO/NO-GO: {go_no_go}

## 审计清单（必须逐项检查）

### 1. 逻辑矛盾检查
- 是否存在依赖不存在的阶段？
- 是否存在循环依赖？
- 输入输出是否匹配？（如 phase_2 需要 phase_1 的输出，但 phase_1 没有该输出）

### 2. 资源冲突检查
- 总时间需求是否超过可用时间？
- 总预算是否超过月度预算？
- 同一时间段是否有多个阶段需要执行？（当前版本都是 immediate，所以会串行，但需检查是否有矛盾）

### 3. 风险遗漏检查
- 是否遗漏了关键风险？（如法规、技术、市场）
- 是否有 fallback 方案？
- 失败后的止损点在哪里？

### 4. 假设错误检查
- 计划中是否有未验证的假设？（如 "用户会自动来"）
- 假设是否过于乐观？
- 是否有数据支撑？

### 5. 执行可行性检查
- 每个阶段的 SOP 是否已知？（如果 SOP 不存在，标记为风险）
- 每个阶段的武器是否已注册？（如果武器不存在，标记为风险）
- 府兵是否能执行？（如果府兵需要人工干预，标记为风险）

## 输出格式（严格JSON）

```json
{{
  "audit_id": "audit_xxx",
  "plan_id": "{plan_id}",
  "fatal_count": 0,
  "warning_count": 2,
  "issues": [
    {{
      "id": "issue_1",
      "category": "逻辑矛盾",
      "severity": "fatal|warning|info",
      "description": "具体问题描述",
      "impact": "如果发生，会导致什么后果",
      "fix": "如何修复"
    }}
  ],
  "verdict": "PASS|PASS_WITH_WARNINGS|BLOCKED",
  "summary": "一句话总结"
}}
```

verdict 规则：
- 无 fatal 问题 = PASS（如果无 warning 也是 PASS）
- 有 warning 但无 fatal = PASS_WITH_WARNINGS
- 有 fatal 问题 = BLOCKED

直接输出 JSON，不要其他说明。
"""


class AuditorAgent:
    """审计 Agent：检查计划漏洞。"""

    def __init__(self, daemon=None):
        self.daemon = daemon
        self._audit_history = []

    def start(self):
        """订阅 AUDIT_REQUESTED 事件。"""
        EventBus().subscribe(EventType.AUDIT_REQUESTED, self._on_audit_request)
        logger.info("审计 Agent 已启动，等待 AUDIT_REQUESTED 事件")

    def _on_audit_request(self, event: Event):
        """处理审计请求。"""
        plan_id = event.data.get("plan_id")
        plan = event.data.get("plan")
        assessment = event.data.get("assessment", {})

        if not plan or not plan_id:
            logger.warning("审计请求缺少 plan 或 plan_id")
            return

        result = self.audit(plan, assessment)

        # 发布审计结果
        if self.daemon:
            self.daemon.publish(Event(
                event_type=EventType.AUDIT_COMPLETED,
                data={
                    "plan_id": plan_id,
                    "audit_result": result,
                },
                source="AuditorAgent",
            ))

    def audit(self, plan: dict, assessment: dict = None) -> dict:
        """
        对计划进行审计。

        Args:
            plan: 结构化计划
            assessment: CEO评估结果（可选）

        Returns:
            审计结果 dict
        """
        plan_id = plan.get("plan_id", "unknown")
        plan_name = plan.get("name", "未命名计划")
        phases = plan.get("phases", [])

        # 构建阶段文本
        phases_text = ""
        for p in phases:
            phases_text += f"\n{p.get('phase_id')}: {p.get('module')} → {p.get('sop_id')}"
            deps = p.get("depends_on", [])
            if deps:
                phases_text += f" (依赖: {', '.join(deps)})"

        risk_level = assessment.get("risk_level", "未知") if assessment else "未评估"
        go_no_go = assessment.get("go_no_go", "未知") if assessment else "未评估"

        prompt = _AUDITOR_PROMPT.format(
            plan_id=plan_id,
            plan_name=plan_name,
            phases_text=phases_text,
            risk_level=risk_level,
            go_no_go=go_no_go,
        )

        llm_context = call_llm({
            "_prompt": prompt,
            "_llm_profile": "execute",
            "_max_tokens": 2000,
        })

        response = llm_context.get("_llm_response", "").strip()
        tokens = llm_context.get("_llm_tokens", {})

        result = _parse_audit_json(response)
        if result is None:
            # LLM 输出无效，手动构建一个审计结果
            result = {
                "audit_id": f"audit_{plan_id}",
                "plan_id": plan_id,
                "fatal_count": 0,
                "warning_count": 1,
                "issues": [{
                    "id": "issue_0",
                    "category": "系统",
                    "severity": "warning",
                    "description": "审计 LLM 输出解析失败，无法自动审计",
                    "impact": "需要人工审计",
                    "fix": "检查 LLM 输出格式",
                }],
                "verdict": "PASS_WITH_WARNINGS",
                "summary": "审计 LLM 输出解析失败，建议人工复查",
            }
            result["_raw_response"] = response

        result["_tokens"] = tokens
        result["_cost_cny"] = tokens.get("total", 0) * 0.0015

        self._audit_history.append(result)

        logger.info(
            "审计完成: %s, verdict=%s, fatal=%d, warning=%d, cost=¥%.2f",
            plan_id, result["verdict"], result["fatal_count"], result["warning_count"], result["_cost_cny"],
        )

        return result

    def get_history(self) -> list:
        """返回审计历史。"""
        return self._audit_history.copy()


def _parse_audit_json(response: str) -> dict | None:
    """从 LLM 响应中提取 JSON 审计结果。"""
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


def run_audit(context: dict) -> dict:
    """
    Skill 入口：对计划进行审计。

    输入 context:
        _plan: dict — 计划（必须）
        _assessment: dict — CEO评估（可选）

    输出 context:
        _audit_result: dict — 审计结果
        _audit_verdict: str — PASS | PASS_WITH_WARNINGS | BLOCKED
    """
    plan = context.get("_plan")
    if not plan:
        context["_audit_error"] = "缺少 _plan"
        return context

    assessment = context.get("_assessment")
    agent = AuditorAgent()
    result = agent.audit(plan, assessment)

    context["_audit_result"] = result
    context["_audit_verdict"] = result.get("verdict", "PASS_WITH_WARNINGS")

    return context


auditor_skill = Skill(
    "auditor",
    run_audit,
    required_keys=["_plan"],
    output_schema={
        "_audit_result": dict,
        "_audit_verdict": str,
    },
    timeout_seconds=120,
)
