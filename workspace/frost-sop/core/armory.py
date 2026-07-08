"""
FROST V4.0 核心——统一武器库（Armory）
PHILOSOPHY: 武器不是代码，武器是元数据驱动的能力单元。

所有家族资产（Skill、TACTIC、情报、免疫规则、平台绑定）统一为 Weapon。
Armory 是武器的唯一注册表、检索器和生命周期管理者。

武器分类（WeaponType）:
  SKILL  — 纯函数能力单元（如 call_llm, assemble_agent）
  TACTIC — 战术/标准操作流程（如 需求澄清SOP、父辈流程）
  SOP    — 向后兼容别名，同 TACTIC
  INTEL  — 情报产物（如 财务简报、客户简报）
  IMMUN  — 免疫规则（如 心跳阈值、熔断规则）
  BIND   — 平台绑定（如 deepseek, openai, local_gguf）
  GENE   — 能力基因（未归档的 Skill 模板）
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
# 武器类型枚举
# ────────────────────────────────────────────────────────────────────────────


class WeaponType(Enum):
    """武器类型：所有家族资产的原子分类"""

    SKILL = "skill"      # 纯函数能力单元（如 call_llm）
    TACTIC = "tactic"    # 战术/标准操作流程（如 需求澄清、父辈流程）
    SOP = "sop"          # 向后兼容：同 TACTIC
    INTEL = "intel"      # 情报产物
    IMMUN = "immun"      # 免疫规则
    BIND = "bind"        # 平台绑定
    GENE = "gene"        # 能力基因


# ────────────────────────────────────────────────────────────────────────────
# 武器分类（功能域）
# ────────────────────────────────────────────────────────────────────────────


class WeaponCategory(Enum):
    """武器功能域：军师检索时的分类维度"""

    COGNITIVE = "cognitive"      # 认知能力
    EXECUTION = "execution"      # 执行能力
    GOVERNANCE = "governance"    # 治理能力
    STRATEGY = "strategy"        # 战略能力
    IMMUNE = "immune"            # 免疫能力
    ORCHESTRATE = "orchestrate"  # 编排能力
    SEARCH = "search"            # 搜索能力
    COMMUNICATION = "comm"       # 通信能力
    UNKNOWN = "unknown"          # 未分类


# ────────────────────────────────────────────────────────────────────────────
# 武器生命周期状态
# ────────────────────────────────────────────────────────────────────────────


class WeaponState(Enum):
    """武器生命周期状态"""

    DISCOVERED = "discovered"    # 狩猎发现，尚未验证
    VALIDATED = "validated"      # 格式/结构校验通过
    TRIALED = "trialed"          # 小规模试炼通过
    ARCHIVED = "archived"        # 已归档入库
    ACTIVE = "active"            # 当前活跃使用
    DEPRECATED = "deprecated"    # 标记废弃
    RETIRED = "retired"          # 已退役


# ────────────────────────────────────────────────────────────────────────────
# 武器元数据
# ────────────────────────────────────────────────────────────────────────────


@dataclass
class WeaponMetadata:
    """
    武器元数据——武器库的唯一入口。
    V7.4 新增：进化机制（evolution）、连续失败追踪（consecutive_failures）
    """

    # ── 基础标识 ──
    id: str                           # 唯一标识
    name: str                         # 人类可读名称
    type: WeaponType                  # 武器类型
    version: str = "1.0"              # 语义版本
    category: WeaponCategory = WeaponCategory.UNKNOWN

    # ── 场景匹配 ──
    applicable_scenarios: list[str] = field(default_factory=list)
    not_applicable_scenarios: list[str] = field(default_factory=list)

    # ── 依赖 ──
    dependencies: list[str] = field(default_factory=list)
    required_platforms: list[str] = field(default_factory=list)

    # ── 标签与描述 ──
    tags: list[str] = field(default_factory=list)
    description: str = ""

    # ── 健康与进化（V7.4）──
    health_score: float = 50.0        # 0-100，初始50
    usage_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0     # V7.4: 连续失败次数
    avg_execution_time: float | None = None
    last_used: str | None = None

    # ── 进化历史（V7.4）──
    evolution_history: list[dict] = field(default_factory=list)
    evolution_count: int = 0

    # ── 来源 ──
    created_from: str = "manual"      # manual | extracted | synthesized | hunted | evolved
    source: str = ""
    source_url: str | None = None
    confidence: float = 1.0

    # ── 生命周期 ──
    state: WeaponState = WeaponState.ACTIVE
    is_active: bool = True
    is_preset: bool = False

    # ── 时序 ──
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    archived_at: str | None = None
    deprecated_at: str | None = None
    retired_at: str | None = None
    activated_at: str | None = None

    # ── 扩展 ──
    card: SkillCard | None = None
    skill_node_id: str | None = None
    capability_profile: Any | None = None
    _skill_instance: Skill | None = field(default=None, repr=False)
    _sop_instance: SOP | None = field(default=None, repr=False)

    def __post_init__(self):
        total = self.success_count + self.failure_count
        self._success_rate = self.success_count / total if total > 0 else None

    @property
    def success_rate(self) -> float | None:
        total = self.success_count + self.failure_count
        return self.success_count / total if total > 0 else None

    @property
    def is_ready(self) -> bool:
        return self.state == WeaponState.ACTIVE and self.health_score >= 30

    # ── V7.4: 进化触发条件 ──
    @property
    def needs_evolution(self) -> bool:
        """是否需要进化：健康评分<30 或 连续失败>=3次"""
        return self.health_score < 30 or self.consecutive_failures >= 3

    @property
    def needs_retirement(self) -> bool:
        """是否需要退役：健康评分<15 且 非预置"""
        return self.health_score < 15 and not self.is_preset

    # ── 核心方法 ──

    def record_usage(self, success: bool, execution_time: float | None = None):
        """记录使用，更新健康评分和连续失败计数（V7.4）"""
        self.usage_count += 1
        self.last_used = datetime.now().isoformat()

        if success:
            self.success_count += 1
            self.consecutive_failures = 0  # 重置连续失败
        else:
            self.failure_count += 1
            self.consecutive_failures += 1  # 累积连续失败

        # 健康评分公式
        import math
        rate = self.success_rate or 0.5
        freq = math.log(self.usage_count + 1) / math.log(101)
        recency = 1.0
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

    def evolve(self, trigger: str, changes: dict) -> "WeaponMetadata":
        """
        V7.4: 武器进化。

        创建新版本的自己，记录进化历史。
        原版本标记为 DEPRECATED，新版本状态为 TRIALED（重新试炼）。

        Args:
            trigger: 进化触发原因
            changes: 变更内容（如 {"description": "新描述", "applicable_scenarios": [...]}）

        Returns:
            进化后的新 WeaponMetadata（尚未注册到武器库）
        """
        # 解析当前版本号并递增
        parts = self.version.split(".")
        try:
            parts[-1] = str(int(parts[-1]) + 1)
        except ValueError:
            parts = ["1", "0", "1"]
        new_version = ".".join(parts)

        # 记录进化历史
        evolution_record = {
            "from_version": self.version,
            "to_version": new_version,
            "trigger": trigger,
            "changes": changes,
            "timestamp": datetime.now().isoformat(),
            "health_before": self.health_score,
            "consecutive_failures": self.consecutive_failures,
        }

        # 创建新实例（深拷贝 + 修改）
        new_data = self.to_dict()
        new_data["version"] = new_version
        new_data["created_from"] = "evolved"
        new_data["state"] = WeaponState.TRIALED.value  # 重新试炼
        new_data["health_score"] = 50.0  # 重置健康评分
        new_data["consecutive_failures"] = 0  # 重置连续失败
        new_data["usage_count"] = 0
        new_data["success_count"] = 0
        new_data["failure_count"] = 0
        new_data["evolution_count"] = self.evolution_count + 1
        new_data["evolution_history"] = list(self.evolution_history) + [evolution_record]
        new_data["updated_at"] = datetime.now().isoformat()

        # 应用变更
        for key, val in changes.items():
            if key in new_data:
                new_data[key] = val

        # 移除运行时实例
        new_data.pop("_skill_instance", None)
        new_data.pop("_sop_instance", None)

        return WeaponMetadata.from_dict(new_data)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.pop("_skill_instance", None)
        d.pop("_sop_instance", None)
        d["type"] = self.type.value
        d["category"] = self.category.value
        d["state"] = self.state.value
        if self.card:
            d["card"] = asdict(self.card)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WeaponMetadata":
        data = dict(data)
        data["type"] = WeaponType(data["type"])
        data["category"] = WeaponCategory(data.get("category", "unknown"))
        data["state"] = WeaponState(data.get("state", "active"))
        data.pop("_skill_instance", None)
        data.pop("_sop_instance", None)
        return cls(**data)

    def __hash__(self):
        return hash(self.id)

    def __eq__(self, other):
        return isinstance(other, WeaponMetadata) and self.id == other.id


# ────────────────────────────────────────────────────────────────────────────
# 武器库注册表（ArmoryRegistry）
# ────────────────────────────────────────────────────────────────────────────


class ArmoryRegistry:
    """武器库注册表——所有武器的统一索引。"""

    def __init__(self, store: Store | None = None):
        self._store = store
        self._weapons: dict[str, WeaponMetadata] = {}
        self._by_type: dict[WeaponType, set[str]] = {t: set() for t in WeaponType}
        self._by_category: dict[WeaponCategory, set[str]] = {c: set() for c in WeaponCategory}
        self._by_scenario: dict[str, set[str]] = {}
        self._by_state: dict[WeaponState, set[str]] = {s: set() for s in WeaponState}
        self._dependents: dict[str, set[str]] = {}

        if store:
            self._load_from_store()

    def _add_to_indexes(self, weapon: WeaponMetadata):
        self._by_type[weapon.type].add(weapon.id)
        self._by_category[weapon.category].add(weapon.id)
        self._by_state[weapon.state].add(weapon.id)
        for scenario in weapon.applicable_scenarios:
            self._by_scenario.setdefault(scenario, set()).add(weapon.id)
        for dep in weapon.dependencies:
            self._dependents.setdefault(dep, set()).add(weapon.id)

    def _remove_from_indexes(self, weapon: WeaponMetadata):
        self._by_type[weapon.type].discard(weapon.id)
        self._by_category[weapon.category].discard(weapon.id)
        self._by_state[weapon.state].discard(weapon.id)
        for scenario in weapon.applicable_scenarios:
            self._by_scenario.get(scenario, set()).discard(weapon.id)
        for dep in weapon.dependencies:
            self._dependents.get(dep, set()).discard(weapon.id)

    def _load_from_store(self):
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
                pass

    def _persist_to_store(self):
        if not self._store:
            return
        data = {wid: w.to_dict() for wid, w in self._weapons.items()}
        self._store.save("armory:registry", data)

    # ── 注册与注销 ──

    def register(self, weapon: WeaponMetadata) -> bool:
        existing = self._weapons.get(weapon.id)
        if existing:
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
        weapon = self._weapons.get(weapon_id)
        if not weapon or weapon.is_preset:
            return False
        self._remove_from_indexes(weapon)
        del self._weapons[weapon_id]
        self._persist_to_store()
        return True

    @staticmethod
    def _compare_version(v1: str, v2: str) -> int:
        def parse(v):
            return [int(x) for x in v.split(".")]
        a, b = parse(v1), parse(v2)
        for x, y in zip(a, b):
            if x != y:
                return 1 if x > y else -1
        return len(a) - len(b)

    # ── 检索 ──

    def get(self, weapon_id: str) -> WeaponMetadata | None:
        return self._weapons.get(weapon_id)

    def find_by_type(self, weapon_type: WeaponType, state: WeaponState = None) -> list[WeaponMetadata]:
        ids = self._by_type.get(weapon_type, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_category(self, category: WeaponCategory, state: WeaponState = None) -> list[WeaponMetadata]:
        ids = self._by_category.get(category, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_scenario(self, scenario: str, state: WeaponState = None) -> list[WeaponMetadata]:
        ids = self._by_scenario.get(scenario, set())
        if state:
            ids = ids & self._by_state.get(state, set())
        return [self._weapons[wid] for wid in ids if wid in self._weapons]

    def find_by_keyword(self, keyword: str, state: WeaponState = None) -> list[WeaponMetadata]:
        """按关键词模糊搜索（名称、场景、描述、标签）"""
        results = []
        keyword_lower = keyword.lower()
        # 分词：先按空格/逗号拆分，再对长词逐字拆分（支持中文单字匹配）
        raw_words = keyword_lower.replace("，", " ").replace(",", " ").split()
        query_words = set()
        for w in raw_words:
            query_words.add(w)
            if len(w) > 2 and any('\u4e00' <= c <= '\u9fff' for c in w):
                # 中文长词额外按单字拆分
                for c in w:
                    if '\u4e00' <= c <= '\u9fff':
                        query_words.add(c)

        for w in self._weapons.values():
            if state and w.state != state:
                continue

            # 收集所有可搜索文本
            searchable = [w.name.lower(), w.id.lower(), w.description.lower()]
            searchable.extend(s.lower() for s in w.applicable_scenarios)
            searchable.extend(t.lower() for t in w.tags)
            searchable_text = " ".join(searchable)

            # 匹配策略
            match = False
            # 1. 完整子串匹配
            if keyword_lower in searchable_text:
                match = True
            # 2. 查询词匹配（至少2个字符的英文词，或任意中文字）
            if not match:
                for qw in query_words:
                    if len(qw) >= 2 or ('\u4e00' <= qw <= '\u9fff'):
                        if qw in searchable_text:
                            match = True
                            break

            if match:
                results.append(w)
        return results
        """按关键词模糊搜索（名称、场景、描述、标签）"""
        results = []
        keyword_lower = keyword.lower()
        # 分词：中文按字/词，英文按空格
        query_words = set(keyword_lower.replace("，", " ").replace(",", " ").split())

        for w in self._weapons.values():
            if state and w.state != state:
                continue

            # 收集所有可搜索文本
            searchable = [w.name.lower(), w.id.lower(), w.description.lower()]
            searchable.extend(s.lower() for s in w.applicable_scenarios)
            searchable.extend(t.lower() for t in w.tags)
            searchable_text = " ".join(searchable)

            # 匹配：完整子串 或 任一查询词出现在可搜索文本中
            match = keyword_lower in searchable_text
            if not match:
                match = any(qw in searchable_text for qw in query_words if len(qw) >= 2)

            if match:
                results.append(w)
        return results
        results = []
        keyword_lower = keyword.lower()
        for w in self._weapons.values():
            if state and w.state != state:
                continue
            if (keyword_lower in w.name.lower()
                or any(keyword_lower in s.lower() for s in w.applicable_scenarios)
                or keyword_lower in w.id.lower()
                or keyword_lower in w.description.lower()):
                results.append(w)
        return results

    # ── V7.4: 场景驱动推荐 ──

    def recommend_for_task(self, task_description: str, top_k: int = 3) -> list[WeaponMetadata]:
        """
        V7.4: 府兵自主决策——为任务推荐最优武器。

        评分公式：score = health_score × success_rate × recency_bonus × category_match
        """
        import math

        # 1. 关键词匹配候选
        candidates = self.find_by_keyword(task_description, state=WeaponState.ACTIVE)
        candidates = [w for w in candidates if w.is_ready]

        if not candidates:
            return []

        # 2. 评分排序
        now = datetime.now()
        scored = []
        for w in candidates:
            # 基础分
            health = w.health_score / 100.0
            rate = w.success_rate or 0.5

            # 时效奖励（最近7天内使用有加成）
            recency_bonus = 1.0
            if w.last_used:
                try:
                    last = datetime.fromisoformat(w.last_used.replace("Z", "+00:00"))
                    days = (now - last).days
                    if days < 7:
                        recency_bonus = 1.0 + (7 - days) * 0.05
                except Exception:
                    pass

            # 类别匹配（任务描述中的关键词与场景匹配度）
            scenario_match = 0
            for scenario in w.applicable_scenarios:
                if any(word in scenario.lower() for word in task_description.lower().split()):
                    scenario_match += 1
            category_match = 1.0 + min(scenario_match * 0.2, 0.5)

            # 使用频率奖励（用过的武器更可靠）
            freq_bonus = 1.0 + math.log(w.usage_count + 1) * 0.1

            score = health * rate * recency_bonus * category_match * freq_bonus
            scored.append((w, score))

        # 3. 按分数降序，取 top_k
        scored.sort(key=lambda x: x[1], reverse=True)
        return [w for w, _ in scored[:top_k]]

    def recommend_bundle_for_task(self, task_description: str) -> dict[str, Any]:
        """
        V7.4: 为任务推荐完整的武器套装（SKILL + TACTIC）。
        """
        # 推荐 SKILL
        skills = self.recommend_for_task(f"{task_description} skill", top_k=2)
        skills = [w for w in skills if w.type == WeaponType.SKILL]

        # 推荐 TACTIC
        tactics = self.recommend_for_task(f"{task_description} tactic sop", top_k=1)
        tactics = [w for w in tactics if w.type in (WeaponType.TACTIC, WeaponType.SOP)]

        return {
            "skills": skills,
            "tactics": tactics,
            "primary": skills[0] if skills else None,
            "tactic": tactics[0] if tactics else None,
            "task": task_description,
        }

    # ── V7.4: 进化管理 ──

    def evolve_weapon(self, weapon_id: str, trigger: str, changes: dict) -> WeaponMetadata | None:
        """
        V7.4: 触发武器进化。

        1. 旧版本标记为 DEPRECATED
        2. 创建新版本并注册
        3. 返回新版本
        """
        old = self._weapons.get(weapon_id)
        if not old:
            return None
        if old.is_preset:
            return None  # 预置武器不自动进化

        # 创建新版本
        new_weapon = old.evolve(trigger, changes)
        new_id = f"{old.id}@v{new_weapon.version}"
        new_weapon.id = new_id

        # 旧版本标记废弃
        self._remove_from_indexes(old)
        old.state = WeaponState.DEPRECATED
        old.deprecated_at = datetime.now().isoformat()
        old.is_active = False
        self._add_to_indexes(old)

        # 注册新版本
        self._weapons[new_id] = new_weapon
        self._add_to_indexes(new_weapon)
        self._persist_to_store()

        return new_weapon

    def check_evolution_triggers(self) -> list[tuple[str, str]]:
        """
        V7.4: 检查所有武器的进化触发条件。

        Returns:
            [(weapon_id, trigger_reason), ...]
        """
        triggers = []
        for wid, w in self._weapons.items():
            if w.is_preset:
                continue
            if w.state not in (WeaponState.ACTIVE, WeaponState.TRIALED):
                continue
            if w.needs_retirement:
                triggers.append((wid, f"health={w.health_score}, 建议退役"))
            elif w.needs_evolution:
                triggers.append((wid, f"health={w.health_score}, consecutive_failures={w.consecutive_failures}, 建议进化"))
        return triggers

    # ── 统计 ──

    def get_stats(self) -> dict[str, Any]:
        total = len(self._weapons)
        by_type = {t.value: len(self._by_type[t]) for t in WeaponType}
        by_category = {c.value: len(self._by_category[c]) for c in WeaponCategory}
        by_state = {s.value: len(self._by_state[s]) for s in WeaponState}
        avg_health = sum(w.health_score for w in self._weapons.values()) / total if total else 0

        # V7.4: 进化统计
        evolving = sum(1 for w in self._weapons.values() if w.needs_evolution)
        retiring = sum(1 for w in self._weapons.values() if w.needs_retirement)

        return {
            "total_weapons": total,
            "by_type": by_type,
            "by_category": by_category,
            "by_state": by_state,
            "avg_health_score": round(avg_health, 1),
            "needs_evolution": evolving,
            "needs_retirement": retiring,
            "top_weapons": [
                w.id for w in sorted(self._weapons.values(), key=lambda x: x.health_score, reverse=True)[:5]
            ],
        }

    def list_all(self, weapon_type: WeaponType = None, state: WeaponState = None) -> list[WeaponMetadata]:
        weapons = list(self._weapons.values())
        if weapon_type:
            weapons = [w for w in weapons if w.type == weapon_type]
        if state:
            weapons = [w for w in weapons if w.state == state]
        return weapons

    def record_usage(self, weapon_id: str, success: bool) -> None:
        weapon = self._weapons.get(weapon_id)
        if not weapon:
            raise ValueError(f"武器 {weapon_id} 不存在")
        weapon.record_usage(success)
        self._persist_to_store()

    def count(self) -> int:
        return len(self._weapons)


# ────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ────────────────────────────────────────────────────────────────────────────

_armory_registry: ArmoryRegistry | None = None


def get_armory_registry(store: Store | None = None) -> ArmoryRegistry:
    global _armory_registry
    if _armory_registry is None:
        _armory_registry = ArmoryRegistry(store=store)
    return _armory_registry


Weapon = WeaponMetadata
WeaponStatus = WeaponState
FunctionDomain = WeaponCategory
