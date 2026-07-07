"""
V7 阶段3 覆盖率补测试 — core/workbench.py (0% → 80%+)
工作台核心模块：项目上下文管理、能量推荐、日终回顾、配置快照
"""

import os
import sys

import pytest

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.db import DBManager, get_db
from core.workbench import (
    DEFAULT_PROJECTS,
    PROJECT_BY_ID,
    PROJECT_BY_MODE,
    ensure_default_projects,
    ensure_workbench_migrations,
    generate_daily_narrative,
    get_business_radar_data,
    get_project_by_id,
    get_project_by_mode,
    get_project_defaults,
    get_recommended_task,
    get_today_review,
    load_project_snapshots,
    save_daily_review,
    save_project_snapshot,
)


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path):
    """每个测试使用独立数据库"""
    db_path = str(tmp_path / "test_workbench.db")
    db = DBManager(db_path=db_path)
    # monkeypatch get_db 全局变量
    import core.db as db_mod

    old_manager = db_mod._db_manager
    db_mod._db_manager = db
    yield db
    db_mod._db_manager = old_manager


class TestProjectConstants:
    """项目配置常量测试"""

    def test_default_projects_has_three(self):
        assert len(DEFAULT_PROJECTS) == 3

    def test_default_projects_ids(self):
        ids = {p["id"] for p in DEFAULT_PROJECTS}
        assert ids == {"saas", "column", "consult"}

    def test_project_by_mode_keys(self):
        assert set(PROJECT_BY_MODE.keys()) == {"dev", "create", "client"}

    def test_project_by_id_keys(self):
        assert set(PROJECT_BY_ID.keys()) == {"saas", "column", "consult"}

    def test_get_project_defaults_returns_list(self):
        result = get_project_defaults()
        assert isinstance(result, list)
        assert len(result) == 3

    def test_get_project_by_mode_dev(self):
        proj = get_project_by_mode("dev")
        assert proj is not None
        assert proj["id"] == "saas"

    def test_get_project_by_mode_create(self):
        proj = get_project_by_mode("create")
        assert proj is not None
        assert proj["id"] == "column"

    def test_get_project_by_mode_client(self):
        proj = get_project_by_mode("client")
        assert proj is not None
        assert proj["id"] == "consult"

    def test_get_project_by_mode_unknown(self):
        result = get_project_by_mode("unknown")
        assert result is None

    def test_get_project_by_id_saas(self):
        proj = get_project_by_id("saas")
        assert proj is not None
        assert proj["name"] == "轻云SaaS"

    def test_get_project_by_id_unknown(self):
        result = get_project_by_id("nonexistent")
        assert result is None


class TestEnsureDefaultProjects:
    """默认项目初始化测试"""

    def test_ensure_creates_projects(self, _fresh_db):
        ensure_workbench_migrations()  # 先跑迁移确保列存在
        ensure_default_projects()
        # 查询确认项目已创建
        db = get_db()
        for proj in DEFAULT_PROJECTS:
            row = db.select_one("projects", "id", proj["id"])
            assert row is not None, f"项目 {proj['id']} 应存在"

    def test_ensure_idempotent(self, _fresh_db):
        ensure_workbench_migrations()
        ensure_default_projects()
        ensure_default_projects()  # 第二次不应报错
        db = get_db()
        count = len(db.select_all("projects"))
        assert count == 3  # 不应重复创建


class TestWorkbenchMigrations:
    """工作台数据库迁移测试"""

    def test_migrations_create_tables(self, _fresh_db):
        ensure_workbench_migrations()
        db = get_db()
        # 验证 project_skills 表
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='project_skills'"
        )
        assert cursor.fetchone() is not None
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config_snapshots'"
        )
        assert cursor.fetchone() is not None
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_reviews'")
        assert cursor.fetchone() is not None

    def test_migrations_add_columns(self, _fresh_db):
        ensure_workbench_migrations()
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cols = {col["name"] for col in cursor.execute("PRAGMA table_info(projects)").fetchall()}
        assert "sop_template" in cols
        assert "energy_level" in cols
        assert "config_ref" in cols
        assert "metadata" in cols
        assert "last_active_at" in cols

    def test_migrations_idempotent(self, _fresh_db):
        ensure_workbench_migrations()
        ensure_workbench_migrations()  # 不应报错


class TestRecommendedTask:
    """能量感知任务推荐测试"""

    def test_get_recommended_task_dev(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_recommended_task("dev")
        assert result["project_id"] == "saas"
        assert result["mode"] == "dev"
        assert "task_name" in result
        assert "energy_match" in result

    def test_get_recommended_task_create(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_recommended_task("create")
        assert result["project_id"] == "column"
        assert result["mode"] == "create"

    def test_get_recommended_task_client(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_recommended_task("client")
        assert result["project_id"] == "consult"

    def test_energy_match_high(self, _fresh_db):
        ensure_workbench_migrations()
        db = get_db()
        db.insert(
            "agents",
            {"id": "test", "name": "test_agent", "agent_type": "mercenary", "generation": 1},
        )
        db.insert(
            "energy_log", {"level": 80, "timestamp": "2026-07-07T12:00:00", "agent_id": "test"}
        )
        result = get_recommended_task("dev")
        assert result["energy_match"] == "match"

    def test_energy_match_medium(self, _fresh_db):
        ensure_workbench_migrations()
        db = get_db()
        db.insert(
            "agents",
            {"id": "test", "name": "test_agent", "agent_type": "mercenary", "generation": 1},
        )
        db.insert(
            "energy_log", {"level": 45, "timestamp": "2026-07-07T12:00:00", "agent_id": "test"}
        )
        result = get_recommended_task("dev")
        assert result["energy_match"] == "partial"

    def test_energy_match_low(self, _fresh_db):
        ensure_workbench_migrations()
        db = get_db()
        db.insert(
            "agents",
            {"id": "test", "name": "test_agent", "agent_type": "mercenary", "generation": 1},
        )
        db.insert(
            "energy_log", {"level": 20, "timestamp": "2026-07-07T12:00:00", "agent_id": "test"}
        )
        result = get_recommended_task("dev")
        assert result["energy_match"] == "mismatch"

    def test_alternatives_present(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_recommended_task("dev")
        assert len(result["alternatives"]) >= 1

    def test_unknown_mode_fallback(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_recommended_task("nonexistent")
        assert result["project_id"] == "nonexistent"
        assert result["project_name"] == "未命名项目"
        assert result["energy_match"] == "match"


class TestDailyReview:
    """日终回顾测试"""

    def test_generate_daily_narrative(self, _fresh_db):
        ensure_workbench_migrations()
        narrative = generate_daily_narrative()
        assert isinstance(narrative, str)
        assert len(narrative) > 0

    def test_save_daily_review_auto(self, _fresh_db):
        ensure_workbench_migrations()
        review_id = save_daily_review()
        assert isinstance(review_id, int)
        assert review_id > 0

    def test_save_daily_review_with_narrative(self, _fresh_db):
        ensure_workbench_migrations()
        review_id = save_daily_review(narrative="自定义叙事", confirmed=True)
        assert review_id > 0
        db = get_db()
        row = db.select_one("daily_reviews", "id", review_id)
        assert row is not None

    def test_get_today_review_none(self, _fresh_db):
        ensure_workbench_migrations()
        result = get_today_review()
        # 如果没有保存，应为None
        assert result is None

    def test_get_today_review_after_save(self, _fresh_db):
        ensure_workbench_migrations()
        save_daily_review(narrative="测试回顾")
        result = get_today_review()
        assert result is not None

    def test_save_daily_review_update_existing(self, _fresh_db):
        ensure_workbench_migrations()
        id1 = save_daily_review(narrative="第一次")
        id2 = save_daily_review(narrative="第二次", confirmed=True)
        assert id1 == id2  # 同一天的review应更新而非新建


class TestProjectSnapshot:
    """项目级配置快照测试"""

    def test_save_project_snapshot(self, _fresh_db):
        ensure_workbench_migrations()
        snap_id = save_project_snapshot(
            "saas",
            "开发登录功能",
            {"phase": 2},
            ["coding", "testing"],
        )
        assert isinstance(snap_id, int)
        assert snap_id > 0

    def test_save_snapshot_with_name(self, _fresh_db):
        ensure_workbench_migrations()
        snap_id = save_project_snapshot(
            "saas",
            "开发登录",
            {},
            [],
            snapshot_name="手动快照V1",
        )
        assert snap_id > 0

    def test_load_project_snapshots(self, _fresh_db):
        ensure_workbench_migrations()
        save_project_snapshot("saas", "任务1", {}, [])
        save_project_snapshot("saas", "任务2", {}, [])
        snapshots = load_project_snapshots("saas")
        assert len(snapshots) == 2

    def test_load_snapshots_empty(self, _fresh_db):
        ensure_workbench_migrations()
        snapshots = load_project_snapshots("nonexistent")
        assert snapshots == []


class TestBusinessRadar:
    """业务雷达数据测试"""

    def test_radar_has_three_lines(self, _fresh_db):
        ensure_workbench_migrations()
        radar = get_business_radar_data()
        assert len(radar) == 3

    def test_radar_data_structure(self, _fresh_db):
        ensure_workbench_migrations()
        radar = get_business_radar_data()
        for item in radar:
            assert "id" in item
            assert "name" in item
            assert "icon" in item
            assert "color" in item
            assert "active_tasks" in item
            assert "revenue_monthly" in item
            assert "mode" in item

    def test_radar_revenue_values(self, _fresh_db):
        ensure_workbench_migrations()
        radar = get_business_radar_data()
        revenues = {r["id"]: r["revenue_monthly"] for r in radar}
        assert revenues["saas"] == 34200
        assert revenues["column"] == 6000
        assert revenues["consult"] == 15000
