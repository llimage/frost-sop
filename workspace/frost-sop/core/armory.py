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

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from core.skill import Skill
from core.skill_graph import SkillCard
from core.sop import SOP
from core.store import Store

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

    SKILL = "skill"  # 纯函数能力单元（如 call_llm）
    SOP = "sop"  # 标准操作程序（如 DEV-001）
    INTEL = "intel"  # 情报产物（如 财务简报、客户简报）
    IMMUN = "immun"  # 免疫规则（如 心跳阈值、熔断规则）
    BIND = "bind"  # 平台绑定（如 deepseek, openai）
    GENE = "gene"  # 能力基因（未归档的 Skill 模板）


# ────────────────────────────────────────────────────────────────────────────
# 武器分类（功能域）
# ────────────────────────────────────────────────────────────────────────────


class WeaponCategory(Enum):
    """武器功能域：军师检索时的分类维度"""

    COGNITIVE = "cognitive"  # 认知能力（LLM调用、推理、分析）
    EXECUTION = "execution"  # 执行能力（文件操作、代码生成、部署）
    GOVERNANCE = "governance"  # 治理能力（审计、合规、校验、权限）
    STRATEGY = "strategy"  # 战略能力（分析、简报、预测、狩猎）
    IMMUNE = "immune"  # 免疫能力（监控、熔断、告警、恢复）
    ORCHESTRATE = "orchestrate"  # 编排能力（spawn、merge、emit、调度）
    SEARCH = "search"  # 搜索能力（外部搜索、比对、检索）
    COMMUNICATION = "comm"  # 通信能力（通知、报告、简报、面板）
    UNKNOWN = "unknown"  # 未分类


# ────────────────────────────────────────────────────────────────────────────
# 武器生命周期状态
# ────────────────────────────────────────────────────────────────────────────


class WeaponState(Enum):
    """武器生命周期状态"""

    DISCOVERED = "discovered"  # 狩猎发现，尚未验证
    VALIDATED = "validated"  # 格式/结构校验通过
    TRIALED = "trialed"  # 小规模试炼通过
    ARCHIVED = "archived"  # 已归档入库，可供配发
    ACTIVE = "active"  # 当前活跃使用
    DEPRECATED = "deprecated"  # 标记废弃，不再推荐
    RETIRED = "retired"  # 已退役，不可使用


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
    id: str  # 唯一标识（如 "skill:call_llm", "sop:DEV-001"）
    name: str  # 人类可读名称
    type: WeaponType  # 武器类型
    version: str = "1.0"  # 语义版本
    category: WeaponCategory = WeaponCategory.UNKNOWN  # 功能域

    # 适用场景（军师检索时匹配）
    applicable_scenarios: list[str] = field(default_factory=list)
    # 如：["代码生成", "LLM推理", "文档分析"]

    # 不适用场景（防止误配发）
    not_applicable_scenarios: list[str] = field(default_factory=list)

    # 依赖关系
    dependencies: list[str] = field(default_factory=list)  # 依赖的武器ID列表
    required_platforms: list[str] = field(default_factory=list)  # 需要平台列表

    # V5.0 新增：标签与描述
    tags: list[str] = field(default_factory=list)  # 标签（用于搜索）
    description: str = ""  # 人类可读描述

    # 健康评分（自然选择驱动）
    health_score: float = 50.0  # 健康评分 0-100，初始50
    usage_count: int = 0  # 使用次数
    success_count: int = 0  # 成功次数
    failure_count: int = 0  # 失败次数
    avg_execution_time: float | None = None  # 平均执行时间(秒)
    last_used: str | None = None  # 最后使用时间（ISO格式）

    # 来源与版本
    created_from: str = "manual"  # "manual" | "extracted" | "synthesized" | "hunted"
    source: str = ""  # 来源标识（文件路径、URL等）
    source_url: str | None = None  # 外部来源URL（狩猎产物）
    confidence: float = 1.0  # 置信度 0.0-1.0

    # 生命周期
    state: WeaponState = WeaponState.ACTIVE
    is_active: bool = True  # 是否激活
    is_preset: bool = False  # 是否为预置武器（不可删除）

    # 时序
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archived_at: str | None = None
    deprecated_at: str | None = None
    retired_at: str | None = None

    # V5.0 新增：激活时间（与 state=ACTIVE 配合使用）
    activated_at: str | None = None

    # 扩展：武器卡（V4.0 技能图）
    card: SkillCard | None = None  # 如果携带技能卡，记录详细信息
    skill_node_id: str | None = None  # 关联的技能图节点ID

    # V5.0 P1：能力画像（能力元数据层）
    capability_profile: Any | None = None  # CapabilityProfile 实例（避免循环导入用 Any）

    # 扩展：适配器（运行时使用）
    _skill_instance: Skill | None = field(default=None, repr=False)  # 运行时Skill实例
    _sop_instance: SOP | None = field(default=None, repr=False)  # 运行时SOP实例

    def __post_init__(self):
        """自动计算成功率"""
        total = self.success_count + self.failure_count
        if total > 0:
            self._success_rate = self.success_count / total
        else:
            self._success_rate = None

    @property
    def success_rate(self) -> float | None:
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

    def record_usage(self, success: bool, execution_time: float | None = None):
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

    def to_dict(self) -> dict[str, Any]:
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
    def from_dict(cls, data: dict[str, Any]) -> WeaponMetadata:
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

    def __init__(self, store: Store | None = None):
        """
        初始化武器库。

        Args:
            store: 持久化 Store。如果提供，武器从 Store 加载；否则从内存运行。
        """
        self._store = store
        self._weapons: dict[str, WeaponMetadata] = {}  # id -> WeaponMetadata
        self._by_type: dict[WeaponType, set[str]] = {t: set() for t in WeaponType}
        self._by_category: dict[WeaponCategory, set[str]] = {c: set() for c in WeaponCategory}
        self._by_scenario: dict[str, set[str]] = {}  # 场景 -> 武器ID集合
        self._by_state: dict[WeaponState, set[str]] = {s: set() for s in WeaponState}
        self._dependents: dict[str, set[str]] = {}  # 被依赖关系：武器ID -> 依赖它的武器ID集合

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
        for _wid, wdata in data.items():
            try:
                weapon = WeaponMetadata.from_dict(wdata)
                self._weapons[weapon.id] = weapon
                self._add_to_indexes(weapon)
            except Exception:
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
        for x, y in zip(a, b):  # noqa: B905
            if x != y:
                return 1 if x > y else -1
        return len(a) - len(b)

    # ── 检索 ─────────────────────────────────────────────────────────────────

    def get(self, weapon_id: str) -> WeaponMetadata | None:
        """按ID获取武器"""
        return self._weapons.get(weapon_id)

    def find_by_type(
        self, weapon_type: WeaponType, state: WeaponState = None
    ) -> list[WeaponMetadata]:
        """按类型检索武器"""
        ids = self._by_type.get(weapon_type, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_category(
        self, category: WeaponCategory, state: WeaponState = None
    ) -> list[WeaponMetadata]:
        """按功能域检索武器"""
        ids = self._by_category.get(category, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_scenario(self, scenario: str, state: WeaponState = None) -> list[WeaponMetadata]:
        """按场景检索武器"""
        ids = self._by_scenario.get(scenario, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_scenarios(
        self, scenarios: list[str], match_all: bool = False, state: WeaponState = None
    ) -> list[WeaponMetadata]:
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
        matched_ids = set.intersection(*result_sets) if match_all else set.union(*result_sets)
        return [self._weapons[wid] for wid in matched_ids if wid in self._weapons]

    def find_by_keyword(self, keyword: str, state: WeaponState = None) -> list[WeaponMetadata]:
        """按关键词模糊搜索（名称、场景、描述）"""
        results = []
        keyword_lower = keyword.lower()
        for _wid, w in self._weapons.items():
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

    def find_dependents(self, weapon_id: str) -> list[WeaponMetadata]:
        """查找依赖指定武器的所有武器"""
        ids = self._dependents.get(weapon_id, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_health_score(
        self, min_score: float = 0, max_score: float = 100, weapon_type: WeaponType = None
    ) -> list[WeaponMetadata]:
        """按健康评分范围检索武器"""
        results = []
        for w in self._weapons.values():
            if weapon_type and w.type != weapon_type:
                continue
            if min_score <= w.health_score <= max_score:
                results.append(w)
        return results

    # ── 排序与推荐 ──────────────────────────────────────────────────────────

    def recommend(
        self,
        requirement: str,
        weapon_type: WeaponType = None,
        top_k: int = 5,
        min_health_score: float = 30.0,
    ) -> list[WeaponMetadata]:
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
        candidates.sort(
            key=lambda w: (w.health_score, w.usage_count, w.success_rate or 0), reverse=True
        )

        return candidates[:top_k]

    def recommend_bundle(
        self, task_description: str, required_categories: list[WeaponCategory] = None
    ) -> dict[str, list[WeaponMetadata]]:
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

    def get_stats(self) -> dict[str, Any]:
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
            "top_weapons": [
                w.id
                for w in sorted(self._weapons.values(), key=lambda x: x.health_score, reverse=True)[
                    :5
                ]
            ],
        }

    def list_all(
        self, weapon_type: WeaponType = None, state: WeaponState = None
    ) -> list[WeaponMetadata]:
        """列出所有武器（可选过滤）"""
        weapons = list(self._weapons.values())
        if weapon_type:
            weapons = [w for w in weapons if w.type == weapon_type]
        if state:
            weapons = [w for w in weapons if w.state == state]
        return weapons

    # ── V5.0 便捷方法 ──────────────────────────────────────────────────────

    def list_active(self) -> list[WeaponMetadata]:
        """V5.0：列出所有可配发的武器（is_ready 为 True 的武器）"""
        return [w for w in self._weapons.values() if w.is_ready]

    def search_by_tags(self, tags: list[str]) -> list[WeaponMetadata]:
        """V5.0：按标签搜索武器（包含任一标签即匹配）"""
        return [w for w in self._weapons.values() if any(t in w.tags for t in tags)]

    def search_by_domain(self, domain: WeaponCategory) -> list[WeaponMetadata]:
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

    def find_similar(
        self, weapon_id: str, top_k: int = 5, min_similarity: float = 0.1
    ) -> list[WeaponMetadata]:
        """V5.0 P1：查找与指定武器能力相似的其他武器"""
        from core.capability_meta import CapabilityComparator

        results = CapabilityComparator.find_similar(self, weapon_id, top_k, min_similarity)
        return [w for w, _ in results]



# WeaponLifecycle, WeaponLoader, ArmoryDispatcher 已拆分至 core/armory_lifecycle.py
# 保持向后兼容：便捷函数内部使用延迟导入，避免循环依赖




# ────────────────────────────────────────────────────────────────────────────
# 便捷函数：获取全局武器库
# ────────────────────────────────────────────────────────────────────────────

_armory_registry: ArmoryRegistry | None = None


def get_armory_registry(store: Store | None = None) -> ArmoryRegistry:
    """获取武器库注册表（单例）"""
    global _armory_registry
    if _armory_registry is None:
        _armory_registry = ArmoryRegistry(store=store)
    return _armory_registry


def get_armory_dispatcher(store: Store | None = None) -> ArmoryDispatcher:  # noqa: F821
    """获取武器配发器（延迟导入，避免循环依赖）"""
    from core.armory_lifecycle import ArmoryDispatcher  # noqa: E402

    registry = get_armory_registry(store=store)
    return ArmoryDispatcher(registry)


def get_weapon_lifecycle(store: Store | None = None) -> WeaponLifecycle:  # noqa: F821
    """获取武器生命周期管理器（延迟导入，避免循环依赖）"""
    from core.armory_lifecycle import WeaponLifecycle  # noqa: E402

    registry = get_armory_registry(store=store)
    return WeaponLifecycle(registry)


def get_weapon_loader(store: Store | None = None) -> WeaponLoader:  # noqa: F821
    """获取武器加载器（延迟导入，避免循环依赖）"""
    from core.armory_lifecycle import WeaponLoader  # noqa: E402

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
