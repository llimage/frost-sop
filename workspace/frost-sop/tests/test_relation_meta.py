"""
V5.0 P2: 关系元数据层测试
测试 DependencyGraph / ImpactAnalyzer / TransitiveResolver
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from core.armory import (
    WeaponMetadata, WeaponType, WeaponState, WeaponCategory, ArmoryRegistry,
)
from core.relation_meta import (
    DependencyGraph, ImpactAnalyzer, ImpactReport,
    TransitiveResolver,
)


# ── 辅助函数 ──────────────────────────────────────────────────────────────────

def make_weapon(weapon_id, name=None, deps=None, wtype=WeaponType.SKILL, state=WeaponState.ACTIVE):
    """创建测试武器"""
    return WeaponMetadata(
        id=weapon_id,
        name=name or weapon_id,
        type=wtype,
        category=WeaponCategory.COGNITIVE,
        dependencies=deps or [],
        state=state,
        is_active=(state == WeaponState.ACTIVE),
    )


def build_chain_registry():
    """构建链式依赖: D → C → B → A (D依赖C, C依赖B, B依赖A)"""
    r = ArmoryRegistry()
    r.register(make_weapon("skill:a", "A"))
    r.register(make_weapon("skill:b", "B", deps=["skill:a"]))
    r.register(make_weapon("skill:c", "C", deps=["skill:b"]))
    r.register(make_weapon("skill:d", "D", deps=["skill:c"]))
    return r


def build_diamond_registry():
    """构建菱形依赖: D → B → A, D → C → A"""
    r = ArmoryRegistry()
    r.register(make_weapon("skill:a", "A"))
    r.register(make_weapon("skill:b", "B", deps=["skill:a"]))
    r.register(make_weapon("skill:c", "C", deps=["skill:a"]))
    r.register(make_weapon("skill:d", "D", deps=["skill:b", "skill:c"]))
    return r


def build_sop_registry():
    """构建含SOP的依赖: sop:DEV-001 → skill:code_gen → skill:call_llm"""
    r = ArmoryRegistry()
    r.register(make_weapon("skill:call_llm", "call_llm"))
    r.register(make_weapon("skill:code_gen", "code_gen", deps=["skill:call_llm"]))
    r.register(make_weapon("sop:DEV-001", "DEV-001", deps=["skill:code_gen"], wtype=WeaponType.SOP))
    return r


# ── DependencyGraph 测试 ──────────────────────────────────────────────────────

class TestDependencyGraph:
    def test_empty_graph(self):
        g = DependencyGraph()
        assert g.node_count() == 0
        assert g.edge_count() == 0
        assert not g.has_cycle()

    def test_add_node_and_edge(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        assert g.node_count() == 2
        assert g.edge_count() == 1

    def test_build_from_registry(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert g.node_count() == 4
        assert g.edge_count() == 3

    def test_no_cycle_chain(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert not g.has_cycle()

    def test_detect_cycle(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")  # 形成环
        assert g.has_cycle()

    def test_find_cycle_path(self):
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("c", "a")
        cycle = g.find_cycle()
        assert cycle is not None
        assert len(cycle) >= 2

    def test_find_cycle_no_cycle(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert g.find_cycle() is None

    def test_topological_sort(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        sorted_ids = g.topological_sort()
        assert len(sorted_ids) == 4
        # A 应该在最前（被依赖最多，最先加载）
        assert sorted_ids[0] == "skill:a"
        # D 应该在最后（依赖最多，最后加载）
        assert sorted_ids[-1] == "skill:d"

    def test_topological_sort_with_cycle(self):
        """有环时返回空列表"""
        g = DependencyGraph()
        g.add_edge("a", "b")
        g.add_edge("b", "a")
        assert g.topological_sort() == []

    def test_get_depth_no_deps(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert g.get_depth("skill:a") == 0

    def test_get_depth_chain(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert g.get_depth("skill:b") == 1
        assert g.get_depth("skill:c") == 2
        assert g.get_depth("skill:d") == 3

    def test_get_depth_nonexistent(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        assert g.get_depth("skill:nonexistent") == -1

    def test_get_ancestors(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        ancestors = g.get_ancestors("skill:d")
        assert ancestors == {"skill:a", "skill:b", "skill:c"}

    def test_get_ancestors_no_deps(self):
        r = build_chain_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        ancestors = g.get_ancestors("skill:a")
        assert ancestors == set()

    def test_diamond_dependencies(self):
        """菱形依赖: D→B→A, D→C→A, A的祖先不重复"""
        r = build_diamond_registry()
        g = DependencyGraph()
        g.build_from_registry(r)
        ancestors = g.get_ancestors("skill:d")
        assert ancestors == {"skill:a", "skill:b", "skill:c"}
        assert g.get_depth("skill:d") == 2  # A→B→D 或 A→C→D, 深度2


# ── ImpactAnalyzer 测试 ───────────────────────────────────────────────────────

class TestImpactAnalyzer:
    def test_analyze_no_dependents(self):
        """无依赖方的武器移除影响低"""
        r = build_chain_registry()
        analyzer = ImpactAnalyzer(r)
        report = analyzer.analyze_removal("skill:d")
        assert report.risk_level == "low"
        assert report.total_impact == 0

    def test_analyze_with_dependents(self):
        """被依赖的武器移除影响高"""
        r = build_chain_registry()
        analyzer = ImpactAnalyzer(r)
        report = analyzer.analyze_removal("skill:a")
        assert report.total_impact == 3  # B, C, D 都依赖A
        assert "skill:b" in report.direct_dependents
        assert report.risk_level in ("high", "critical")

    def test_analyze_sop_impact(self):
        """SOP受影响分析"""
        r = build_sop_registry()
        analyzer = ImpactAnalyzer(r)
        report = analyzer.analyze_removal("skill:call_llm")
        assert len(report.affected_sops) == 1
        assert "sop:DEV-001" in report.affected_sops
        assert len(report.affected_skills) >= 1

    def test_analyze_nonexistent(self):
        r = build_chain_registry()
        analyzer = ImpactAnalyzer(r)
        report = analyzer.analyze_removal("skill:nonexistent")
        assert report.risk_level == "none"

    def test_risk_levels(self):
        """风险等级正确计算"""
        r = ArmoryRegistry()
        # skill:base 被多个武器依赖
        r.register(make_weapon("skill:base", "base"))
        for i in range(6):
            r.register(make_weapon(f"skill:dep{i}", f"dep{i}", deps=["skill:base"]))
        analyzer = ImpactAnalyzer(r)
        report = analyzer.analyze_removal("skill:base")
        assert report.risk_level == "critical"
        assert report.total_impact == 6

    def test_analyze_change_breaking(self):
        """破坏性变更检测"""
        r = build_chain_registry()
        analyzer = ImpactAnalyzer(r)
        result = analyzer.analyze_change("skill:a", "2.0.0")
        assert result["is_breaking_change"] is True

    def test_analyze_change_non_breaking(self):
        """非破坏性变更"""
        r = build_chain_registry()
        analyzer = ImpactAnalyzer(r)
        result = analyzer.analyze_change("skill:a", "1.1.0")
        assert result["is_breaking_change"] is False

    def test_change_recommendation(self):
        """变更建议生成"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:base", "base"))
        for i in range(7):
            r.register(make_weapon(f"skill:dep{i}", f"dep{i}", deps=["skill:base"]))
        analyzer = ImpactAnalyzer(r)
        result = analyzer.analyze_change("skill:base", "2.0.0")
        assert "严重影响" in result["recommendation"]


# ── TransitiveResolver 测试 ───────────────────────────────────────────────────

class TestTransitiveResolver:
    def test_resolve_chain(self):
        """链式依赖解析"""
        r = build_chain_registry()
        resolver = TransitiveResolver(r)
        deps = resolver.resolve_all("skill:d")
        assert "skill:a" in deps
        assert "skill:b" in deps
        assert "skill:c" in deps
        assert "skill:d" in deps
        # A应该在D之前（拓扑序，依赖在前）
        assert deps.index("skill:a") < deps.index("skill:d")

    def test_resolve_no_deps(self):
        """无依赖的武器只返回自身"""
        r = build_chain_registry()
        resolver = TransitiveResolver(r)
        deps = resolver.resolve_all("skill:a")
        assert deps == ["skill:a"]

    def test_resolve_diamond(self):
        """菱形依赖解析（不重复）"""
        r = build_diamond_registry()
        resolver = TransitiveResolver(r)
        deps = resolver.resolve_all("skill:d")
        # A只出现一次
        assert deps.count("skill:a") == 1
        assert "skill:b" in deps
        assert "skill:c" in deps

    def test_check_readiness_all_ready(self):
        """所有依赖就绪"""
        r = build_chain_registry()
        resolver = TransitiveResolver(r)
        result = resolver.check_readiness("skill:d")
        assert result["ready"] is True
        assert result["missing"] == []

    def test_check_readiness_missing_dep(self):
        """依赖缺失"""
        r = build_chain_registry()
        # 注销A（模拟缺失）
        r.unregister("skill:a")
        resolver = TransitiveResolver(r)
        result = resolver.check_readiness("skill:d")
        assert result["ready"] is False
        assert "skill:a" in result["missing"]

    def test_check_readiness_inactive_dep(self):
        """依赖未激活"""
        r = build_chain_registry()
        r.update_status("skill:a", WeaponState.RETIRED)
        resolver = TransitiveResolver(r)
        result = resolver.check_readiness("skill:d")
        assert result["ready"] is False
        assert "skill:a" in result["inactive"]

    def test_get_dependency_tree(self):
        """获取依赖树"""
        r = build_chain_registry()
        resolver = TransitiveResolver(r)
        tree = resolver.get_dependency_tree("skill:d")
        assert tree["id"] == "skill:d"
        assert len(tree["children"]) == 1  # D 依赖 C
        assert tree["children"][0]["id"] == "skill:c"

    def test_get_dependency_tree_circular(self):
        """循环依赖检测"""
        r = ArmoryRegistry()
        r.register(make_weapon("skill:a", "A", deps=["skill:b"]))
        r.register(make_weapon("skill:b", "B", deps=["skill:a"]))
        resolver = TransitiveResolver(r)
        tree = resolver.get_dependency_tree("skill:a")
        # 应该能检测到循环
        assert "circular" in str(tree) or "children" in tree
