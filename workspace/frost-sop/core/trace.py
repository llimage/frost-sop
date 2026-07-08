"""
FROST-SOP V8.0 — 执行追踪（Execution Trace）

PHILOSOPHY:
- 每个项目运行时自动生成结构化追踪记录
- 追踪是系统的"黑匣子"，用于调试和审计
- 用户遇到问题只需提供 trace_id 或最后几条日志

关键设计：
- Trace 与 Project 1:1 绑定
- 所有关键节点自动写入（创建、对齐、执行、偏差、决策）
- 支持导出为可读的日志格式
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.store import Store

logger = logging.getLogger(__name__)


@dataclass
class ExecutionTrace:
    """
    执行追踪——项目的完整运行记录。
    """
    trace_id: str                      # 唯一追踪ID
    project_id: str                    # 关联项目ID
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    events: list[dict] = field(default_factory=list)      # 事件序列
    decisions: list[dict] = field(default_factory=list)   # 关键决策点
    errors: list[dict] = field(default_factory=list)      # 异常记录
    
    def add_event(self, actor: str, action: str, data: dict = None):
        """添加一个事件记录。"""
        event = {
            "time": datetime.now().isoformat(),
            "actor": actor,
            "action": action,
            "data": data or {},
        }
        self.events.append(event)
        logger.debug("[Trace:%s] %s.%s", self.trace_id, actor, action)
    
    def add_decision(self, decision: str, reason: str, context: dict = None):
        """添加一个决策记录。"""
        record = {
            "time": datetime.now().isoformat(),
            "decision": decision,
            "reason": reason,
            "context": context or {},
        }
        self.decisions.append(record)
    
    def add_error(self, phase: str, error: str, recovery: str = None):
        """添加一个异常记录。"""
        record = {
            "time": datetime.now().isoformat(),
            "phase": phase,
            "error": error,
            "recovery": recovery,
        }
        self.errors.append(record)
        logger.warning("[Trace:%s] ERROR in %s: %s", self.trace_id, phase, error)
    
    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "project_id": self.project_id,
            "created_at": self.created_at,
            "events": self.events,
            "decisions": self.decisions,
            "errors": self.errors,
        }
    
    def to_log_text(self) -> str:
        """导出为可读的日志文本。"""
        lines = [
            f"=== Execution Trace: {self.trace_id} ===",
            f"Project: {self.project_id}",
            f"Started: {self.created_at}",
            "",
            "--- Events ---",
        ]
        for e in self.events:
            lines.append(f"[{e['time']}] {e['actor']}: {e['action']}")
            if e['data']:
                lines.append(f"  data: {json.dumps(e['data'], ensure_ascii=False)}")
        
        if self.decisions:
            lines.extend(["", "--- Decisions ---"])
            for d in self.decisions:
                lines.append(f"[{d['time']}] {d['decision']}: {d['reason']}")
        
        if self.errors:
            lines.extend(["", "--- Errors ---"])
            for err in self.errors:
                lines.append(f"[{err['time']}] {err['phase']}: {err['error']}")
                if err['recovery']:
                    lines.append(f"  recovery: {err['recovery']}")
        
        return "\n".join(lines)
    
    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionTrace":
        trace = cls(
            trace_id=data["trace_id"],
            project_id=data["project_id"],
            created_at=data.get("created_at", datetime.now().isoformat()),
        )
        trace.events = data.get("events", [])
        trace.decisions = data.get("decisions", [])
        trace.errors = data.get("errors", [])
        return trace


class TraceStore:
    """追踪存储。"""
    
    PREFIX = "trace"
    
    def __init__(self, store: Store = None):
        self.store = store or Store()
    
    def _key(self, trace_id: str) -> str:
        return f"{self.PREFIX}:{trace_id}"
    
    def save(self, trace: ExecutionTrace):
        self.store.save(self._key(trace.trace_id), trace.to_dict())
    
    def load(self, trace_id: str) -> ExecutionTrace | None:
        data = self.store.load(self._key(trace_id))
        if data and isinstance(data, dict):
            return ExecutionTrace.from_dict(data)
        return None
    
    def get_by_project(self, project_id: str) -> ExecutionTrace | None:
        """通过项目ID查找追踪记录。"""
        # 简单扫描
        for key in self.store.list_keys():
            if key.startswith(f"{self.PREFIX}:"):
                data = self.store.load(key)
                if data and data.get("project_id") == project_id:
                    return ExecutionTrace.from_dict(data)
        return None


def create_trace(project_id: str) -> ExecutionTrace:
    """为项目创建新的追踪记录。"""
    trace_id = f"trace_{uuid.uuid4().hex[:12]}"
    trace = ExecutionTrace(trace_id=trace_id, project_id=project_id)
    trace.add_event("TraceStore", "trace_created", {"project_id": project_id})
    return trace
