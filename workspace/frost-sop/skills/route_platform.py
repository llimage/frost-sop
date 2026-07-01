"""
V4.0 P0-a: 路由平台Skill

包含：
1. RoutePlatformSkill - 无状态路由Skill
"""

import logging
import os

import yaml

logger = logging.getLogger(__name__)

# 默认绑定目录
DEFAULT_BINDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "bindings")


def route_platform(context: dict) -> dict:
    """
    根据skill_id和target_platform，返回ExecutionPlan。

    输入context键：
        _skill_id: Skill ID（如 "call_llm_for_output"）
        _target_platform: 目标平台（如 "wechat-mp", "web", "desktop"）
        _inputs: 输入参数（dict）

    输出context键：
        _execution_plan: dict（执行计划）

    执行计划格式：
        {
            "skill_id": "call_llm_for_output",
            "platform": "wechat-mp",
            "binding_type": "api",  # native / api / sdk
            "config": {...},  # 平台特定配置
            "dependencies": [...],  # 依赖列表
            "estimated_cost": 0.0,  # 预估成本（USD）
            "estimated_time": 0.0  # 预估耗时（秒）
        }
    """
    skill_id = context.get("_skill_id")
    target_platform = context.get("_target_platform")
    inputs = context.get("_inputs", {})

    if not skill_id:
        logger.error("[RoutePlatform] 缺少 _skill_id")
        context["_execution_plan"] = {"error": "missing_skill_id"}
        return context

    if not target_platform:
        logger.error("[RoutePlatform] 缺少 _target_platform")
        context["_execution_plan"] = {"error": "missing_target_platform"}
        return context

    logger.info(f"[RoutePlatform] 路由规划: skill={skill_id}, platform={target_platform}")

    # 加载平台绑定配置
    binding = _load_binding(skill_id, target_platform)

    # 构建执行计划
    execution_plan = {
        "skill_id": skill_id,
        "platform": target_platform,
        "binding_type": binding.get("binding_type", "native"),
        "config": binding.get("config", {}),
        "dependencies": binding.get("dependencies", []),
        "estimated_cost": binding.get("estimated_cost", 0.0),
        "estimated_time": binding.get("estimated_time", 0.0),
        "inputs": inputs,
        "note": binding.get("note", ""),
    }

    context["_execution_plan"] = execution_plan
    logger.info(
        f"[RoutePlatform] 执行计划已生成: {skill_id} @ {target_platform} ({binding.get('binding_type', 'native')})"
    )

    return context


def _load_binding(skill_id: str, platform: str) -> dict:
    """
    加载指定Skill在指定平台的绑定配置。

    Args:
        skill_id: Skill ID
        platform: 平台名称

    Returns:
        dict: 绑定配置（如果未找到，返回默认配置）
    """
    config_path = os.path.join(DEFAULT_BINDINGS_DIR, platform, f"{skill_id}.yaml")

    if os.path.exists(config_path):
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)
            logger.debug(f"[RoutePlatform] 已加载绑定: {config_path}")
            return config
        except Exception as e:
            logger.error(f"[RoutePlatform] 加载绑定失败 {config_path}: {e}")
            return _default_binding(skill_id, platform)
    else:
        logger.warning(f"[RoutePlatform] 绑定配置不存在: {config_path}")
        return _default_binding(skill_id, platform)


def _default_binding(skill_id: str, platform: str) -> dict:
    """
    返回默认绑定配置（原生执行）。
    """
    return {
        "skill_id": skill_id,
        "platform": platform,
        "binding_type": "native",
        "config": {},
        "dependencies": [],
        "estimated_cost": 0.0,
        "estimated_time": 0.0,
        "note": "默认绑定（原生执行）",
    }


# 导出
__all__ = ["route_platform"]
