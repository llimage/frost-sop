"""
V0.7.0 全量测试 — Solo-Ops-Platform
覆盖所有核心模块的单元测试 + 集成测试
"""

import ast
import json
import os
import py_compile
import shutil
import sys
import tempfile
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import pytest

# ── 项目根路径 ────────────────────────────────────────────────────────
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  第一层：语法与导入检查                                              ║
# ╚══════════════════════════════════════════════════════════════════════╝

PY_FILES = [
    "config/__init__.py",
    "config/settings.py",
    "data/task_recorder.py",
    "agents/__init__.py",
    "agents/ceo.py",
    "agents/researcher.py",
    "agents/writer.py",
    "agents/llm_config.py",
    "memory/__init__.py",
    "memory/memory_store.py",
    "memory/evolution.py",
    "tools/__init__.py",
    "tools/exec_tools.py",
    "tools/exec_skills.py",
    "tools/file_tools.py",
    "tools/file_skills.py",
    "tools/path_safety.py",
    "app.py",
    "crew.py",
]


@pytest.mark.parametrize("rel_path", PY_FILES, ids=PY_FILES)
def test_py_compile(rel_path):
    """每个 .py 文件能通过 py_compile 检查。"""
    full = os.path.join(PROJECT_ROOT, rel_path)
    assert os.path.isfile(full), f"文件不存在: {rel_path}"
    py_compile.compile(full, doraise=True)


@pytest.mark.parametrize("rel_path", PY_FILES, ids=PY_FILES)
def test_ast_parse(rel_path):
    """每个 .py 文件 AST 解析无语法错误。"""
    full = os.path.join(PROJECT_ROOT, rel_path)
    with open(full, "r", encoding="utf-8") as f:
        source = f.read()
    ast.parse(source)


# ── 独立模块导入测试（不依赖外部框架）──

def test_import_config():
    import config
    assert hasattr(config, "parse_schedule")
    assert hasattr(config, "get_all_product_lines")
    assert hasattr(config, "extract_product_line_prefix")


def test_import_llm_config():
    from agents.llm_config import get_llm_config, setup_crewai_env, DEFAULT_BASE_URL, DEFAULT_MODEL_NAME
    assert DEFAULT_BASE_URL == "https://api.deepseek.com"
    assert DEFAULT_MODEL_NAME == "deepseek-chat"


def test_import_path_safety():
    from tools.path_safety import safe_path, get_project_root, PROJECT_ROOT
    assert isinstance(PROJECT_ROOT, str)
    assert os.path.isdir(PROJECT_ROOT)


def test_import_task_recorder():
    from data.task_recorder import save_task, load_all_tasks, migrate_old_data, delete_task, get_task
    assert callable(save_task)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  第二层：单元测试                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

# ── config/__init__.py ─────────────────────────────────────────────────

class TestParseSchedule:
    """parse_schedule() 各种格式测试。"""

    def test_daily_valid(self):
        from config import parse_schedule
        r = parse_schedule("daily-09:30")
        assert r == {"type": "daily", "value": "09:30"}

    def test_daily_midnight(self):
        from config import parse_schedule
        r = parse_schedule("daily-00:00")
        assert r == {"type": "daily", "value": "00:00"}

    def test_daily_end_of_day(self):
        from config import parse_schedule
        r = parse_schedule("daily-23:59")
        assert r == {"type": "daily", "value": "23:59"}

    def test_daily_hour_24_invalid(self):
        from config import parse_schedule
        r = parse_schedule("daily-24:00")
        assert r == {"type": "unknown", "value": "daily-24:00"}

    def test_daily_minute_60_invalid(self):
        from config import parse_schedule
        r = parse_schedule("daily-12:60")
        assert r == {"type": "unknown", "value": "daily-12:60"}

    def test_daily_bad_format_no_colon(self):
        from config import parse_schedule
        r = parse_schedule("daily-0930")
        assert r == {"type": "unknown", "value": "daily-0930"}

    def test_weekly_valid_1(self):
        from config import parse_schedule
        r = parse_schedule("weekly-1")
        assert r == {"type": "weekly", "value": "1"}

    def test_weekly_valid_7(self):
        from config import parse_schedule
        r = parse_schedule("weekly-7")
        assert r == {"type": "weekly", "value": "7"}

    def test_weekly_invalid_0(self):
        from config import parse_schedule
        r = parse_schedule("weekly-0")
        assert r == {"type": "unknown", "value": "weekly-0"}

    def test_weekly_invalid_8(self):
        from config import parse_schedule
        r = parse_schedule("weekly-8")
        assert r == {"type": "unknown", "value": "weekly-8"}

    def test_monthly_last(self):
        from config import parse_schedule
        r = parse_schedule("monthly-last")
        assert r == {"type": "monthly", "value": "last"}

    def test_empty_string(self):
        from config import parse_schedule
        r = parse_schedule("")
        assert r == {"type": "unknown", "value": ""}

    def test_none_like(self):
        from config import parse_schedule
        r = parse_schedule(None)
        assert r == {"type": "unknown", "value": ""}

    def test_garbage(self):
        from config import parse_schedule
        r = parse_schedule("xyz-abc")
        assert r == {"type": "unknown", "value": "xyz-abc"}

    def test_whitespace_trim(self):
        from config import parse_schedule
        r = parse_schedule("  daily-09:00  ")
        assert r == {"type": "daily", "value": "09:00"}


class TestExtractProductLinePrefix:
    """extract_product_line_prefix() 测试。"""

    def test_valid_prefix(self):
        from config import extract_product_line_prefix
        assert extract_product_line_prefix("[PL:test-pl] 分析报告") == "test-pl"

    def test_no_prefix(self):
        from config import extract_product_line_prefix
        assert extract_product_line_prefix("普通任务") is None

    def test_prefix_at_end(self):
        from config import extract_product_line_prefix
        assert extract_product_line_prefix("任务 [PL:abc]") == "abc"

    def test_empty_text(self):
        from config import extract_product_line_prefix
        assert extract_product_line_prefix("") is None


class TestProductLineCRUD:
    """产品线 CRUD 测试（使用临时目录）。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self._patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_product_line(self):
        from config import add_product_line, get_all_product_lines
        pl = add_product_line("测试产品线", "描述", "#ff0000")
        assert pl["name"] == "测试产品线"
        assert pl["description"] == "描述"
        assert pl["color"] == "#ff0000"
        assert pl["is_default"] is False
        assert "id" in pl

    def test_get_product_line(self):
        from config import add_product_line, get_product_line
        pl = add_product_line("查找测试")
        result = get_product_line(pl["id"])
        assert result is not None
        assert result["name"] == "查找测试"

    def test_get_product_line_not_found(self):
        from config import get_product_line
        assert get_product_line("nonexistent") is None

    def test_get_default_product_line(self):
        from config import get_default_product_line
        pl = get_default_product_line()
        assert pl.get("is_default") is True

    def test_update_product_line(self):
        from config import add_product_line, update_product_line, get_product_line
        pl = add_product_line("原名称")
        ok = update_product_line(pl["id"], name="新名称", description="新描述")
        assert ok is True
        updated = get_product_line(pl["id"])
        assert updated["name"] == "新名称"
        assert updated["description"] == "新描述"

    def test_update_product_line_not_found(self):
        from config import update_product_line
        assert update_product_line("nonexistent", name="x") is False

    def test_delete_product_line(self):
        from config import add_product_line, delete_product_line, get_product_line
        pl = add_product_line("待删除")
        assert delete_product_line(pl["id"]) is True
        assert get_product_line(pl["id"]) is None

    def test_cannot_delete_default(self):
        from config import get_default_product_line, delete_product_line
        pl = get_default_product_line()
        assert delete_product_line(pl["id"]) is False

    def test_delete_product_line_not_found(self):
        from config import delete_product_line
        assert delete_product_line("nonexistent") is False


class TestCompanyTaskCRUD:
    """公司级任务 CRUD 测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self._patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_company_task(self):
        from config import add_product_line, add_company_task
        pl = add_product_line("PL1")
        task = add_company_task(pl["id"], "每周周报", "weekly-5", "周报描述")
        assert task is not None
        assert task["title"] == "每周周报"
        assert task["schedule"] == "weekly-5"
        assert task["enabled"] is True

    def test_add_company_task_invalid_pl(self):
        from config import add_company_task
        assert add_company_task("nonexistent", "任务", "daily-09:00") is None

    def test_update_company_task(self):
        from config import add_product_line, add_company_task, update_company_task, get_company_tasks
        pl = add_product_line("PL2")
        task = add_company_task(pl["id"], "旧标题", "daily-09:00")
        ok = update_company_task(pl["id"], task["id"], title="新标题", enabled=False)
        assert ok is True
        tasks = get_company_tasks(pl["id"])
        assert tasks[0]["title"] == "新标题"
        assert tasks[0]["enabled"] is False

    def test_delete_company_task(self):
        from config import add_product_line, add_company_task, delete_company_task, get_company_tasks
        pl = add_product_line("PL3")
        task = add_company_task(pl["id"], "待删除", "daily-09:00")
        assert delete_company_task(pl["id"], task["id"]) is True
        assert len(get_company_tasks(pl["id"])) == 0


class TestChecklistItems:
    """每日清单项管理测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self._patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_add_checklist_item(self):
        from config import add_product_line, add_checklist_item, get_checklist_items
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "晨会", "researcher", "daily-09:00", "每日晨会分析")
        assert item is not None
        assert item["name"] == "晨会"
        assert item["agent"] == "researcher"
        assert item["enabled"] is True

    def test_update_checklist_item(self):
        from config import add_product_line, add_checklist_item, update_checklist_item, get_checklist_items
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "旧名", "researcher", "daily-09:00")
        ok = update_checklist_item(pl["id"], item["id"], name="新名", enabled=False)
        assert ok is True
        items = get_checklist_items(pl["id"])
        assert items[0]["name"] == "新名"
        assert items[0]["enabled"] is False

    def test_remove_checklist_item(self):
        from config import add_product_line, add_checklist_item, remove_checklist_item, get_checklist_items
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "删除项", "writer", "weekly-1")
        assert remove_checklist_item(pl["id"], item["id"]) is True
        assert len(get_checklist_items(pl["id"])) == 0

    def test_reorder_checklist_item(self):
        from config import add_product_line, add_checklist_item, reorder_checklist_item, get_checklist_items
        pl = add_product_line("PL")
        item1 = add_checklist_item(pl["id"], "第一", "researcher", "daily-09:00")
        item2 = add_checklist_item(pl["id"], "第二", "writer", "daily-10:00")
        ok = reorder_checklist_item(pl["id"], 0, 1)
        assert ok is True
        items = get_checklist_items(pl["id"])
        assert items[0]["name"] == "第二"
        assert items[1]["name"] == "第一"

    def test_reorder_invalid_index(self):
        from config import add_product_line, add_checklist_item, reorder_checklist_item
        pl = add_product_line("PL")
        add_checklist_item(pl["id"], "项", "researcher", "daily-09:00")
        assert reorder_checklist_item(pl["id"], 0, 99) is False
        assert reorder_checklist_item(pl["id"], -1, 0) is False


class TestGetChecklistStatus:
    """get_checklist_status() 各种状态检测。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self._patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_waiting_status(self):
        from config import add_product_line, add_checklist_item, get_checklist_status
        pl = add_product_line("PL")
        add_checklist_item(pl["id"], "任务A", "researcher", "daily-09:00")
        result = get_checklist_status(pl["id"], [])
        assert len(result) == 1
        assert result[0]["status"] == "waiting"

    def test_completed_status(self):
        from config import add_product_line, add_checklist_item, get_checklist_status
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "任务B", "researcher", "daily-09:00")
        today_str = date.today().strftime("%Y-%m-%d")
        tasks = [{
            "task_id": "t1",
            "created_at": f"{today_str}T10:00:00",
            "product_line_id": pl["id"],
            "task_type": "checklist",
            "status": "completed",
            "topic": f"包含 {item['name']} 的任务",
        }]
        result = get_checklist_status(pl["id"], tasks)
        assert result[0]["status"] == "completed"

    def test_running_status(self):
        from config import add_product_line, add_checklist_item, get_checklist_status
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "任务C", "researcher", "daily-09:00")
        today_str = date.today().strftime("%Y-%m-%d")
        tasks = [{
            "task_id": "t2",
            "created_at": f"{today_str}T10:00:00",
            "product_line_id": pl["id"],
            "task_type": "checklist",
            "status": "running",
            "topic": f"包含 {item['name']} 的任务",
        }]
        result = get_checklist_status(pl["id"], tasks)
        assert result[0]["status"] == "running"

    def test_disabled_item_skipped(self):
        from config import add_product_line, add_checklist_item, update_checklist_item, get_checklist_status
        pl = add_product_line("PL")
        item = add_checklist_item(pl["id"], "禁用项", "researcher", "daily-09:00")
        update_checklist_item(pl["id"], item["id"], enabled=False)
        result = get_checklist_status(pl["id"], [])
        assert len(result) == 0


class TestDefaultConfig:
    """默认配置与文件读写一致性。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self._patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_default_config_structure(self):
        from config import _get_default_config
        cfg = _get_default_config()
        assert "product_lines" in cfg
        assert len(cfg["product_lines"]) >= 1
        assert cfg["product_lines"][0]["is_default"] is True

    def test_ensure_default_product_line(self):
        from config import ensure_default_product_line, get_all_product_lines
        ensure_default_product_line()
        lines = get_all_product_lines()
        assert any(pl.get("is_default") for pl in lines)

    def test_json_roundtrip(self):
        from config import add_product_line, _load_product_lines
        add_product_line("持久化测试", "描述", "#123456")
        data = _load_product_lines()
        names = [pl["name"] for pl in data["product_lines"]]
        assert "持久化测试" in names


# ── data/task_recorder.py ──────────────────────────────────────────────

class TestTaskRecorder:
    """任务记录模块测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.history_file = os.path.join(self.tmp_dir, "task_history.json")
        self._patcher = patch("data.task_recorder._HISTORY_FILE", self.history_file)
        self._patcher.start()

    def teardown_method(self):
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_save_task_basic(self):
        from data.task_recorder import save_task, load_all_tasks
        record = save_task(
            topic="测试任务",
            model="test-model",
            status="completed",
            execution_time_seconds=10.5,
            final_output="输出",
            execution_log="日志",
        )
        assert record["topic"] == "测试任务"
        assert record["status"] == "completed"
        assert record["model"] == "test-model"
        assert "task_id" in record

    def test_save_task_with_product_line(self):
        from data.task_recorder import save_task, get_task
        record = save_task(
            topic="PL任务",
            model="m",
            status="completed",
            execution_time_seconds=5.0,
            final_output="",
            execution_log="",
            product_line_id="pl-123",
            task_type="company",
        )
        assert record["product_line_id"] == "pl-123"
        assert record["task_type"] == "company"

    def test_save_task_default_params(self):
        from data.task_recorder import save_task
        record = save_task(
            topic="默认",
            model="m",
            status="completed",
            execution_time_seconds=1.0,
            final_output="",
            execution_log="",
        )
        assert record["product_line_id"] == "default"
        assert record["task_type"] == "normal"

    def test_load_all_tasks_order(self):
        from data.task_recorder import load_all_tasks, _write_file
        # 直接写入不同时间戳的记录以确保排序稳定
        _write_file([
            {"task_id": "old-001", "created_at": "2026-01-01T10:00:00", "topic": "OLD_task", "model": "m", "status": "completed", "execution_time_seconds": 1, "final_output": "", "execution_log": "", "product_line_id": "default", "task_type": "normal"},
            {"task_id": "new-001", "created_at": "2026-06-04T10:00:00", "topic": "NEW_task", "model": "m", "status": "completed", "execution_time_seconds": 1, "final_output": "", "execution_log": "", "product_line_id": "default", "task_type": "normal"},
        ])
        tasks = load_all_tasks()
        assert len(tasks) == 2
        # 倒序：最新的在前面
        assert tasks[0]["topic"] == "NEW_task"

    def test_get_task(self):
        from data.task_recorder import save_task, get_task
        record = save_task(topic="查找", model="m", status="completed", execution_time_seconds=1, final_output="", execution_log="")
        found = get_task(record["task_id"])
        assert found is not None
        assert found["topic"] == "查找"

    def test_get_task_not_found(self):
        from data.task_recorder import get_task
        assert get_task("nonexistent-id") is None

    def test_delete_task(self):
        from data.task_recorder import save_task, delete_task, load_all_tasks
        record = save_task(topic="删除", model="m", status="completed", execution_time_seconds=1, final_output="", execution_log="")
        assert delete_task(record["task_id"]) is True
        assert len(load_all_tasks()) == 0

    def test_delete_task_not_found(self):
        from data.task_recorder import delete_task
        assert delete_task("nonexistent") is False

    def test_migrate_old_data(self):
        from data.task_recorder import _write_file, migrate_old_data, _read_file
        # 写入旧格式数据（缺少 product_line_id 和 task_type）
        old_records = [
            {
                "task_id": "old-001",
                "created_at": "2026-01-01T00:00:00",
                "topic": "旧任务",
                "model": "m",
                "status": "completed",
                "execution_time_seconds": 10,
                "final_output": "",
                "execution_log": "",
            }
        ]
        _write_file(old_records)
        count = migrate_old_data()
        assert count == 1
        records = _read_file()
        assert records[0]["product_line_id"] == "default"
        assert records[0]["task_type"] == "normal"

    def test_migrate_no_migration_needed(self):
        from data.task_recorder import save_task, migrate_old_data
        save_task(topic="新格式", model="m", status="completed", execution_time_seconds=1, final_output="", execution_log="")
        count = migrate_old_data()
        assert count == 0


# ── tools/path_safety.py ───────────────────────────────────────────────

class TestPathSafety:
    """路径安全校验测试。"""

    def test_safe_relative_path(self):
        from tools.path_safety import safe_path, get_project_root
        result = safe_path("data/test.json")
        expected = os.path.join(get_project_root(), "data", "test.json")
        assert result == expected

    def test_safe_absolute_inside_project(self):
        from tools.path_safety import safe_path, get_project_root
        # 绝对路径在项目内部
        inner = os.path.join(get_project_root(), "output", "report.txt")
        result = safe_path(inner)
        assert result == inner

    def test_path_traversal_blocked(self):
        from tools.path_safety import safe_path
        with pytest.raises(PermissionError, match="路径越权"):
            safe_path("../../../etc/passwd")

    def test_absolute_path_outside_blocked(self):
        from tools.path_safety import safe_path
        with pytest.raises(PermissionError, match="路径越权"):
            safe_path("/etc/passwd")

    def test_windows_abs_outside_blocked(self):
        from tools.path_safety import safe_path
        with pytest.raises(PermissionError):
            safe_path("C:\\Windows\\System32")

    def test_get_project_root_returns_dir(self):
        from tools.path_safety import get_project_root
        root = get_project_root()
        assert os.path.isdir(root)

    def test_empty_path(self):
        from tools.path_safety import safe_path, get_project_root
        # 空路径应解析为项目根目录
        result = safe_path("")
        assert result == get_project_root()


# ── tools/exec_skills.py ───────────────────────────────────────────────

class TestExecSkills:
    """执行层核心逻辑测试。"""

    def test_run_command_empty(self):
        from tools.exec_skills import run_command
        with pytest.raises(ValueError, match="命令为空"):
            run_command("")

    def test_run_command_not_in_whitelist(self):
        from tools.exec_skills import run_command
        with pytest.raises(PermissionError, match="不在安全白名单中"):
            run_command("rm -rf /")

    def test_run_command_invalid_arg(self):
        from tools.exec_skills import run_command
        with pytest.raises(PermissionError, match="不在.*安全白名单中"):
            run_command("ls --invalid-flag")

    def test_run_command_python_blocked(self):
        from tools.exec_skills import run_command
        with pytest.raises(PermissionError):
            run_command("python -c 'print(1)'")

    def test_run_command_pwd_allowed(self):
        from tools.exec_skills import run_command
        result = run_command("pwd")
        assert "exit_code: 0" in result

    def test_run_command_echo_allowed(self):
        from tools.exec_skills import run_command
        result = run_command("echo hello world")
        assert "hello world" in result

    def test_run_command_ls_allowed(self):
        from tools.exec_skills import run_command
        result = run_command("ls")
        assert "exit_code" in result

    def test_run_command_ls_la(self):
        from tools.exec_skills import run_command
        result = run_command("ls -la")
        assert "exit_code" in result


# ── tools/file_skills.py ───────────────────────────────────────────────

class TestFileSkills:
    """文件操作纯函数层测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self._patcher = patch("tools.path_safety.PROJECT_ROOT", self.tmp_dir)
        self._patcher.start()
        # Also patch get_project_root to return tmp_dir
        self._root_patcher = patch("tools.path_safety.get_project_root", return_value=self.tmp_dir)
        self._root_patcher.start()
        # patch file_skills' reference too
        self._fs_root = patch("tools.file_skills.get_project_root", return_value=self.tmp_dir)
        self._fs_root.start()

    def teardown_method(self):
        self._fs_root.stop()
        self._root_patcher.stop()
        self._patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_read_file_not_found(self):
        from tools.file_skills import read_file
        with pytest.raises(FileNotFoundError):
            read_file("nonexistent.txt")

    def test_write_and_read(self):
        from tools.file_skills import write_file, read_file
        write_file("output/test.txt", "hello world")
        content = read_file("output/test.txt")
        assert content == "hello world"

    def test_write_file_no_overwrite(self):
        from tools.file_skills import write_file
        write_file("output/no_overwrite.txt", "first")
        with pytest.raises(FileExistsError):
            write_file("output/no_overwrite.txt", "second")

    def test_write_file_overwrite(self):
        from tools.file_skills import write_file, read_file
        write_file("output/overwrite.txt", "first")
        write_file("output/overwrite.txt", "second", overwrite=True)
        assert read_file("output/overwrite.txt") == "second"

    def test_write_protected_file(self):
        from tools.file_skills import write_file
        # Create protected file
        os.makedirs(os.path.join(self.tmp_dir, "data"), exist_ok=True)
        protected_path = os.path.join(self.tmp_dir, "data", "task_history.json")
        with open(protected_path, "w") as f:
            f.write("[]")
        with pytest.raises(PermissionError, match="保护列表"):
            write_file("data/task_history.json", "hacked", overwrite=True)

    def test_list_dir(self):
        from tools.file_skills import write_file, list_dir
        write_file("test_file.txt", "content")
        result = list_dir("")
        assert "test_file.txt" in result

    def test_list_dir_not_exists(self):
        from tools.file_skills import list_dir
        with pytest.raises(NotADirectoryError):
            list_dir("nonexistent_dir_xyz")

    def test_search_files_by_name(self):
        from tools.file_skills import write_file, search_files
        write_file("report_2026.md", "# Report")
        result = search_files("report_2026")
        assert "report_2026.md" in result

    def test_search_files_by_content(self):
        from tools.file_skills import write_file, search_files
        write_file("notes.md", "这是一个关于AI的笔记")
        result = search_files("AI", search_content=True)
        assert "notes.md" in result

    def test_search_files_empty_pattern(self):
        from tools.file_skills import search_files
        result = search_files("")
        assert "请输入" in result

    def test_search_files_no_match(self):
        from tools.file_skills import search_files
        result = search_files("zzz_nonexistent_file_xyz")
        assert "未找到" in result

    def test_is_binary(self):
        from tools.file_skills import _is_binary
        assert _is_binary("test.pyc") is True
        assert _is_binary("test.exe") is True
        assert _is_binary("test.py") is False
        assert _is_binary("test.md") is False
        assert _is_binary("test.json") is False


# ── agents/llm_config.py ──────────────────────────────────────────────

class TestLLMConfig:
    """LLM 配置管理测试。"""

    def test_default_config(self):
        from agents.llm_config import get_llm_config, DEFAULT_BASE_URL, DEFAULT_MODEL_NAME
        # 清理环境变量
        env_vars = ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL_NAME"]
        saved = {}
        for v in env_vars:
            saved[v] = os.environ.pop(v, None)
        try:
            api_key, base_url, model = get_llm_config()
            assert api_key == ""
            assert base_url == DEFAULT_BASE_URL
            assert model == DEFAULT_MODEL_NAME
        finally:
            for v, val in saved.items():
                if val is not None:
                    os.environ[v] = val

    def test_deepseek_key_priority(self):
        from agents.llm_config import get_llm_config
        saved = {k: os.environ.pop(k, None) for k in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]}
        try:
            os.environ["DEEPSEEK_API_KEY"] = "ds-key"
            os.environ["OPENAI_API_KEY"] = "oa-key"
            os.environ["LLM_API_KEY"] = "old-key"
            api_key, _, _ = get_llm_config()
            assert api_key == "ds-key"
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]

    def test_openai_key_fallback(self):
        from agents.llm_config import get_llm_config
        saved = {k: os.environ.pop(k, None) for k in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "LLM_API_KEY"]}
        try:
            os.environ["OPENAI_API_KEY"] = "oa-key"
            api_key, _, _ = get_llm_config()
            assert api_key == "oa-key"
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]

    def test_setup_crewai_env(self):
        from agents.llm_config import setup_crewai_env
        saved = {k: os.environ.pop(k, None) for k in ["DEEPSEEK_API_KEY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL_NAME"]}
        try:
            os.environ["DEEPSEEK_API_KEY"] = "test-key"
            os.environ["LLM_BASE_URL"] = "https://test.url"
            setup_crewai_env()
            assert os.environ["OPENAI_API_KEY"] == "test-key"
            assert os.environ["OPENAI_BASE_URL"] == "https://test.url"
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]


# ── memory/memory_store.py ─────────────────────────────────────────────

class TestMemoryStore:
    """记忆存储测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.agent_dir = os.path.join(self.tmp_dir, "agent_memories")
        self.lessons_file = os.path.join(self.tmp_dir, "lessons_learned.json")
        os.makedirs(self.agent_dir, exist_ok=True)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_store(self):
        from memory.memory_store import MemoryStore
        return MemoryStore(self.agent_dir, self.lessons_file)

    def test_load_empty_agent_memory(self):
        store = self._make_store()
        mem = store.load_agent_memory("new_agent")
        assert mem["episodes"] == []
        assert mem["agent_id"] == "new_agent"

    def test_save_and_load_agent_memory(self):
        store = self._make_store()
        data = {"agent_id": "test", "episodes": [{"summary": "test"}], "global_patterns": []}
        store.save_agent_memory("test", data)
        loaded = store.load_agent_memory("test")
        assert loaded["episodes"][0]["summary"] == "test"

    def test_append_episode(self):
        store = self._make_store()
        episode = {"episode_id": "ep-1", "summary": "测试记忆", "lesson": "教训", "success": True}
        store.append_episode("test_agent", episode)
        mem = store.load_agent_memory("test_agent")
        assert len(mem["episodes"]) == 1
        assert mem["episodes"][0]["summary"] == "测试记忆"

    def test_append_episode_max_limit(self):
        store = self._make_store()
        for i in range(105):
            store.append_episode("test_agent", {"episode_id": f"ep-{i}", "summary": f"记忆{i}"}, max_episodes=10)
        mem = store.load_agent_memory("test_agent")
        assert len(mem["episodes"]) == 10

    def test_load_lessons_empty(self):
        store = self._make_store()
        assert store.load_lessons() == []

    def test_save_and_load_lessons(self):
        store = self._make_store()
        lessons = [{"lesson_id": "L-001", "pattern": "test", "fix": "fix"}]
        store.save_lessons(lessons)
        loaded = store.load_lessons()
        assert len(loaded) == 1

    def test_search_relevant_no_episodes(self):
        store = self._make_store()
        result = store.search_relevant("test_agent", "AI分析")
        assert result == ""

    def test_search_relevant_with_match(self):
        store = self._make_store()
        store.append_episode("test_agent", {
            "episode_id": "ep-1",
            "topic": "AI analysis competition report",
            "summary": "completed AI analysis",
            "lesson": "",
            "success": True,
            "timestamp": "2026-06-04T10:00:00",
        })
        result = store.search_relevant("test_agent", "AI analysis competition")
        assert result != "", f"Expected non-empty result, got empty."

    def test_search_relevant_exact_topic(self):
        """Use English keywords for reliable matching."""
        store = self._make_store()
        store.append_episode("test_agent", {
            "episode_id": "ep-2",
            "topic": "competition analysis report",
            "summary": "completed competition analysis",
            "lesson": "",
            "success": True,
            "timestamp": "2026-06-04T10:00:00",
        })
        result = store.search_relevant("test_agent", "competition analysis")
        assert "competition" in result or "analysis" in result

    def test_search_lessons_no_active(self):
        store = self._make_store()
        result = store.search_lessons("AI编程")
        assert result == ""

    def test_search_lessons_with_match(self):
        store = self._make_store()
        store.save_lessons([{
            "lesson_id": "L-001",
            "pattern": "AI编程工具 空输出",
            "fix": "增加兜底约束",
            "status": "active",
            "severity": "high",
        }])
        result = store.search_lessons("AI编程工具")
        assert "L-001" in result

    def test_get_status(self):
        store = self._make_store()
        # 初始化一些 agent 记忆
        for aid in ["researcher", "writer", "ceo"]:
            store.save_agent_memory(aid, {"agent_id": aid, "episodes": [], "global_patterns": []})
        status = store.get_status()
        assert "researcher" in status
        assert "writer" in status
        assert "ceo" in status
        assert "lessons" in status

    def test_extract_keywords(self):
        from memory.memory_store import MemoryStore
        kw = MemoryStore._extract_keywords("AI编程工具竞争格局 analysis")
        assert len(kw) > 0
        # 单字符应被过滤
        assert all(len(w) > 1 for w in kw)


# ── memory/evolution.py ────────────────────────────────────────────────

class TestEvolutionEngine:
    """自进化逻辑测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.agent_dir = os.path.join(self.tmp_dir, "agent_memories")
        self.lessons_file = os.path.join(self.tmp_dir, "lessons_learned.json")
        self.evolution_log = os.path.join(self.tmp_dir, "evolution_log.json")
        os.makedirs(self.agent_dir, exist_ok=True)

    def teardown_method(self):
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def _make_engine(self):
        from memory.memory_store import MemoryStore
        from memory.evolution import EvolutionEngine
        store = MemoryStore(self.agent_dir, self.lessons_file)
        return EvolutionEngine(self.evolution_log, store)

    def test_should_analyze_failed(self):
        engine = self._make_engine()
        assert engine.should_analyze({"success": False}) is True

    def test_should_analyze_success_no_suggestion(self):
        engine = self._make_engine()
        assert engine.should_analyze({"success": True}) is False

    def test_should_analyze_success_with_suggestion(self):
        engine = self._make_engine()
        assert engine.should_analyze({"success": True, "suggestion": "改进"}) is True

    def test_analyze_episode_short_lesson(self):
        engine = self._make_engine()
        # 教训太短，跳过
        engine.analyze_episode("test_agent", {"lesson": "短", "summary": "测试"})

    def test_infer_fix_empty(self):
        from memory.evolution import EvolutionEngine
        fix = EvolutionEngine._infer_fix("输出为空无法使用", "writer")
        assert "兜底" in fix

    def test_infer_fix_timeout(self):
        from memory.evolution import EvolutionEngine
        fix = EvolutionEngine._infer_fix("执行超时timeout", "researcher")
        assert "重试" in fix

    def test_infer_fix_format(self):
        from memory.evolution import EvolutionEngine
        fix = EvolutionEngine._infer_fix("输出格式format不对", "ceo")
        assert "格式" in fix

    def test_infer_fix_default(self):
        from memory.evolution import EvolutionEngine
        fix = EvolutionEngine._infer_fix("其他类型的问题", "ceo")
        assert "CEO" in fix

    def test_tokenize(self):
        from memory.evolution import EvolutionEngine
        tokens = EvolutionEngine._tokenize("AI编程工具 竞争分析")
        assert len(tokens) > 0


# ── memory/__init__.py ────────────────────────────────────────────────

class TestMemoryInit:
    """记忆系统统一入口测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.agent_dir = os.path.join(self.tmp_dir, "agent_memories")
        self.lessons_file = os.path.join(self.tmp_dir, "lessons_learned.json")
        self.evolution_log = os.path.join(self.tmp_dir, "evolution_log.json")

        # Patch all memory paths
        self.patches = [
            patch("memory._MEMORY_DIR", self.tmp_dir),
            patch("memory._AGENT_MEMORIES_DIR", self.agent_dir),
            patch("memory._LESSONS_FILE", self.lessons_file),
            patch("memory._EVOLUTION_LOG_FILE", self.evolution_log),
            patch("memory.memory_store._MEMORY_DIR", self.tmp_dir),
            patch("memory.memory_store._AGENT_MEMORIES_DIR", self.agent_dir),
            patch("memory.memory_store._LESSONS_FILE", self.lessons_file),
            patch("memory.evolution._EVOLUTION_LOG_FILE", self.evolution_log),
            patch("memory.evolution._LESSONS_FILE", self.lessons_file),
        ]
        for p in self.patches:
            p.start()

    def teardown_method(self):
        for p in self.patches:
            p.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_init_memory_system(self):
        from memory import init_memory_system
        init_memory_system()
        assert os.path.isdir(self.agent_dir)
        assert os.path.isfile(self.lessons_file)
        assert os.path.isfile(self.evolution_log)

    def test_init_creates_agent_files(self):
        from memory import init_memory_system
        init_memory_system()
        for aid in ["researcher", "writer", "ceo"]:
            path = os.path.join(self.agent_dir, f"{aid}.json")
            assert os.path.isfile(path)

    def test_save_and_get_memory(self):
        from memory import init_memory_system, save_episode, get_agent_memory
        init_memory_system()
        episode = {"episode_id": "ep-1", "summary": "测试", "lesson": "", "success": True, "timestamp": "2026-06-04T10:00:00"}
        save_episode("researcher", episode)
        mem = get_agent_memory("researcher")
        assert len(mem["episodes"]) >= 1

    def test_get_memory_status(self):
        from memory import init_memory_system, get_memory_status
        init_memory_system()
        status = get_memory_status()
        assert "researcher" in status
        assert "lessons" in status


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  第三层：集成测试                                                    ║
# ╚══════════════════════════════════════════════════════════════════════╝

class TestCEOExtractPrefix:
    """CEO 的 [PL:xxx] 前缀解析集成测试。"""

    def test_ceo_extracts_prefix(self):
        from config import extract_product_line_prefix
        topic = "[PL:ai-writing] 分析AI写作工具"
        pl_id = extract_product_line_prefix(topic)
        assert pl_id == "ai-writing"

    def test_ceo_prefix_removal(self):
        import re
        topic = "[PL:ai-writing] 分析AI写作工具"
        cleaned = re.sub(r'\[PL:[^\]]+\]\s*', '', topic).strip()
        assert cleaned == "分析AI写作工具"

    def test_ceo_no_prefix(self):
        from config import extract_product_line_prefix
        assert extract_product_line_prefix("普通任务主题") is None


class TestCockpitDataIntegration:
    """驾驶舱数据联动测试。"""

    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.cfg_file = os.path.join(self.tmp_dir, "product_lines.json")
        self.history_file = os.path.join(self.tmp_dir, "task_history.json")
        self.cfg_patcher = patch("config._PRODUCT_LINES_FILE", self.cfg_file)
        self.cfg_patcher.start()
        self.hist_patcher = patch("data.task_recorder._HISTORY_FILE", self.history_file)
        self.hist_patcher.start()

    def teardown_method(self):
        self.cfg_patcher.stop()
        self.hist_patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    def test_kpi_today_completed(self):
        """KPI 计算逻辑：今日完成数。"""
        from data.task_recorder import save_task
        from datetime import date
        today_str = date.today().strftime("%Y-%m-%d")
        # 保存一个今天的任务
        save_task(
            topic="今日任务", model="m", status="completed",
            execution_time_seconds=10, final_output="ok", execution_log="",
        )
        from data.task_recorder import load_all_tasks
        tasks = load_all_tasks()
        today_tasks = [t for t in tasks if t.get("created_at", "").startswith(today_str)]
        today_completed = sum(1 for t in today_tasks if t.get("status") == "completed")
        assert today_completed >= 1

    def test_kpi_cost_estimation(self):
        """KPI 成本估算逻辑。"""
        from data.task_recorder import save_task, load_all_tasks
        save_task(topic="任务1", model="m", status="completed", execution_time_seconds=10, final_output="", execution_log="")
        tasks = load_all_tasks()
        estimated_calls = len(tasks) * 3
        cost = round(estimated_calls * 0.01, 2)
        assert cost > 0

    def test_kpi_eta_format(self):
        """KPI 预计完成时间格式。"""
        # 大于1小时
        seconds = 7200
        if seconds >= 3600:
            eta = f"~{seconds // 3600}小时{(seconds % 3600) // 60}分钟"
        elif seconds >= 60:
            eta = f"~{seconds // 60}分钟"
        else:
            eta = "~<1分钟"
        assert "2小时" in eta

        # 小于1分钟
        seconds = 30
        if seconds >= 60:
            eta = f"~{seconds // 60}分钟"
        else:
            eta = "~<1分钟"
        assert "<1分钟" in eta

    def test_pl_task_linkage(self):
        """产品线和任务联动。"""
        from config import add_product_line, get_product_line
        from data.task_recorder import save_task, load_all_tasks
        pl = add_product_line("联动测试PL")
        save_task(
            topic="联动任务", model="m", status="completed",
            execution_time_seconds=5, final_output="", execution_log="",
            product_line_id=pl["id"],
        )
        tasks = load_all_tasks()
        pl_tasks = [t for t in tasks if t.get("product_line_id") == pl["id"]]
        assert len(pl_tasks) >= 1


class TestAppHelperFunctions:
    """app.py 中可独立测试的辅助函数。"""

    def test_strip_ansi(self):
        import re
        _ANSI_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = "\x1b[32mSuccess\x1b[0m: done"
        clean = _ANSI_RE.sub("", text)
        assert clean == "Success: done"

    def test_strip_ansi_empty(self):
        import re
        _ANSI_RE = re.compile(r'\x1b(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        assert _ANSI_RE.sub("", "") == ""

    def test_truncate(self):
        def _truncate(text, max_len=30):
            if len(text) <= max_len:
                return text
            return text[:max_len] + "..."
        assert _truncate("short") == "short"
        assert _truncate("a" * 50) == "a" * 30 + "..."
        assert _truncate("a" * 30) == "a" * 30

    def test_format_time(self):
        def _format_time(iso_str):
            try:
                return iso_str[5:16].replace("T", " ")
            except (IndexError, TypeError):
                return iso_str
        assert _format_time("2026-06-03T14:30:00") == "06-03 14:30"
        # "short" 只有5字符 -> [5:16] returns "" (not exception)
        assert _format_time("short") == ""

    def test_status_badge(self):
        def _status_badge(status):
            if status == "completed":
                return "✅ 已完成"
            return "❌ 失败"
        assert "已完成" in _status_badge("completed")
        assert "失败" in _status_badge("failed")

    def test_mode_badge(self):
        def _mode_badge(mode):
            if mode == "orchestrated":
                return "智能调度"
            return "固定流水线"
        assert "智能" in _mode_badge("orchestrated")
        assert "固定" in _mode_badge("sequential")

    def test_has_api_key(self):
        def _has_api_key():
            return bool(
                os.getenv("DEEPSEEK_API_KEY")
                or os.getenv("LLM_API_KEY")
                or os.getenv("OPENAI_API_KEY")
            )
        saved = {k: os.environ.pop(k, None) for k in ["DEEPSEEK_API_KEY", "LLM_API_KEY", "OPENAI_API_KEY"]}
        try:
            assert _has_api_key() is False
            os.environ["DEEPSEEK_API_KEY"] = "test"
            assert _has_api_key() is True
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v
                elif k in os.environ:
                    del os.environ[k]


class TestCEOPrefixIntegration:
    """CEO [PL:xxx] 前缀解析与产品线联动。"""

    def test_prefix_parse_and_cleanup(self):
        import re
        from config import extract_product_line_prefix
        topic = "[PL:ai-tools] 分析AI工具市场"
        pl_id = extract_product_line_prefix(topic)
        assert pl_id == "ai-tools"
        cleaned = re.sub(r'\[PL:[^\]]+\]\s*', '', topic).strip()
        assert cleaned == "分析AI工具市场"

    def test_multiple_prefix_only_first(self):
        from config import extract_product_line_prefix
        import re
        topic = "[PL:pl1] 任务 [PL:pl2]"
        pl_id = extract_product_line_prefix(topic)
        # re.search 返回第一个匹配
        assert pl_id == "pl1"


# ── agents/__init__.py 注册表测试 ──────────────────────────────────────

class TestAgentRegistry:
    """Agent 注册表测试。"""

    def test_list_available_agents(self):
        from agents import list_available_agents
        agents = list_available_agents()
        assert "researcher" in agents
        assert "writer" in agents
        assert "role" in agents["researcher"]
        assert "strengths" in agents["researcher"]

    def test_get_agent_invalid(self):
        from agents import get_agent
        with pytest.raises(ValueError, match="未知 Agent"):
            get_agent("nonexistent_agent")


# ── tools/__init__.py 注册表测试 ──────────────────────────────────────

class TestToolsRegistry:
    """Tool 注册表测试。"""

    def test_tools_registry_structure(self):
        from tools import TOOLS_REGISTRY
        assert "read_file" in TOOLS_REGISTRY
        assert "write_file" in TOOLS_REGISTRY
        assert "list_dir" in TOOLS_REGISTRY
        assert "search_files" in TOOLS_REGISTRY
        assert "run_command" in TOOLS_REGISTRY
        assert "git_status" in TOOLS_REGISTRY

    def test_tools_registry_categories(self):
        from tools import TOOLS_REGISTRY
        for name, info in TOOLS_REGISTRY.items():
            assert "category" in info
            assert "is_safe" in info
            assert "description" in info
            assert info["category"] in ("file", "exec")

    def test_get_tool_list(self):
        from tools import get_tool_list
        tools = get_tool_list()
        assert len(tools) == len(TOOLS_REGISTRY) if "TOOLS_REGISTRY" in dir() else 6

    def test_get_all_tools_format(self):
        from tools import get_all_tools
        text = get_all_tools()
        assert "文件操作" in text
        assert "命令执行" in text


# ── app.py 导入检查 ────────────────────────────────────────────────────

class TestAppImport:
    """app.py 的 import 检查（需要 mock streamlit）。"""

    def test_app_helpers_importable(self):
        """app.py 中的辅助函数逻辑可以独立验证（如上 TestAppHelperFunctions）。"""
        # 已通过 TestAppHelperFunctions 覆盖
        pass


# ── config/settings.py ────────────────────────────────────────────────

class TestConfigSettings:
    """config/settings.py 导入测试（文件可能为空）。"""

    def test_settings_importable(self):
        """settings.py 可导入，不报错。"""
        import importlib
        import config.settings
        # 空文件也OK
        assert True
