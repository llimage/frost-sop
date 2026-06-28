"""
FROST V5.0 P2: 关系元数据层 (Relation Metadata Layer)

PHILOSOPHY: 武器不是孤岛。一个 SOP 依赖多个 Skill，一个 Skill 依赖平台绑定。
当一把武器被退役时，哪些武器会受影响？当一把新武器被注册时，
它的依赖链是否完整？这些问题的答案在"关系元数据层"。

本模块提供：
1. DependencyGraph    — 依赖图构建与拓扑排序
2. ImpactAnalyzer     — 影响分析（武器变更/移除的波及面）
3. TransitiveResolver — 传递依赖解析
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
from enum import Enum
from collections import defaultdict, deque


# ────────────────────────────────────────────────────────────────────────────
# 依赖图
# ────────────────────────────────────────────────────────────────────────────

class DependencyGraph:
    """
    依赖图——从武器注册表构建有向无环图（DAG）。

    节点 = 武器ID
    边 = 依赖关系（A 依赖 B → 边 A→B）

    提供：
    - 拓扑排序（确定武器加载顺序）
    - 环检测（防止循环依赖）
    - 层级计算（依赖深度）
    """

    def __init__(self):
        self._adj: Dict[str, Set[str]] = defaultdict(set)  # 邻接表: weapon_id -> 依赖的weapon_id集合
        self._nodes: Set[str] = set()

    def add_node(self, weapon_id: str):
        """添加节点"""
        self._nodes.add(weapon_id)

    def add_edge(self, from_id: str, to_id: str):
        """
        添加依赖边：from_id 依赖 to_id

        Args:
            from_id: 依赖方武器ID
            to_id: 被依赖方武器ID
        """
        self._nodes.add(from_id)
        self._nodes.add(to_id)
        self._adj[from_id].add(to_id)

    def build_from_registry(self, registry) -> "DependencyGraph":
        """从武器注册表构建依赖图"""
        for weapon in registry.list_all():
            self.add_node(weapon.id)
            for dep_id in weapon.dependencies:
                self.add_edge(weapon.id, dep_id)
        return self

    def has_cycle(self) -> bool:
        """检测是否有环（循环依赖）"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._nodes}

        def dfs(node):
            color[node] = GRAY
            for neighbor in self._adj.get(node, set()):
                if color.get(neighbor, WHITE) == GRAY:
                    return True
                if color.get(neighbor, WHITE) == WHITE:
                    if dfs(neighbor):
                        return True
            color[node] = BLACK
            return False

        for node in self._nodes:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        return False

    def find_cycle(self) -> Optional[List[str]]:
        """查找环路径（返回参与循环的节点列表，无环返回None）"""
        WHITE, GRAY, BLACK = 0, 1, 2
        color = {node: WHITE for node in self._nodes}
        parent = {node: None for node in self._nodes}

        def dfs(node):
            color[node] = GRAY
            for neighbor in self._adj.get(node, set()):
                if color.get(neighbor, WHITE) == GRAY:
                    # 找到环，回溯路径
                    cycle = [neighbor, node]
                    curr = node
                    while parent[curr] is not None and parent[curr] != neighbor:
                        curr = parent[curr]
                        cycle.append(curr)
                    cycle.reverse()
                    return cycle
                if color.get(neighbor, WHITE) == WHITE:
                    parent[neighbor] = node
                    result = dfs(neighbor)
                    if result:
                        return result
            color[node] = BLACK
            return None

        for node in self._nodes:
            if color[node] == WHITE:
                result = dfs(node)
                if result:
                    return result
        return None

    def topological_sort(self) -> List[str]:
        """
        拓扑排序——返回武器加载顺序（被依赖的在前）。

        Returns:
            排序后的武器ID列表，如果有环则返回空列表
        """
        if self.has_cycle():
            return []

        in_degree = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._adj.get(node, set()):
                in_degree[dep] = in_degree.get(dep, 0)  # 确保存在
                # in_degree[node] 表示有多少节点依赖 node
                # 实际上我们需要反向：dep 被 node 依赖

        # 重新计算：in_degree = 被多少节点依赖
        in_degree = {node: 0 for node in self._nodes}
        for node in self._nodes:
            for dep in self._adj.get(node, set()):
                if dep in in_degree:
                    in_degree[dep] += 1

        # Kahn's algorithm
        queue = deque([n for n in self._nodes if in_degree[n] == 0])
        result = []

        while queue:
            node = queue.popleft()
            result.append(node)
            for dep in self._adj.get(node, set()):
                if dep in in_degree:
                    in_degree[dep] -= 1
                    if in_degree[dep] == 0:
                        queue.append(dep)

        result.reverse()  # 被依赖的在前
        return result

    def get_depth(self, weapon_id: str) -> int:
        """
        计算武器的依赖深度。
        深度0 = 无依赖
        深度1 = 依赖深度0的武器
        深度N = 依赖链最长路径

        Returns:
            依赖深度，-1 如果武器不存在或有环
        """
        if weapon_id not in self._nodes:
            return -1

        memo = {}

        def compute_depth(node):
            if node in memo:
                return memo[node]
            deps = self._adj.get(node, set())
            if not deps:
                memo[node] = 0
                return 0
            memo[node] = 1 + max(compute_depth(d) for d in deps if d in self._nodes)
            return memo[node]

        return compute_depth(weapon_id)

    def get_ancestors(self, weapon_id: str) -> Set[str]:
        """
        获取所有祖先（直接和间接被依赖的武器）。

        Returns:
            祖先武器ID集合
        """
        if weapon_id not in self._nodes:
            return set()

        visited = set()
        queue = deque([weapon_id])

        while queue:
            node = queue.popleft()
            for dep in self._adj.get(node, set()):
                if dep not in visited:
                    visited.add(dep)
                    queue.append(dep)

        return visited

    def node_count(self) -> int:
        """节点数量"""
        return len(self._nodes)

    def edge_count(self) -> int:
        """边数量"""
        return sum(len(deps) for deps in self._adj.values())


# ────────────────────────────────────────────────────────────────────────────
# 影响分析器
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class ImpactReport:
    """影响分析报告"""
    weapon_id: str                          # 被分析的武器ID
    direct_dependents: List[str] = field(default_factory=list)    # 直接依赖方
    transitive_dependents: List[str] = field(default_factory=list) # 传递依赖方
    affected_sops: List[str] = field(default_factory=list)        # 受影响的SOP
    affected_skills: List[str] = field(default_factory=list)      # 受影响的Skill
    total_impact: int = 0                   # 总影响数
    risk_level: str = "low"                 # 风险等级: low/medium/high/critical

    def to_dict(self) -> Dict:
        return {
            "weapon_id": self.weapon_id,
            "direct_dependents": self.direct_dependents,
            "transitive_dependents": self.transitive_dependents,
            "affected_sops": self.affected_sops,
            "affected_skills": self.affected_skills,
            "total_impact": self.total_impact,
            "risk_level": self.risk_level,
        }


class ImpactAnalyzer:
    """
    影响分析器——分析武器变更/移除的影响范围。

    当一把武器被退役或修改时，需要知道：
    1. 哪些武器直接依赖它？
    2. 哪些武器间接依赖它（传递依赖）？
    3. 哪些SOP会因此无法执行？
    4. 风险等级是什么？
    """

    def __init__(self, registry):
        self.registry = registry

    def analyze_removal(self, weapon_id: str) -> ImpactReport:
        """
        分析移除指定武器的影响。

        Args:
            weapon_id: 要移除的武器ID

        Returns:
            ImpactReport 影响报告
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return ImpactReport(weapon_id=weapon_id, risk_level="none")

        # 直接依赖方（谁依赖了这把武器）
        direct = self.registry.find_dependents(weapon_id)
        direct_ids = [w.id for w in direct]

        # 传递依赖方（通过依赖链间接依赖）
        graph = DependencyGraph()
        graph.build_from_registry(self.registry)
        all_dependents = set(direct_ids)

        # 反向遍历：找出所有传递依赖方
        to_check = deque(direct_ids)
        while to_check:
            current = to_check.popleft()
            dependents = self.registry.find_dependents(current)
            for dep in dependents:
                if dep.id not in all_dependents:
                    all_dependents.add(dep.id)
                    to_check.append(dep.id)

        transitive_ids = list(all_dependents - set(direct_ids))

        # 分类受影响的武器
        affected_sops = []
        affected_skills = []
        for wid in all_dependents:
            w = self.registry.get(wid)
            if w:
                from core.armory import WeaponType
                if w.type == WeaponType.SOP:
                    affected_sops.append(wid)
                elif w.type == WeaponType.SKILL:
                    affected_skills.append(wid)

        # 风险评估
        total = len(all_dependents)
        if total == 0:
            risk = "low"
        elif total <= 2:
            risk = "medium"
        elif total <= 5:
            risk = "high"
        else:
            risk = "critical"

        return ImpactReport(
            weapon_id=weapon_id,
            direct_dependents=direct_ids,
            transitive_dependents=transitive_ids,
            affected_sops=affected_sops,
            affected_skills=affected_skills,
            total_impact=total,
            risk_level=risk,
        )

    def analyze_change(self, weapon_id: str, new_version: str) -> Dict[str, any]:
        """
        分析版本变更的影响。

        Args:
            weapon_id: 武器ID
            new_version: 新版本号

        Returns:
            变更影响分析结果
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return {"error": "武器不存在"}

        report = self.analyze_removal(weapon_id)

        return {
            "weapon_id": weapon_id,
            "current_version": weapon.version,
            "new_version": new_version,
            "is_breaking_change": self._is_breaking_change(weapon, new_version),
            "affected_count": report.total_impact,
            "risk_level": report.risk_level,
            "recommendation": self._change_recommendation(report),
        }

    def _is_breaking_change(self, weapon, new_version: str) -> bool:
        """判断是否为破坏性变更（简化：主版本号变化即为破坏性）"""
        try:
            old_major = int(weapon.version.split(".")[0])
            new_major = int(new_version.split(".")[0])
            return new_major > old_major
        except (ValueError, IndexError):
            return False

    @staticmethod
    def _change_recommendation(report: ImpactReport) -> str:
        """根据影响报告生成建议"""
        if report.risk_level == "critical":
            return "严重影响：建议先通知所有依赖方，分批次迁移后再变更"
        elif report.risk_level == "high":
            return "高度影响：建议先验证所有依赖方兼容性"
        elif report.risk_level == "medium":
            return "中等影响：建议在测试环境验证后再变更"
        else:
            return "低影响：可以直接变更"


# ────────────────────────────────────────────────────────────────────────────
# 传递依赖解析器
# ────────────────────────────────────────────────────────────────────────────

class TransitiveResolver:
    """
    传递依赖解析器——解析武器的完整依赖链。

    当一个 SOP 被配发时，需要确保它的所有依赖（包括依赖的依赖）
    都已就绪。TransitiveResolver 负责这个解析。
    """

    def __init__(self, registry):
        self.registry = registry

    def resolve_all(self, weapon_id: str) -> List[str]:
        """
        解析武器的所有传递依赖（包括自身）。

        返回顺序：被依赖的在前（拓扑序），确保加载顺序正确。

        Args:
            weapon_id: 起始武器ID

        Returns:
            完整依赖链的武器ID列表（拓扑排序）
        """
        graph = DependencyGraph()
        graph.build_from_registry(self.registry)

        if weapon_id not in graph._nodes:
            return [weapon_id] if self.registry.get(weapon_id) else []

        # 获取所有祖先（被依赖的武器）
        ancestors = graph.get_ancestors(weapon_id)

        # 构建子图并拓扑排序
        sub_graph = DependencyGraph()
        sub_graph.add_node(weapon_id)
        for ancestor in ancestors:
            sub_graph.add_node(ancestor)
            weapon = self.registry.get(ancestor)
            if weapon:
                for dep in weapon.dependencies:
                    if dep in ancestors or dep == weapon_id:
                        sub_graph.add_edge(ancestor, dep)

        # 也添加起始武器的直接依赖
        weapon = self.registry.get(weapon_id)
        if weapon:
            for dep in weapon.dependencies:
                sub_graph.add_edge(weapon_id, dep)

        sorted_deps = sub_graph.topological_sort()
        return sorted_deps if sorted_deps else [weapon_id]

    def check_readiness(self, weapon_id: str) -> Dict[str, any]:
        """
        检查武器的所有依赖是否就绪。

        Args:
            weapon_id: 武器ID

        Returns:
            {
                "ready": bool,
                "missing": [缺失的依赖ID列表],
                "inactive": [未激活的依赖ID列表],
                "total_deps": int,
            }
        """
        all_deps = self.resolve_all(weapon_id)
        all_deps = [d for d in all_deps if d != weapon_id]  # 排除自身

        missing = []
        inactive = []

        for dep_id in all_deps:
            weapon = self.registry.get(dep_id)
            if not weapon:
                missing.append(dep_id)
            elif not weapon.is_active:
                inactive.append(dep_id)

        return {
            "ready": len(missing) == 0 and len(inactive) == 0,
            "missing": missing,
            "inactive": inactive,
            "total_deps": len(all_deps),
        }

    def get_dependency_tree(self, weapon_id: str, max_depth: int = 10) -> Dict:
        """
        获取依赖树结构。

        Args:
            weapon_id: 起始武器ID
            max_depth: 最大深度（防止无限递归）

        Returns:
            嵌套字典表示的依赖树
        """
        def build_tree(wid: str, depth: int, visited: set) -> Dict:
            if depth >= max_depth or wid in visited:
                return {"id": wid, "circular": wid in visited}

            visited = visited | {wid}
            weapon = self.registry.get(wid)
            if not weapon:
                return {"id": wid, "missing": True}

            children = []
            for dep_id in weapon.dependencies:
                children.append(build_tree(dep_id, depth + 1, visited))

            return {
                "id": wid,
                "name": weapon.name,
                "type": weapon.type.value,
                "children": children,
            }

        return build_tree(weapon_id, 0, set())
