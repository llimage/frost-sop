"""
PHILOSOPHY:
Constitution Store holds the immutable rules that govern all agents.
It is the root of the read-only hierarchy.
"""

from core.store import HierarchicalStore, Store


def create_constitution_store(rules: dict = None) -> HierarchicalStore:
    """
    Create constitution store with default or custom rules.

    Args:
        rules: Dictionary of rules (defaults to built-in rules)

    Returns:
        HierarchicalStore instance with readonly keys
    """
    if rules is None:
        rules = {
            "const.budget_monthly": 300,
            "const.max_agents": 3,
            "const.audit_append_only": True,
            "compliance.required_stages": ["审查交付"],
            "compliance.forbidden_skills": ["direct_db_write"],
            # V2.0 新增：成本规则
            "const.cost_alert_ratio": 0.8,  # 预警比例 80%
            "const.cheap_model": "deepseek-chat",  # 默认模型
            "const.expensive_model": "deepseek-chat",  # 复杂任务模型（当前统一）
            "const.max_cost_per_task": 50,  # 单任务成本上限 ¥50
        }

    own = Store()
    for key, value in rules.items():
        own.save(key, value)

    return HierarchicalStore(own_store=own, parent=None)
