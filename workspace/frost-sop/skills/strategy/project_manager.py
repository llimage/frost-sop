"""
FROST-SOP V8.0 — 项目管理器（ProjectManager）

入口不变：使用者下达任务 → 系统开始处理。

ProjectManager 的职责：
1. 接收所有使用者输入
2. 判断：新任务？还是已有项目的对话？
3. 新任务 → 创建 Project → 任命 TaskParentAgent → 启动愿景对齐
4. 已有项目 → 路由到该项目的 TaskParentAgent

PHILOSOPHY:
- 使用者不需要知道"项目"概念，系统内部管理
- 使用者的每条消息都被视为"对某个项目的输入"
- 如果没有活跃项目，视为新任务
"""

import logging
import uuid

from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.project import Project, ProjectStore
from core.trace import ExecutionTrace, TraceStore, create_trace
from agents.task_parent import TaskParentAgent

logger = logging.getLogger(__name__)


class ProjectManager:
    """
    项目管理器——使用者输入的第一接收者。
    所有朝廷消息先到这里，由这里决定路由。
    """

    def __init__(self, daemon: EventBusDaemon = None, project_store: ProjectStore = None, trace_store: TraceStore = None):
        self.daemon = daemon or EventBusDaemon()
        self.project_store = project_store or ProjectStore()
        self.trace_store = trace_store or TraceStore()
        self._active_parents: dict[str, TaskParentAgent] = {}  # project_id -> TaskParentAgent
        self._traces: dict[str, ExecutionTrace] = {}  # project_id -> Trace

    def start(self):
        """启动项目管理器，开始监听使用者输入。"""
        EventBus().subscribe(EventType.USER_INPUT, self._on_user_input)
        logger.info("[ProjectManager] 项目管理器已启动")

    def handle_input(self, user_message: str, project_id: str | None = None) -> dict:
        """
        处理使用者输入。

        Args:
            user_message: 使用者的消息
            project_id: 可选，指定项目ID

        Returns:
            {"action": "created"|"routed", "project_id": str, "response": str}
        """
        if project_id:
            return self._route_to_project(user_message, project_id)

        active_projects = self.project_store.list_active()

        if not active_projects:
            return self._create_new_project(user_message)

        if len(active_projects) == 1:
            return self._route_to_project(user_message, active_projects[0].id)

        best_match = self._find_best_match(user_message, active_projects)
        if best_match:
            return self._route_to_project(user_message, best_match.id)

        return {
            "action": "clarify",
            "response": self._build_project_clarification(active_projects),
        }

    # ── 内部方法 ──

    def _create_new_project(self, user_message: str) -> dict:
        """创建新项目。"""
        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        project = Project(
            id=project_id,
            name=user_message[:30],
            raw_input=user_message,
            status="created",
        )

        # 创建执行追踪
        trace = create_trace(project_id)
        self._traces[project_id] = trace
        trace.add_event("ProjectManager", "project_created", {"raw_input": user_message})

        # 任命项目负责人
        parent = TaskParentAgent(
            project=project,
            project_store=self.project_store,
            daemon=self.daemon,
            trace=trace,
        )
        project.parent_agent_id = parent.agent_id

        self.project_store.save(project)
        self._active_parents[project_id] = parent

        parent.start()
        parent.handle_new_task(user_message)

        # 记录决策
        trace.add_decision("create_new_project", "no_active_projects", {"project_id": project_id})
        self.trace_store.save(trace)

        logger.info("[ProjectManager] 新项目创建: %s", project_id)

        return {
            "action": "created",
            "project_id": project_id,
            "response": f"收到任务，已创建项目 [{project.name}]。项目负责人正在对齐愿景...",
            "trace_id": trace.trace_id,
        }

    def _route_to_project(self, user_message: str, project_id: str) -> dict:
        """将消息路由到已有项目。"""
        trace = self._traces.get(project_id)

        project = self.project_store.load(project_id)
        if not project:
            if trace:
                trace.add_error("routing", f"project {project_id} not found, creating new")
                self.trace_store.save(trace)
            return self._create_new_project(user_message)

        # 获取或创建项目负责人
        parent = self._active_parents.get(project_id)
        if not parent:
            parent = TaskParentAgent(
                project=project,
                project_store=self.project_store,
                daemon=self.daemon,
                trace=trace,
            )
            parent.start()
            self._active_parents[project_id] = parent

        parent.handle_user_message(user_message)

        if trace:
            trace.add_event("ProjectManager", "message_routed", {"project_id": project_id})
            trace.add_decision("route_to_project", "existing_project", {"project_id": project_id})
            self.trace_store.save(trace)

        logger.info("[ProjectManager] 消息路由到项目 %s", project_id)

        return {
            "action": "routed",
            "project_id": project_id,
            "response": f"消息已送达项目负责人 [{parent.agent_id}]。",
            "trace_id": trace.trace_id if trace else None,
        }

    def _find_best_match(self, message: str, projects: list[Project]) -> Project | None:
        """从多个项目中找到最匹配的一个。"""
        message_lower = message.lower()
        best_score = 0
        best_project = None

        for p in projects:
            score = 0
            if p.name.lower() in message_lower:
                score += 10
            if p.vision and any(word in p.vision.lower() for word in message_lower.split()):
                score += 5
            if p.raw_input.lower() in message_lower:
                score += 3

            if score > best_score:
                best_score = score
                best_project = p

        return best_project if best_score > 0 else None

    def _build_project_clarification(self, projects: list[Project]) -> str:
        """构建项目澄清提示。"""
        lines = ["您有多个活跃项目，请指定要处理哪个："]
        for i, p in enumerate(projects, 1):
            vision = p.vision or "愿景对齐中"
            lines.append(f"{i}. {p.name} ({vision[:30]}...)")
        lines.append("\n或直接输入新的任务创建新项目。")
        return "\n".join(lines)

    def _on_user_input(self, event: Event):
        """监听用户输入事件。"""
        data = event.data
        message = data.get("message", "")
        project_id = data.get("project_id")
        self.handle_input(message, project_id)
