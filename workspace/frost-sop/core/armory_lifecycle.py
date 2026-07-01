"""
FROST V4.0 — 武器生命周期、加载与配发（从 armory.py 拆分）

包含:
  - WeaponLifecycle: 管理武器从发现到退役的完整状态流转
  - WeaponLoader: 从三种来源（Python模块/YAML/Store）加载武器并注册到武器库
  - ArmoryDispatcher: 从武器库为府兵配发武器
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from core.path_safety import safe_open
from core.skill import Skill
from core.sop import SOP
from core.store import Store

if TYPE_CHECKING:
    from core.armory import ArmoryRegistry, WeaponCategory, WeaponMetadata, WeaponState


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

    def transition(
        self, weapon_id: str, to_state: WeaponState, reason: str = ""
    ) -> tuple[bool, str]:
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

        from core.armory import WeaponState

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

        return (
            True,
            f"武器 {weapon_id} 从 {from_state.value} 转换为 {to_state.value}。原因: {reason}",
        )

    def _check_transition_rules(
        self, weapon: WeaponMetadata, from_state: WeaponState, to_state: WeaponState
    ) -> tuple[bool, str]:
        """检查状态转换规则"""
        from core.armory import WeaponState

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
        if to_state == WeaponState.TRIALED and weapon.usage_count < 1:
            # 试炼需要：至少试炼1次（简化）
            return False, "试炼条件不满足：usage_count < 1"

        if to_state == WeaponState.ACTIVE:
            # 激活需要：已归档且健康评分≥30
            if weapon.state != WeaponState.ARCHIVED:
                return False, "激活需要：先归档到武器库"
            if weapon.health_score < 30:
                return False, f"激活条件不满足：健康评分 {weapon.health_score} < 30"

        return True, "OK"

    def auto_evaluate(self, weapon_id: str) -> tuple[WeaponState, str]:
        """
        自动评估武器状态，返回推荐状态。

        评估规则：
        - 使用频率连续30天为0 + 非预置 → DEPRECATED
        - 健康评分<20 + 非预置 → RETIRED
        - 成功率>80% + 使用>10次 → 推荐升级为 ACTIVE（如果当前是 ARCHIVED）
        """
        from core.armory import WeaponState

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

        if (
            weapon.state == WeaponState.ARCHIVED
            and weapon.success_rate
            and weapon.success_rate > 0.8
            and weapon.usage_count >= 10
        ):
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

    def load_from_module(
        self,
        module_name: str,
        category: WeaponCategory = None,
        scenarios: list[str] = None,
    ) -> WeaponMetadata | None:
        """
        从 Python 模块加载 Skill 武器。

        Args:
            module_name: 模块名（如 "skills.llm"）
            category: 功能域
            scenarios: 适用场景

        Returns:
            WeaponMetadata 或 None
        """
        from core.armory import WeaponCategory, WeaponMetadata, WeaponType

        if category is None:
            category = WeaponCategory.UNKNOWN

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

        except Exception:
            return None

    def load_from_sop_yaml(self, yaml_path: str) -> WeaponMetadata | None:
        """
        从 SOP YAML 文件加载 SOP 武器。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            WeaponMetadata 或 None
        """
        from core.armory import WeaponCategory, WeaponMetadata, WeaponType

        try:
            import yaml

            with safe_open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "stages" not in data:
                return None

            sop_id = data.get("sop_id", Path(yaml_path).stem)
            name = data.get("name", sop_id)

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

        except Exception:
            return None

    def load_from_skill_card(self, yaml_path: str) -> WeaponMetadata | None:
        """
        从技能卡 YAML 加载 GENE 武器。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            WeaponMetadata 或 None
        """
        from core.armory import WeaponCategory, WeaponMetadata, WeaponType

        try:
            import yaml

            with safe_open(yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            if not data or "intent" not in data:
                return None

            card_name = Path(yaml_path).stem
            weapon = WeaponMetadata(
                id=f"gene:{card_name}",
                name=card_name,
                type=WeaponType.GENE,
                category=WeaponCategory.COGNITIVE,
                applicable_scenarios=data.get("applicable_when", "").split(", ")
                if isinstance(data.get("applicable_when"), str)
                else [],
                not_applicable_scenarios=data.get("not_applicable_when", "").split(", ")
                if isinstance(data.get("not_applicable_when"), str)
                else [],
                source=f"yaml:{yaml_path}",
                created_from="manual",
                is_preset=True,
            )
            return weapon

        except Exception:
            return None

    def load_from_store(self, store: Store, prefix: str = "skill_gene:") -> list[WeaponMetadata]:
        """
        从 Store 加载 GENE 武器。

        Args:
            store: Store 实例
            prefix: 键前缀

        Returns:
            WeaponMetadata 列表
        """
        from core.armory import WeaponCategory, WeaponMetadata, WeaponType

        weapons = []
        if not hasattr(store, "list_keys"):
            return weapons

        for key in store.list_keys():
            if key.startswith(prefix):
                gene_data = store.load(key)
                if gene_data and isinstance(gene_data, dict):
                    gene_name = key[len(prefix) :]
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

    def discover_all(
        self,
        project_root: str = ".",
        skill_modules: list[str] = None,
        sop_dirs: list[str] = None,
        skill_card_dirs: list[str] = None,
    ) -> dict[str, int]:
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

    def dispatch(self, weapon_id: str) -> Skill | None:
        """
        为府兵配发武器。

        Args:
            weapon_id: 武器ID

        Returns:
            Skill 实例或 None
        """
        from core.armory import WeaponType

        weapon = self.registry.get(weapon_id)
        if not weapon or not weapon.is_active:
            return None

        if weapon.type == WeaponType.SKILL and weapon._skill_instance:
            return weapon._skill_instance

        # TODO: 从模块动态加载（如果 _skill_instance 为 None）
        return None

    def dispatch_sop(self, sop_id: str) -> SOP | None:
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

    def dispatch_for_task(
        self, task_description: str, required_categories: list[WeaponCategory] = None
    ) -> dict[str, Any]:
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
        from core.armory import WeaponType

        # 军师推荐
        bundle = self.registry.recommend_bundle(task_description, required_categories)

        skills = {}
        for _cat, weapons in bundle.items():
            for w in weapons:
                if w.type == WeaponType.SKILL:
                    skill = self.dispatch(w.id)
                    if skill:
                        skills[w.name] = skill

        # 推荐 SOP
        sop_candidates = self.registry.recommend(
            task_description, weapon_type=WeaponType.SOP, top_k=1
        )
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
