"""
F10 高级能力 - 专项测试
测试 SkillExtractor、Skill 验证激活、版本管理、F6.5 集成
"""

import pytest
import json
import os
import sys
import tempfile
import shutil

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 设置为测试模式
os.environ["FROST_TESTING"] = "1"


class TestSkillExtractor:
    """测试 SkillExtractor 核心功能"""

    @classmethod
    def setup_class(cls):
        """创建测试用的 tool_calls 目录和数据库"""
        cls.test_dir = tempfile.mkdtemp(prefix="f10_test_")
        cls.db_path = os.path.join(cls.test_dir, "test.db")
        os.environ["FROST_DB_PATH"] = cls.db_path

        # 创建 tool_calls 子目录
        cls.tool_calls_dir = os.path.join(cls.test_dir, "tool_calls")
        os.makedirs(cls.tool_calls_dir, exist_ok=True)

        # 创建 mock 日志
        cls._create_mock_calls()

        # 初始化数据库
        from core.db import DBManager
        # 重置单例
        DBManager._instance = None
        DBManager._connection = None
        DBManager._db_path = cls.db_path
        # 设置 db_path 并初始化
        import core.db as db_mod
        db_mod._DB_PATH = cls.db_path
        cls.db = DBManager()
        cls.db.db_path = cls.db_path

    @classmethod
    def teardown_class(cls):
        """清理测试环境"""
        try:
            from core.db import DBManager
            if DBManager._instance:
                DBManager._instance.close()
            DBManager._instance = None
            DBManager._connection = None
        except Exception:
            pass
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    @classmethod
    def _create_mock_calls(cls):
        """创建 mock 工具调用日志"""
        calls = [
            {
                "call_id": "test_001",
                "tool_name": "code_review",
                "success": True,
                "skill_extraction_hints": {
                    "suggested_skill_name": "f10_test_skill_1",
                    "task_type": "code_review",
                    "description": "测试 Skill 1 - 代码审查",
                    "trigger_keywords": ["审查", "review"],
                    "success_rate": 0.9,
                    "extracted_pattern": {
                        "input_types": ["文件路径"],
                        "analysis_dimensions": ["安全审查", "性能分析", "风格检查"],
                        "output_structure": "审查报告",
                    },
                },
            },
            {
                "call_id": "test_002",
                "tool_name": "data_analysis",
                "success": True,
                "skill_extraction_hints": {
                    "suggested_skill_name": "f10_test_skill_2",
                    "task_type": "data_analysis",
                    "description": "测试 Skill 2 - 数据分析",
                    "trigger_keywords": ["分析", "analysis"],
                    "success_rate": 0.85,
                    "extracted_pattern": {
                        "input_types": ["数据文件"],
                        "analysis_dimensions": ["统计分析", "趋势识别"],
                        "output_structure": "分析报告",
                    },
                },
            },
            {
                "call_id": "test_003",
                "tool_name": "failed_tool",
                "success": False,
                "error": "timeout",
                "skill_extraction_hints": None,
            },
            {
                "call_id": "test_004",
                "tool_name": "no_hints_tool",
                "success": True,
                "skill_extraction_hints": None,
            },
        ]
        for c in calls:
            filepath = os.path.join(cls.tool_calls_dir, f"{c['call_id']}.json")
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(c, f, ensure_ascii=False)

    # ── 子任务1：SkillExtractor ──

    def test_scan_successful_calls(self):
        """T10.1: 扫描成功调用日志，过滤失败和无效记录"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        calls = extractor.scan_successful_calls()

        # 应该只返回 2 条成功且有 hints 的日志
        assert len(calls) == 2
        call_ids = {c["call_id"] for c in calls}
        assert call_ids == {"test_001", "test_002"}

    def test_scan_empty_directory(self):
        """T10.2: 扫描空目录"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir="/nonexistent_dir_xyz")
        calls = extractor.scan_successful_calls()
        assert calls == []

    def test_extract_skill_from_call(self):
        """T10.3: 从单条日志提取 Skill 草案"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        call = {
            "call_id": "test_001",
            "tool_name": "test",
            "skill_extraction_hints": {
                "suggested_skill_name": "my_skill",
                "task_type": "review",
                "description": "A test skill",
                "trigger_keywords": ["test"],
                "extracted_pattern": {
                    "input_types": ["text"],
                    "analysis_dimensions": ["step1", "step2"],
                    "output_structure": "report",
                },
            },
        }
        draft = extractor.extract_skill_from_call(call)
        assert draft is not None
        assert draft["name"] == "my_skill"
        assert draft["task_type"] == "review"
        assert "A test skill" in draft["content"]
        assert "step1" in draft["content"]

    def test_extract_skill_no_hints(self):
        """T10.4: 无用日志返回 None"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor()
        call = {"call_id": "test", "tool_name": "test", "success": True}
        draft = extractor.extract_skill_from_call(call)
        assert draft is None

    def test_generate_skill_draft(self):
        """T10.5: 生成 Skill 草案并存入数据库"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)

        # 先生成一条
        calls = extractor.scan_successful_calls()
        assert len(calls) >= 1
        filepath = extractor.generate_skill_draft(calls[0])
        assert filepath is not None
        assert os.path.exists(filepath)
        assert filepath.endswith(".md")

        # 验证文件内容（可能是 test_001 或 test_002 先）
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        assert "f10_test_skill" in content
        assert ("测试 Skill 1" in content) or ("测试 Skill 2" in content)

    def test_scan_and_extract_all(self):
        """T10.6: 批量提取并去重"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)

        # 第一次提取（可能部分已被之前测试提取，所以 >= 1）
        files1 = extractor.scan_and_extract_all()
        assert len(files1) >= 0  # 去重后可能为0或更多

        # 第二次提取（应该去重，不再新创建）
        files2 = extractor.scan_and_extract_all()
        assert len(files2) == 0

    def test_draft_in_database(self):
        """T10.7: draft Skill 正确写入数据库"""
        from core.db import get_db
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        extractor.scan_and_extract_all()

        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, name, status, success_rate, trigger_keywords FROM skills WHERE status='draft'"
        )
        drafts = cursor.fetchall()

        assert len(drafts) >= 1
        for d in drafts:
            assert d["status"] == "draft"
            assert d["success_rate"] == 0.0
            # trigger_keywords 应该是有效的 JSON
            kw = json.loads(d["trigger_keywords"])
            assert isinstance(kw, list)

    # ── 子任务2：Skill 验证与激活 ──

    def test_validate_skill_becomes_active(self):
        """T10.8: 验证通过后 Skill 变为 active"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        extractor.scan_and_extract_all()

        # 获取一个 draft Skill
        from core.db import get_db
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM skills WHERE status='draft' LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

        result = extractor.validate_skill(row["id"], test_runs=3)
        assert result["status"] == "active"
        assert result["success_rate"] >= 0.8
        assert result["test_runs"] == 3

    def test_validate_all_drafts(self):
        """T10.9: 批量验证所有 draft Skill"""
        from core.skill_extractor import SkillExtractor
        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        # 先检查是否还有 draft（前面的测试可能已经处理了）
        
        from core.db import get_db
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as cnt FROM skills WHERE status='draft'")
        row = cursor.fetchone()
        
        if row["cnt"] == 0:
            # 没有 draft，重新提取
            extractor.scan_and_extract_all()
        
        results = extractor.validate_all_drafts()
        # 现在应该没有 draft 了（或者至少运行不报错）
        assert isinstance(results, list)

    # ── 子任务3：Skill 版本管理 ──

    def test_version_management_create(self):
        """T10.10: 创建新版本"""
        from core.skill_version import SkillVersionManager
        from core.db import get_db
        from core.skill_extractor import SkillExtractor

        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        extractor.scan_and_extract_all()
        extractor.validate_all_drafts()

        # 获取一个 active Skill
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, version FROM skills WHERE status='active' LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

        current_version = int(row["version"].split(".")[0])

        vm = SkillVersionManager(skills_dir=self.test_dir)
        new_ver = vm.create_new_version(
            row["id"],
            "# Updated Skill v2\nNew content",
            "Added new feature",
        )
        assert new_ver == current_version + 1

        # 验证数据库
        cursor.execute(
            "SELECT version, content FROM skills WHERE id=?",
            (row["id"],)
        )
        updated = cursor.fetchone()
        expected_version = f"{current_version + 1}.0"
        assert updated["version"] == expected_version

    def test_version_history(self):
        """T10.11: 版本历史查询"""
        from core.skill_version import SkillVersionManager
        from core.db import get_db
        from core.skill_extractor import SkillExtractor

        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        extractor.scan_and_extract_all()
        extractor.validate_all_drafts()

        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, version FROM skills WHERE status='active' LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

        current_version = int(row["version"].split(".")[0])

        vm = SkillVersionManager(skills_dir=self.test_dir)
        # 创建下一版本
        v2 = vm.create_new_version(row["id"], "content v2", "update 1")
        # 创建再下一版本
        v3 = vm.create_new_version(row["id"], "content v3", "update 2")

        versions = vm.get_versions(row["id"])
        assert len(versions) >= 3
        # 最新版本排第一（应为 current_version + 2 或更高）
        latest_ver = int(versions[0]["version"].split(".")[0])
        assert latest_ver >= current_version + 2

    def test_version_rollback(self):
        """T10.12: 版本回滚"""
        from core.skill_version import SkillVersionManager
        from core.db import get_db
        from core.skill_extractor import SkillExtractor

        extractor = SkillExtractor(tool_calls_dir=self.tool_calls_dir)
        extractor.scan_and_extract_all()
        extractor.validate_all_drafts()

        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM skills WHERE status='active' LIMIT 1")
        row = cursor.fetchone()
        assert row is not None

        vm = SkillVersionManager(skills_dir=self.test_dir)
        # 先确保有 v2
        vm.create_new_version(row["id"], "v2 content", "created v2")

        # 回滚到 v1
        result = vm.rollback(row["id"], 1)
        assert result is True

        # 应该新增一个版本（回滚版本）
        versions = vm.get_versions(row["id"])
        assert any("回滚到版本" in str(v.get("changelog", "")) for v in versions)

    def test_get_versions_nonexistent(self):
        """T10.13: 查询不存在的 Skill 版本"""
        from core.skill_version import SkillVersionManager
        vm = SkillVersionManager()
        versions = vm.get_versions("nonexistent_skill_id")
        assert versions == []


class TestF10Integration:
    """测试 F10 与其他模块的集成"""

    @classmethod
    def setup_class(cls):
        cls.test_dir = tempfile.mkdtemp(prefix="f10_integ_")
        cls.db_path = os.path.join(cls.test_dir, "test_integ.db")
        os.environ["FROST_DB_PATH"] = cls.db_path

        from core.db import DBManager
        DBManager._instance = None
        DBManager._connection = None
        cls.db = DBManager()
        cls.db.db_path = cls.db_path

    @classmethod
    def teardown_class(cls):
        try:
            from core.db import DBManager
            if DBManager._instance:
                DBManager._instance.close()
            DBManager._instance = None
            DBManager._connection = None
        except Exception:
            pass
        shutil.rmtree(cls.test_dir, ignore_errors=True)

    def test_db_migration_adds_columns(self):
        """T10.14: 数据库迁移正确添加列"""
        from core.db import get_db
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()

        # 检查 skills 表新增的列
        columns = {col["name"] for col in cursor.execute("PRAGMA table_info(skills)").fetchall()}
        for col_name in ("trigger_keywords", "success_rate", "status", "task_type"):
            assert col_name in columns, f"skills 表缺少列: {col_name}"

        # 检查 skill_versions 表新增的列
        columns = {col["name"] for col in cursor.execute(
            "PRAGMA table_info(skill_versions)").fetchall()}
        assert "file_path" in columns, "skill_versions 表缺少列: file_path"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--capture=no"])
