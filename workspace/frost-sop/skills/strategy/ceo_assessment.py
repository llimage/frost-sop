"""
FROST-SOP V7.2 — CEO 评估技能

在计划生成后、执行前，评估资源/法规/竞争/退出路径。
用5个战略问题的答案作为评估依据，不依赖假设。

PHILOSOPHY: 评估不是锦上添花，是必选项。不评估就执行 = 盲目。
"""

import json
import logging

from core.skill import Skill
from skills.llm import call_llm

logger = logging.getLogger(__name__)


_CEO_ASSESSMENT_PROMPT = """你是一名资深 CEO 顾问，评估以下商业计划的可行性。

## 评估依据（5个战略问题的答案）

{intake_answers}

## 商业计划概述

{plan_summary}

## 月度预算

¥{budget}

## 评估框架（必须逐项回答）

### 1. 资源充足度评估
- 当前技能是否足够支撑生产模块？
- 时间投入是否足够？（小于40小时/月 = 严重不足）
- 预算是否足够覆盖最低启动成本？

### 2. 法规合规检查
- 该业务是否需要特殊资质？（如心理咨询需要执照）
- 是否存在内容审查风险？
- 数据隐私要求？（GDPR/个保法）

### 3. 竞争格局分析
- 市场上已有多少同类服务？
- 差异化优势是什么？（如果没有，标记为高风险）
- 替代方案是什么？（用户不选你的理由）

### 4. 退出路径分析
- 如果3个月后没有收入，备选方案是什么？
- 沉没成本是否可接受？
- 技能是否可以转移到其他项目？

### 5. 总体风险评级
- 综合1-4，给出风险评级：低/中/高/极高
- 如果是高或极高，必须给出具体的降低风险建议

## 输出格式（严格JSON）

```json
{{
  "assessment_id": "ceo_xxx",
  "plan_id": "{plan_id}",
  "risk_level": "中",
  "dimensions": {{
    "resource": {{
      "score": 7,
      "max": 10,
      "assessment": "...",
      "concerns": ["..."]
    }},
    "regulation": {{
      "score": 8,
      "max": 10,
      "assessment": "...",
      "concerns": []
    }},
    "competition": {{
      "score": 5,
      "max": 10,
      "assessment": "...",
      "concerns": ["..."]
    }},
    "exit_path": {{
      "score": 6,
      "max": 10,
      "assessment": "...",
      "concerns": ["..."]
    }}
  }},
  "recommendations": [
    "具体建议1",
    "具体建议2"
  ],
  "go_no_go": "GO"
}}
```

评分规则：
- 8-10分 = 绿色（可行）
- 5-7分 = 黄色（有条件可行）
- 0-4分 = 红色（高风险）

go_no_go 规则：
- 所有维度 >= 6 分 = GO
- 任一维度 < 4 分 = NO-GO
- 否则 = CONDITIONAL（需要完成建议后才能继续）

直接输出 JSON，不要其他说明。
"""


def assess_plan(context: dict) -> dict:
    """
    CEO 评估：在计划执行前评估可行性。

    输入 context:
        _plan: dict — 结构化计划（必须）
        _plan_id: str — 计划ID（必须）
        _intake_answers: dict — 需求澄清答案（可选）
        _budget_cny: float — 预算（默认1000）

    输出 context:
        _assessment: dict — 评估结果
        _risk_level: str — 风险等级
        _go_no_go: str — GO / NO-GO / CONDITIONAL
    """
    plan = context.get("_plan")
    plan_id = context.get("_plan_id")
    if not plan or not plan_id:
        context["_assessment_error"] = "缺少 _plan 或 _plan_id"
        return context

    # 组装计划摘要
    plan_summary = f"计划名称: {plan.get('name', '未命名')}\n"
    plan_summary += f"阶段数: {len(plan.get('phases', []))}\n"
    for p in plan.get("phases", []):
        plan_summary += f"- {p.get('phase_id')}: {p.get('module')} → {p.get('sop_id')}\n"

    # 需求澄清答案
    intake = context.get("_intake_answers", {})
    if intake:
        intake_lines = []
        for qid, ans in intake.items():
            intake_lines.append(f"{qid}: {ans}")
        intake_answers = "\n".join(intake_lines)
    else:
        intake_answers = "未提供需求澄清答案（基于假设进行评估）"

    budget = context.get("_budget_cny", 1000)

    prompt = _CEO_ASSESSMENT_PROMPT.format(
        plan_id=plan_id,
        plan_summary=plan_summary,
        intake_answers=intake_answers,
        budget=budget,
    )

    llm_context = call_llm({
        "_prompt": prompt,
        "_llm_profile": "execute",
        "_max_tokens": 2000,
    })

    response = llm_context.get("_llm_response", "").strip()
    tokens = llm_context.get("_llm_tokens", {})

    assessment = _parse_assessment_json(response)
    if assessment is None:
        context["_assessment_error"] = "评估 JSON 解析失败"
        context["_assessment_raw_response"] = response
        context["_assessment_llm_tokens"] = tokens
        return context

    # 提取关键字段
    risk_level = assessment.get("risk_level", "未知")
    go_no_go = assessment.get("go_no_go", "CONDITIONAL")

    # 验证 go_no_go 与评分一致性
    dims = assessment.get("dimensions", {})
    scores = []
    for dim_name, dim_data in dims.items():
        if isinstance(dim_data, dict):
            score = dim_data.get("score", 0)
            scores.append(score)

    if scores:
        min_score = min(scores)
        # 自动修正不一致的 go_no_go
        if min_score < 4 and go_no_go != "NO-GO":
            logger.warning("评分显示最低分 %d < 4，但 go_no_go 为 %s，自动修正", min_score, go_no_go)
            go_no_go = "NO-GO"
            assessment["go_no_go"] = go_no_go
        elif all(s >= 6 for s in scores) and go_no_go != "GO":
            logger.warning("所有评分 >= 6，但 go_no_go 为 %s，自动修正", go_no_go)
            go_no_go = "GO"
            assessment["go_no_go"] = go_no_go

    context["_assessment"] = assessment
    context["_risk_level"] = risk_level
    context["_go_no_go"] = go_no_go
    context["_assessment_llm_tokens"] = tokens

    logger.info(
        "CEO评估完成: %s, risk=%s, go_no_go=%s, tokens=%s",
        plan_id, risk_level, go_no_go, tokens,
    )

    return context


def _parse_assessment_json(response: str) -> dict | None:
    """从 LLM 响应中提取 JSON 评估结果。"""
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


ceo_assessment_skill = Skill(
    "ceo_assessment",
    assess_plan,
    required_keys=["_plan", "_plan_id"],
    output_schema={
        "_assessment": dict,
        "_risk_level": str,
        "_go_no_go": str,
    },
    timeout_seconds=120,
)
