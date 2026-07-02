"""
FROST-SOP 初始化任务触发器测试
"""

import json
import os
import tempfile
import unittest

from skills.init.questionnaire import InitQuestionnaire
from skills.init.task_trigger import HAS_CORE, INIT_PROJECT_ID, InitTaskTrigger


class TestInitTaskTrigger(unittest.TestCase):
    """初始化任务触发器测试套件"""

    def setUp(self):
        """每个测试前准备临时环境"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test_frost_sop.db")
        self.results_path = os.path.join(self.tmpdir.name, "test_init_results.json")

        # 生成样本问卷结果
        self.sample_questionnaire_result = {
            "timestamp": "2026-07-02T12:00:00",
            "answers": {
                "identity": "IT小白，一人公司",
                "destination_6m": "零收入，想盈利",
                "destination_12m": "收入稳定",
                "destination_36m": "平台成熟",
                "assets": "FROST框架",
                "constraints": "零预算",
                "content_strategy": "小红书",
                "growth_flywheel": "不知道",
            },
            "gaps": [
                {
                    "gap_id": "GAP-001",
                    "description": "技术执行能力",
                    "source_question": "identity",
                    "priority": "P0",
                    "suggested_hunt_target": "tech_execution",
                },
                {
                    "gap_id": "GAP-002",
                    "description": "零预算工具栈",
                    "source_question": "constraints",
                    "priority": "P0",
                    "suggested_hunt_target": "zero_budget_tools",
                },
                {
                    "gap_id": "GAP-003",
                    "description": "小红书运营能力",
                    "source_question": "content_strategy",
                    "priority": "P0",
                    "suggested_hunt_target": "redbook_ops",
                },
            ],
            "tasks": [
                {
                    "task_id": "INIT-HUNT-001",
                    "title": "初始狩猎：技术执行能力",
                    "target_skill": "tech_execution",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-001",
                },
                {
                    "task_id": "INIT-HUNT-002",
                    "title": "初始狩猎：零预算工具栈",
                    "target_skill": "zero_budget_tools",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-002",
                },
                {
                    "task_id": "INIT-HUNT-003",
                    "title": "初始狩猎：小红书运营能力",
                    "target_skill": "redbook_ops",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-003",
                },
            ],
        }

        with open(self.results_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_questionnaire_result, f, ensure_ascii=False, indent=2)

        # 如果核心模块可用，清理 EventBus 订阅者
        if HAS_CORE:
            from core.event_bus import EventBus

            EventBus.clear_subscribers(EventBus(), None)

    def tearDown(self):
        """测试后清理"""
        self.tmpdir.cleanup()

    # ----------------------------------------------------------
    # TC-001: 加载问卷结果
    # ----------------------------------------------------------

    def test_load_from_questionnaire(self):
        """TC-001: 能从 JSON 文件加载任务"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        tasks = trigger.load_from_questionnaire()

        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["task_id"], "INIT-HUNT-001")
        self.assertEqual(tasks[0]["target_skill"], "tech_execution")

    # ----------------------------------------------------------
    # TC-002: 文件不存在处理
    # ----------------------------------------------------------

    def test_load_missing_file(self):
        """TC-002: 文件不存在时返回空列表"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path="/nonexistent/path.json",
        )
        tasks = trigger.load_from_questionnaire()

        self.assertEqual(tasks, [])

    # ----------------------------------------------------------
    # TC-003: 任务数据结构
    # ----------------------------------------------------------

    def test_task_structure(self):
        """TC-003: 任务数据结构完整"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        first = trigger.tasks[0]

        required_keys = ["task_id", "title", "target_skill", "priority", "status", "gap_id"]
        for key in required_keys:
            self.assertIn(key, first, f"任务缺少 {key} 字段")

    # ----------------------------------------------------------
    # TC-004: 生成 SOP 文档
    # ----------------------------------------------------------

    def test_generate_sop(self):
        """TC-004: 能生成 SOP Markdown 文档"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        sop_path = trigger.generate_init_sop()

        self.assertTrue(os.path.exists(sop_path))
        with open(sop_path, encoding="utf-8") as f:
            content = f.read()
        self.assertIn("初始化任务 SOP", content)
        self.assertIn("INIT-HUNT-001", content)

    # ----------------------------------------------------------
    # TC-005: 首个狩猎触发（P0 筛选）
    # ----------------------------------------------------------

    def test_trigger_first_hunt(self):
        """TC-005: 正确触发第一个 P0 任务"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        info = trigger.trigger_first_hunt()

        self.assertIsNotNone(info)
        self.assertEqual(info["target"], "tech_execution")  # 第一个 P0
        self.assertEqual(info["task_id"], "INIT-HUNT-001")
        self.assertIn("python main.py --hunt", info["command"])

    # ----------------------------------------------------------
    # TC-006: 无 P0 任务时
    # ----------------------------------------------------------

    def test_no_p0_tasks(self):
        """TC-006: 没有 P0 任务时返回 None"""
        # 构造只有 P1 任务的结果
        result = dict(self.sample_questionnaire_result)
        for t in result["tasks"]:
            t["priority"] = "P1"

        path = os.path.join(self.tmpdir.name, "no_p0.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f)

        trigger = InitTaskTrigger(db_path=self.db_path, init_results_path=path)
        trigger.load_from_questionnaire()
        info = trigger.trigger_first_hunt()

        self.assertIsNone(info)

    # ----------------------------------------------------------
    # TC-007: 数据库写入（如果核心模块可用）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def _cleanup_init_data(self):
        """清理初始化测试数据"""
        try:
            from core.db import get_db

            db = get_db()
            # 删除 INIT 任务
            rows = db.select_all("tasks", where="project_id = ?", params=[INIT_PROJECT_ID])
            for row in rows:
                db.delete("tasks", "id", row["id"])
            # 删除 INIT 项目
            db.delete("projects", "id", INIT_PROJECT_ID)
        except Exception:
            pass

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_save_to_database(self):
        """TC-007: 任务能写入 tasks 表"""
        self._cleanup_init_data()  # 清理之前的数据
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        result = trigger.save_to_database()

        self.assertTrue(result)

        # 验证数据库内容
        rows = trigger.get_init_tasks()
        self.assertGreater(len(rows), 0)

        # 验证 project_id 标记
        first = rows[0]
        self.assertEqual(first.get("project_id"), INIT_PROJECT_ID)

    # ----------------------------------------------------------
    # TC-008: 重复写入不重复（幂等性）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_idempotent_save(self):
        """TC-008: 重复保存不重复插入"""
        self._cleanup_init_data()  # 清理之前的数据
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        trigger.save_to_database()
        trigger.save_to_database()  # 第二次

        rows = trigger.get_init_tasks()
        # 应该还是3条，不是6条
        self.assertEqual(len(rows), 3)

    # ----------------------------------------------------------
    # TC-009: 更新任务状态
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_update_task_status(self):
        """TC-009: 能更新任务状态"""
        self._cleanup_init_data()  # 清理之前的数据
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        trigger.save_to_database()

        result = trigger.update_task_status("INIT-HUNT-001", "running")
        self.assertTrue(result)

        rows = trigger.get_init_tasks(status="running")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "INIT-HUNT-001")

    # ----------------------------------------------------------
    # TC-010: 完整流水线
    # ----------------------------------------------------------

    def test_full_pipeline(self):
        """TC-010: run_full_pipeline 完整运行"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        result = trigger.run_full_pipeline()

        self.assertEqual(result["tasks_count"], 3)
        self.assertEqual(result["p0_count"], 3)
        self.assertIsNotNone(result["sop_path"])
        self.assertIsNotNone(result["trigger_info"])
        self.assertTrue(os.path.exists(result["sop_path"]))

    # ----------------------------------------------------------
    # TC-011: 端到端（问卷 → 触发器）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_end_to_end(self):
        """TC-011: 问卷 → 触发器 完整端到端"""
        self._cleanup_init_data()  # 清理之前的数据
        # 1. 运行问卷
        q = InitQuestionnaire(
            non_interactive=True,
            mock_inputs={
                "identity": "IT小白",
                "destination_6m": "零收入",
                "destination_12m": "",
                "destination_36m": "",
                "assets": "FROST框架",
                "constraints": "零预算",
                "content_strategy": "小红书",
                "growth_flywheel": "不知道",
            },
        )
        q.run_full_pipeline()

        # 2. 运行触发器
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path="init_results.json",
        )
        result = trigger.run_full_pipeline()

        self.assertGreater(result["tasks_count"], 0)
        self.assertGreater(result["p0_count"], 0)

        # 3. 验证数据库
        rows = trigger.get_init_tasks()
        self.assertGreater(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
