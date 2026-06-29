"""
FROST V5.0 Human Agent 决策流程状态机

PHILOSOPHY: 决策不是一次性的按钮点击，而是完整的流程——
展示 → 等待输入 → 验证 → 记录 → 触发事件 → 回传执行引擎。

决策状态机是面板系统与 SOP 执行引擎之间的桥梁。
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from datetime import datetime
import threading
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Callable

from core.event_bus import EventBus, Event


# ────────────────────────────────────────────────────────────────────────────
# 决策状态
# ────────────────────────────────────────────────────────────────────────────

class DecisionStatus(Enum):
    """决策状态"""
    PENDING = "pending"              # 等待 Human Agent 决策
    IN_PROGRESS = "in_progress"      # 决策中（如需要填写理由）
    APPROVED = "approved"          # 确认通过
    REJECTED = "rejected"          # 驳回
    MODIFIED = "modified"          # 修改后确认
    TIMEOUT = "timeout"            # 决策超时（Human Agent 未响应）
    CANCELLED = "cancelled"        # 取消（任务被终止）


# ────────────────────────────────────────────────────────────────────────────
# 决策记录
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class DecisionRecord:
    """
    决策记录——每次 Human Agent 决策的完整快照。

    记录内容包括：
    - 决策前状态（产出、质量评分、上下文）
    - 决策过程（选择、理由、修改内容）
    - 决策后状态（结果、时间戳、审批链）
    """

    # 基础标识
    decision_id: str                   # 唯一ID（如 "decision:task_001:stage_3"）
    task_id: str                       # 关联任务ID
    stage_id: str                      # 关联阶段ID
    stage_name: str = ""               # 阶段名称（人类可读）

    # 决策状态
    status: DecisionStatus = DecisionStatus.PENDING

    # 决策前状态（上下文）
    context_before: Dict[str, Any] = field(default_factory=dict)
    # {
    #     "outputs": [...],           # 当前阶段的产出物
    #     "quality_score": {...},     # 质量评分
    #     "stage_result": {...},      # 阶段执行结果
    #     "briefing": "...",          # 军师简报（如果有）
    # }

    # 决策结果
    decision: str = ""               # "确认" / "驳回" / "修改"
    reason: str = ""                 # 驳回/修改理由
    modified_inputs: Dict[str, Any] = field(default_factory=dict)
    # 如果 decision="修改"，记录修改后的输入

    # 元数据
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    decided_at: Optional[str] = None
    timeout_at: Optional[str] = None   # 决策超时时间
    human_agent_id: str = "monarch"    # 决策人（默认君主）

    # 审批链（如果决策需要多级审批）
    approval_chain: List[Dict[str, str]] = field(default_factory=list)
    # [{"role": "父辈", "decision": "确认", "at": "2026-06-28T10:00:00"}]

    # 事件记录（与该决策相关的所有事件ID）
    event_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionRecord":
        """从字典反序列化"""
        data = dict(data)
        data["status"] = DecisionStatus(data.get("status", "pending"))
        return cls(**data)

    def is_final(self) -> bool:
        """决策是否已结束（有最终结果）"""
        return self.status in (
            DecisionStatus.APPROVED,
            DecisionStatus.REJECTED,
            DecisionStatus.MODIFIED,
            DecisionStatus.TIMEOUT,
            DecisionStatus.CANCELLED,
        )

    def can_modify(self) -> bool:
        """决策是否可以修改（未最终确定）"""
        return self.status in (DecisionStatus.PENDING, DecisionStatus.IN_PROGRESS)


# ────────────────────────────────────────────────────────────────────────────
# 决策流程配置
# ────────────────────────────────────────────────────────────────────────────

@dataclass
class DecisionFlowConfig:
    """决策流程配置"""
    # 超时设置
    timeout_seconds: int = 3600        # 默认1小时超时
    reminder_intervals: List[int] = field(default_factory=lambda: [300, 600, 1800])
    # 提醒间隔（5分钟、10分钟、30分钟）

    # 多级审批
    require_multi_approval: bool = False
    approval_roles: List[str] = field(default_factory=list)
    # 如：["parent", "ancestor", "monarch"]

    # 必填字段
    require_reason_for_reject: bool = True
    require_reason_for_modify: bool = True
    min_reason_length: int = 10         # 理由最小长度

    # 修改限制
    allow_modify: bool = True
    max_modifications: int = 3          # 最多修改次数

    # 自动决策
    auto_approve_on_timeout: bool = False
    auto_approve_threshold: float = 0.9  # 质量评分超过阈值自动确认


# ────────────────────────────────────────────────────────────────────────────
# 决策流程状态机
# ────────────────────────────────────────────────────────────────────────────

class DecisionFlow:
    """
    决策流程状态机。

    完整流程：
    1. SOP 执行引擎遇到决策点 → create_decision() → 状态 PENDING
    2. 面板生成器生成决策面板 → 渲染引擎展示
    3. Human Agent 查看产出、评分、简报 → 做出选择
    4. submit_decision() → 状态 IN_PROGRESS（如果需要理由）
    5. Human Agent 填写理由 → submit_decision() → 状态 APPROVED/REJECTED/MODIFIED
    6. 触发事件 → SOP 执行引擎收到决策 → 继续/回退/重试
    7. 记录决策 → 写入 Store → 审计可追溯

    超时处理：
    - 如果 Human Agent 在 timeout_seconds 内未响应
    - 状态变为 TIMEOUT
    - 根据配置：自动确认 / 驳回 / 上报祖辈
    """

    def __init__(self, event_bus: Optional[EventBus] = None,
                 config: DecisionFlowConfig = None,
                 store=None):
        self.event_bus = event_bus
        self.config = config or DecisionFlowConfig()
        self.store = store
        self.records: Dict[str, DecisionRecord] = {}

    # ── 创建决策 ──────────────────────────────────────────────────────────

    def create_decision(self, task_id: str, stage_id: str, stage_name: str = "",
                        context_before: Dict[str, Any] = None) -> DecisionRecord:
        """
        创建决策记录。

        由 SOP 执行引擎在遇到决策点时调用。
        """
        decision_id = f"decision:{task_id}:{stage_id}"

        record = DecisionRecord(
            decision_id=decision_id,
            task_id=task_id,
            stage_id=stage_id,
            stage_name=stage_name,
            status=DecisionStatus.PENDING,
            context_before=context_before or {},
            created_at=datetime.now().isoformat(),
        )

        self.records[decision_id] = record

        # 持久化到 Store
        if self.store:
            self.store.save(decision_id, record.to_dict())

        # 触发事件
        if self.event_bus:
            event = Event(
                event_type="decision.created",
                source="sop_engine",
                data={
                    "decision_id": decision_id,
                    "task_id": task_id,
                    "stage_id": stage_id,
                    "stage_name": stage_name,
                },
            )
            self.event_bus.publish(event)
            record.event_ids.append(event.event_id)

        return record

    # ── 提交决策 ──────────────────────────────────────────────────────────

    def submit_decision(self, decision_id: str, decision: str,
                        reason: str = "", modified_inputs: Dict[str, Any] = None,
                        human_agent_id: str = "monarch") -> DecisionRecord:
        """
        提交决策。

        由面板渲染引擎在 Human Agent 做出选择后调用。

        Args:
            decision_id: 决策ID
            decision: "确认" / "驳回" / "修改"
            reason: 理由（驳回/修改时必填）
            modified_inputs: 修改后的输入（decision="修改"时）
            human_agent_id: 决策人ID

        Returns:
            更新后的 DecisionRecord

        Raises:
            ValueError: 决策不存在或已结束
        """
        record = self.records.get(decision_id)
        if not record:
            raise ValueError(f"Decision {decision_id} not found")

        if record.is_final():
            raise ValueError(f"Decision {decision_id} is already final ({record.status.value})")

        # 验证决策值
        if decision not in ("确认", "驳回", "修改"):
            raise ValueError(f"Invalid decision: {decision}. Must be 确认/驳回/修改")

        # 验证理由（如果需要）
        if decision == "驳回" and self.config.require_reason_for_reject:
            if not reason or len(reason) < self.config.min_reason_length:
                record.status = DecisionStatus.IN_PROGRESS
                record.reason = reason  # 保存已输入的部分理由
                return record

        if decision == "修改" and self.config.require_reason_for_modify:
            if not reason or len(reason) < self.config.min_reason_length:
                record.status = DecisionStatus.IN_PROGRESS
                record.reason = reason
                return record

        # 验证修改次数
        if decision == "修改":
            modify_count = sum(1 for r in record.approval_chain if r.get("decision") == "修改")
            if modify_count >= self.config.max_modifications:
                raise ValueError(f"Maximum modifications ({self.config.max_modifications}) reached")

        # 更新记录
        record.decision = decision
        record.reason = reason
        if modified_inputs:
            record.modified_inputs = modified_inputs
        record.human_agent_id = human_agent_id
        record.decided_at = datetime.now().isoformat()

        # 更新状态
        if decision == "确认":
            record.status = DecisionStatus.APPROVED
        elif decision == "驳回":
            record.status = DecisionStatus.REJECTED
        elif decision == "修改":
            record.status = DecisionStatus.MODIFIED

        # 添加到审批链
        record.approval_chain.append({
            "role": human_agent_id,
            "decision": decision,
            "reason": reason,
            "at": record.decided_at,
        })

        # 持久化
        if self.store:
            self.store.save(decision_id, record.to_dict())

        # 触发事件
        if self.event_bus:
            event = Event(
                event_type="decision.made",
                source=human_agent_id,
                data={
                    "decision_id": decision_id,
                    "task_id": record.task_id,
                    "stage_id": record.stage_id,
                    "decision": decision,
                    "reason": reason,
                    "status": record.status.value,
                },
            )
            self.event_bus.publish(event)
            record.event_ids.append(event.event_id)

        return record

    # ── 获取决策 ──────────────────────────────────────────────────────────

    def get_decision(self, decision_id: str) -> Optional[DecisionRecord]:
        """获取决策记录"""
        return self.records.get(decision_id)

    def get_task_decisions(self, task_id: str) -> List[DecisionRecord]:
        """获取任务的所有决策记录"""
        return [r for r in self.records.values() if r.task_id == task_id]

    def get_pending_decisions(self, human_agent_id: str = "monarch") -> List[DecisionRecord]:
        """获取指定 Human Agent 的所有待决策"""
        return [
            r for r in self.records.values()
            if r.status == DecisionStatus.PENDING and r.human_agent_id == human_agent_id
        ]

    # ── 超时处理 ──────────────────────────────────────────────────────────

    def check_timeout(self, decision_id: str) -> bool:
        """
        检查决策是否超时。

        Returns:
            True 如果已超时并处理了
        """
        record = self.records.get(decision_id)
        if not record or record.is_final():
            return False

        # 检查是否超时
        created = datetime.fromisoformat(record.created_at)
        now = datetime.now()
        if (now - created).total_seconds() > self.config.timeout_seconds:
            # 超时
            record.status = DecisionStatus.TIMEOUT
            record.decided_at = now.isoformat()

            # 自动处理
            if self.config.auto_approve_on_timeout:
                # 检查质量评分是否超过阈值
                quality = record.context_before.get("quality_score", {})
                avg_score = sum(quality.values()) / len(quality) if quality else 0
                if avg_score >= self.config.auto_approve_threshold * 100:
                    record.decision = "确认（自动）"
                    record.status = DecisionStatus.APPROVED
                else:
                    record.decision = "驳回（超时）"
                    record.status = DecisionStatus.REJECTED
            else:
                record.decision = "驳回（超时）"
                record.status = DecisionStatus.REJECTED

            # 持久化
            if self.store:
                self.store.save(decision_id, record.to_dict())

            # 触发事件
            if self.event_bus:
                event = Event(
                    event_type="decision.timeout",
                    source="system",
                    data={
                        "decision_id": decision_id,
                        "task_id": record.task_id,
                        "status": record.status.value,
                        "decision": record.decision,
                    },
                )
                self.event_bus.publish(event)

            return True

        return False

    def check_all_timeouts(self) -> List[str]:
        """检查所有待决策的超时情况"""
        timed_out = []
        for decision_id, record in self.records.items():
            if record.status == DecisionStatus.PENDING:
                if self.check_timeout(decision_id):
                    timed_out.append(decision_id)
        return timed_out

    # ── 取消决策 ──────────────────────────────────────────────────────────

    def cancel_decision(self, decision_id: str, reason: str = "") -> DecisionRecord:
        """取消决策（任务被终止时）"""
        record = self.records.get(decision_id)
        if not record:
            raise ValueError(f"Decision {decision_id} not found")

        if record.is_final():
            raise ValueError(f"Cannot cancel final decision {decision_id}")

        record.status = DecisionStatus.CANCELLED
        record.reason = reason
        record.decided_at = datetime.now().isoformat()

        # 持久化
        if self.store:
            self.store.save(decision_id, record.to_dict())

        # 触发事件
        if self.event_bus:
            event = Event(
                event_type="decision.cancelled",
                source="system",
                data={
                    "decision_id": decision_id,
                    "task_id": record.task_id,
                    "reason": reason,
                },
            )
            self.event_bus.publish(event)

        return record

    # ── 决策统计 ──────────────────────────────────────────────────────────

    def get_decision_stats(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """获取决策统计"""
        records = self.records.values()
        if task_id:
            records = [r for r in records if r.task_id == task_id]

        total = len(records)
        if total == 0:
            return {"total": 0}

        stats = {
            "total": total,
            "approved": sum(1 for r in records if r.status == DecisionStatus.APPROVED),
            "rejected": sum(1 for r in records if r.status == DecisionStatus.REJECTED),
            "modified": sum(1 for r in records if r.status == DecisionStatus.MODIFIED),
            "timeout": sum(1 for r in records if r.status == DecisionStatus.TIMEOUT),
            "pending": sum(1 for r in records if r.status == DecisionStatus.PENDING),
        }

        # 平均决策时间
        decision_times = []
        for r in records:
            if r.decided_at and r.created_at:
                created = datetime.fromisoformat(r.created_at)
                decided = datetime.fromisoformat(r.decided_at)
                decision_times.append((decided - created).total_seconds())

        if decision_times:
            stats["avg_decision_time_seconds"] = sum(decision_times) / len(decision_times)
            stats["max_decision_time_seconds"] = max(decision_times)

        return stats


# ────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ────────────────────────────────────────────────────────────────────────────

def create_decision_flow(event_bus=None, config=None, store=None) -> DecisionFlow:
    """便捷函数：创建决策流程"""
    return DecisionFlow(event_bus=event_bus, config=config, store=store)

# ───────────────────────────────────────────────────────────────────────────
# 单例（供 orchestration.py 直接调用）
# ───────────────────────────────────────────────────────────────────────────


# ──────────────────────────────────────────────────────────────────────────
# 单例（供 orchestration.py 直接调用）
# ──────────────────────────────────────────────────────────────────────────

_decision_flow_instance = None
_flow_lock = threading.Lock()

def get_decision_flow(event_bus=None, config=None, store=None):
    """
    获取 DecisionFlow 单例。

    用法：
        flow = get_decision_flow(event_bus=bus, store=store)
        record = flow.create_decision(task_id, stage_id, stage_name)
    """
    global _decision_flow_instance
    with _flow_lock:
        if _decision_flow_instance is None:
            _decision_flow_instance = DecisionFlow(
                event_bus=event_bus,
                config=config,
                store=store,
            )
        else:
            if event_bus is not None:
                _decision_flow_instance.event_bus = event_bus
            if store is not None:
                _decision_flow_instance.store = store
            if config is not None:
                _decision_flow_instance.config = config
        return _decision_flow_instance


def reset_decision_flow():
    """重置单例（仅测试用）"""
    global _decision_flow_instance
    _decision_flow_instance = None
