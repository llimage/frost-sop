"""
FROST-SOP V7.4 — 并行编排库（原 core/coordinator.py 重构）

从"硬编码核心组件"降级为"可调用库"。

PHILOSOPHY: 核心只提供机制（事件总线、Store、武器配发），
策略层（并行编排、计划细化）由武器库决定。

ParallelCoordinator 现在是一个库函数，被 parallel_orchestrator Skill 调用。
它不直接操作事件总线，只提供组解析和状态跟踪。

调用方（parallel_orchestrator Skill）负责：
- 启动/停止 EventBusDaemon
- 发布事件
- 订阅完成事件
"""

import logging
import threading
from collections import defaultdict
from typing import Any

from core.event_bus import EventBus, Event, EventType
from core.store import Store

logger = logging.getLogger(__name__)


class ExecutionGroup:
    """执行组：一组可并行执行的阶段。"""

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
        with self._lock:
            self._completed_phases.add(phase_id)
            self._phase_outputs[phase_id] = outputs
            self.outputs.update(outputs)

    def is_all_completed(self) -> bool:
        with self._lock:
            return len(self._completed_phases) == len(self.phases)

    def get_completion_rate(self) -> float:
        with self._lock:
            if not self.phases:
                return 1.0
            return len(self._completed_phases) / len(self.phases)


class ParallelCoordinator:
    """
    并行编排器（库级别）。

    不再直接操作事件总线，只提供：
    1. 计划解析为执行组
    2. 组状态跟踪
    3. 输入收集

    调用方（parallel_orchestrator Skill）负责事件发布。
    """

    def __init__(self, store: Store = None):
        self.store = store or Store()
        self._groups: dict[str, ExecutionGroup] = {}
        self._phase_to_group: dict[str, str] = {}
        self._plan_id: str | None = None

    def load_plan(self, plan: dict):
        """加载计划并解析为执行组。"""
        self._plan_id = plan.get("plan_id", "unknown")
        phases = plan.get("phases", [])

        # 按 parallel_group 分组
        group_map: dict[str, list[dict]] = defaultdict(list)
        for phase in phases:
            gid = phase.get("parallel_group", f"group_{phase.get('phase_id')}")
            group_map[gid].append(phase)
            self._phase_to_group[phase["phase_id"]] = gid

        # 创建 ExecutionGroup
        for gid, group_phases in group_map.items():
            self._groups[gid] = ExecutionGroup(gid, group_phases)

        # 计算组间依赖
        for gid, group in self._groups.items():
            for phase in group.phases:
                for dep_phase_id in phase.get("depends_on", []):
                    dep_group = self._phase_to_group.get(dep_phase_id)
                    if dep_group and dep_group != gid:
                        if dep_group not in group.depends_on_groups:
                            group.depends_on_groups.append(dep_group)

        logger.info(
            "[ParallelCoordinator] 解析计划 %s: %d 组, %d 阶段",
            self._plan_id, len(self._groups), len(phases),
        )

    def get_entry_groups(self) -> list[str]:
        """获取所有无依赖的入口组。"""
        return [
            gid for gid, g in self._groups.items()
            if not g.depends_on_groups
        ]

    def get_group(self, gid: str) -> ExecutionGroup | None:
        return self._groups.get(gid)

    def get_group_for_phase(self, phase_id: str) -> str | None:
        return self._phase_to_group.get(phase_id)

    def mark_group_phase_completed(self, phase_id: str, outputs: dict):
        """标记组内阶段完成。返回整组是否完成。"""
        gid = self._phase_to_group.get(phase_id)
        if not gid:
            return False

        group = self._groups.get(gid)
        if not group:
            return False

        group.mark_phase_completed(phase_id, outputs)
        logger.info(
            "[ParallelCoordinator] 阶段完成: %s (组 %s, 进度 %.0f%%)",
            phase_id, gid, group.get_completion_rate() * 100,
        )

        if group.is_all_completed():
            group.status = "completed"
            logger.info("[ParallelCoordinator] 组完成: %s", gid)
            return True  # 整组完成

        return False

    def get_ready_dependent_groups(self, completed_gid: str) -> list[str]:
        """获取因 completed_gid 完成而可以启动的后续组。"""
        ready = []
        for gid, group in self._groups.items():
            if completed_gid not in group.depends_on_groups:
                continue
            if group.status != "pending":
                continue

            all_deps_ready = all(
                self._groups.get(dep_gid, ExecutionGroup("", [])).status == "completed"
                for dep_gid in group.depends_on_groups
            )
            if all_deps_ready:
                ready.append(gid)
        return ready

    def collect_group_inputs(self, gid: str) -> dict:
        """收集一个组的所有前置组的输出，合并为输入。"""
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

    def get_overall_progress(self) -> float:
        if not self._groups:
            return 0.0
        total = sum(g.get_completion_rate() for g in self._groups.values())
        return total / len(self._groups)

    def is_plan_completed(self) -> bool:
        return all(g.status == "completed" for g in self._groups.values())

    def get_execution_report(self) -> dict:
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
