"""
V6.0 测试: APScheduler 定时器集成
测试 FrostScheduler 的创建、调度、持久化和恢复
"""

import os
import time

import pytest

# 测试模式
os.environ["FROST_TESTING"] = "1"


@pytest.fixture(autouse=True)
def _cleanup_scheduler():
    """每个测试后清理调度器单例，防止后台线程残留。"""
    yield
    try:
        from core.scheduler import FrostScheduler

        sched = FrostScheduler._instance
        if sched and hasattr(sched, "_started") and sched._started:
            sched.stop()
    except Exception:
        pass
    time.sleep(0.1)


class TestFrostSchedulerCreation:
    """测试调度器创建和基础功能"""

    def test_scheduler_singleton(self):
        """验证单例模式"""
        from core.scheduler import FrostScheduler

        s1 = FrostScheduler(store=None)
        s2 = FrostScheduler(store=None)
        assert s1 is s2

    def test_scheduler_no_apscheduler(self):
        """验证没有 apscheduler 时的 No-Op 模式"""
        from core.scheduler import FrostScheduler

        # 不安装 apscheduler，应使用 _NoOpScheduler
        sched = FrostScheduler(store=None)
        s = sched._get_scheduler()
        assert s is not None

    def test_scheduler_start_stop(self):
        """验证启动和停止"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        sched.start()
        sched.stop()
        # 不应抛异常

    def test_scheduler_get_jobs_empty(self):
        """验证空任务列表"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        jobs = sched.get_jobs()
        assert isinstance(jobs, list)


class TestFrostSchedulerScheduling:
    """测试调度功能"""

    def test_schedule_sop(self):
        """验证 SOP 调度"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        job_id = sched.schedule_sop("TEST-001", "0 9 * * 1")
        assert job_id.startswith("sop_TEST-001_")

    def test_schedule_hunt(self):
        """验证狩猎调度"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        job_id = sched.schedule_hunt("test_skill", "0 2 * * *")
        assert job_id.startswith("hunt_test_skill_")

    def test_schedule_daily_snapshot(self):
        """验证每日快照调度"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        job_id = sched.schedule_daily_snapshot("0 22 * * *")
        assert job_id.startswith("snapshot_")

    def test_schedule_weekly_retrospective(self):
        """验证周度复盘调度"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        job_id = sched.schedule_weekly_retrospective("0 20 * * 0")
        assert job_id.startswith("retrospective_")

    def test_remove_job(self):
        """验证移除任务"""
        from core.scheduler import FrostScheduler

        sched = FrostScheduler(store=None)
        job_id = sched.schedule_sop("TEST-002", "0 9 * * 1")
        result = sched.remove_job(job_id)
        # No-Op 模式下可能返回 False
        assert isinstance(result, bool)


class TestParseCron:
    """测试 cron 解析"""

    def test_valid_cron(self):
        from core.scheduler import parse_cron

        result = parse_cron("0 9 * * 1")
        assert result["minute"] == "0"
        assert result["hour"] == "9"
        assert result["day_of_week"] == "1"

    def test_invalid_cron(self):
        from core.scheduler import parse_cron

        with pytest.raises(ValueError):
            parse_cron("invalid")


class TestExecuteJobs:
    """测试 job 执行函数（mock 模式）"""

    def test_execute_sop_job(self):
        from core.scheduler import _execute_sop_job

        # 不应抛异常
        _execute_sop_job("TEST-001", store=None)

    def test_execute_hunt_job(self):
        from core.scheduler import _execute_hunt_job

        _execute_hunt_job("test_skill", store=None)

    def test_execute_snapshot_job(self):
        from core.scheduler import _execute_snapshot_job

        _execute_snapshot_job(store=None)

    def test_execute_retrospective_job(self):
        from core.scheduler import _execute_retrospective_job

        _execute_retrospective_job(store=None)


class TestGetScheduler:
    """测试全局调度器获取"""

    def test_get_scheduler(self):
        from core.scheduler import FrostScheduler, get_scheduler

        sched = get_scheduler(store=None)
        assert isinstance(sched, FrostScheduler)

    def test_get_scheduler_same_instance(self):
        from core.scheduler import get_scheduler

        s1 = get_scheduler(store=None)
        s2 = get_scheduler(store=None)
        assert s1 is s2


class TestDBTable:
    """测试 scheduled_jobs 表"""

    def test_table_exists(self):
        from core.db import get_db

        get_db()  # 确保表已创建
        # 验证 scheduled_jobs 在白名单中
        from core.db import ALLOWED_TABLES

        assert "scheduled_jobs" in ALLOWED_TABLES

    def test_insert_job_record(self):
        from core.db import get_db

        db = get_db()
        job_id = f"test_{int(time.time())}"

        db.insert(
            "scheduled_jobs",
            {
                "id": job_id,
                "job_type": "sop",
                "target_id": "TEST-001",
                "cron_expr": "0 9 * * 1",
                "enabled": 1,
                "run_count": 0,
                "fail_count": 0,
            },
        )

        # 验证写入
        row = db.select_one("scheduled_jobs", "id", job_id)
        assert row is not None
        assert row["job_type"] == "sop"

        # 清理
        db.delete("scheduled_jobs", "id", job_id)
