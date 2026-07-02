"""
FROST-SOP 初始化问卷测试
"""

import json
import os
import tempfile
import unittest

from skills.init.questionnaire import (
    InitQuestionnaire,
)


class TestInitQuestionnaire(unittest.TestCase):
    """初始化问卷测试套件"""

    def setUp(self):
        """每个测试前的准备"""
        self.sample_answers = {
            "identity": "IT小白，一人公司创业者，社恐",
            "destination_6m": "零收入零读者，想建立稳定现金流",
            "destination_12m": "收入稳定，找到PMF",
            "destination_36m": "FROST平台成熟，能养活自己",
            "assets": "FROST框架，FROST-SOP平台，白皮书",
            "constraints": "零预算，每天2小时，不懂代码",
            "content_strategy": "想做小红书，但完全不知道怎么开始",
            "growth_flywheel": "不知道，还在探索",
        }

    # ----------------------------------------------------------
    # TC-001: 问卷采集（程序模式）
    # ----------------------------------------------------------

    def test_run_programmatic(self):
        """TC-001: 程序模式问卷能正常采集"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()

        self.assertEqual(answer.identity, self.sample_answers["identity"])
        self.assertEqual(answer.destination_6m, self.sample_answers["destination_6m"])
        self.assertEqual(answer.constraints, self.sample_answers["constraints"])

    # ----------------------------------------------------------
    # TC-002: 缺口识别 - 身份类
    # ----------------------------------------------------------

    def test_gap_identity_tech(self):
        """TC-002: IT小白 → 识别技术执行能力缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("tech_execution", targets)
        self.assertIn("solo_ops", targets)

    # ----------------------------------------------------------
    # TC-003: 缺口识别 - 约束类
    # ----------------------------------------------------------

    def test_gap_constraints_budget(self):
        """TC-003: 零预算 → 识别零预算工具栈缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("zero_budget_tools", targets)
        self.assertIn("no_code_automation", targets)

    # ----------------------------------------------------------
    # TC-004: 缺口识别 - 内容策略类
    # ----------------------------------------------------------

    def test_gap_content_strategy(self):
        """TC-004: 小红书 → 识别小红书运营能力缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("redbook_ops", targets)
        self.assertIn("content_strategy_design", targets)

    # ----------------------------------------------------------
    # TC-005: 缺口识别 - 增长飞轮
    # ----------------------------------------------------------

    def test_gap_flywheel(self):
        """TC-005: 不知道增长飞轮 → 识别增长飞轮设计缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("flywheel_design", targets)

    # ----------------------------------------------------------
    # TC-006: 缺口去重
    # ----------------------------------------------------------

    def test_gap_deduplication(self):
        """TC-006: 同 target 的缺口只保留一次"""
        # 构造一个会触发重复的答案
        answers = {
            "identity": "IT小白",
            "destination_6m": "",
            "destination_12m": "",
            "destination_36m": "",
            "assets": "",
            "constraints": "",
            "content_strategy": "",
            "growth_flywheel": "",
        }
        q = InitQuestionnaire(non_interactive=True, mock_inputs=answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertEqual(len(targets), len(set(targets)), "存在重复 target")

    # ----------------------------------------------------------
    # TC-007: 优先级排序
    # ----------------------------------------------------------

    def test_gap_priority_sorting(self):
        """TC-007: P0 排在 P1 前面"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        if len(gaps) >= 2:
            priorities = [g.priority for g in gaps]
            # P0 应该在 P1 前面
            for i in range(len(priorities) - 1):
                self.assertLessEqual(
                    {"P0": 0, "P1": 1, "P2": 2}[priorities[i]],
                    {"P0": 0, "P1": 1, "P2": 2}[priorities[i + 1]],
                    f"优先级排序错误: {priorities[i]} 在 {priorities[i + 1]} 之后",
                )

    # ----------------------------------------------------------
    # TC-008: 任务生成
    # ----------------------------------------------------------

    def test_task_generation(self):
        """TC-008: 缺口正确转化为任务"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        self.assertGreater(len(tasks), 0, "至少生成1个任务")

        # 检查第一个任务的结构
        first = tasks[0]
        self.assertTrue(first.task_id.startswith("INIT-HUNT-"))
        self.assertEqual(first.status, "pending")
        self.assertTrue(first.title.startswith("初始狩猎："))

    # ----------------------------------------------------------
    # TC-009: 任务与缺口关联
    # ----------------------------------------------------------

    def test_task_gap_association(self):
        """TC-009: 每个任务关联到正确的缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        gap_ids = {g.gap_id for g in gaps}
        for task in tasks:
            self.assertIn(task.gap_id, gap_ids, f"任务 {task.task_id} 关联到不存在的缺口")

    # ----------------------------------------------------------
    # TC-010: 结果导出
    # ----------------------------------------------------------

    def test_export_results(self):
        """TC-010: 结果能正确导出为 JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_init_results.json")

            q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
            q.run_full_pipeline()
            q.export_results(filepath)

            self.assertTrue(os.path.exists(filepath))

            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("timestamp", data)
            self.assertIn("answers", data)
            self.assertIn("gaps", data)
            self.assertIn("tasks", data)
            self.assertGreater(len(data["gaps"]), 0)
            self.assertGreater(len(data["tasks"]), 0)

    # ----------------------------------------------------------
    # TC-011: 空答案处理
    # ----------------------------------------------------------

    def test_empty_answers(self):
        """TC-011: 空答案不会崩溃"""
        empty_answers = {
            q["id"]: ""
            for q in [
                {"id": "identity"},
                {"id": "destination_6m"},
                {"id": "destination_12m"},
                {"id": "destination_36m"},
                {"id": "assets"},
                {"id": "constraints"},
                {"id": "content_strategy"},
                {"id": "growth_flywheel"},
            ]
        }
        q = InitQuestionnaire(non_interactive=True, mock_inputs=empty_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        # 空答案应该不产生崩溃，但可能识别不到任何缺口
        self.assertIsInstance(gaps, list)
        self.assertIsInstance(tasks, list)

    # ----------------------------------------------------------
    # TC-012: 全流水线一键运行
    # ----------------------------------------------------------

    def test_full_pipeline(self):
        """TC-012: run_full_pipeline 能完整运行"""
        q = InitQuestionnaire()
        result = q.run_full_pipeline(answers=self.sample_answers)

        self.assertIn("timestamp", result)
        self.assertIn("answers", result)
        self.assertIn("gaps", result)
        self.assertIn("tasks", result)
        self.assertGreater(len(result["gaps"]), 0)
        self.assertGreater(len(result["tasks"]), 0)


if __name__ == "__main__":
    unittest.main()
