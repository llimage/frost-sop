"""
FROST-SOP V7.2 — 教训归档技能（Lesson Archivist）

在府兵执行完成后，自动记录：
- 执行结果（成功/失败）
- 失败原因（如果失败）
- 改进建议（LLM 生成）
- 关联的计划ID和阶段ID

PHILOSOPHY: 不从失败中学习 = 重复失败。教训是系统的记忆。
"""

import json
import logging
import uuid
from datetime import datetime

from core.skill import Skill
from core.store import Store
from skills.llm import call_llm

logger = logging.getLogger(__name__)

# 全局 store 实例（供教训归档使用）
_global_store = Store()


_LESSON_ARCHIVIST_PROMPT = """你是一名复盘教练。基于以下执行记录，生成结构化教训。

## 执行记录

计划ID: {plan_id}
阶段ID: {phase_id}
模块: {module}
SOP: {sop_id}

执行结果: {status}
输出摘要: {outputs}

## 复盘问题（必须回答）

1. 如果失败：根本原因是什么？（技术/资源/假设/外部）
2. 如果成功：哪些因素可复制到下次？
3. 计划本身是否有缺陷？（SOP 不合理、依赖缺失、预算不足）
4. 如果重来一次，你会怎么改进？

## 输出格式（严格JSON）

```json
{{
  "lesson_id": "lesson_xxx",
  "plan_id": "{plan_id}",
  "phase_id": "{phase_id}",
  "severity": "critical|major|minor|info",
  "category": "技术|资源|假设|SOP|外部|未知",
  "root_cause": "根本原因描述",
  "actionable_fix": "具体可执行的改进建议",
  "preventable": true,
  "applicable_to_future": "这个教训适用于什么类型的未来计划"
}}
```

directive:
- 如果 status 为 "success"，severity 通常为 "info" 或 "minor"
- 如果 status 为 "failed"，severity 至少为 "major"
- actionable_fix 必须是具体可执行的动作，不是抽象建议
- applicable_to_future 帮助系统在生成新计划时检索相关教训

直接输出 JSON，不要其他说明。
"""


def archive_lesson(context: dict) -> dict:
    """
    归档执行教训。

    输入 context:
        _plan_id: str — 计划ID（必须）
        _phase_id: str — 阶段ID（必须）
        _module: str — 模块名称
        _sop_id: str — SOP ID
        _execution_status: str — "success" | "failed" | "partial"
        _outputs: dict — 执行输出摘要
        _error: str — 错误信息（如果失败）

    输出 context:
        _lesson_id: str — 教训ID
        _lesson: dict — 结构化教训
    """
    plan_id = context.get("_plan_id")
    phase_id = context.get("_phase_id")
    module = context.get("_module", "未知")
    sop_id = context.get("_sop_id", "未知")
    status = context.get("_execution_status", "unknown")
    outputs = context.get("_outputs", {})
    error = context.get("_error", "")

    if not plan_id or not phase_id:
        context["_lesson_error"] = "缺少 _plan_id 或 _phase_id"
        return context

    # 构建输出摘要文本
    outputs_text = json.dumps(outputs, ensure_ascii=False, indent=2) if outputs else "无输出"
    if error:
        outputs_text += f"\n\n错误信息: {error}"

    prompt = _LESSON_ARCHIVIST_PROMPT.format(
        plan_id=plan_id,
        phase_id=phase_id,
        module=module,
        sop_id=sop_id,
        status=status,
        outputs=outputs_text,
    )

    llm_context = call_llm({
        "_prompt": prompt,
        "_llm_profile": "execute",
        "_max_tokens": 1000,
    })

    response = llm_context.get("_llm_response", "").strip()
    tokens = llm_context.get("_llm_tokens", {})

    lesson = _parse_lesson_json(response)
    if lesson is None:
        # 解析失败，手动构造基础教训
        lesson_id = f"lesson_{uuid.uuid4().hex[:8]}"
        lesson = {
            "lesson_id": lesson_id,
            "plan_id": plan_id,
            "phase_id": phase_id,
            "severity": "major" if status == "failed" else "info",
            "category": "未知",
            "root_cause": f"LLM 解析失败，原始状态: {status}",
            "actionable_fix": "检查 lesson_archivist 的 LLM 输出格式",
            "preventable": False,
            "applicable_to_future": "所有计划",
            "_raw_response": response,
        }
    else:
        lesson_id = lesson.get("lesson_id", f"lesson_{uuid.uuid4().hex[:8]}")
        lesson["lesson_id"] = lesson_id

    # 添加元数据
    lesson["_archived_at"] = datetime.now().isoformat()
    lesson["_tokens"] = tokens
    lesson["_cost_cny"] = tokens.get("total", 0) * 0.0015

    # 存储
    store = context.get("_store", _global_store)
    store.save(f"lesson:{lesson_id}", lesson)
    store.save(f"plan:{plan_id}/lessons", lesson_id)

    context["_lesson_id"] = lesson_id
    context["_lesson"] = lesson

    logger.info(
        "教训归档: %s (plan=%s, phase=%s, severity=%s, cost=¥%.2f)",
        lesson_id, plan_id, phase_id, lesson.get("severity", "?"), lesson["_cost_cny"],
    )

    return context


def get_lessons_for_plan(plan_id: str, store: Store = None) -> list:
    """获取指定计划的所有教训。"""
    store = store or _global_store
    lesson_ids = store.load(f"plan:{plan_id}/lessons")
    if not lesson_ids:
        return []

    if isinstance(lesson_ids, str):
        lesson_ids = [lesson_ids]

    lessons = []
    for lid in lesson_ids:
        lesson = store.load(f"lesson:{lid}")
        if lesson:
            lessons.append(lesson)

    return lessons


def get_all_lessons(store: Store = None) -> list:
    """获取所有教训。"""
    store = store or _global_store
    all_keys = store.list_keys()
    lessons = []
    for key in all_keys:
        if key.startswith("lesson:"):
            lesson = store.load(key)
            if lesson:
                lessons.append(lesson)
    return lessons


def _parse_lesson_json(response: str) -> dict | None:
    """从 LLM 响应中提取 JSON 教训。"""
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


lesson_archivist_skill = Skill(
    "lesson_archivist",
    archive_lesson,
    required_keys=["_plan_id", "_phase_id"],
    output_schema={
        "_lesson_id": str,
        "_lesson": dict,
    },
    timeout_seconds=60,
)
