"""
FROST-SOP Parent Agent Factory
PHILOSOPHY: 父辈是成年Agent。出厂预装13个本能Skill。
所有Skill都是普通Skill，不引入特权组件。
"""

from core.agent import Agent
from skills.orchestration import (
    spawn_skill, emit_skill, validate_sop_skill, merge_from_skill,
    internalize_sop_skill, execute_stage_skill, finalize_task_skill,
)
from skills.search import search_sop_skill, search_skill_skill
from skills.llm import call_llm_skill
from skills.knowledge import archive_sop_skill, archive_lesson_skill, query_lessons_skill
from skills.assemble import assemble_agent_skill
from skills.importer import import_agency_agents_skill
from skills.evolution import (
    load_task_history_skill, analyze_trends_skill,
    generate_suggestions_skill, present_for_approval_skill,
)


def create_parent(name: str, coordination_store) -> Agent:
    """
    创建父辈Agent。出厂预装15个本能Skill。
    
    本能Skill清单（实际注册15个）：
    - 编排: spawn, emit, validate_sop, merge_from, internalize_sop, execute_stage, finalize_task（7个）
    - 搜索: search_sop, search_skill（2个）
    - LLM: call_llm（1个）
    - 知识: archive_sop, archive_lesson, query_lessons（3个）
    - 组装: assemble_agent（1个）
    - 导入: import_agency_agents（1个）
    """
    skills = {
        # 编排 Skill（7个，V2.0 新增 finalize_task）
        "spawn": spawn_skill,
        "emit": emit_skill,
        "validate_sop": validate_sop_skill,
        "merge_from": merge_from_skill,
        "internalize_sop": internalize_sop_skill,
        "execute_stage": execute_stage_skill,
        "finalize_task": finalize_task_skill,   # V2.0: 任务收尾 + 触发长老审计
        # 搜索 Skill（2个）
        "search_sop": search_sop_skill,
        "search_skill": search_skill_skill,
        # LLM Skill（1个）
        "call_llm": call_llm_skill,
        # 知识归档 Skill（3个）
        "archive_sop": archive_sop_skill,
        "archive_lesson": archive_lesson_skill,
        "query_lessons": query_lessons_skill,
        # 组装 Skill（2个）
        "assemble_agent": assemble_agent_skill,
        # 导入 Skill（1个）
        "import_agency_agents": import_agency_agents_skill,
        # 自进化 Skill（4个）
        "load_task_history": load_task_history_skill,
        "analyze_trends": analyze_trends_skill,
        "generate_suggestions": generate_suggestions_skill,
        "present_for_approval": present_for_approval_skill,
    }
    return Agent(
        name=name,
        store=coordination_store,
        skills=skills,
        generation=1,
    )
