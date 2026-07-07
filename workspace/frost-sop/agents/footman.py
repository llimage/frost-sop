"""
FROST-SOP V7.2 — 府兵 Agent

府兵是执行者。从武器库领取武器，按计划执行。

职责：
1. 订阅 SCHEDULED_EXECUTED 事件（计划阶段触发）
2. 读取计划阶段配置
3. 从武器库（Armory）配发武器（Skill + SOP）
4. 执行武器
5. 发布阶段完成事件（触发下一阶段）

PHILOSOPHY: 府兵不自备武器，武器由朝廷兵器库统一配发。
出征时领取，战后归还。元数据永久保留。
"""

import logging

from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.armory import ArmoryRegistry
from core.armory_lifecycle import ArmoryDispatcher
from core.store import Store

logger = logging.getLogger(__name__)


class FootmanAgent:
    """
    府兵 Agent。

    订阅计划阶段触发事件，读取计划，从武器库配发武器，执行，发布完成事件。
    """

    def __init__(
        self,
        registry: ArmoryRegistry,
        store: Store,
        daemon: EventBusDaemon = None,
    ):
        self.registry = registry
        self.store = store
        self.daemon = daemon or EventBusDaemon()
        self._dispatcher = ArmoryDispatcher(registry)

    # ────────── 生命周期 ──────────

    def start(self):
        """注册事件订阅，开始监听阶段触发事件。"""
        bus = EventBus()
        bus.subscribe(EventType.SCHEDULED_EXECUTED, self._on_phase_trigger)
        logger.info("[FootmanAgent] 已注册事件订阅")

    # ────────── 事件处理 ──────────

    def _on_phase_trigger(self, event: Event):
        """处理计划阶段触发事件。"""
        data = event.data
        plan_id = data.get("plan_id")
        phase_id = data.get("phase_id")
        immediate = data.get("immediate", False)
        # V7.3: 接收 Coordinator 传递的合并输入（来自前置并行组的输出）
        coordinator_inputs = data.get("inputs", {})

        trigger_type = "立即触发" if immediate else "定时触发"
        logger.info(
            "[FootmanAgent] 收到阶段触发 [%s]: plan=%s phase=%s",
            trigger_type, plan_id, phase_id,
        )

        # 1. 读取计划
        plan = self._load_plan(plan_id)
        if not plan:
            logger.error("[FootmanAgent] 计划不存在: %s", plan_id)
            return

        # 2. 读取阶段
        phase = self._find_phase(plan, phase_id)
        if not phase:
            logger.error("[FootmanAgent] 阶段不存在: %s", phase_id)
            return

        # 3. 从武器库配发武器
        module_name = phase.get("module", "")
        weapons = self._dispatcher.dispatch_for_task(module_name)

        logger.info(
            "[FootmanAgent] 配发武器: %d skills + SOP=%s",
            len(weapons.get("skills", {})),
            weapons.get("sop") is not None,
        )

        # 4. 执行武器（传入 Coordinator 合并的前置组输出）
        outputs = self._execute_weapons(phase, weapons, coordinator_inputs)

        # 5. 记录使用到武器库（健康评分）
        self._record_usage(weapons, outputs)

        # 6. 发布阶段完成事件
        if self.daemon.is_running():
            self.daemon.publish_phase_completed(plan_id, phase_id, outputs)
            logger.info("[FootmanAgent] 阶段完成事件已发布")
        else:
            logger.warning("[FootmanAgent] 事件总线未运行，无法发布完成事件")
        """处理计划阶段触发事件。"""
        data = event.data
        plan_id = data.get("plan_id")
        phase_id = data.get("phase_id")
        immediate = data.get("immediate", False)

        trigger_type = "立即触发" if immediate else "定时触发"
        logger.info(
            "[FootmanAgent] 收到阶段触发 [%s]: plan=%s phase=%s",
            trigger_type, plan_id, phase_id,
        )

        # 1. 读取计划
        plan = self._load_plan(plan_id)
        if not plan:
            logger.error("[FootmanAgent] 计划不存在: %s", plan_id)
            return

        # 2. 读取阶段
        phase = self._find_phase(plan, phase_id)
        if not phase:
            logger.error("[FootmanAgent] 阶段不存在: %s", phase_id)
            return

        # 3. 从武器库配发武器
        module_name = phase.get("module", "")
        weapons = self._dispatcher.dispatch_for_task(module_name)

        logger.info(
            "[FootmanAgent] 配发武器: %d skills + SOP=%s",
            len(weapons.get("skills", {})),
            weapons.get("sop") is not None,
        )

        # 4. 执行武器
        outputs = self._execute_weapons(phase, weapons)

        # 5. 记录使用到武器库（健康评分）
        self._record_usage(weapons, outputs)

        # 6. 发布阶段完成事件
        if self.daemon.is_running():
            self.daemon.publish_phase_completed(plan_id, phase_id, outputs)
            logger.info("[FootmanAgent] 阶段完成事件已发布")
        else:
            logger.warning("[FootmanAgent] 事件总线未运行，无法发布完成事件")

    # ────────── 计划读取 ──────────

    def _load_plan(self, plan_id: str) -> dict | None:
        """从 Store 读取计划。"""
        key = f"plan:{plan_id}"
        plan = self.store.load(key)
        if plan is None:
            return None
        return plan if isinstance(plan, dict) else None

    def _find_phase(self, plan: dict, phase_id: str) -> dict | None:
        """在计划中找到对应阶段。"""
        phases = plan.get("phases", [])
        for phase in phases:
            if phase.get("phase_id") == phase_id:
                return phase
        return None

    # ────────── 武器执行 ──────────

    def _execute_weapons(self, phase: dict, weapons: dict, coordinator_inputs: dict = None) -> dict:
        """
        执行配发的武器。

        V7.3 更新: 支持接收 Coordinator 传递的前置组合并输出。

        Args:
            phase: 阶段配置
            weapons: 配发的武器
            coordinator_inputs: Coordinator 传递的合并输入（可选）

        Returns:
            所有执行结果合并后的字典
        """
        outputs = {}
        # 合并输入：Coordinator 输入（前置组输出）优先于 phase 自身 inputs
        inputs = dict(phase.get("inputs", {}))
        if coordinator_inputs:
            inputs.update(coordinator_inputs)
            logger.info("[FootmanAgent] 接收 Coordinator 输入: %s", list(coordinator_inputs.keys()))
        """
        执行配发的武器。

        执行顺序：
        1. SOP（如果配发了）—— 按 SOP 阶段执行
        2. Skill（逐个执行）

        Returns:
            所有执行结果合并后的字典
        """
        outputs = {}
        inputs = phase.get("inputs", {})

        # 执行 SOP
        sop = weapons.get("sop")
        if sop:
            logger.info("[FootmanAgent] 执行 SOP: %s", getattr(sop, "sop_id", "unknown"))
            # 注意：SOP 执行需要 orchestration 模块支持
            # 当前简化处理：将 SOP 信息放入输出，实际执行由后续完善
            outputs["_sop_id"] = getattr(sop, "sop_id", "unknown")
            outputs["_sop_name"] = getattr(sop, "name", "unknown")

        # 执行 Skill
        for skill_name, skill in weapons.get("skills", {}).items():
            logger.info("[FootmanAgent] 执行 Skill: %s", skill_name)
            try:
                result = skill.execute(inputs)
                if isinstance(result, dict):
                    outputs.update(result)
                    logger.info("[FootmanAgent] Skill %s 执行成功", skill_name)
                else:
                    logger.warning(
                        "[FootmanAgent] Skill %s 返回值非 dict: %s",
                        skill_name, type(result),
                    )
                    outputs[f"_{skill_name}_result"] = result
            except Exception as e:
                logger.error("[FootmanAgent] Skill %s 执行失败: %s", skill_name, e)
                outputs[f"_error_{skill_name}"] = str(e)

        return outputs

    # ────────── 武器库记录 ──────────

    def _record_usage(self, weapons: dict, outputs: dict):
        """记录武器使用情况到武器库（健康评分）。"""
        # 检查是否有错误
        has_error = any(k.startswith("_error_") for k in outputs.keys())
        success = not has_error

        # 记录每个 Skill 的使用
        for skill_name, skill in weapons.get("skills", {}).items():
            weapon_id = f"skill:{skill_name}"
            if self.registry.get(weapon_id):
                self.registry.record_usage(weapon_id, success)
                logger.debug(
                    "[FootmanAgent] 记录使用: %s success=%s", weapon_id, success
                )

        # 记录 SOP 的使用
        sop = weapons.get("sop")
        if sop:
            sop_id = getattr(sop, "sop_id", None)
            if sop_id:
                weapon_id = f"sop:{sop_id}"
                if self.registry.get(weapon_id):
                    self.registry.record_usage(weapon_id, success)
