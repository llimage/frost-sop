"""
FROST-SOP V8.0 — 项目生命周期（Project Lifecycle）

PHILOSOPHY: 
- 入口不变：使用者下达任务 → 任务生命周期开始
- 每个任务 = 一个独立项目（Project）
- 每个项目有一个项目负责人（TaskParentAgent）
- 项目负责人组建执行小队（TaskFootmanAgents）
- 项目内对话 ≠ 任务下达：朝廷 ↔ 父辈（项目负责人）持续沟通

架构分层：
  朝廷（使用者）
    │ 下达任务 / 项目内对话
    ▼
  项目识别层（ProjectManager）
    │ 判断：新任务？还是已有项目的对话？
    ├── 新任务 → 创建 Project → 任命 TaskParentAgent
    └── 已有项目 → 路由到该项目的 TaskParentAgent
    ▼
  项目层（Project）
    ├── TaskParentAgent（项目负责人）
    │   ├── 愿景对齐（与朝廷持续对话）
    │   ├── 计划细化
    │   └── 组建/调度 Footman 小队
    └── TaskFootmanAgents（执行小队）
        ├── 执行计划阶段
        └── 向父辈报告状态
"""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from core.store import Store

logger = logging.getLogger(__name__)


@dataclass
class Project:
    """
    项目实体。

    每个任务对应一个项目，有独立的生命周期和上下文。
    """
    id: str                          # 项目ID（如 proj_xxx）
    name: str                        # 项目名称（从使用者输入提取）
    raw_input: str                   # 使用者的原始输入
    vision: str | None = None        # 对齐后的愿景
    status: str = "created"          # created → vision_aligned → planning → executing → reviewing → completed
    parent_agent_id: str | None = None   # 项目负责人（TaskParentAgent）
    plan_id: str | None = None       # 关联的计划ID
    footman_ids: list[str] = field(default_factory=list)  # 执行小队成员
    context: dict = field(default_factory=dict)  # 项目级上下文（跨阶段共享）
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "raw_input": self.raw_input,
            "vision": self.vision,
            "status": self.status,
            "parent_agent_id": self.parent_agent_id,
            "plan_id": self.plan_id,
            "footman_ids": self.footman_ids,
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def update_status(self, new_status: str):
        self.status = new_status
        self.updated_at = datetime.now().isoformat()
        if new_status == "completed":
            self.completed_at = self.updated_at


class ProjectStore:
    """项目存储，基于 Store 封装。"""

    PREFIX = "project"

    def __init__(self, store: Store = None):
        self.store = store or Store()

    def _key(self, project_id: str) -> str:
        return f"{self.PREFIX}:{project_id}"

    def save(self, project: Project):
        self.store.save(self._key(project.id), project.to_dict())

    def load(self, project_id: str) -> Project | None:
        data = self.store.load(self._key(project_id))
        if data and isinstance(data, dict):
            return Project.from_dict(data)
        return None

    def list_active(self) -> list[Project]:
        """列出所有活跃项目（非 completed）。"""
        projects = []
        # 简单扫描：获取所有 project: 前缀的键
        all_keys = self.store.list_keys()
        for key in all_keys:
            if key.startswith(f"{self.PREFIX}:"):
                data = self.store.load(key)
                if data and isinstance(data, dict):
                    p = Project.from_dict(data)
                    if p.status != "completed":
                        projects.append(p)
        return projects

    def find_by_name(self, name: str) -> list[Project]:
        """按项目名称模糊搜索。"""
        results = []
        for p in self.list_active():
            if name.lower() in p.name.lower() or name.lower() in p.raw_input.lower():
                results.append(p)
        return results
