"""
FROST V5.0 P1: 能力元数据层 (Capability Metadata Layer)

PHILOSOPHY: 武器不只是有 ID 和类型，它还有"能力画像"——
输入什么、输出什么、在什么上下文中执行、复杂度如何。
军师检索武器时，不只是按关键词匹配，而是按"能力相似度"推荐。

本模块提供：
1. CapabilityProfile  — 能力画像数据类
2. ScenarioMatcher    — 场景匹配引擎（加权评分）
3. CapabilityComparator — 能力对比器（相似度计算）
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from enum import Enum


# ────────────────────────────────────────────────────────────────────────────
# 复杂度等级
# ────────────────────────────────────────────────────────────────────────────

class ComplexityLevel(Enum):
    """武器复杂度等级"""
    TRIVIAL = "trivial"      # 简单：单步操作，无依赖
    SIMPLE = "simple"        # 简易：少量步骤，少量依赖
    MODERATE = "moderate"    # 中等：多步骤，有依赖链
    COMPLEX = "complex"      # 复杂：多阶段，跨域依赖
    ADVANCED = "advanced"    # 高级：需要编排多个子武器


# ────────────────────────────────────────────────────────────────────────────
# 能力画像
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class CapabilityProfile:
    """
    能力画像——描述武器的输入、输出、执行上下文和复杂度。

    这是武器元数据的"能力维度"，让军师能按能力相似度推荐武器，
    而非仅靠关键词匹配。
    """
    # 输入类型（如 "text", "json", "yaml", "file_path"）
    input_types: List[str] = field(default_factory=list)
    # 输出类型
    output_types: List[str] = field(default_factory=list)
    # 执行上下文（如 "local", "cloud", "sandbox", "offline"）
    execution_context: List[str] = field(default_factory=list)
    # 复杂度
    complexity: ComplexityLevel = ComplexityLevel.SIMPLE
    # 预估执行时间（秒）
    estimated_duration: Optional[float] = None
    # 资源消耗标签（如 "cpu_heavy", "memory_light", "api_call"）
    resource_tags: List[str] = field(default_factory=list)
    # 能力关键词（用于能力匹配，不同于 tags）
    capability_keywords: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "input_types": self.input_types,
            "output_types": self.output_types,
            "execution_context": self.execution_context,
            "complexity": self.complexity.value,
            "estimated_duration": self.estimated_duration,
            "resource_tags": self.resource_tags,
            "capability_keywords": self.capability_keywords,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "CapabilityProfile":
        """从字典反序列化"""
        complexity_str = data.get("complexity", "simple")
        try:
            complexity = ComplexityLevel(complexity_str)
        except ValueError:
            complexity = ComplexityLevel.SIMPLE
        return cls(
            input_types=data.get("input_types", []),
            output_types=data.get("output_types", []),
            execution_context=data.get("execution_context", []),
            complexity=complexity,
            estimated_duration=data.get("estimated_duration"),
            resource_tags=data.get("resource_tags", []),
            capability_keywords=data.get("capability_keywords", []),
        )


# ────────────────────────────────────────────────────────────────────────────
# 场景匹配引擎
# ────────────────────────────────────────────────────────────────────────────

class ScenarioMatcher:
    """
    场景匹配引擎——按加权评分匹配武器与场景。

    匹配逻辑：
    1. 精确匹配 applicable_scenarios → 1.0 分
    2. 模糊匹配（关键词包含）→ 0.5-0.8 分
    3. 检查 not_applicable_scenarios → 扣分
    4. 检查 capability_keywords → 加分
    """

    # 权重配置
    WEIGHT_EXACT_MATCH = 1.0
    WEIGHT_PARTIAL_MATCH = 0.6
    WEIGHT_KEYWORD_MATCH = 0.4
    WEIGHT_NOT_APPLICABLE_PENALTY = -0.5
    WEIGHT_CAPABILITY_BONUS = 0.2

    @classmethod
    def match_score(cls, weapon, scenario: str) -> float:
        """
        计算武器与单个场景的匹配分数。

        Args:
            weapon: WeaponMetadata 实例
            scenario: 场景描述

        Returns:
            匹配分数（0.0-1.0+，可超过1.0因为有能力加分）
        """
        score = 0.0
        scenario_lower = scenario.lower()

        # 1. 精确匹配 applicable_scenarios
        if scenario in weapon.applicable_scenarios:
            score += cls.WEIGHT_EXACT_MATCH
        else:
            # 2. 模糊匹配（场景关键词包含在 applicable_scenarios 中）
            for app_scn in weapon.applicable_scenarios:
                if scenario_lower in app_scn.lower() or app_scn.lower() in scenario_lower:
                    score += cls.WEIGHT_PARTIAL_MATCH
                    break

        # 3. 检查 not_applicable_scenarios（扣分）
        for not_scn in weapon.not_applicable_scenarios:
            if scenario_lower in not_scn.lower() or not_scn.lower() in scenario_lower:
                score += cls.WEIGHT_NOT_APPLICABLE_PENALTY
                break

        # 4. 能力关键词加分
        capability_profile = getattr(weapon, 'capability_profile', None)
        if capability_profile and isinstance(capability_profile, CapabilityProfile):
            for kw in capability_profile.capability_keywords:
                if kw.lower() in scenario_lower:
                    score += cls.WEIGHT_CAPABILITY_BONUS
                    break

        return round(score, 3)

    @classmethod
    def match_multi_scenario(cls, weapon, scenarios: List[str],
                             require_all: bool = False) -> float:
        """
        计算武器与多个场景的综合匹配分数。

        Args:
            weapon: WeaponMetadata 实例
            scenarios: 场景列表
            require_all: True=所有场景都必须匹配(取最小值), False=取平均值

        Returns:
            综合匹配分数
        """
        if not scenarios:
            return 0.0

        scores = [cls.match_score(weapon, s) for s in scenarios]

        if require_all:
            # 所有场景都需匹配：取最小值（短板效应）
            return min(scores)
        else:
            # 取平均值
            return round(sum(scores) / len(scores), 3)

    @classmethod
    def best_matches(cls, registry, scenario: str, top_k: int = 5,
                     min_score: float = 0.1) -> List[Tuple[object, float]]:
        """
        从注册表中找出与场景最匹配的武器。

        Args:
            registry: ArmoryRegistry 实例
            scenario: 场景描述
            top_k: 返回前K个
            min_score: 最低匹配分数

        Returns:
            [(weapon, score), ...] 按分数降序
        """
        results = []
        for weapon in registry.list_all():
            if not weapon.is_active:
                continue
            score = cls.match_score(weapon, scenario)
            if score >= min_score:
                results.append((weapon, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]


# ────────────────────────────────────────────────────────────────────────────
# 能力对比器
# ────────────────────────────────────────────────────────────────────────────

class CapabilityComparator:
    """
    能力对比器——计算两个武器的能力相似度。

    相似度算法（Jaccard + 加权）：
    1. 输入类型相似度（权重 0.25）
    2. 输出类型相似度（权重 0.25）
    3. 执行上下文相似度（权重 0.20）
    4. 能力关键词相似度（权重 0.20）
    5. 复杂度相似度（权重 0.10）
    """

    # 相似度权重
    WEIGHTS = {
        "input_types": 0.25,
        "output_types": 0.25,
        "execution_context": 0.20,
        "capability_keywords": 0.20,
        "complexity": 0.10,
    }

    @staticmethod
    def _jaccard_similarity(set_a: List[str], set_b: List[str]) -> float:
        """计算两个列表的 Jaccard 相似度"""
        if not set_a and not set_b:
            return 1.0  # 两个都为空视为完全相似
        if not set_a or not set_b:
            return 0.0
        sa, sb = set(set_a), set(set_b)
        intersection = sa & sb
        union = sa | sb
        return len(intersection) / len(union) if union else 0.0

    @classmethod
    def similarity(cls, weapon_a, weapon_b) -> float:
        """
        计算两个武器的能力相似度。

        Args:
            weapon_a: WeaponMetadata 实例
            weapon_b: WeaponMetadata 实例

        Returns:
            相似度分数 0.0-1.0
        """
        profile_a = getattr(weapon_a, 'capability_profile', None)
        profile_b = getattr(weapon_b, 'capability_profile', None)

        # 如果都没有能力画像，退化为场景相似度
        if not profile_a and not profile_b:
            return cls._jaccard_similarity(
                weapon_a.applicable_scenarios,
                weapon_b.applicable_scenarios
            )

        # 如果一方有能力画像而另一方没有
        if not profile_a or not profile_b:
            return 0.0

        # 计算各维度相似度
        input_sim = cls._jaccard_similarity(profile_a.input_types, profile_b.input_types)
        output_sim = cls._jaccard_similarity(profile_a.output_types, profile_b.output_types)
        context_sim = cls._jaccard_similarity(profile_a.execution_context, profile_b.execution_context)
        keyword_sim = cls._jaccard_similarity(profile_a.capability_keywords, profile_b.capability_keywords)

        # 复杂度相似度：相同=1.0，差一级=0.5，差两级+=0.0
        complexity_levels = list(ComplexityLevel)
        idx_a = complexity_levels.index(profile_a.complexity)
        idx_b = complexity_levels.index(profile_b.complexity)
        diff = abs(idx_a - idx_b)
        complexity_sim = 1.0 if diff == 0 else (0.5 if diff == 1 else 0.0)

        # 加权综合
        total = (
            cls.WEIGHTS["input_types"] * input_sim
            + cls.WEIGHTS["output_types"] * output_sim
            + cls.WEIGHTS["execution_context"] * context_sim
            + cls.WEIGHTS["capability_keywords"] * keyword_sim
            + cls.WEIGHTS["complexity"] * complexity_sim
        )

        return round(total, 3)

    @classmethod
    def find_similar(cls, registry, weapon_id: str, top_k: int = 5,
                     min_similarity: float = 0.1) -> List[Tuple[object, float]]:
        """
        从注册表中找出与指定武器最相似的其他武器。

        Args:
            registry: ArmoryRegistry 实例
            weapon_id: 目标武器ID
            top_k: 返回前K个
            min_similarity: 最低相似度

        Returns:
            [(weapon, similarity), ...] 按相似度降序
        """
        target = registry.get(weapon_id)
        if not target:
            return []

        results = []
        for weapon in registry.list_all():
            if weapon.id == weapon_id:
                continue
            if not weapon.is_active:
                continue
            sim = cls.similarity(target, weapon)
            if sim >= min_similarity:
                results.append((weapon, sim))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    @classmethod
    def capability_gap(cls, weapon_a, weapon_b) -> Dict[str, float]:
        """
        分析两个武器的能力差距（各维度分别计算）。

        Returns:
            {维度: 差距分数} 差距=1.0-相似度
        """
        profile_a = getattr(weapon_a, 'capability_profile', None)
        profile_b = getattr(weapon_b, 'capability_profile', None)

        if not profile_a or not profile_b:
            return {"overall": 1.0 - cls.similarity(weapon_a, weapon_b)}

        return {
            "input_types": 1.0 - cls._jaccard_similarity(profile_a.input_types, profile_b.input_types),
            "output_types": 1.0 - cls._jaccard_similarity(profile_a.output_types, profile_b.output_types),
            "execution_context": 1.0 - cls._jaccard_similarity(profile_a.execution_context, profile_b.execution_context),
            "capability_keywords": 1.0 - cls._jaccard_similarity(profile_a.capability_keywords, profile_b.capability_keywords),
            "complexity": 1.0 - (1.0 if profile_a.complexity == profile_b.complexity else
                                 (0.5 if abs(list(ComplexityLevel).index(profile_a.complexity) -
                                            list(ComplexityLevel).index(profile_b.complexity)) == 1 else 0.0)),
        }
