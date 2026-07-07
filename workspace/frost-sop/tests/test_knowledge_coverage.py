"""
V7 阶段3 覆盖率补测试 — skills/knowledge.py (20% → 80%+)
知识归档技能：archive_sop, archive_lesson, query_lessons
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.knowledge import (
    archive_lesson,
    archive_lesson_skill,
    archive_sop,
    archive_sop_skill,
    query_lessons,
    query_lessons_skill,
)


class MockStore:
    """模拟资产Store"""

    def __init__(self):
        self._data = {}

    def save(self, key, value):
        self._data[key] = value

    def load(self, key):
        return self._data.get(key)

    def list_keys(self):
        return list(self._data.keys())


class TestArchiveSop:
    """SOP归档测试"""

    def test_archive_sop_success(self):
        store = MockStore()
        sop_data = {"sop_id": "TEST-001", "name": "测试SOP", "stages": []}
        ctx = {
            "_sop_to_archive": sop_data,
            "_sop_source": "web",
            "_asset_store": store,
            "_task_id": "task-001",
        }
        result = archive_sop(ctx)
        assert result["_archive_result"]["success"] is True
        assert result["_archive_result"]["sop_id"] == "TEST-001"
        # 验证Store中已保存
        saved = store.load("sop_template:TEST-001")
        assert saved is not None
        assert saved["source"] == "web"

    def test_archive_sop_missing_data(self):
        ctx = {"_sop_to_archive": {}, "_asset_store": None}
        result = archive_sop(ctx)
        assert result["_archive_result"]["success"] is False

    def test_archive_sop_no_store(self):
        sop_data = {"sop_id": "X-001", "name": "X SOP"}
        ctx = {"_sop_to_archive": sop_data, "_asset_store": None}
        result = archive_sop(ctx)
        assert result["_archive_result"]["success"] is False

    def test_archive_sop_missing_sop_data(self):
        store = MockStore()
        ctx = {"_sop_to_archive": None, "_asset_store": store}
        result = archive_sop(ctx)
        assert result["_archive_result"]["success"] is False

    def test_archive_sop_skill_instance(self):
        assert archive_sop_skill.name == "archive_sop"


class TestArchiveLesson:
    """错题本归档测试"""

    def test_archive_lesson_new(self):
        store = MockStore()
        lesson = {
            "task_id": "task-001",
            "error_type": "format_error",
            "description": "格式不合规",
            "solution": "添加格式约束",
        }
        ctx = {"_lesson": lesson, "_asset_store": store}
        result = archive_lesson(ctx)
        assert result["_archive_result"]["success"] is True
        saved = store.load("lesson:task-001:format_error")
        assert saved is not None
        assert saved["times_encountered"] == 1

    def test_archive_lesson_existing_updates(self):
        store = MockStore()
        # 先存一个
        existing = {
            "task_id": "task-001",
            "error_type": "format_error",
            "times_encountered": 2,
            "solution": "旧方案",
        }
        store.save("lesson:task-001:format_error", existing)
        # 再归档同一类型
        lesson = {"task_id": "task-001", "error_type": "format_error", "solution": "新方案"}
        ctx = {"_lesson": lesson, "_asset_store": store}
        result = archive_lesson(ctx)
        assert result["_archive_result"]["success"] is True
        saved = store.load("lesson:task-001:format_error")
        assert saved["times_encountered"] == 3  # 应增加
        assert saved["solution"] == "新方案"  # 应更新

    def test_archive_lesson_missing_data(self):
        ctx = {"_lesson": None, "_asset_store": None}
        result = archive_lesson(ctx)
        assert result["_archive_result"]["success"] is False

    def test_archive_lesson_skill_instance(self):
        assert archive_lesson_skill.name == "archive_lesson"


class TestQueryLessons:
    """错题本查询测试"""

    def test_query_all_lessons(self):
        store = MockStore()
        store.save("lesson:task-001:error1", {"error_type": "error1", "times_encountered": 3})
        store.save("lesson:task-002:error2", {"error_type": "error2", "times_encountered": 1})
        ctx = {"_asset_store": store}
        result = query_lessons(ctx)
        assert len(result["_lessons"]) == 2
        # 应按 times_encountered 降序排列
        assert (
            result["_lessons"][0]["times_encountered"] >= result["_lessons"][1]["times_encountered"]
        )

    def test_query_with_error_type_filter(self):
        store = MockStore()
        store.save("lesson:t1:format_error", {"error_type": "format_error", "times_encountered": 2})
        store.save(
            "lesson:t2:timeout_error", {"error_type": "timeout_error", "times_encountered": 5}
        )
        ctx = {"_error_type": "format", "_asset_store": store}
        result = query_lessons(ctx)
        assert len(result["_lessons"]) == 1
        assert result["_lessons"][0]["error_type"] == "format_error"

    def test_query_no_store(self):
        ctx = {"_asset_store": None}
        result = query_lessons(ctx)
        assert result["_lessons"] == []

    def test_query_empty_store(self):
        store = MockStore()
        ctx = {"_asset_store": store}
        result = query_lessons(ctx)
        assert result["_lessons"] == []

    def test_query_lessons_limit_10(self):
        store = MockStore()
        for i in range(15):
            store.save(f"lesson:t{i}:error{i}", {"error_type": f"error{i}", "times_encountered": i})
        ctx = {"_asset_store": store}
        result = query_lessons(ctx)
        assert len(result["_lessons"]) <= 10

    def test_query_lessons_skill_instance(self):
        assert query_lessons_skill.name == "query_lessons"
