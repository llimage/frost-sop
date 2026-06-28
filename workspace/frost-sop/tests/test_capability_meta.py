"""
V5.0 P1: 能力元数据层测试
测试 CapabilityProfile / ScenarioMatcher / CapabilityComparator
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.armory import (
    WeaponMetadata, WeaponType, WeaponState, WeaponCategory, ArmoryRegistry,
)
from core.capability_meta import (
    CapabilityProfile, ComplexityLevel, ScenarioMatcher, CapabilityComparator,
)


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def make_weapon(weapon_id="skill:test", name="test", scenarios=None,
                not_scenarios=None, profile=None, category=WeaponCategory.COGNITIVE):
    """创建测试武器"""
    return WeaponMetadata(
        id=weapon_id,
        name=name,
        type=WeaponType.SKILL,
        category=category,
        applicable_scenarios=scenarios or [],
        not_applicable_scenarios=not_scenarios or [],
        capability_profile=profile,
    )


def make_profile(inputs=None, outputs=None, context=None, complexity=ComplexityLevel.SIMPLE,
                 keywords=None, resources=None, duration=None):
    """创建测试能力画像"""
    return CapabilityProfile(
        input_types=inputs or [],
        output_types=outputs or [],
        execution_context=context or [],
        complexity=complexity,
        capability_keywords=keywords or [],
        resource_tags=resources or [],
        estimated_duration=duration,
    )


# ── CapabilityProfile 测试 ───────────────────────────────────────────────────

class TestCapabilityProfile:
    def test_create_default(self):
        p = CapabilityProfile()
        assert p.input_types == []
        assert p.output_types == []
        assert p.complexity == ComplexityLevel.SIMPLE
        assert p.estimated_duration is None

    def test_create_with_values(self):
        p = make_profile(
            inputs=["text", "json"],
            outputs=["json"],
            context=["cloud"],
            complexity=ComplexityLevel.COMPLEX,
            keywords=["llm", "analysis"],
            resources=["api_call"],
            duration=5.0,
        )
        assert p.input_types == ["text", "json"]
        assert p.output_types == ["json"]
        assert p.execution_context == ["cloud"]
        assert p.complexity == ComplexityLevel.COMPLEX
        assert p.capability_keywords == ["llm", "analysis"]
        assert p.resource_tags == ["api_call"]
        assert p.estimated_duration == 5.0

    def test_to_dict(self):
        p = make_profile(inputs=["text"], outputs=["json"], complexity=ComplexityLevel.MODERATE)
        d = p.to_dict()
        assert d["input_types"] == ["text"]
        assert d["output_types"] == ["json"]
        assert d["complexity"] == "moderate"

    def test_from_dict(self):
        data = {
            "input_types": ["yaml"],
            "output_types": ["document"],
            "execution_context": ["local"],
            "complexity": "complex",
            "estimated_duration": 10.0,
            "resource_tags": ["cpu_heavy"],
            "capability_keywords": ["sop", "orchestration"],
        }
        p = CapabilityProfile.from_dict(data)
        assert p.input_types == ["yaml"]
        assert p.output_types == ["document"]
        assert p.complexity == ComplexityLevel.COMPLEX
        assert p.estimated_duration == 10.0

    def test_from_dict_invalid_complexity(self):
        """无效复杂度回退到 SIMPLE"""
        p = CapabilityProfile.from_dict({"complexity": "invalid_value"})
        assert p.complexity == ComplexityLevel.SIMPLE

    def test_complexity_levels(self):
        """所有复杂度等级都可创建"""
        levels = [ComplexityLevel.TRIVIAL, ComplexityLevel.SIMPLE,
                  ComplexityLevel.MODERATE, ComplexityLevel.COMPLEX,
                  ComplexityLevel.ADVANCED]
        for level in levels:
            p = CapabilityProfile(complexity=level)
            assert p.complexity == level


# ── ScenarioMatcher 测试 ──────────────────────────────────────────────────────

class TestScenarioMatcher:
    def test_exact_match(self):
        """精确匹配场景得满分"""
        w = make_weapon(scenarios=["代码生成"])
        score = ScenarioMatcher.match_score(w, "代码生成")
        assert score == 1.0

    def test_no_match(self):
        """不匹配场景得0分"""
        w = make_weapon(scenarios=["代码生成"])
        score = ScenarioMatcher.match_score(w, "财务分析")
        assert score == 0.0

    def test_partial_match(self):
        """模糊匹配（关键词包含）得部分分"""
        w = make_weapon(scenarios=["代码生成与测试"])
        score = ScenarioMatcher.match_score(w, "代码生成")
        assert 0 < score < 1.0

    def test_not_applicable_penalty(self):
        """不适用场景扣分"""
        w = make_weapon(scenarios=["代码生成"], not_scenarios=["财务分析"])
        score = ScenarioMatcher.match_score(w, "财务分析")
        assert score < 0  # 扣分后为负

    def test_capability_keyword_bonus(self):
        """能力关键词加分"""
        profile = make_profile(keywords=["llm"])
        w = make_weapon(scenarios=["推理"], profile=profile)
        score_with_keyword = ScenarioMatcher.match_score(w, "llm推理")
        w2 = make_weapon(scenarios=["推理"])
        score_without = ScenarioMatcher.match_score(w2, "llm推理")
        assert score_with_keyword > score_without

    def test_multi_scenario_average(self):
        """多场景取平均"""
        w = make_weapon(scenarios=["代码生成", "测试"])
        score = ScenarioMatcher.match_multi_scenario(w, ["代码生成", "财务分析"])
        # 一个匹配1.0，一个匹配0.0，平均0.5
        assert 0.4 < score < 0.6

    def test_multi_scenario_require_all(self):
        """多场景全匹配取最小值"""
        w = make_weapon(scenarios=["代码生成", "测试"])
        score = ScenarioMatcher.match_multi_scenario(w, ["代码生成", "财务分析"], require_all=True)
        # 财务分析不匹配，最小值为0
        assert score == 0.0

    def test_best_matches(self):
        """从注册表找最佳匹配"""
        registry = ArmoryRegistry()
        w1 = make_weapon("skill:code_gen", "code_gen", scenarios=["代码生成"])
        w2 = make_weapon("skill:finance", "finance", scenarios=["财务分析"])
        w3 = make_weapon("skill:code_test", "code_test", scenarios=["代码生成", "测试"])
        registry.register(w1)
        registry.register(w2)
        registry.register(w3)

        results = ScenarioMatcher.best_matches(registry, "代码生成", top_k=2)
        assert len(results) <= 2
        # 代码生成武器应该排第一
        assert results[0][0].id in ("skill:code_gen", "skill:code_test")

    def test_best_matches_min_score(self):
        """最低分数过滤"""
        registry = ArmoryRegistry()
        w1 = make_weapon("skill:code", "code", scenarios=["代码"])
        registry.register(w1)
        results = ScenarioMatcher.best_matches(registry, "完全不相关", min_score=0.5)
        assert len(results) == 0


# ── CapabilityComparator 测试 ─────────────────────────────────────────────────

class TestCapabilityComparator:
    def test_jaccard_both_empty(self):
        """两个空列表 Jaccard=1.0"""
        sim = CapabilityComparator._jaccard_similarity([], [])
        assert sim == 1.0

    def test_jaccard_one_empty(self):
        """一个空列表 Jaccard=0.0"""
        sim = CapabilityComparator._jaccard_similarity(["a"], [])
        assert sim == 0.0

    def test_jaccard_identical(self):
        """完全相同 Jaccard=1.0"""
        sim = CapabilityComparator._jaccard_similarity(["a", "b"], ["a", "b"])
        assert sim == 1.0

    def test_jaccard_partial(self):
        """部分重叠"""
        sim = CapabilityComparator._jaccard_similarity(["a", "b"], ["b", "c"])
        assert 0 < sim < 1.0
        assert sim == 1/3  # 交集1，并集3

    def test_similarity_identical_profiles(self):
        """相同能力画像的武器相似度高"""
        profile = make_profile(inputs=["text"], outputs=["json"], context=["cloud"],
                               complexity=ComplexityLevel.COMPLEX, keywords=["llm"])
        w1 = make_weapon("skill:a", "a", profile=profile)
        w2 = make_weapon("skill:b", "b", profile=profile)
        sim = CapabilityComparator.similarity(w1, w2)
        assert sim == 1.0

    def test_similarity_no_profiles(self):
        """无能力画像时退化为场景相似度"""
        w1 = make_weapon("skill:a", "a", scenarios=["代码生成", "测试"])
        w2 = make_weapon("skill:b", "b", scenarios=["代码生成"])
        sim = CapabilityComparator.similarity(w1, w2)
        assert 0 < sim < 1.0

    def test_similarity_one_profile(self):
        """一方有能力画像而另一方没有"""
        profile = make_profile(inputs=["text"])
        w1 = make_weapon("skill:a", "a", profile=profile)
        w2 = make_weapon("skill:b", "b")
        sim = CapabilityComparator.similarity(w1, w2)
        assert sim == 0.0

    def test_find_similar(self):
        """从注册表查找相似武器"""
        registry = ArmoryRegistry()
        profile1 = make_profile(inputs=["text"], outputs=["json"], keywords=["llm"])
        profile2 = make_profile(inputs=["text"], outputs=["json"], keywords=["llm"])
        profile3 = make_profile(inputs=["image"], outputs=["image"], keywords=["vision"])

        w1 = make_weapon("skill:llm_a", "llm_a", profile=profile1)
        w2 = make_weapon("skill:llm_b", "llm_b", profile=profile2)
        w3 = make_weapon("skill:vision", "vision", profile=profile3)

        registry.register(w1)
        registry.register(w2)
        registry.register(w3)

        similar = CapabilityComparator.find_similar(registry, "skill:llm_a", top_k=2)
        assert len(similar) > 0
        # llm_b 应该比 vision 更相似
        assert similar[0][0].id == "skill:llm_b"

    def test_find_similar_not_found(self):
        """目标武器不存在返回空"""
        registry = ArmoryRegistry()
        results = CapabilityComparator.find_similar(registry, "skill:nonexistent")
        assert results == []

    def test_capability_gap(self):
        """能力差距分析"""
        profile1 = make_profile(inputs=["text", "json"], outputs=["json"], keywords=["llm"])
        profile2 = make_profile(inputs=["text"], outputs=["yaml"], keywords=["vision"])
        w1 = make_weapon("skill:a", "a", profile=profile1)
        w2 = make_weapon("skill:b", "b", profile=profile2)

        gap = CapabilityComparator.capability_gap(w1, w2)
        assert "input_types" in gap
        assert "output_types" in gap
        assert "capability_keywords" in gap
        assert 0 <= gap["input_types"] <= 1.0
        assert 0 <= gap["output_types"] <= 1.0

    def test_find_similar_via_registry(self):
        """通过 ArmoryRegistry.find_similar 方法查找"""
        registry = ArmoryRegistry()
        profile1 = make_profile(inputs=["text"], outputs=["json"], keywords=["llm"])
        profile2 = make_profile(inputs=["text"], outputs=["json"], keywords=["llm"])

        w1 = make_weapon("skill:a", "a", profile=profile1)
        w2 = make_weapon("skill:b", "b", profile=profile2)
        registry.register(w1)
        registry.register(w2)

        similar = registry.find_similar("skill:a", top_k=5)
        assert len(similar) > 0
        assert similar[0].id == "skill:b"

    def test_complexity_similarity_same(self):
        """相同复杂度相似度为1.0"""
        profile1 = make_profile(complexity=ComplexityLevel.COMPLEX)
        profile2 = make_profile(complexity=ComplexityLevel.COMPLEX)
        w1 = make_weapon("skill:a", "a", profile=profile1)
        w2 = make_weapon("skill:b", "b", profile=profile2)
        sim = CapabilityComparator.similarity(w1, w2)
        assert sim > 0.5  # 复杂度维度满分，其他维度也满分(都为空=1.0)
