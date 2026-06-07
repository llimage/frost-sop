"""
agents/__init__.py - Agent 声明式注册表
项目：Solo-Ops-Platform V0.3.0
---
集中管理所有 Agent 的元信息（能力、强项、弱点、质量标准）。
CEO 在 Plan 阶段读取此注册表来做出编排决策。
"""

from agents.researcher import create_researcher_agent, build_research_task
from agents.writer import create_writer_agent, build_writing_task


# ── Agent 声明式注册表 ─────────────────────────────────────────────────────────

AGENT_REGISTRY = {
    "researcher": {
        "factory": create_researcher_agent,
        "task_builder": build_research_task,
        "profile": {
            "role": "资深商业分析师",
            "strengths": ["信息搜集", "趋势分析", "竞品研究", "数据整理"],
            "weaknesses": ["创意写作", "感性表达", "视觉设计"],
            "input_requirements": ["研究主题或问题"],
            "output_products": ["结构化分析结论（含要点、数据、趋势判断）"],
            "quality_rubric": (
                "分析结论必须有至少3个要点，"
                "每个要点有数据或案例支撑，"
                "包含趋势判断"
            ),
        },
    },
    "writer": {
        "factory": create_writer_agent,
        "task_builder": build_writing_task,
        "profile": {
            "role": "资深内容创作者",
            "strengths": ["报告撰写", "简报制作", "语言生动化", "结构优化"],
            "weaknesses": ["原始数据搜集", "深度分析", "实时信息获取"],
            "input_requirements": ["分析结论", "目标受众", "格式要求"],
            "output_products": ["完整简报（标题+段落+总结）"],
            "quality_rubric": (
                "必须有醒目标题，分段落且每段有小标题，"
                "结尾有总结句，600-800字"
            ),
        },
    },
}


def get_agent(agent_id: str, model_name: str = "deepseek-chat"):
    """
    根据 ID 获取 Agent 实例、profile 和 task_builder。

    参数：
        agent_id: 注册表中的 Agent ID（如 "researcher"）
        model_name: LLM 模型名称

    返回：
        (agent_instance, profile_dict, task_builder_func) 三元组

    异常：
        ValueError: 未知的 agent_id
    """
    if agent_id not in AGENT_REGISTRY:
        available = ", ".join(AGENT_REGISTRY.keys())
        raise ValueError(f"未知 Agent: {agent_id}，可用: {available}")

    config = AGENT_REGISTRY[agent_id]
    agent = config["factory"](model_name=model_name)
    return agent, config["profile"], config["task_builder"]


def list_available_agents() -> dict:
    """
    列出所有可用 Agent 的 profile（不含 factory 函数）。

    返回：
        {agent_id: profile_dict} 字典
    """
    return {
        agent_id: config["profile"]
        for agent_id, config in AGENT_REGISTRY.items()
    }
