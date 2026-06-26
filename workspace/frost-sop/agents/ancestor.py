"""
PHILOSOPHY:
Ancestor Agent is the root of the agent family tree (generation=0).
It holds the constitution and has the highest authority to spawn parent agents.
"""

from core.agent import Agent
from core.skill import Skill
from skills.orchestration import spawn_skill, emit_skill, validate_sop_skill
from skills.llm import call_llm_skill


def create_ancestor(constitution_store, asset_store) -> Agent:
    """
    Create ancestor Agent with constitution store.

    Args:
        constitution_store: HierarchicalStore containing constitution rules
        asset_store: HierarchicalStore for asset storage

    Returns:
        Agent instance (ancestor)
    """
    skills = {
        "spawn": spawn_skill,
        "emit": emit_skill,
        "validate_sop": validate_sop_skill,
        "call_llm": call_llm_skill,
    }

    return Agent(
        name="ancestor",
        store=constitution_store,
        skills=skills,
        generation=0,
        max_spawn_generation=1,
    )
