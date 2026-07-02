"""
FROST-SOP 初始化任务触发器
将问卷生成的任务写入调度系统

PHILOSOPHY: 缺口不是终点，是狩猎的起点。
问卷识别的每一个缺口，都自动转化为一个可执行的狩猎任务。
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# 核心模块可用性检测（软依赖）
HAS_CORE = False
try:
    # 优先使用项目根目录作为导入基准
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from core.db import DBManager, get_db
    from core.event_bus import Event, EventBus, EventType
    from core.scheduler import FrostScheduler

    HAS_CORE = True
    logger.info("[InitTaskTrigger] 核心模块已加载")
except ImportError as e:
    logger.warning("[InitTaskTrigger] 核心模块未加载: %s", e)
    HAS_CORE = False


# ============================================================
# 常量定义
# ============================================================

INIT_PROJECT_ID = "INIT"  # 初始化任务标记
DEFAULT_DB_PATH = "data/frost_sop.db"
DEFAULT_INIT_RESULTS_PATH = "init_results.json"


# ============================================================
# 核心类：任务触发器
# ============================================================


class InitTaskTrigger:
    """
    V1.0: 初始化任务触发器。

    职责：
    1. 从问卷结果加载任务
    2. 将任务写入数据库（tasks 表，project_id="INIT"）
    3. 发布 HUNT_COMPLETED 事件（触发首个 P0 狩猎）
    4. 生成初始化 SOP 文档
    5. 可选：调度首个狩猎任务到 FrostScheduler

    降级模式：如果核心模块不可用，使用本地 JSON 存储。
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        init_results_path: str = DEFAULT_INIT_RESULTS_PATH,
    ):
        self.db_path = db_path
        self.init_results_path = init_results_path
        self.tasks: list[dict[str, Any]] = []
        self._db: DBManager | None = None
        self._event_bus: EventBus | None = None
        self._scheduler: FrostScheduler | None = None

        if HAS_CORE:
            try:
                self._db = get_db()
                self._event_bus = EventBus()
                self._scheduler = FrostScheduler()
            except Exception as e:
                logger.warning("[InitTaskTrigger] 核心模块初始化失败: %s", e)

    # ----------------------------------------------------------
    # 阶段 1：加载问卷结果
    # ----------------------------------------------------------

    def load_from_questionnaire(self) -> list[dict[str, Any]]:
        """从问卷结果 JSON 文件加载任务"""
        if not os.path.exists(self.init_results_path):
            logger.error("[InitTaskTrigger] 未找到 %s，请先运行问卷", self.init_results_path)
            return []

        with open(self.init_results_path, encoding="utf-8") as f:
            data = json.load(f)

        self.tasks = data.get("tasks", [])
        logger.info("[InitTaskTrigger] 加载到 %d 个初始化任务", len(self.tasks))
        return self.tasks

    # ----------------------------------------------------------
    # 阶段 2：写入数据库
    # ----------------------------------------------------------

    def save_to_database(self) -> bool:
        """将任务写入 tasks 表（project_id="INIT" 标记）"""
        if not self.tasks:
            logger.warning("[InitTaskTrigger] 没有任务可保存")
            return False

        if HAS_CORE and self._db:
            self._save_to_tasks_table()
            logger.info("[InitTaskTrigger] 已写入 tasks 表 (project_id=INIT)")
        else:
            self._save_to_json_fallback()

        return True

    def _ensure_init_project(self) -> None:
        """确保 INIT 项目存在，不存在则创建"""
        if not self._db:
            return
        try:
            existing = self._db.select_one("projects", "id", INIT_PROJECT_ID)
            if not existing:
                self._db.insert(
                    "projects",
                    {
                        "id": INIT_PROJECT_ID,
                        "name": "初始化任务",
                        "description": "由初始化问卷自动创建",
                        "status": "active",
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                        "sop_template": "INIT-001",
                        "energy_level": 100.0,
                        "config_ref": "",
                        "metadata": "{}",
                        "last_active_at": datetime.now().isoformat(),
                    },
                )
                logger.info("[InitTaskTrigger] 已创建 INIT 项目")
        except Exception as e:
            logger.warning("[InitTaskTrigger] 创建 INIT 项目失败: %s", e)

    def _save_to_tasks_table(self) -> None:
        """使用 DBManager 写入 tasks 表"""
        if not self._db:
            return
        # 首先确保 INIT 项目存在
        self._ensure_init_project()

        for task in self.tasks:
            task_id = task["task_id"]
            # 检查是否已存在（避免重复）
            existing = self._db.select_one("tasks", "id", task_id)
            if existing:
                logger.debug("[InitTaskTrigger] 任务已存在，跳过: %s", task_id)
                continue

            # 构造 tasks 表数据
            task_data = {
                "id": task_id,
                "title": task["title"],
                "description": (
                    f"来源缺口: {task.get('gap_id', '')} | "
                    f"优先级: {task['priority']} | "
                    f"目标技能: {task['target_skill']}"
                ),
                "project_id": INIT_PROJECT_ID,
                "status": task.get("status", "pending"),
                "created_at": task.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                "result_summary": json.dumps(
                    {
                        "gap_id": task.get("gap_id", ""),
                        "target_skill": task["target_skill"],
                        "priority": task["priority"],
                        "source": "init_questionnaire",
                    },
                    ensure_ascii=False,
                ),
            }
            self._db.insert("tasks", task_data)
            logger.info("[InitTaskTrigger] 任务已创建: %s", task_id)

    def _save_to_json_fallback(self) -> None:
        """降级：本地 JSON 存储"""
        fallback_path = "init_tasks.json"
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        logger.info("[InitTaskTrigger] 已保存到本地: %s", fallback_path)

    # ----------------------------------------------------------
    # 阶段 3：触发首个狩猎
    # ----------------------------------------------------------

    def trigger_first_hunt(self) -> dict[str, Any] | None:
        """
        触发第一个 P0 狩猎任务。

        1. 找到第一个 P0 任务
        2. 发布 HUNT_COMPLETED 事件（供 event_subscribers 处理）
        3. 可选：调度到 FrostScheduler
        4. 返回触发信息
        """
        p0_tasks = [t for t in self.tasks if t.get("priority") == "P0"]
        if not p0_tasks:
            logger.warning("[InitTaskTrigger] 没有 P0 任务，跳过首个狩猎触发")
            return None

        first_task = p0_tasks[0]
        target = first_task["target_skill"]
        task_id = first_task["task_id"]

        logger.info("[InitTaskTrigger] 触发首个狩猎任务: %s → %s", task_id, target)

        # 发布事件（如果核心模块可用）
        if HAS_CORE and self._event_bus:
            try:
                event = Event(
                    event_type=EventType.HUNT_COMPLETED,
                    source="init_task_trigger",
                    data={
                        "task_id": task_id,
                        "target": target,
                        "trigger": "init_questionnaire",
                        "priority": "P0",
                        "is_first_hunt": True,
                    },
                )
                self._event_bus.publish(event)
                logger.info("[InitTaskTrigger] 已发布 HUNT_COMPLETED 事件")
            except Exception as e:
                logger.warning("[InitTaskTrigger] 事件发布失败: %s", e)

        # 可选：调度到 FrostScheduler
        if HAS_CORE and self._scheduler:
            try:
                job_id = self._scheduler.schedule_hunt(
                    skill_id=target,
                    cron_expr="0 2 * * *",  # 每日02:00（可调整）
                )
                logger.info("[InitTaskTrigger] 已调度狩猎任务: %s", job_id)
                first_task["scheduled_job_id"] = job_id
            except Exception as e:
                logger.warning("[InitTaskTrigger] 调度失败: %s", e)

        return {
            "task_id": task_id,
            "target": target,
            "command": f"python main.py --hunt --hunt-target {target}",
            "event_published": HAS_CORE and self._event_bus is not None,
        }

    # ----------------------------------------------------------
    # 阶段 4：生成初始化 SOP 文档
    # ----------------------------------------------------------

    def generate_init_sop(self) -> str:
        """生成初始化 SOP Markdown 文档"""
        sop_dir = "sops/generated"
        os.makedirs(sop_dir, exist_ok=True)

        lines = [
            "# 初始化任务 SOP",
            "",
            f"生成时间: {datetime.now().isoformat()}",
            "来源: 初始化问卷自动触发",
            "",
            "## 任务清单",
            "",
        ]

        for task in self.tasks:
            status_icon = "⬜" if task.get("status") == "pending" else "✅"
            lines.append(
                f"{status_icon} [{task.get('priority', 'P1')}] {task['task_id']}: {task['title']}"
            )
            lines.append(f"   目标技能: {task['target_skill']}")
            lines.append(
                f"   执行命令: `python main.py --hunt --hunt-target {task['target_skill']}`"
            )
            lines.append("")

        lines.extend(
            [
                "## 执行顺序",
                "",
                "1. 按优先级执行（P0 → P1 → P2）",
                "2. 每个任务完成后更新状态",
                "3. 所有 P0 完成后进入常规运营",
                "",
                "---",
                "",
                "本文件由 InitTaskTrigger 自动生成，请勿手动修改。",
            ]
        )

        sop_path = os.path.join(sop_dir, "init_task_sop.md")
        with open(sop_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("[InitTaskTrigger] 初始化 SOP 已生成: %s", sop_path)
        return sop_path

    # ----------------------------------------------------------
    # 阶段 5：更新任务状态
    # ----------------------------------------------------------

    def update_task_status(self, task_id: str, new_status: str) -> bool:
        """更新任务状态（pending → running → done）"""
        if not HAS_CORE or not self._db:
            logger.warning("[InitTaskTrigger] 数据库不可用，无法更新状态")
            return False

        try:
            self._db.update(
                "tasks",
                "id",
                task_id,
                {
                    "status": new_status,
                    "updated_at": datetime.now().isoformat(),
                },
            )
            logger.info("[InitTaskTrigger] 任务状态更新: %s → %s", task_id, new_status)
            return True
        except Exception as e:
            logger.error("[InitTaskTrigger] 状态更新失败: %s, %s", task_id, e)
            return False

    # ----------------------------------------------------------
    # 阶段 6：获取初始化任务列表
    # ----------------------------------------------------------

    def get_init_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """从数据库获取初始化任务列表"""
        if not HAS_CORE or not self._db:
            logger.warning("[InitTaskTrigger] 数据库不可用，返回内存中的任务")
            return self.tasks

        try:
            if status:
                rows = self._db.select_all(
                    "tasks",
                    where="project_id = ? AND status = ?",
                    params=[INIT_PROJECT_ID, status],
                )
            else:
                rows = self._db.select_all(
                    "tasks",
                    where="project_id = ?",
                    params=[INIT_PROJECT_ID],
                )
            return rows
        except Exception as e:
            logger.error("[InitTaskTrigger] 查询失败: %s", e)
            return self.tasks

    # ----------------------------------------------------------
    # 完整流水线
    # ----------------------------------------------------------

    def run_full_pipeline(self) -> dict[str, Any]:
        """运行完整触发流水线"""
        logger.info("=" * 60)
        logger.info("FROST-SOP 初始化任务触发器")
        logger.info("=" * 60)

        self.load_from_questionnaire()
        self.save_to_database()
        sop_path = self.generate_init_sop()
        trigger_info = self.trigger_first_hunt()

        result = {
            "tasks_count": len(self.tasks),
            "p0_count": len([t for t in self.tasks if t.get("priority") == "P0"]),
            "sop_path": sop_path,
            "trigger_info": trigger_info,
            "database_mode": HAS_CORE and self._db is not None,
        }

        logger.info("=" * 60)
        logger.info(
            "初始化流水线完成: %d 个任务, %d 个 P0", result["tasks_count"], result["p0_count"]
        )
        logger.info("=" * 60)
        return result


# ============================================================
# CLI 入口
# ============================================================


def run_trigger() -> dict[str, Any]:
    """CLI 入口：运行完整触发流水线"""
    trigger = InitTaskTrigger()
    return trigger.run_full_pipeline()


if __name__ == "__main__":
    run_trigger()
