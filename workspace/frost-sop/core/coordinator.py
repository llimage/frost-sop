"""
FROST-SOP V7.3 — 并行协调器 (ParallelCoordinator)

解决府兵并行执行与协同的核心组件。

PHILOSOPHY: 祖辈制定计划时标记哪些阶段可以并行。
Coordinator 负责按"执行组"调度，收集组内输出，触发下一组。

执行组模型
──────────
计划中的 phases 按 parallel_group 分组：
  group_0: [phase_1]           ← 串行起始
  group_1: [phase_2a, phase_2b] ← 并行：交付Agent + 库存Agent
  group_2: [phase_3]           ← 串行：销售Agent（等 group_1 完成）

同组内的阶段无相互依赖，可并行。
组的依赖 = 组内所有阶段的 depends_on 的并集所在的前序组。

自行车定制示例
──────────────
  phase_1 (需求解析) → group_0
  phase_2a (交付拆解) → group_1  [depends_on: phase_1]
  phase_2b (库存查询) → group_1  [depends_on: phase_1]
  phase_3  (报价生成) → group_2  [depends_on: phase_2a, phase_2b]

Coordinator 行为：
1. group_0 完成后，同时触发 group_1 的两个府兵
2. 等待 group_1 两个府兵都完成
3. 将 group_1 的输出合并为 group_2 的输入
4. 触发 group_2
"""

import json
import logging
import threading
from collections import defaultdict
from typing import Any

from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.store import Store

logger = logging.getLogger(__name__)


class ExecutionGroup:
    """
    执行组：一组可并行执行的阶段。

    Attributes:
        group_id: 组ID（如 "group_0"）
        phases: 组内阶段列表
        depends_on_groups: 依赖的前序组ID列表
        status: "pending" | "running" | "completed" | "failed"
        outputs: 组内所有府兵完成后的合并输出
    """

    def __init__(self, group_id: str, phases: list[dict]):
        self.group_id = group_id
        self.phases = phases
        self.depends_on_groups: list[str] = []
        self.status: str = "pending"
        self.outputs: dict[str, Any] = {}
        self._completed_phases: set[str] = set()
        self._phase_outputs: dict[str, dict] = {}
        self._lock = threading.Lock()

    def mark_phase_completed(self, phase_id: str, outputs: dict):
        """标记组内一个阶段完成。"""
        with self._lock:
            self._completed_phases.add(phase_id)
            self._phase_outputs[phase_id] = outputs
            # 合并输出到组级别
            self.outputs.update(outputs)

    def is_all_completed(self) -> bool:
        """检查组内所有阶段是否都已完成。"""
        with self._lock:
            return len(self._completed_phases) == len(self.phases)

    def get_completion_rate(self) -> float:
        """返回完成百分比。"""
        with self._lock:
            if not self.phases:
                return 1.0
            return len(self._completed_phases) / len(self.phases)


class ParallelCoordinator:
    """
    并行协调器。

    职责：
    1. 解析计划为执行组
    2. 按组依赖图顺序调度
    3. 管理组状态机（pending → running → completed）
    4. 收集组内输出并传递给下一组

    使用方式：
        coordinator = ParallelCoordinator(daemon, store)
        coordinator.load_plan(plan)
        coordinator.start_execution()  # 自动开始执行
    """

    def __init__(self, daemon: EventBusDaemon = None, store: Store = None):
        self.daemon = daemon or EventBusDaemon()
        self.store = store or Store()
        self._groups: dict[str, ExecutionGroup] = {}
        self._phase_to_group: dict[str, str] = {}
        self._plan_id: str | None = None
        self._lock = threading.Lock()
        self._running = False

    # ────────── 计划加载 ──────────

    def load_plan(self, plan: dict):
        """
        加载计划并解析为执行组。

        解析规则：
        - 每个 phase 的 parallel_group 决定所属组
        - 无 parallel_group 的阶段默认独占一组（串行）
        - 组间依赖 = 组内所有阶段的 depends_on 对应的前序组
        """
        self._plan_id = plan.get("plan_id", "unknown")
        phases = plan.get("phases", [])

        # 第一步：按 parallel_group 分组
        group_map: dict[str, list[dict]] = defaultdict(list)
        for phase in phases:
            gid = phase.get("parallel_group", f"group_{phase.get('phase_id')}")
            group_map[gid].append(phase)
            self._phase_to_group[phase["phase_id"]] = gid

        # 第二步：创建 ExecutionGroup
        for gid, group_phases in group_map.items():
            self._groups[gid] = ExecutionGroup(gid, group_phases)

        # 第三步：计算组间依赖
        for gid, group in self._groups.items():
            for phase in group.phases:
                for dep_phase_id in phase.get("depends_on", []):
                    dep_group = self._phase_to_group.get(dep_phase_id)
                    if dep_group and dep_group != gid:
                        if dep_group not in group.depends_on_groups:
                            group.depends_on_groups.append(dep_group)

        logger.info(
            "[Coordinator] 计划解析完成: %s, %d 组, %d 阶段",
            self._plan_id, len(self._groups), len(phases),
        )
        for gid, group in self._groups.items():
            phase_ids = [p["phase_id"] for p in group.phases]
            deps = group.depends_on_groups
            logger.info(
                "  %s: phases=%s, depends_on=%s",
                gid, phase_ids, deps if deps else "无",
            )

    # ────────── 执行控制 ──────────

    def start_execution(self):
        """开始执行计划。触发所有无依赖的初始组。"""
        self._running = True
        self._subscribe_events()

        # 找到所有无依赖的组（入口组）
        entry_groups = [
            gid for gid, g in self._groups.items()
            if not g.depends_on_groups
        ]

        logger.info(
            "[Coordinator] 开始执行计划 %s, 入口组: %s",
            self._plan_id, entry_groups,
        )

        for gid in entry_groups:
            self._trigger_group(gid)

    def _subscribe_events(self):
        """订阅阶段完成事件，以便跟踪组进度。"""
        EventBus().subscribe(EventType.STAGE_COMPLETED, self._on_phase_completed)

    def _on_phase_completed(self, event: Event):
        """处理阶段完成事件，更新组状态并可能触发下一组。"""
        data = event.data
        plan_id = data.get("plan_id")
        phase_id = data.get("phase_id")
        outputs = data.get("outputs", {})

        # 只处理当前计划的事件
        if plan_id != self._plan_id:
            return

        gid = self._phase_to_group.get(phase_id)
        if not gid:
            logger.warning("[Coordinator] 未知阶段完成: %s", phase_id)
            return

        group = self._groups.get(gid)
        if not group:
            return

        # 标记阶段完成
        group.mark_phase_completed(phase_id, outputs)
        logger.info(
            "[Coordinator] 阶段完成: %s (组 %s, 进度 %.0f%%)",
            phase_id, gid, group.get_completion_rate() * 100,
        )

        # 如果整组完成，触发后续组
        if group.is_all_completed():
            group.status = "completed"
            logger.info("[Coordinator] 组完成: %s", gid)
            self._trigger_dependent_groups(gid)

    def _trigger_group(self, gid: str):
        """触发一个执行组（组内所有阶段并行触发）。"""
        group = self._groups.get(gid)
        if not group:
            return

        group.status = "running"
        phase_ids = [p["phase_id"] for p in group.phases]

        logger.info(
            "[Coordinator] 触发组 %s (并行 %d 个阶段): %s",
            gid, len(phase_ids), phase_ids,
        )

        # 为组内每个阶段准备输入（合并所有前置组的输出）
        group_inputs = self._collect_group_inputs(gid)

        # 并行触发组内所有阶段
        for phase in group.phases:
            phase_id = phase["phase_id"]
            # 将组输入 + 阶段特有输入合并
            phase_inputs = dict(group_inputs)
            phase_inputs.update(phase.get("inputs", {}))

            # 发布触发事件（带合并后的输入）
            self._publish_phase_trigger(self._plan_id, phase_id, phase_inputs)

    def _trigger_dependent_groups(self, completed_gid: str):
        """某个组完成后，检查并触发依赖它的后续组。"""
        for gid, group in self._groups.items():
            if completed_gid not in group.depends_on_groups:
                continue
            if group.status != "pending":
                continue

            # 检查所有前置组是否都已完成
            all_deps_ready = all(
                self._groups.get(dep_gid, ExecutionGroup("", [])).status == "completed"
                for dep_gid in group.depends_on_groups
            )

            if all_deps_ready:
                logger.info(
                    "[Coordinator] 前置组 %s 完成，触发后续组 %s",
                    completed_gid, gid,
                )
                self._trigger_group(gid)

    def _collect_group_inputs(self, gid: str) -> dict:
        """
        收集一个组的所有前置组的输出，合并为输入。

        合并策略：
        - 简单 dict update（后覆盖前）
        - 特殊键 _group_outputs 保留各组的原始输出
        """
        group = self._groups.get(gid)
        if not group:
            return {}

        merged = {}
        group_outputs = {}

        for dep_gid in group.depends_on_groups:
            dep_group = self._groups.get(dep_gid)
            if dep_group and dep_group.outputs:
                merged.update(dep_group.outputs)
                group_outputs[dep_gid] = dep_group.outputs

        if group_outputs:
            merged["_group_outputs"] = group_outputs

        return merged

    def _publish_phase_trigger(self, plan_id: str, phase_id: str, inputs: dict):
        """发布阶段触发事件。"""
        if not self.daemon.is_running():
            logger.warning("[Coordinator] 事件总线未运行，无法触发 %s", phase_id)
            return

        self.daemon.publish(
            Event(
                event_type=EventType.SCHEDULED_EXECUTED,
                source="parallel_coordinator",
                data={
                    "job_type": "plan_phase",
                    "plan_id": plan_id,
                    "phase_id": phase_id,
                    "inputs": inputs,
                    "coordinated": True,
                },
            )
        )

    # ────────── 状态查询 ──────────

    def get_group_status(self, gid: str) -> str:
        """获取指定组的状态。"""
        group = self._groups.get(gid)
        return group.status if group else "unknown"

    def get_overall_progress(self) -> float:
        """获取整体进度（0.0 ~ 1.0）。"""
        if not self._groups:
            return 0.0
        total = sum(g.get_completion_rate() for g in self._groups.values())
        return total / len(self._groups)

    def is_plan_completed(self) -> bool:
        """检查整个计划是否已完成。"""
        return all(g.status == "completed" for g in self._groups.values())

    def get_execution_report(self) -> dict:
        """生成执行报告。"""
        return {
            "plan_id": self._plan_id,
            "progress": self.get_overall_progress(),
            "completed": self.is_plan_completed(),
            "groups": {
                gid: {
                    "status": g.status,
                    "phases": [p["phase_id"] for p in g.phases],
                    "completion_rate": g.get_completion_rate(),
                }
                for gid, g in self._groups.items()
            },
        }
