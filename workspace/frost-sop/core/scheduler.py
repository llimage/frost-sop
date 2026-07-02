"""
PHILOSOPHY:
定时器是FROST的"自律系统"。
不依赖外部cron，所有任务在BackgroundScheduler中调度，
支持持久化（数据库）和热更新。

设计原则：
- BackgroundScheduler：不阻塞主线程
- 所有任务失败仅记录audit_log，不影响调度器
- 支持从数据库加载持久化任务（重启不丢失）
- 单例模式，全局共享
"""

import logging
from datetime import datetime

from core.skill import Skill

logger = logging.getLogger(__name__)


class FrostScheduler:
    """
    V6.0: FROST定时调度器。
    封装 APScheduler BackgroundScheduler，提供 SOP/狩猎/快照/复盘调度。

    使用方式:
        scheduler = FrostScheduler(store=asset_store)
        scheduler.schedule_sop("REDBOOK-001", "0 9 * * 1")
        scheduler.schedule_hunt("skill_id", "0 2 * * *")
        scheduler.start()
    """

    _instance = None

    def __new__(cls, store=None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, store=None):
        if self._initialized:
            return
        self._initialized = True

        self._store = store
        self._scheduler = None  # lazy init
        self._started = False

        logger.info("[FrostScheduler] 调度器实例已创建")

    # ────────── 懒加载调度器 ──────────

    def _get_scheduler(self):
        """懒加载 BackgroundScheduler"""
        if self._scheduler is None:
            try:
                from apscheduler.schedulers.background import BackgroundScheduler

                self._scheduler = BackgroundScheduler(
                    timezone="Asia/Shanghai",
                    job_defaults={
                        "misfire_grace_time": 300,
                        "coalesce": True,
                        "max_instances": 1,
                    },
                )
                logger.info("[FrostScheduler] BackgroundScheduler已创建")
                # 从数据库恢复任务
                self._restore_jobs()
            except ImportError:
                logger.warning("[FrostScheduler] apscheduler未安装，使用No-Op模式")
                self._scheduler = _NoOpScheduler()
        return self._scheduler

    # ────────── 任务调度 ──────────

    def schedule_sop(self, sop_id: str, cron_expr: str) -> str:
        """
        定时执行SOP。

        Args:
            sop_id: SOP模板ID (e.g. REDBOOK-001)
            cron_expr: cron 表达式 (e.g. "0 9 * * 1")

        Returns:
            job_id: 任务ID，可用于后续管理
        """
        job_id = f"sop_{sop_id}_{_timestamp_short()}"

        def _job():
            _execute_sop_job(sop_id, self._store)

        self._get_scheduler().add_job(
            _job,
            "cron",
            id=job_id,
            **parse_cron(cron_expr),
        )
        self._persist_job(job_id, "sop", sop_id, cron_expr)
        logger.info("[FrostScheduler] SOP调度: %s @ %s", sop_id, cron_expr)
        return job_id

    def schedule_hunt(self, skill_id: str, cron_expr: str) -> str:
        """
        定时执行狩猎。

        Args:
            skill_id: 狩猎目标 Skill ID
            cron_expr: cron 表达式

        Returns:
            job_id: 任务ID
        """
        job_id = f"hunt_{skill_id}_{_timestamp_short()}"

        def _job():
            _execute_hunt_job(skill_id, self._store)

        self._get_scheduler().add_job(
            _job,
            "cron",
            id=job_id,
            **parse_cron(cron_expr),
        )
        self._persist_job(job_id, "hunt", skill_id, cron_expr)
        logger.info("[FrostScheduler] 狩猎调度: %s @ %s", skill_id, cron_expr)
        return job_id

    def schedule_daily_snapshot(self, cron_expr: str = "0 22 * * *") -> str:
        """
        每日快照：记录当日系统状态。

        Args:
            cron_expr: cron 表达式（默认每日22:00）

        Returns:
            job_id: 任务ID
        """
        job_id = f"snapshot_{_timestamp_short()}"

        def _job():
            _execute_snapshot_job(self._store)

        self._get_scheduler().add_job(
            _job,
            "cron",
            id=job_id,
            **parse_cron(cron_expr),
        )
        self._persist_job(job_id, "snapshot", None, cron_expr)
        logger.info("[FrostScheduler] 每日快照: @ %s", cron_expr)
        return job_id

    def schedule_weekly_retrospective(self, cron_expr: str = "0 20 * * 0") -> str:
        """
        周度复盘：分析本周所有任务。

        Args:
            cron_expr: cron 表达式（默认每周日20:00）

        Returns:
            job_id: 任务ID
        """
        job_id = f"retrospective_{_timestamp_short()}"

        def _job():
            _execute_retrospective_job(self._store)

        self._get_scheduler().add_job(
            _job,
            "cron",
            id=job_id,
            **parse_cron(cron_expr),
        )
        self._persist_job(job_id, "retrospective", None, cron_expr)
        logger.info("[FrostScheduler] 周度复盘: @ %s", cron_expr)
        return job_id

    # ────────── 调度器控制 ──────────

    def start(self):
        """启动调度器（在 FastAPI 启动时调用）"""
        sched = self._get_scheduler()
        if not self._started:
            sched.start()
            self._started = True
            logger.info("[FrostScheduler] 调度器已启动")

    def stop(self):
        """停止调度器（在 FastAPI 关闭时调用）"""
        if self._started and self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._started = False
            logger.info("[FrostScheduler] 调度器已关闭")

    def get_jobs(self) -> list:
        """获取所有已注册的定时任务"""
        sched = self._get_scheduler()
        jobs = []
        for job in sched.get_jobs():
            jobs.append(
                {
                    "id": job.id,
                    "next_run_time": str(job.next_run_time) if job.next_run_time else None,
                    "trigger": str(job.trigger),
                }
            )
        return jobs

    def remove_job(self, job_id: str) -> bool:
        """移除定时任务"""
        try:
            self._get_scheduler().remove_job(job_id)
            self._remove_persisted_job(job_id)
            logger.info("[FrostScheduler] 移除任务: %s", job_id)
            return True
        except Exception as e:
            logger.warning("[FrostScheduler] 移除任务失败: %s, error=%s", job_id, e)
            return False

    # ────────── 持久化 ──────────

    def _persist_job(self, job_id, job_type, target_id, cron_expr):
        """持久化任务到数据库"""
        try:
            from core.db import get_db

            db = get_db()
            db.insert(
                "scheduled_jobs",
                {
                    "id": job_id,
                    "job_type": job_type,
                    "target_id": target_id or "",
                    "cron_expr": cron_expr,
                    "enabled": 1,
                    "run_count": 0,
                    "fail_count": 0,
                },
            )
        except Exception as e:
            logger.warning("[FrostScheduler] 持久化任务失败: %s, error=%s", job_id, e)

    def _remove_persisted_job(self, job_id):
        """从数据库移除任务记录"""
        try:
            from core.db import get_db

            db = get_db()
            db.delete("scheduled_jobs", "id", job_id)
        except Exception as e:
            logger.warning("[FrostScheduler] 移除持久化失败: %s", e)

    def _restore_jobs(self):
        """从数据库恢复所有任务"""
        try:
            from core.db import get_db

            db = get_db()
            rows = db.select_all("scheduled_jobs", where="enabled=1")
            if not rows:
                return

            restored = 0
            for row in rows:
                job_id = row.get("id", "")
                job_type = row.get("job_type", "")
                target_id = row.get("target_id", "")
                cron_expr = row.get("cron_expr", "")

                if not cron_expr:
                    continue

                _job_func = _job_factory(job_type, target_id, self._store)
                self._get_scheduler().add_job(
                    _job_func,
                    "cron",
                    id=job_id,
                    **parse_cron(cron_expr),
                )
                restored += 1

            logger.info("[FrostScheduler] 从数据库恢复了 %d 个任务", restored)
        except Exception as e:
            logger.warning("[FrostScheduler] 恢复任务失败: %s", e)


class _NoOpScheduler:
    """当 apscheduler 不可用时的 No-Op 实现"""

    def add_job(self, func, trigger, **kwargs):
        logger.warning("[FrostScheduler/NoOp] 跳过 add_job (apscheduler未安装)")

    def get_jobs(self):
        return []

    def remove_job(self, job_id):
        pass

    def start(self):
        pass

    def shutdown(self, wait=False):
        pass


# ============================================================
# 辅助函数
# ============================================================


def parse_cron(cron_expr: str) -> dict:
    """解析 cron 表达式为 APScheduler 参数"""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError(f"无效的 cron 表达式: {cron_expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def _timestamp_short() -> str:
    """生成短时间戳"""
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _job_factory(job_type: str, target_id: str, store):
    """工厂函数：返回对应类型的 job 函数"""
    if job_type == "sop":

        def _job():
            _execute_sop_job(target_id, store)

        return _job
    elif job_type == "hunt":

        def _job():
            _execute_hunt_job(target_id, store)

        return _job
    elif job_type == "snapshot":

        def _job():
            _execute_snapshot_job(store)

        return _job
    elif job_type == "retrospective":

        def _job():
            _execute_retrospective_job(store)

        return _job
    else:
        logger.warning("[FrostScheduler] 未知job类型: %s", job_type)
        return lambda: None


# ============================================================
# Job 执行函数
# ============================================================


def _execute_sop_job(sop_id: str, store) -> None:
    """执行定时SOP任务"""
    try:
        from core.db import get_db
        from skills.orchestration import execute_stage

        logger.info("[FrostScheduler/SOP] 开始执行: %s", sop_id)
        ctx = {
            "_sop_id": sop_id,
            "_asset_store": store,
        }
        ctx = execute_stage(ctx)
        stage_result = ctx.get("_result", "unknown")
        logger.info("[FrostScheduler/SOP] 完成: %s → %s", sop_id, stage_result)

        # 记录审计
        db = get_db()
        db.log_audit(
            {
                "agent_id": "scheduler",
                "action": "scheduled_sop_executed",
                "details": f"sop_id={sop_id} | result={stage_result}",
                "level": "info",
            }
        )
    except Exception as e:
        logger.warning("[FrostScheduler/SOP] 失败: %s, error=%s", sop_id, e)
        try:
            from core.db import get_db

            get_db().log_audit(
                {
                    "agent_id": "scheduler",
                    "action": "scheduled_sop_failed",
                    "details": f"sop_id={sop_id} | error={str(e)[:200]}",
                    "level": "warning",
                }
            )
        except Exception:
            pass


def _execute_hunt_job(skill_id: str, store) -> None:
    """执行定时狩猎任务"""
    try:
        from core.db import get_db
        from skills.hunt_orchestration import hunt_and_evolve

        logger.info("[FrostScheduler/Hunt] 开始狩猎: %s", skill_id)
        ctx = {
            "_asset_store": store,
            "_hunt_targets": [{"skill_id": skill_id}],
            "_hunt_mode": "continuous",
            "_auto_execute": False,
        }
        ctx = hunt_and_evolve(ctx)
        result = ctx.get("_hunt_evolution_result", {})
        logger.info("[FrostScheduler/Hunt] 完成: %s", skill_id)

        db = get_db()
        db.log_audit(
            {
                "agent_id": "scheduler",
                "action": "scheduled_hunt_executed",
                "details": (
                    f"skill_id={skill_id} | "
                    f"absorbed={result.get('hunt', {}).get('absorbed_count', 0)}"
                ),
                "level": "info",
            }
        )
    except Exception as e:
        logger.warning("[FrostScheduler/Hunt] 失败: %s, error=%s", skill_id, e)
        try:
            from core.db import get_db

            get_db().log_audit(
                {
                    "agent_id": "scheduler",
                    "action": "scheduled_hunt_failed",
                    "details": f"skill_id={skill_id} | error={str(e)[:200]}",
                    "level": "warning",
                }
            )
        except Exception:
            pass


def _execute_snapshot_job(store) -> None:
    """每日快照：记录系统状态"""
    try:
        from core.db import get_db

        db = get_db()

        # 快照：任务数、审计数、成本
        tasks = db.select_all("tasks") or []
        audits = db.select_all("audit_log") or []
        costs = db.select_all("cost_log") or []

        snapshot = {
            "timestamp": datetime.now().isoformat(),
            "task_count": len(tasks),
            "audit_count": len(audits),
            "cost_count": len(costs),
        }

        if store:
            store.save(f"snapshot:{datetime.now().strftime('%Y%m%d')}", snapshot)

        db.log_audit(
            {
                "agent_id": "scheduler",
                "action": "daily_snapshot",
                "details": str(snapshot),
                "level": "info",
            }
        )
        logger.info("[FrostScheduler/Snapshot] 完成: %s", snapshot)
    except Exception as e:
        logger.warning("[FrostScheduler/Snapshot] 失败: %s", e)


def _execute_retrospective_job(store) -> None:
    """周度复盘：分析本周所有任务"""
    try:
        from core.db import get_db
        from skills.analytics import (
            analyze_audit,
            analyze_finance,
            analyze_heartbeat,
            analyze_hunt,
            analyze_skill,
            analyze_task,
            integrate_briefings,
        )

        logger.info("[FrostScheduler/Retrospective] 开始周度复盘")
        ctx = {"_asset_store": store, "_analysis_depth": "light"}

        ctx = analyze_finance(ctx)
        ctx = analyze_skill(ctx)
        ctx = analyze_task(ctx)
        ctx = analyze_audit(ctx)
        ctx = analyze_heartbeat(ctx)
        ctx = analyze_hunt(ctx)
        ctx = integrate_briefings(ctx)

        briefing = ctx.get("_integrated_briefing", {})
        if store:
            store.save(f"retrospective:{datetime.now().strftime('%Y%m%d')}", briefing)

        db = get_db()
        db.log_audit(
            {
                "agent_id": "scheduler",
                "action": "weekly_retrospective",
                "details": str(briefing)[:500],
                "level": "info",
            }
        )
        logger.info("[FrostScheduler/Retrospective] 完成")
    except Exception as e:
        logger.warning("[FrostScheduler/Retrospective] 失败: %s", e)


# Skill 实例
frost_scheduler_schedule_skill = Skill("frost_scheduler_schedule", FrostScheduler)

# 全局调度器（懒加载，单例）
_global_scheduler = None


def get_scheduler(store=None) -> FrostScheduler:
    """获取全局调度器实例（单例）"""
    global _global_scheduler
    if _global_scheduler is None:
        _global_scheduler = FrostScheduler(store=store)
    return _global_scheduler
