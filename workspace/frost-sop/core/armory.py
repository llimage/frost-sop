"""
FROST V4.0 核心——统一武器库（Armory）
PHILOSOPHY: 武器不是代码，武器是元数据驱动的能力单元。

所有家族资产（Skill、SOP、情报、免疫规则、平台绑定）统一为 Weapon。
Armory 是武器的唯一注册表、检索器和生命周期管理者。

武器分类（WeaponType）:
  SKILL — 纯函数能力单元（如 call_llm, assemble_agent）
  SOP   — 标准操作程序（如 DEV-001, STR-002）
  INTEL — 情报产物（如 财务简报、客户简报）
  IMMUN — 免疫规则（如 心跳阈值、熔断规则）
  BIND  — 平台绑定（如 deepseek, openai, local_gguf）
  GENE  — 能力基因（未归档的 Skill 模板）
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable, Set, Tuple

from core.store import Store
from core.skill import Skill
from core.sop import SOP
from core.skill_graph import (
    SkillNode, SkillEdge, EdgeType, SkillCard, PlatformBinding, ParamSpec
)


# ────────────────────────────────────────────────────────────────────────────
# V5.0 类型别名（向后兼容）
# ────────────────────────────────────────────────────────────────────────────
# V5.0 五维元数据层使用新命名，但底层指向 V4.0 已有实现，确保不破坏现有代码。
# 这些别名将在 P0-P4 逐步使用，P4 完成后可考虑统一命名。

# Weapon = WeaponMetadata（V5.0 简称）
# WeaponStatus = WeaponState（V5.0 命名）
# FunctionDomain = WeaponCategory（V5.0 命名，WeaponCategory 是超集）
# 上述别名在类定义之后声明，见文件底部。


# ────────────────────────────────────────────────────────────────────────────
# 武器类型枚举
# ────────────────────────────────────────────────────────────────────────────

class WeaponType(Enum):
    """武器类型：所有家族资产的原子分类"""
    SKILL = "skill"          # 纯函数能力单元（如 call_llm）
    SOP = "sop"              # 标准操作程序（如 DEV-001）
    INTEL = "intel"          # 情报产物（如 财务简报、客户简报）
    IMMUN = "immun"          # 免疫规则（如 心跳阈值、熔断规则）
    BIND = "bind"            # 平台绑定（如 deepseek, openai）
    GENE = "gene"            # 能力基因（未归档的 Skill 模板）


# ────────────────────────────────────────────────────────────────────────────
# 武器分类（功能域）
# ────────────────────────────────────────────────────────────────────────────

class WeaponCategory(Enum):
    """武器功能域：军师检索时的分类维度"""
    COGNITIVE = "cognitive"      # 认知能力（LLM调用、推理、分析）
    EXECUTION = "execution"      # 执行能力（文件操作、代码生成、部署）
    GOVERNANCE = "governance"    # 治理能力（审计、合规、校验、权限）
    STRATEGY = "strategy"        # 战略能力（分析、简报、预测、狩猎）
    IMMUNE = "immune"            # 免疫能力（监控、熔断、告警、恢复）
    ORCHESTRATE = "orchestrate"  # 编排能力（spawn、merge、emit、调度）
    SEARCH = "search"            # 搜索能力（外部搜索、比对、检索）
    COMMUNICATION = "comm"       # 通信能力（通知、报告、简报、面板）
    UNKNOWN = "unknown"          # 未分类


# ────────────────────────────────────────────────────────────────────────────
# 武器生命周期状态
# ────────────────────────────────────────────────────────────────────────────

class WeaponState(Enum):
    """武器生命周期状态"""
    DISCOVERED = "discovered"      # 狩猎发现，尚未验证
    VALIDATED = "validated"        # 格式/结构校验通过
    TRIALED = "trialed"            # 小规模试炼通过
    ARCHIVED = "archived"          # 已归档入库，可供配发
    ACTIVE = "active"              # 当前活跃使用
    DEPRECATED = "deprecated"      # 标记废弃，不再推荐
    RETIRED = "retired"            # 已退役，不可使用


# ────────────────────────────────────────────────────────────────────────────
# 武器元数据
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class WeaponMetadata:
    """
    武器元数据——武器库的唯一入口。

    每个武器（无论Skill、SOP、情报还是免疫规则）
    都必须携带完整的元数据才能注册到武器库。
    """
    # 基础标识
    id: str                          # 唯一标识（如 "skill:call_llm", "sop:DEV-001"）
    name: str                        # 人类可读名称
    type: WeaponType                 # 武器类型
    version: str = "1.0"             # 语义版本
    category: WeaponCategory = WeaponCategory.UNKNOWN  # 功能域

    # 适用场景（军师检索时匹配）
    applicable_scenarios: List[str] = field(default_factory=list)
    # 如：["代码生成", "LLM推理", "文档分析"]

    # 不适用场景（防止误配发）
    not_applicable_scenarios: List[str] = field(default_factory=list)

    # 依赖关系
    dependencies: List[str] = field(default_factory=list)  # 依赖的武器ID列表
    required_platforms: List[str] = field(default_factory=list)  # 需要平台列表

    # V5.0 新增：标签与描述
    tags: List[str] = field(default_factory=list)  # 标签（用于搜索）
    description: str = ""  # 人类可读描述

    # 健康评分（自然选择驱动）
    health_score: float = 50.0       # 健康评分 0-100，初始50
    usage_count: int = 0             # 使用次数
    success_count: int = 0           # 成功次数
    failure_count: int = 0           # 失败次数
    avg_execution_time: Optional[float] = None  # 平均执行时间(秒)
    last_used: Optional[str] = None   # 最后使用时间（ISO格式）

    # 来源与版本
    created_from: str = "manual"     # "manual" | "extracted" | "synthesized" | "hunted"
    source: str = ""                 # 来源标识（文件路径、URL等）
    source_url: Optional[str] = None  # 外部来源URL（狩猎产物）
    confidence: float = 1.0          # 置信度 0.0-1.0

    # 生命周期
    state: WeaponState = WeaponState.ACTIVE
    is_active: bool = True           # 是否激活
    is_preset: bool = False          # 是否为预置武器（不可删除）

    # 时序
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archived_at: Optional[str] = None
    deprecated_at: Optional[str] = None
    retired_at: Optional[str] = None

    # V5.0 新增：激活时间（与 state=ACTIVE 配合使用）
    activated_at: Optional[str] = None

    # 扩展：武器卡（V4.0 技能图）
    card: Optional[SkillCard] = None  # 如果携带技能卡，记录详细信息
    skill_node_id: Optional[str] = None  # 关联的技能图节点ID

    # 扩展：适配器（运行时使用）
    _skill_instance: Optional[Skill] = field(default=None, repr=False)  # 运行时Skill实例
    _sop_instance: Optional[SOP] = field(default=None, repr=False)      # 运行时SOP实例

    def __post_init__(self):
        """自动计算成功率"""
        total = self.success_count + self.failure_count
        if total > 0:
            self._success_rate = self.success_count / total
        else:
            self._success_rate = None

    @property
    def success_rate(self) -> Optional[float]:
        """动态计算成功率"""
        total = self.success_count + self.failure_count
        if total > 0:
            return self.success_count / total
        return None

    @property
    def is_ready(self) -> bool:
        """
        V5.0：是否可配发给府兵。
        条件：状态为 ACTIVE 且健康评分 >= 30（0-100 量表）。
        """
        return self.state == WeaponState.ACTIVE and self.health_score >= 30

    def record_usage(self, success: bool, execution_time: Optional[float] = None):
        """记录一次使用，更新健康评分"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()

        if success:
            self.success_count += 1
        else:
            self.failure_count += 1

        # 更新健康评分：使用频率+成功率+时效性
        # 健康评分 = 0.4 * 成功率 + 0.3 * log(使用次数+1)/log(101) + 0.3 * 时效衰减
        import math
        rate = self.success_rate or 0.5
        freq = math.log(self.usage_count + 1) / math.log(101)  # 使用100次达到1.0
        recency = 1.0  # 简化：最近使用不衰减
        self.health_score = min(100, 0.4 * rate * 100 + 0.3 * freq * 100 + 0.3 * recency * 100)
        self.health_score = round(self.health_score, 1)

        if execution_time is not None:
            if self.avg_execution_time is None:
                self.avg_execution_time = execution_time
            else:
                self.avg_execution_time = (
                    self.avg_execution_time * (self.usage_count - 1) + execution_time
                ) / self.usage_count

        self.updated_at = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典（运行时实例不序列化）"""
        d = asdict(self)
        # 移除运行时实例
        d.pop("_skill_instance", None)
        d.pop("_sop_instance", None)
        # 枚举转字符串
        d["type"] = self.type.value
        d["category"] = self.category.value
        d["state"] = self.state.value
        if self.card:
            d["card"] = asdict(self.card)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WeaponMetadata":
        """从字典反序列化"""
        data = dict(data)
        data["type"] = WeaponType(data["type"])
        data["category"] = WeaponCategory(data.get("category", "unknown"))
        data["state"] = WeaponState(data.get("state", "active"))
        # card 反序列化
        if "card" in data and data["card"]:
            # 简化：不递归反序列化 SkillCard，留作运行时加载
            pass
        data.pop("_skill_instance", None)
        data.pop("_sop_instance", None)
        return cls(**data)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        if isinstance(other, WeaponMetadata):
            return self.id == other.id
        return False


# ────────────────────────────────────────────────────────────────────────────
# 武器库注册表（ArmoryRegistry）
# ────────────────────────────────────────────────────────────────────────────

class ArmoryRegistry:
    """
    武器库注册表——所有武器的统一索引。

    提供多维检索：
    - 按ID精确查找
    - 按类型筛选（所有 SKILL、所有 SOP）
    - 按场景匹配（军师推荐时检索）
    - 按评分排序（自然选择排序）
    - 按依赖关系查找（哪些武器依赖本武器）
    - 按状态筛选（只检索 ACTIVE 武器）
    """

    def __init__(self, store: Optional[Store] = None):
        """
        初始化武器库。

        Args:
            store: 持久化 Store。如果提供，武器从 Store 加载；否则从内存运行。
        """
        self._store = store
        self._weapons: Dict[str, WeaponMetadata] = {}  # id -> WeaponMetadata
        self._by_type: Dict[WeaponType, Set[str]] = {t: set() for t in WeaponType}
        self._by_category: Dict[WeaponCategory, Set[str]] = {c: set() for c in WeaponCategory}
        self._by_scenario: Dict[str, Set[str]] = {}    # 场景 -> 武器ID集合
        self._by_state: Dict[WeaponState, Set[str]] = {s: set() for s in WeaponState}
        self._dependents: Dict[str, Set[str]] = {}     # 被依赖关系：武器ID -> 依赖它的武器ID集合

        if store:
            self._load_from_store()

    # ── 内部索引 ──────────────────────────────────────────────────────────

    def _add_to_indexes(self, weapon: WeaponMetadata):
        """将武器添加到所有索引"""
        self._by_type[weapon.type].add(weapon.id)
        self._by_category[weapon.category].add(weapon.id)
        self._by_state[weapon.state].add(weapon.id)
        for scenario in weapon.applicable_scenarios:
            self._by_scenario.setdefault(scenario, set()).add(weapon.id)
        for dep in weapon.dependencies:
            self._dependents.setdefault(dep, set()).add(weapon.id)

    def _remove_from_indexes(self, weapon: WeaponMetadata):
        """从所有索引中移除武器"""
        self._by_type[weapon.type].discard(weapon.id)
        self._by_category[weapon.category].discard(weapon.id)
        self._by_state[weapon.state].discard(weapon.id)
        for scenario in weapon.applicable_scenarios:
            self._by_scenario.get(scenario, set()).discard(weapon.id)
        for dep in weapon.dependencies:
            self._dependents.get(dep, set()).discard(weapon.id)

    def _load_from_store(self):
        """从 Store 加载武器注册表"""
        if not self._store:
            return
        data = self._store.load("armory:registry")
        if not data:
            return
        for wid, wdata in data.items():
            try:
                weapon = WeaponMetadata.from_dict(wdata)
                self._weapons[weapon.id] = weapon
                self._add_to_indexes(weapon)
            except Exception as e:
                # 忽略损坏数据
                pass

    def _persist_to_store(self):
        """持久化武器注册表到 Store"""
        if not self._store:
            return
        data = {wid: w.to_dict() for wid, w in self._weapons.items()}
        self._store.save("armory:registry", data)

    # ── 注册与注销 ──────────────────────────────────────────────────────────

    def register(self, weapon: WeaponMetadata) -> bool:
        """
        注册武器到武器库。

        Args:
            weapon: 武器元数据

        Returns:
            True 注册成功，False 已存在（版本更高则不覆盖）
        """
        existing = self._weapons.get(weapon.id)
        if existing:
            # 版本比较：如果新武器版本更高，则更新
            if self._compare_version(weapon.version, existing.version) > 0:
                self._remove_from_indexes(existing)
                self._weapons[weapon.id] = weapon
                self._add_to_indexes(weapon)
                self._persist_to_store()
                return True
            return False

        self._weapons[weapon.id] = weapon
        self._add_to_indexes(weapon)
        self._persist_to_store()
        return True

    def unregister(self, weapon_id: str) -> bool:
        """从武器库注销武器（预置武器不可删除）"""
        weapon = self._weapons.get(weapon_id)
        if not weapon or weapon.is_preset:
            return False
        self._remove_from_indexes(weapon)
        del self._weapons[weapon_id]
        self._persist_to_store()
        return True

    @staticmethod
    def _compare_version(v1: str, v2: str) -> int:
        """比较语义版本，v1 > v2 返回 1，v1 < v2 返回 -1，相等返回 0"""
        def parse(v):
            return [int(x) for x in v.split(".")]
        a, b = parse(v1), parse(v2)
        for x, y in zip(a, b):
            if x != y:
                return 1 if x > y else -1
        return len(a) - len(b)

    # ── 检索 ─────────────────────────────────────────────────────────────────

    def get(self, weapon_id: str) -> Optional[WeaponMetadata]:
        """按ID获取武器"""
        return self._weapons.get(weapon_id)

    def find_by_type(self, weapon_type: WeaponType, state: WeaponState = None) -> List[WeaponMetadata]:
        """按类型检索武器"""
        ids = self._by_type.get(weapon_type, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_category(self, category: WeaponCategory, state: WeaponState = None) -> List[WeaponMetadata]:
        """按功能域检索武器"""
        ids = self._by_category.get(category, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_scenario(self, scenario: str, state: WeaponState = None) -> List[WeaponMetadata]:
        """按场景检索武器"""
        ids = self._by_scenario.get(scenario, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_scenarios(self, scenarios: List[str], match_all: bool = False, state: WeaponState = None) -> List[WeaponMetadata]:
        """
        按多个场景检索武器。

        Args:
            scenarios: 场景列表
            match_all: True=所有场景都匹配，False=任意场景匹配
            state: 可选状态过滤
        """
        if not scenarios:
            return []
        result_sets = []
        for s in scenarios:
            ids = self._by_scenario.get(s, set())
            if state:
                ids = ids & self._by_state.get(state, set())
            result_sets.append(ids)
        if not result_sets:
            return []
        if match_all:
            matched_ids = set.intersection(*result_sets)
        else:
            matched_ids = set.union(*result_sets)
        return [self._weapons[wid] for wid in matched_ids if wid in self._weapons]

    def find_by_keyword(self, keyword: str, state: WeaponState = None) -> List[WeaponMetadata]:
        """按关键词模糊搜索（名称、场景、描述）"""
        results = []
        keyword_lower = keyword.lower()
        for wid, w in self._weapons.items():
            if state and w.state != state:
                continue
            match = (
                keyword_lower in w.name.lower()
                or any(keyword_lower in s.lower() for s in w.applicable_scenarios)
                or keyword_lower in w.id.lower()
            )
            if match:
                results.append(w)
        return results

    def find_dependents(self, weapon_id: str) -> List[WeaponMetadata]:
        """查找依赖指定武器的所有武器"""
        ids = self._dependents.get(weapon_id, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_health_score(self, min_score: float = 0, max_score: float = 100,
                              weapon_type: WeaponType = None) -> List[WeaponMetadata]:
        """按健康评分范围检索武器"""
        results = []
        for w in self._weapons.values():
            if weapon_type and w.type != weapon_type:
                continue
            if min_score <= w.health_score <= max_score:
                results.append(w)
        return results

    # ── 排序与推荐 ──────────────────────────────────────────────────────────

    def recommend(self, requirement: str, weapon_type: WeaponType = None,
                  top_k: int = 5, min_health_score: float = 30.0) -> List[WeaponMetadata]:
        """
        军师推荐：根据需求描述推荐最佳武器。

        推荐逻辑：
        1. 关键词匹配（场景+名称+ID）
        2. 按健康评分排序（自然选择）
        3. 过滤掉非ACTIVE状态和低评分武器
        """
        # 关键词匹配
        candidates = self.find_by_keyword(requirement, state=WeaponState.ACTIVE)
        if weapon_type:
            candidates = [w for w in candidates if w.type == weapon_type]

        # 过滤低评分
        candidates = [w for w in candidates if w.health_score >= min_health_score]

        # 按健康评分降序，使用次数降序，成功率降序
        candidates.sort(key=lambda w: (
            w.health_score,
            w.usage_count,
            w.success_rate or 0
        ), reverse=True)

        return candidates[:top_k]

    def recommend_bundle(self, task_description: str, required_categories: List[WeaponCategory] = None) -> Dict[str, List[WeaponMetadata]]:
        """
        推荐武器组合：为任务推荐完整的能力套装。

        Returns:
            {category: [WeaponMetadata, ...]} 按功能域分组的推荐武器
        """
        bundle = {}
        categories = required_categories or list(WeaponCategory)

        for cat in categories:
            # 先找该类别下的高评分武器
            weapons = self.find_by_category(cat, state=WeaponState.ACTIVE)
            weapons = [w for w in weapons if w.health_score >= 30.0]
            weapons.sort(key=lambda w: (w.health_score, w.usage_count), reverse=True)
            # 取前3个
            bundle[cat.value] = weapons[:3]

        return bundle

    # ── 统计与概览 ──────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """武器库统计"""
        total = len(self._weapons)
        by_type = {t.value: len(self._by_type[t]) for t in WeaponType}
        by_category = {c.value: len(self._by_category[c]) for c in WeaponCategory}
        by_state = {s.value: len(self._by_state[s]) for s in WeaponState}

        avg_health = 0.0
        if total > 0:
            avg_health = sum(w.health_score for w in self._weapons.values()) / total

        return {
            "total_weapons": total,
            "by_type": by_type,
            "by_category": by_category,
            "by_state": by_state,
            "avg_health_score": round(avg_health, 1),
            "top_weapons": [w.id for w in sorted(self._weapons.values(),
                                                   key=lambda x: x.health_score, reverse=True)[:5]],
        }

    def list_all(self, weapon_type: WeaponType = None, state: WeaponState = None) -> List[WeaponMetadata]:
        """列出所有武器（可选过滤）"""
        weapons = list(self._weapons.values())
        if weapon_type:
            weapons = [w for w in weapons if w.type == weapon_type]
        if state:
            weapons = [w for w in weapons if w.state == state]
        return weapons

    # ── V5.0 便捷方法 ──────────────────────────────────────────────────────

    def list_active(self) -> List[WeaponMetadata]:
        """V5.0：列出所有可配发的武器（is_ready 为 True 的武器）"""
        return [w for w in self._weapons.values() if w.is_ready]

    def search_by_tags(self, tags: List[str]) -> List[WeaponMetadata]:
        """V5.0：按标签搜索武器（包含任一标签即匹配）"""
        return [w for w in self._weapons.values() if any(t in w.tags for t in tags)]

    def search_by_domain(self, domain: WeaponCategory) -> List[WeaponMetadata]:
        """V5.0：按功能域搜索武器（find_by_category 的别名）"""
        return self.find_by_category(domain)

    def update_status(self, weapon_id: str, new_state: WeaponState) -> None:
        """
        V5.0：直接更新武器状态（便捷方法）。
        注意：此方法绕过 WeaponLifecycle 的转换规则检查。
        对于需要规则验证的状态转换，请使用 WeaponLifecycle.transition()。
        """
        weapon = self._weapons.get(weapon_id)
        if not weapon:
            raise ValueError(f"武器 {weapon_id} 不存在")
        self._remove_from_indexes(weapon)
        weapon.state = new_state
        now = datetime.now().isoformat()
        weapon.updated_at = now
        if new_state == WeaponState.ACTIVE:
            weapon.activated_at = now
            weapon.is_active = True
        elif new_state == WeaponState.RETIRED:
            weapon.retired_at = now
            weapon.is_active = False
        elif new_state == WeaponState.DEPRECATED:
            weapon.deprecated_at = now
            weapon.is_active = False
        self._add_to_indexes(weapon)
        self._persist_to_store()

    def record_usage(self, weapon_id: str, success: bool) -> None:
        """V5.0：在注册表级别记录武器使用（委托给 WeaponMetadata.record_usage）"""
        weapon = self._weapons.get(weapon_id)
        if not weapon:
            raise ValueError(f"武器 {weapon_id} 不存在")
        weapon.record_usage(success)
        self._persist_to_store()

    def count(self) -> int:
        """V5.0：武器总数"""
        return len(self._weapons)


# ────────────────────────────────────────────────────────────────────────────
# 武器生命周期管理器
# ────────────────────────────────────────────────────────────────────────────

class WeaponLifecycle:
    """
    武器生命周期管理器。

    管理武器从发现到退役的完整流转：
    DISCOVERED → VALIDATED → TRIALED → ARCHIVED → ACTIVE → DEPRECATED → RETIRED

    每个状态转换都需要满足条件：
    - DISCOVERED → VALIDATED: 格式校验通过（结构完整、依赖可解析）
    - VALIDATED → TRIALED: 小规模试炼（10次运行，成功率≥70%）
    - TRIALED → ARCHIVED: 归档入库（写入武器库注册表）
    - ARCHIVED → ACTIVE: 被首次配发使用
    - ACTIVE → DEPRECATED: 使用频率连续30天低于阈值，或有更好替代品
    - DEPRECATED → RETIRED: 新版本已稳定，旧版本完全退役
    - 任意 → RETIRED: 发现严重安全/合规问题
    """

    def __init__(self, registry: ArmoryRegistry):
        self.registry = registry

    def transition(self, weapon_id: str, to_state: WeaponState,
                   reason: str = "") -> Tuple[bool, str]:
        """
        状态转换。

        Args:
            weapon_id: 武器ID
            to_state: 目标状态
            reason: 转换原因

        Returns:
            (成功, 消息)
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return False, f"武器不存在: {weapon_id}"

        from_state = weapon.state
        if from_state == to_state:
            return True, "无需转换"

        # 检查转换规则
        ok, msg = self._check_transition_rules(weapon, from_state, to_state)
        if not ok:
            return False, msg

        # 执行转换
        self.registry._remove_from_indexes(weapon)
        weapon.state = to_state
        now = datetime.now().isoformat()

        if to_state == WeaponState.ARCHIVED:
            weapon.archived_at = now
        elif to_state == WeaponState.DEPRECATED:
            weapon.deprecated_at = now
            weapon.is_active = False
        elif to_state == WeaponState.RETIRED:
            weapon.retired_at = now
            weapon.is_active = False

        weapon.updated_at = now
        self.registry._add_to_indexes(weapon)
        self.registry._persist_to_store()

        return True, f"武器 {weapon_id} 从 {from_state.value} 转换为 {to_state.value}。原因: {reason}"

    def _check_transition_rules(self, weapon: WeaponMetadata,
                                 from_state: WeaponState, to_state: WeaponState) -> Tuple[bool, str]:
        """检查状态转换规则"""
        # 定义有效转换
        valid_transitions = {
            WeaponState.DISCOVERED: {WeaponState.VALIDATED, WeaponState.RETIRED},
            WeaponState.VALIDATED: {WeaponState.TRIALED, WeaponState.ARCHIVED, WeaponState.RETIRED},
            WeaponState.TRIALED: {WeaponState.ARCHIVED, WeaponState.RETIRED},
            WeaponState.ARCHIVED: {WeaponState.ACTIVE, WeaponState.DEPRECATED, WeaponState.RETIRED},
            WeaponState.ACTIVE: {WeaponState.DEPRECATED, WeaponState.RETIRED},
            WeaponState.DEPRECATED: {WeaponState.ACTIVE, WeaponState.RETIRED},
            WeaponState.RETIRED: set(),  # 不可转换
        }

        if to_state not in valid_transitions.get(from_state, set()):
            return False, f"无效转换: {from_state.value} → {to_state.value}"

        # 特殊条件检查
        if to_state == WeaponState.TRIALED:
            # 试炼需要：至少试炼1次（简化）
            if weapon.usage_count < 1:
                return False, "试炼条件不满足：usage_count < 1"

        if to_state == WeaponState.ACTIVE:
            # 激活需要：已归档且健康评分≥30
            if weapon.state != WeaponState.ARCHIVED:
                return False, "激活需要：先归档到武器库"
            if weapon.health_score < 30:
                return False, f"激活条件不满足：健康评分 {weapon.health_score} < 30"

        return True, "OK"

    def auto_evaluate(self, weapon_id: str) -> Tuple[WeaponState, str]:
        """
        自动评估武器状态，返回推荐状态。

        评估规则：
        - 使用频率连续30天为0 + 非预置 → DEPRECATED
        - 健康评分<20 + 非预置 → RETIRED
        - 成功率>80% + 使用>10次 → 推荐升级为 ACTIVE（如果当前是 ARCHIVED）
        """
        weapon = self.registry.get(weapon_id)
        if not weapon:
            return WeaponState.RETIRED, "武器不存在"

        if weapon.is_preset:
            return weapon.state, "预置武器不参与自动评估"

        # 评估逻辑
        if weapon.health_score < 20:
            return WeaponState.RETIRED, f"健康评分过低 ({weapon.health_score})"

        if weapon.state == WeaponState.ACTIVE and weapon.usage_count == 0:
            # 简化：如果从未使用且不是预置，考虑废弃
            return WeaponState.DEPRECATED, "从未使用"

        if weapon.state == WeaponState.ARCHIVED and weapon.success_rate and weapon.success_rate > 0.8:
            if weapon.usage_count >= 10:
                return WeaponState.ACTIVE, "高成功率+高使用频率，推荐激活"

        return weapon.state, "当前状态合适"


# ────────────────────────────────────────────────────────────────────────────
# 统一武器加载器
# ────────────────────────────────────────────────────────────────────────────

class WeaponLoader:
    """
    统一武器加载器——从三种来源加载武器并注册到武器库。

    来源1: Python 模块（skills/*.py）→ 加载为 SKILL 类型
    来源2: YAML 文件（sops/templates/*.yaml, sops/skill_cards/*.yaml）→ 加载为 SOP 或 GENE 类型
    来源3: Store 条目（skill_gene:*, armory:registry）→ 加载为 GENE 或已有武器
    """

    def __init__(self, registry: ArmoryRegistry):
        self.registry = registry

    def load_from_module(self, module_name: str, category: WeaponCategory = WeaponCategory.UNKNOWN,
                         scenarios: List[str] = None) -> Optional[WeaponMetadata]:
        """
        从 Python 模块加载 Skill 武器。

        Args:
            module_name: 模块名（如 "skills.llm"）
            category: 功能域
            scenarios: 适用场景

        Returns:
            WeaponMetadata 或 None
        """
        try:
            import importlib
            module = importlib.import_module(module_name)

            # 提取模块中导出的 Skill 实例（如 call_llm_skill = Skill("call_llm", call_llm)）
            skills = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, Skill):
                    skills.append((attr_name, attr))

            if not skills:
                return None

            # 取第一个 Skill 作为代表（一个模块通常只导出一个主Skill）
            skill_name, skill = skills[0]
            weapon_id = f"skill:{skill.name}"

            # 构建元数据
            weapon = WeaponMetadata(
                id=weapon_id,
                name=skill.name,
                type=WeaponType.SKILL,
                category=category,
                applicable_scenarios=scenarios or [],
                source=f"module:{module_name}",
                created_from="manual",
                is_preset=True,  # 模块加载的视为预置
            )
            weapon._skill_instance = skill
            return weapon

        except Exception as e:
            return None

    def load_from_sop_yaml(self, yaml_path: str) -> Optional[WeaponMetadata]:
        """
        从 SOP YAML 文件加载 SOP 武器。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            WeaponMetadata 或 None
        """
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "stages" not in data:
                return None

            sop_id = data.get("sop_id", Path(yaml_path).stem)
            name = data.get("name", sop_id)
            output_type = data.get("output_type", "document")

            # 推断适用场景
            scenarios = []
            if "DEV" in sop_id:
                scenarios = ["代码开发", "技术实现"]
            elif "STR" in sop_id:
                scenarios = ["战略分析", "战略审视"]
            elif "OPS" in sop_id:
                scenarios = ["运营管理", "客户交付"]
            elif "MT" in sop_id:
                scenarios = ["内容创作", "文案生成"]

            # 推断依赖（SOP中引用的技能）
            dependencies = []
            for stage in data.get("stages", []):
                for skill in stage.get("skills", []):
                    dep_id = f"skill:{skill}"
                    if dep_id not in dependencies:
                        dependencies.append(dep_id)

            weapon = WeaponMetadata(
                id=f"sop:{sop_id}",
                name=name,
                type=WeaponType.SOP,
                category=WeaponCategory.EXECUTION,
                applicable_scenarios=scenarios,
                dependencies=dependencies,
                source=f"yaml:{yaml_path}",
                created_from="manual",
                is_preset=True,
            )
            return weapon

        except Exception as e:
            return None

    def load_from_skill_card(self, yaml_path: str) -> Optional[WeaponMetadata]:
        """
        从技能卡 YAML 加载 GENE 武器。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            WeaponMetadata 或 None
        """
        try:
            import yaml
            with open(yaml_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "intent" not in data:
                return None

            card_name = Path(yaml_path).stem
            weapon = WeaponMetadata(
                id=f"gene:{card_name}",
                name=card_name,
                type=WeaponType.GENE,
                category=WeaponCategory.COGNITIVE,
                applicable_scenarios=data.get("applicable_when", "").split(", ") if isinstance(data.get("applicable_when"), str) else [],
                not_applicable_scenarios=data.get("not_applicable_when", "").split(", ") if isinstance(data.get("not_applicable_when"), str) else [],
                source=f"yaml:{yaml_path}",
                created_from="manual",
                is_preset=True,
            )
            return weapon

        except Exception as e:
            return None

    def load_from_store(self, store: Store, prefix: str = "skill_gene:") -> List[WeaponMetadata]:
        """
        从 Store 加载 GENE 武器。

        Args:
            store: Store 实例
            prefix: 键前缀

        Returns:
            WeaponMetadata 列表
        """
        weapons = []
        if not hasattr(store, "list_keys"):
            return weapons

        for key in store.list_keys():
            if key.startswith(prefix):
                gene_data = store.load(key)
                if gene_data and isinstance(gene_data, dict):
                    gene_name = key[len(prefix):]
                    weapon = WeaponMetadata(
                        id=f"gene:{gene_name}",
                        name=gene_name,
                        type=WeaponType.GENE,
                        category=WeaponCategory.COGNITIVE,
                        applicable_scenarios=gene_data.get("applicable_scenarios", []),
                        source=f"store:{key}",
                        created_from="extracted",
                    )
                    weapons.append(weapon)
        return weapons

    def discover_all(self, project_root: str = ".",
                      skill_modules: List[str] = None,
                      sop_dirs: List[str] = None,
                      skill_card_dirs: List[str] = None) -> Dict[str, int]:
        """
        发现并加载所有武器。

        Args:
            project_root: 项目根目录
            skill_modules: 要扫描的 Skill 模块列表
            sop_dirs: SOP YAML 目录列表
            skill_card_dirs: 技能卡 YAML 目录列表

        Returns:
            {类型: 加载数量} 统计
        """
        stats = {"skill": 0, "sop": 0, "gene": 0, "total": 0}

        # 加载 Skill 模块
        if skill_modules:
            for module in skill_modules:
                weapon = self.load_from_module(module)
                if weapon and self.registry.register(weapon):
                    stats["skill"] += 1

        # 加载 SOP YAML
        if sop_dirs:
            for sop_dir in sop_dirs:
                path = Path(sop_dir)
                if path.exists():
                    for yaml_file in path.glob("*.yaml"):
                        weapon = self.load_from_sop_yaml(str(yaml_file))
                        if weapon and self.registry.register(weapon):
                            stats["sop"] += 1

        # 加载技能卡 YAML
        if skill_card_dirs:
            for card_dir in skill_card_dirs:
                path = Path(card_dir)
                if path.exists():
                    for yaml_file in path.glob("*.yaml"):
                        weapon = self.load_from_skill_card(str(yaml_file))
                        if weapon and self.registry.register(weapon):
                            stats["gene"] += 1

        stats["total"] = sum(stats.values()) - stats["total"]
        return stats


# ────────────────────────────────────────────────────────────────────────────
# 武器配发器（ArmoryDispatcher）
# ────────────────────────────────────────────────────────────────────────────

class ArmoryDispatcher:
    """
    武器配发器——从武器库为府兵配发武器。

    PHILOSOPHY: 府兵不自备武器，武器由朝廷兵器库统一配发。
    出征时领取，战后归还。但元数据（评分、使用次数）永久保留。
    """

    def __init__(self, registry: ArmoryRegistry):
        self.registry = registry

    def dispatch(self, weapon_id: str) -> Optional[Skill]:
        """
        为府兵配发武器。

        Args:
            weapon_id: 武器ID

        Returns:
            Skill 实例或 None
        """
        weapon = self.registry.get(weapon_id)
        if not weapon or not weapon.is_active:
            return None

        if weapon.type == WeaponType.SKILL and weapon._skill_instance:
            return weapon._skill_instance

        # TODO: 从模块动态加载（如果 _skill_instance 为 None）
        return None

    def dispatch_sop(self, sop_id: str) -> Optional[SOP]:
        """配发 SOP"""
        weapon = self.registry.get(f"sop:{sop_id}")
        if not weapon or not weapon.is_active:
            return None

        if weapon._sop_instance:
            return weapon._sop_instance

        # 从 YAML 加载
        if weapon.source.startswith("yaml:"):
            yaml_path = weapon.source[5:]
            try:
                return SOP.load_from_yaml(yaml_path)
            except Exception:
                pass
        return None

    def dispatch_for_task(self, task_description: str,
                          required_categories: List[WeaponCategory] = None) -> Dict[str, Any]:
        """
        根据任务描述配发完整武器套装。

        Returns:
            {
                "skills": {skill_name: Skill, ...},
                "sop": SOP,
                "recommended_weapons": [WeaponMetadata, ...],
                "reason": str
            }
        """
        # 军师推荐
        bundle = self.registry.recommend_bundle(task_description, required_categories)

        skills = {}
        for cat, weapons in bundle.items():
            for w in weapons:
                if w.type == WeaponType.SKILL:
                    skill = self.dispatch(w.id)
                    if skill:
                        skills[w.name] = skill

        # 推荐 SOP
        sop_candidates = self.registry.recommend(task_description, weapon_type=WeaponType.SOP, top_k=1)
        sop = None
        if sop_candidates:
            sop_weapon = sop_candidates[0]
            sop_id = sop_weapon.id.replace("sop:", "")
            sop = self.dispatch_sop(sop_id)

        return {
            "skills": skills,
            "sop": sop,
            "recommended_weapons": [w for ws in bundle.values() for w in ws],
            "reason": f"根据任务'{task_description}'配发 {len(skills)} 个Skill + SOP",
        }


# ────────────────────────────────────────────────────────────────────────────
# 便捷函数：获取全局武器库
# ────────────────────────────────────────────────────────────────────────────

_armory_registry: Optional[ArmoryRegistry] = None


def get_armory_registry(store: Optional[Store] = None) -> ArmoryRegistry:
    """获取武器库注册表（单例）"""
    global _armory_registry
    if _armory_registry is None:
        _armory_registry = ArmoryRegistry(store=store)
    return _armory_registry


def get_armory_dispatcher(store: Optional[Store] = None) -> ArmoryDispatcher:
    """获取武器配发器"""
    registry = get_armory_registry(store=store)
    return ArmoryDispatcher(registry)


def get_weapon_lifecycle(store: Optional[Store] = None) -> WeaponLifecycle:
    """获取武器生命周期管理器"""
    registry = get_armory_registry(store=store)
    return WeaponLifecycle(registry)


def get_weapon_loader(store: Optional[Store] = None) -> WeaponLoader:
    """获取武器加载器"""
    registry = get_armory_registry(store=store)
    return WeaponLoader(registry)


# ────────────────────────────────────────────────────────────────────────────
# V5.0 类型别名（在所有类定义之后声明）
# ────────────────────────────────────────────────────────────────────────────
# 这些别名使 V5.0 代码可以使用简洁命名，同时不破坏 V4.0 代码。
# Weapon → WeaponMetadata
# WeaponStatus → WeaponState
# FunctionDomain → WeaponCategory（超集，包含 V5.0 定义的 6 个功能域）

Weapon = WeaponMetadata
WeaponStatus = WeaponState
FunctionDomain = WeaponCategory


# ────────────────────────────────────────────────────────────────────────────
# V5.0 迁移工具
# ────────────────────────────────────────────────────────────────────────────

def migrate_skill_registry_to_armory(skill_registry, armory: ArmoryRegistry) -> int:
    """
    V5.0：将现有 SkillRegistry 中的技能迁移到武器注册表。

    此函数确保向后兼容——原有 SkillRegistry 功能不被破坏。
    迁移后 SkillRegistry 仍然可用，武器注册表获得 SKILL 类型武器的镜像。

    Args:
        skill_registry: SkillRegistry 实例（需有 _catalog 属性）
        armory: ArmoryRegistry 实例

    Returns:
        迁移数量
    """
    count = 0
    for skill_name in skill_registry._catalog:
        skill_info = skill_registry._catalog[skill_name]
        weapon = WeaponMetadata(
            id=f"skill:{skill_name}",
            name=skill_name,
            type=WeaponType.SKILL,
            category=WeaponCategory.COGNITIVE,
            description=skill_info.get("description", ""),
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
            source="migrated_from_skill_registry",
            created_from="manual",
        )
        if armory.register(weapon):
            count += 1
    return count
