"""
FROST-SOP 集成测试 - 完整任务执行流程

测试完整的任务执行流程：
1. 创建任务
2. 加载SOP模板
3. 创建Agent（祖辈→父辈→孙辈）
4. 执行所有阶段
5. 验证结果

使用真实组件，不mock关键逻辑（除了LLM）。
"""

import os
import sys
import unittest
from pathlib import Path

# 设置测试环境
os.environ["FROST_TESTING"] = "1"

# 确保 frost-sop 在 Python 路径中
frost_sop_path = Path(__file__).parent.parent
sys.path.insert(0, str(frost_sop_path))

from api.main import create_and_run_task
from api.models import TaskCreateRequest
from core.db import get_db


class TestIntegrationFullFlow(unittest.TestCase):
    """完整任务执行流程集成测试"""

    @classmethod
    def setUpClass(cls):
        """测试类初始化"""
        cls.db = get_db()
        print(f"\n{'=' * 60}")
        print("开始集成测试 - 完整任务执行流程")
        print(f"{'=' * 60}\n")

    def test_01_create_and_execute_dev_task(self):
        """测试：创建并执行DEV类型任务（新功能开发）"""
        print("\n▶ 测试1: DEV类型任务（新功能开发）")
        print("   SOP: DEV-001 (新功能开发)")

        # 创建任务请求
        req = TaskCreateRequest(
            description="集成测试：实现一个用户登录功能", sop_id="DEV-001", project_id="default"
        )

        # 执行任务
        result = create_and_run_task(req)

        # 验证结果
        self.assertEqual(
            result.status, "completed", f"任务应该成功完成，但实际状态: {result.status}"
        )
        self.assertGreater(len(result.stages), 0, "任务应该至少有一个阶段")
        self.assertIn("完成", result.message, "消息应该包含'完成'")

        # 验证数据库中的任务记录
        task_record = self.db.select_one("tasks", "id", result.task_id)
        self.assertIsNotNone(task_record, "任务记录应该存在")
        self.assertEqual(task_record["status"], "completed", "数据库中的任务状态应该是completed")

        # 验证阶段记录
        stages = self.db.select_all("task_stages", f"task_id = '{result.task_id}'")
        self.assertEqual(len(stages), len(result.stages), "阶段记录数应该匹配")

        print(f"   ✅ 任务ID: {result.task_id}")
        print(f"   ✅ 状态: {result.status}")
        print(f"   ✅ 阶段数: {len(result.stages)}")
        print(f"   ✅ 消息: {result.message}")

    def test_02_create_and_execute_fix_task(self):
        """测试：创建并执行FIX类型任务（Bug修复）"""
        print("\n▶ 测试2: FIX类型任务（Bug修复）")
        print("   SOP: DEV-002 (Bug修复)")

        req = TaskCreateRequest(
            description="集成测试：修复用户登录失败的Bug", sop_id="DEV-002", project_id="default"
        )

        result = create_and_run_task(req)

        # 验证
        self.assertEqual(result.status, "completed")
        self.assertGreater(len(result.stages), 0)

        print(f"   ✅ 任务ID: {result.task_id}")
        print(f"   ✅ 状态: {result.status}")

    def test_03_create_and_execute_str_task(self):
        """测试：创建并执行STR类型任务（战略立项）"""
        print("\n▶ 测试3: STR类型任务（战略立项）")
        print("   SOP: STR-001 (立项)")

        req = TaskCreateRequest(
            description="集成测试：立项'长上下文记忆管理'功能",
            sop_id="STR-001",
            project_id="default",
        )

        result = create_and_run_task(req)

        # 验证
        self.assertEqual(result.status, "completed")

        print(f"   ✅ 任务ID: {result.task_id}")
        print(f"   ✅ 状态: {result.status}")

    def test_04_task_with_chinese_description(self):
        """测试：包含中文和特殊字符的任务描述"""
        print("\n▶ 测试4: 中文任务描述")
        print("   描述: 包含中文、emoji、特殊字符")

        req = TaskCreateRequest(
            description="狩猎任务：关于长上下文记忆管理、有效精简历史消息、减少token消耗方面的优秀的实践和skill 🔮",
            sop_id="DEV-001",
            project_id="default",
        )

        result = create_and_run_task(req)

        # 验证
        self.assertEqual(result.status, "completed")

        # 验证任务描述被正确保存
        task_record = self.db.select_one("tasks", "id", result.task_id)
        self.assertIn("长上下文", task_record["description"])

        print(f"   ✅ 任务ID: {result.task_id}")
        print("   ✅ 中文描述正确保存")

    def test_05_multiple_tasks_sequential(self):
        """测试：连续创建多个任务"""
        print("\n▶ 测试5: 连续创建多个任务")

        task_ids = []
        for i in range(3):
            req = TaskCreateRequest(
                description=f"集成测试：批量任务 {i + 1}", sop_id="DEV-001", project_id="default"
            )

            result = create_and_run_task(req)
            self.assertEqual(result.status, "completed")
            task_ids.append(result.task_id)

        # 验证所有任务都成功
        self.assertEqual(len(task_ids), 3)

        # 验证任务ID唯一
        self.assertEqual(len(set(task_ids)), 3)

        print("   ✅ 成功创建3个任务")
        print(f"   ✅ 任务ID: {', '.join(task_ids)}")

    def test_06_verify_database_persistence(self):
        """测试：验证数据持久化"""
        print("\n▶ 测试6: 数据持久化验证")

        # 创建任务
        req = TaskCreateRequest(
            description="集成测试：验证数据持久化", sop_id="DEV-001", project_id="default"
        )

        result = create_and_run_task(req)

        # 验证任务记录
        task = self.db.select_one("tasks", "id", result.task_id)
        self.assertIsNotNone(task)
        self.assertEqual(task["status"], "completed")

        # 验证阶段记录
        stages = self.db.select_all("task_stages", f"task_id = '{result.task_id}'")
        self.assertGreater(len(stages), 0)

        # 验证SOP执行记录
        sop_executions = self.db.select_all("sop_executions", f"task_id = '{result.task_id}'")
        self.assertGreater(len(sop_executions), 0)

        print("   ✅ 任务记录已持久化")
        print(f"   ✅ 阶段记录已持久化 ({len(stages)} 个阶段)")
        print("   ✅ SOP执行记录已持久化")

    def test_07_different_sop_templates(self):
        """测试：使用不同的SOP模板"""
        print("\n▶ 测试7: 多SOP模板测试")

        sop_list = ["DEV-001", "DEV-002", "STR-001", "STR-002"]

        for sop_id in sop_list:
            req = TaskCreateRequest(
                description=f"集成测试：SOP模板 {sop_id}", sop_id=sop_id, project_id="default"
            )

            result = create_and_run_task(req)
            self.assertEqual(result.status, "completed", f"SOP {sop_id} 执行失败")
            print(f"   ✅ SOP {sop_id}: 执行成功")

    @classmethod
    def tearDownClass(cls):
        """测试类清理"""
        print(f"\n{'=' * 60}")
        print("集成测试完成")
        print(f"{'=' * 60}\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
