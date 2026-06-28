"""
PHILOSOPHY:
Agent is the neuron. Holds memory and capabilities.
Behavior is entirely determined by external SOP steps.

V2.0 变更：
- 新增 destroy() 方法：写入 agent_status 销毁事件，记录生命周期结束
- 新增 _cleanup() 方法：释放临时资源
- run() 方法增加生命周期追踪：开始时记录 "running"，结束时调用 destroy()
- V2.0 子阶段 4.3: run() 在步骤完成后发布 STEP_COMPLETED 事件
- V2.0 子阶段 4.3: __init__ 发布 AGENT_CREATED 事件，destroy() 发布 AGENT_DESTROYED 事件
- 向后兼容：保持原有直接调用模式不变，事件驱动作为可选扩展
"""

from core.store import Store
import copy
import asyncio
import logging
import time
from datetime import datetime
from typing import Callable, Dict, Optional, Union

logger = logging.getLogger(__name__)


class Agent:
    """
    PHILOSOPHY: The neuron. Holds memory and capabilities.
    Behavior is entirely determined by external SOP steps.

    V2.0: 支持瞬态生命周期追踪（created → running → destroyed）
    V2.0 子阶段 4.3: 集成 EventBus，步骤完成时发布 STEP_COMPLETED 事件
    """

    def __init__(self, name: str = None, store: Store = None, skills: dict = None,
                 sop_steps: list = None, generation: int = 0,
                 max_spawn_generation: int = None,
                 retry_config: Dict = None,
                 on_max_retries: Optional[Callable] = None,
                 event_driven: bool = False):
        """
        Initialize an Agent.

        Args:
            name: The name of the agent
            store: The store for memory (defaults to new Store)
            skills: Dictionary of skills (name -> Skill object)
            sop_steps: List of SOP steps for this agent
            generation: The generation number (0 for ancestor)
            max_spawn_generation: Maximum generation this agent can spawn
            retry_config: Retry configuration dict with keys:
                max_retries (default 3), retry_delay_seconds (default 5)
            on_max_retries: Callback function(max_retries, step_name, error)
                Called when max retries exceeded, for elder reporting
            event_driven: V2.0 新增。True 时在步骤完成后发布 STEP_COMPLETED 事件。
                          默认 False，保持向后兼容。
        """
        self.name = name
        self.store = store if store is not None else Store()
        self.skills = skills if skills is not None else {}
        self._sop_steps = sop_steps if sop_steps is not None else []
        self.generation = generation
        self.max_spawn_generation = max_spawn_generation
        self._parent = None
        self._pending_sop = []
        self._execution_history = []
        self._max_history = 100

        # P0-2: 自修复重试配置
        retry_config = retry_config or {}
        self._max_retries = retry_config.get("max_retries", 3)
        self._retry_delay_seconds = retry_config.get("retry_delay_seconds", 5)
        self._on_max_retries = on_max_retries

        # V2.0: 生命周期状态追踪
        self._status: str = "idle"          # idle / running / destroyed
        self._created_at: datetime = datetime.now()
        self._destroyed_at: Optional[datetime] = None

        # V2.0 子阶段 4.3: 事件驱动模式开关
        # True = 步骤完成后发布 STEP_COMPLETED 事件
        # False = 纯直接调用模式（V1.0 兼容）
        self._event_driven: bool = event_driven

        # V2.0 子阶段 4.3: 发布 AGENT_CREATED 事件
        if self._event_driven:
            self._publish_event("agent_created", {
                "agent_name": self.name,
                "generation": self.generation,
            })

    def run(self, sop_steps: list, initial_context: dict = None) -> dict:
        """
        Core execution loop. Execute SOP steps sequentially.
        P0-2: Supports retry on failure (max 3 retries, 5s interval).
        V2.0: 在任务开始/结束时写入 agent_status 生命周期记录。
        V2.0 子阶段 4.3: event_driven=True 时，步骤完成后发布 STEP_COMPLETED 事件。

        Args:
            sop_steps: List of steps (string skill names or Agent instances)
            initial_context: Initial context dictionary

        Returns:
            Updated context dictionary

        Raises:
            KeyError: If a string step is not found in skills
            TypeError: If a step is neither string nor Agent
            Exception: If max retries exceeded for any step
        """
        context = dict(initial_context) if initial_context else {}
        context['_store'] = self.store
        step_records = []
        overall_success = True
        execution_error = None

        # V2.0: 任务开始时写入 agent_status "running"
        self._status = "running"
        self._write_agent_status("running", context.get("_task_id", ""))

        try:
            for step in sop_steps:
                step_name = step if isinstance(step, str) else (step.name if step else "unknown")
                step_result = self._execute_step_with_retry(step, context, step_records)
                if not step_result["success"]:
                    overall_success = False
                    execution_error = step_result.get("error")
                    # Already recorded in step_records by _execute_step_with_retry
                    break
                context = step_result["context"]

                # V2.0 子阶段 4.3: 步骤成功后发布 STEP_COMPLETED 事件
                if self._event_driven:
                    self._publish_event("step_completed", {
                        "agent_name": self.name,
                        "step_name": step_name,
                        "task_id": context.get("_task_id", ""),
                    })

            # Record execution history
            self._execution_history.append({
                "timestamp": datetime.now(),
                "sop_steps": sop_steps,
                "step_records": step_records,
                "overall_success": overall_success,
            })
            # Trim history if exceeds max
            if len(self._execution_history) > self._max_history:
                self._execution_history = self._execution_history[-self._max_history:]

        finally:
            # V2.0: 任务完成时（正常或异常）调用 destroy()
            self.destroy()

        # Re-raise the error if execution failed
        if execution_error:
            raise execution_error

        return context

    # ============================================================
    # V2.0: 生命周期管理方法
    # ============================================================

    def destroy(self):
        """
        V2.0: 销毁 Agent，记录生命周期结束。

        - 设置 _status = "destroyed"
        - 记录 _destroyed_at 时间戳
        - 调用 _write_agent_status() 写入 destroyed 事件
        - V2.0 子阶段 4.3: event_driven=True 时发布 AGENT_DESTROYED 事件
        - 调用 _cleanup() 释放资源
        """
        if self._status == "destroyed":
            # 防止重复销毁
            return

        self._status = "destroyed"
        self._destroyed_at = datetime.now()

        # 写入 agent_status 销毁记录
        self._write_agent_status("destroyed", "")

        # V2.0 子阶段 4.3: 发布 AGENT_DESTROYED 事件
        if self._event_driven:
            self._publish_event("agent_destroyed", {
                "agent_name": self.name,
                "generation": self.generation,
                "destroyed_at": self._destroyed_at.isoformat(),
            })

        # 释放资源
        self._cleanup()

    def _publish_event(self, event_type: str, data: dict) -> None:
        """
        V2.0 子阶段 4.3: 向 EventBus 发布事件。
        失败时仅打印警告，不影响主流程。

        Args:
            event_type: 事件类型（对应 EventType 常量值）
            data: 事件数据字典
        """
        try:
            from core.event_bus import get_event_bus, Event
            bus = get_event_bus()
            event = Event(
                event_type=event_type,
                source=self.name or "unknown_agent",
                data=data,
            )
            bus.publish(event)
        except Exception as e:
            # 事件发布失败不影响主流程
            logger.warning("事件发布失败 (%s, %s): %s", self.name, event_type, e)

    def _cleanup(self):
        """
        V2.0: 清理 Agent 临时资源。

        - 清理临时上下文数据（不清理 store，store 由外部管理）
        - 释放对父辈的引用（避免循环引用）
        """
        # 清理挂起的 SOP（已执行完成，不再需要）
        self._pending_sop = []

        # 释放父辈引用（避免循环引用导致内存泄漏）
        # 注意：不清除 _execution_history，保留审计轨迹
        self._parent = None

    def _write_agent_status(self, status: str, task_id: str):
        """
        V2.0: 将 Agent 状态写入 agent_status 表。
        写入失败时仅打印警告，不影响主流程。

        Args:
            status: 状态字符串（"running" / "destroyed"）
            task_id: 关联的任务 ID（可为空）
        """
        try:
            from core.db import get_db
            db = get_db()

            # P1-9: 确保 agents 表有此 Agent 的记录（UPSERT）
            existing_agent = db.select_one("agents", "id", self.name)
            if not existing_agent:
                db.insert("agents", {
                    "id": self.name,
                    "name": self.name,
                    "agent_type": "transient",          # 瞬态 Agent（run() 驱动）
                    "generation": self.generation,
                    "created_at": self._created_at.isoformat(),
                })
            else:
                # 重复运行时不报 UNIQUE 约束错误，直接更新
                conn = db.get_connection()
                conn.execute(
                    "INSERT OR REPLACE INTO agents (id, name, agent_type, generation, created_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (self.name, self.name, "transient", self.generation,
                     self._created_at.isoformat())
                )
                conn.commit()

            # 写入 agent_status 记录
            existing_status = db.select_one("agent_status", "agent_id", self.name)
            status_data = {
                "status": status,
                "current_task_id": task_id or "",
                "last_heartbeat": datetime.now().isoformat(),
            }
            if existing_status:
                db.update("agent_status", "agent_id", self.name, status_data)
            else:
                db.insert("agent_status", {
                    "agent_id": self.name,
                    **status_data,
                })

        except Exception as e:
            # 生命周期记录失败不影响主流程
            logger.warning("Agent生命周期记录失败 (%s, %s): %s", self.name, status, e)

    def _execute_step_with_retry(
        self, step: Union[str, 'Agent'], context: dict, step_records: list
    ) -> dict:
        """
        Execute a single step with retry logic (P0-2).

        Retry behavior:
        1. Try the primary step/skill up to max_retries times
        2. Between retries, apply backoff delay
        3. On max retries exceeded, invoke on_max_retries callback for elder reporting

        Returns:
            {"success": bool, "context": dict, "error": Exception|None}
        """
        step_name = step if isinstance(step, str) else step.name
        last_error = None

        for attempt in range(1, self._max_retries + 1):
            try:
                is_retry = attempt > 1
                if is_retry:
                    logger.info("[%s] 重试 %s/%s — 步骤: %s",
                                self.name, attempt, self._max_retries, step_name)

                # Execute the step
                if isinstance(step, str):
                    if step not in self.skills:
                        raise KeyError(f"Skill '{step}' not found")
                    new_context = self.skills[step].execute(dict(context))
                elif isinstance(step, Agent):
                    new_context = step.run(step._sop_steps, dict(context))
                else:
                    raise TypeError(f"Invalid step type: {type(step)}")

                # Success!
                step_records.append({
                    "step": step_name,
                    "success": True,
                    "error": None,
                    "retries": attempt - 1,
                    "reason": new_context.get("_reason", None)
                })
                return {"success": True, "context": new_context, "error": None}

            except Exception as e:
                last_error = e
                error_str = str(e)[:200]
                logger.error("[%s] 步骤 '%s' 失败 (尝试 %s/%s): %s",
                             self.name, step_name, attempt, self._max_retries, error_str)

                if attempt < self._max_retries:
                    # 备用 Skill 切换（P0-2: 第2次重试时尝试）
                    if attempt == 2 and isinstance(step, str):
                        alt_step = self._find_alternate_skill(step)
                        if alt_step and alt_step != step:
                            logger.info("[%s] 切换备用 Skill: %s → %s",
                                        self.name, step, alt_step)
                            step = alt_step

                    # Wait before retry
                    logger.info("[%s] 等待 %s秒后重试...", self.name, self._retry_delay_seconds)
                    time.sleep(self._retry_delay_seconds)
                else:
                    # Max retries exceeded — report to elder
                    logger.error("[%s] 步骤 '%s' 已达最大重试 (%s次)，上报祖辈...",
                                 self.name, step_name, self._max_retries)

                    if self._on_max_retries:
                        try:
                            self._on_max_retries(
                                max_retries=self._max_retries,
                                step_name=step_name,
                                error=last_error,
                                agent_name=self.name,
                            )
                            logger.info("[%s] 已上报祖辈 Agent", self.name)
                        except Exception as report_err:
                            logger.warning("[%s] 上报祖辈失败: %s", self.name, report_err)

                    # Record failure
                    step_records.append({
                        "step": step_name,
                        "success": False,
                        "error": str(last_error),
                        "retries": self._max_retries,
                        "escalated_to_elder": True,
                    })

        return {"success": False, "context": context, "error": last_error}

    def _find_alternate_skill(self, skill_name: str) -> Optional[str]:
        """
        Find an alternate skill for the given skill name (P0-2).
        Uses simple heuristic: append '_backup' or search for similar named skills.

        Args:
            skill_name: Original skill name

        Returns:
            Alternate skill name or None
        """
        # Check if a backup skill exists
        backup_name = f"{skill_name}_backup"
        if backup_name in self.skills:
            return backup_name

        # Check for generic fallback
        if "call_llm_base" in self.skills and skill_name.startswith("call_llm"):
            return "call_llm_base"

        # Check for similar named skills (same prefix)
        prefixes = skill_name.split("_")[:2]
        if len(prefixes) >= 1:
            prefix = prefixes[0]
            for key in self.skills:
                if key != skill_name and key.startswith(prefix):
                    return key

        return None

    async def run_async(self, sop_steps: list, initial_context: dict = None) -> dict:
        """
        Asynchronous version of run. Uses asyncio.to_thread for sync Skills.

        Args:
            sop_steps: List of steps (string skill names or Agent instances)
            initial_context: Initial context dictionary

        Returns:
            Updated context dictionary
        """
        context = dict(initial_context) if initial_context else {}
        context['_store'] = self.store

        for step in sop_steps:
            if isinstance(step, str):
                # Execute sync skill in thread
                context = await asyncio.to_thread(self.skills[step].execute, context)
            elif isinstance(step, Agent):
                # Recursively run agent
                context = await step.run_async(step._sop_steps, context)

        return context

    def spawn(self, name: str = None, store: Store = None, skills: dict = None,
              sop_steps: list = None, **kwargs) -> 'Agent':
        """
        Create a child Agent.

        Args:
            name: Name of the child agent
            store: Store for the child (defaults to new Store)
            skills: Skills for the child
            sop_steps: SOP steps for the child
            **kwargs: Additional arguments for Agent constructor

        Returns:
            New Agent instance (child)

        Raises:
            PermissionError: If max_spawn_generation is exceeded
        """
        child_generation = self.generation + 1

        # Check if this agent can spawn based on max_spawn_generation
        if self.max_spawn_generation is not None and child_generation > self.max_spawn_generation:
            raise PermissionError(
                f"Agent '{self.name}' (gen {self.generation}) cannot spawn gen {child_generation}"
            )

        # Set child's max_spawn_generation to limit further spawning
        if self.max_spawn_generation is not None:
            kwargs['max_spawn_generation'] = self.max_spawn_generation - 1

        kwargs['generation'] = child_generation
        return Agent(name=name, store=store, skills=skills, sop_steps=sop_steps, **kwargs)

    def teach(self, child: 'Agent', sop_steps: list):
        """
        Teach a child agent by sending SOP steps.

        Args:
            child: The child agent to teach
            sop_steps: The SOP steps to teach
        """
        child.receive_teaching(sop_steps)
        child._parent = self

    def receive_teaching(self, sop_steps: list):
        """
        Receive teaching (SOP steps) from parent.

        Args:
            sop_steps: The SOP steps received
        """
        self._pending_sop = copy.deepcopy(sop_steps)

    def internalize(self):
        """Internalize the pending SOP steps."""
        self._sop_steps = self._pending_sop
        self._pending_sop = []

    def learn(self, key: str, value):
        """
        Learn (store) a memory.

        Args:
            key: The memory key
            value: The memory value
        """
        self.store.save(key, value)

    def recall(self, key: str):
        """
        Recall (retrieve) a memory.

        Args:
            key: The memory key

        Returns:
            The stored value, or None if not found
        """
        return self.store.load(key)

    def get_history(self, limit: int = None) -> list:
        """
        Get execution history.

        Args:
            limit: Maximum number of records to return (None for all)

        Returns:
            List of execution history records (newest first)
        """
        if limit is None:
            return self._execution_history[::-1]
        return self._execution_history[-limit:][::-1]
