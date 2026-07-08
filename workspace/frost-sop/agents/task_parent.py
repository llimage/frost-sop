"""
FROST-SOP V8.0 - TaskParentAgent

Each project has one TaskParentAgent as its project manager.
"""

import logging
from datetime import datetime

from core.event_bus import EventBus, Event, EventType
from core.event_bus_daemon import EventBusDaemon
from core.project import Project, ProjectStore
from skills.llm import call_llm

logger = logging.getLogger(__name__)


_TASK_PARENT_PROMPT = """You are a senior project manager.
Project: {project_name}
Vision: {project_vision}
"""


class TaskParentAgent:
    """Task-level project manager, bound to one Project."""

    def __init__(self, project: Project, project_store: ProjectStore, daemon: EventBusDaemon = None):
        self.project = project
        self.project_store = project_store
        self.daemon = daemon or EventBusDaemon()
        self._agent_id = f"parent_{project.id}"

    @property
    def agent_id(self) -> str:
        return self._agent_id

    def start(self):
        EventBus().subscribe(EventType.STAGE_COMPLETED, self._on_stage_completed)
        EventBus().subscribe(EventType.USER_INPUT, self._on_user_input)
        logger.info("[TaskParent] %s started for project %s", self._agent_id, self.project.id)

    def handle_new_task(self, raw_input: str):
        logger.info("[TaskParent] New task: %s", raw_input)
        self.project.raw_input = raw_input
        self.project.name = raw_input[:30] + ("..." if len(raw_input) > 30 else "")
        self.project.status = "vision_aligning"
        self.project_store.save(self.project)
        self._align_vision()

    def handle_user_message(self, message: str):
        logger.info("[TaskParent] User message: %s", message)
        intent = self._classify_intent(message)
        if intent == "vision_update":
            self._handle_vision_update(message)
        elif intent == "status_query":
            self._handle_status_query()
        else:
            self._handle_general_chat(message)

    def _align_vision(self):
        prompt = f'User said: "{self.project.raw_input}"\nExtract a clear project vision.'
        result = call_llm({"_prompt": prompt, "_llm_profile": "execute"})
        vision = result.get("_llm_response", "No vision generated").strip()
        self.project.vision = vision
        self.project.status = "vision_aligned"
        self.project_store.save(self.project)
        logger.info("[TaskParent] Vision aligned: %s", vision[:80])

    def _handle_vision_update(self, message: str):
        if self.project.status == "executing":
            self._report_deviation("vision_change_during_execution",
                "Project is executing. Changing vision may require replanning.",
                ["A. Adjust future phases only", "B. Full replan", "C. Keep current plan"])
        else:
            self.project.vision = message
            self.project.status = "vision_aligned"
            self.project_store.save(self.project)
            logger.info("[TaskParent] Vision updated")

    def _handle_status_query(self):
        report = self._generate_status_report()
        logger.info("[TaskParent] Status report: %s", report)

    def _handle_general_chat(self, message: str):
        self.project.context.setdefault("chat_history", []).append({
            "role": "user", "content": message, "timestamp": datetime.now().isoformat()
        })
        self.project_store.save(self.project)

    def _on_stage_completed(self, event: Event):
        data = event.data
        if data.get("project_id") != self.project.id:
            return
        deviation = self._check_deviation(data.get("phase_id", ""), data.get("outputs", {}))
        if deviation:
            self._report_deviation(deviation["type"], deviation["description"], deviation.get("options", []))

    def _on_user_input(self, event: Event):
        if event.data.get("project_id") != self.project.id:
            return
        self.handle_user_message(event.data.get("message", ""))

    def _check_deviation(self, phase_id: str, outputs: dict) -> dict | None:
        errors = [k for k in outputs.keys() if k.startswith("_error_")]
        if errors:
            return {"type": "execution_error", "description": f"Phase {phase_id} error: {errors}",
                    "options": ["A. Retry", "B. Skip", "C. Abort"]}
        return None

    def _report_deviation(self, dev_type: str, description: str, options: list):
        report = {"project_id": self.project.id, "type": dev_type, "description": description,
                  "options": options, "requires_decision": True}
        logger.info("[TaskParent] Deviation reported: %s", dev_type)
        if self.daemon.is_running():
            self.daemon.publish(Event(event_type=EventType.DEVIATION_REPORTED, source=self._agent_id, data=report))

    def _generate_status_report(self) -> str:
        return f"Project: {self.project.name}\nStatus: {self.project.status}\nVision: {self.project.vision or 'N/A'}"

    def _classify_intent(self, message: str) -> str:
        m = message.lower()
        if any(w in m for w in ["progress", "status"]):
            return "status_query"
        if any(w in m for w in ["change", "update", "modify", "\u6539\u6210", "\u6362\u6210", "\u53d8\u6210"]):
            return "vision_update"
        return "general"
        m = message.lower()
        if any(w in m for w in ["progress", "status"]):
            return "status_query"
        if any(w in m for w in ["change", "update", "modify"]):
            return "vision_update"
        return "general"
