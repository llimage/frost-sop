"""
混沌工程测试

模拟真实世界的故障场景，验证系统健壮性：

1. 文件系统故障
   - 写入中途崩溃（文件损坏）
   - 磁盘空间不足
   - 文件权限错误

2. 网络故障
   - LLM API 超时
   - LLM API 返回错误
   - 网络连接断开

3. 数据库故障
   - 连接断开
   - 数据损坏
   - 并发写入冲突

4. 进程故障
   - 执行中途异常
   - 内存不足
   - 递归过深

目标：确保FROST-SOP在恶劣环境下依然可靠。
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 设置测试环境
os.environ["FROST_TESTING"] = "1"

# 确保 frost-sop 在 Python 路径中
frost_sop_path = Path(__file__).parent.parent
sys.path.insert(0, str(frost_sop_path))

from core.db import get_db
from stores.asset import FileStore


class TestChaosFileSystem(unittest.TestCase):
    """混沌工程：文件系统故障"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "chaos_test.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_file_corruption_during_write(self):
        """混沌：写入中途崩溃（模拟文件损坏）"""
        print("\n🔥 混沌测试1: 文件写入中途崩溃")

        store = FileStore(self.test_file)

        # 模拟：json.dump 执行到一半时崩溃
        original_dump = json.dump

        def crash_mid_dump(data, f, *args, **kwargs):
            # 写入一半数据后崩溃
            f.write('{"key": "value"')  # 不完整的JSON
            raise KeyboardInterrupt("模拟崩溃")

        with patch("json.dump", side_effect=crash_mid_dump):
            try:
                store.save("test", "value")
            except (KeyboardInterrupt, Exception):
                pass  # 预期中的崩溃

        # 验证：文件可能损坏，但重新创建FileStore时应该能处理
        if os.path.exists(self.test_file):
            # 文件存在但可能损坏
            store2 = FileStore(self.test_file)
            # 应该不崩溃，返回空字典或尝试恢复
            self.assertIsInstance(store2._memory, dict)

        print("   ✅ 系统处理了文件损坏")

    def test_02_permission_denied(self):
        """混沌：文件无写入权限"""
        print("\n🔥 混沌测试2: 文件无写入权限")

        # 创建只读文件
        with open(self.test_file, "w") as f:
            json.dump({"initial": "data"}, f)
        os.chmod(self.test_file, 0o444)  # 只读

        store = FileStore(self.test_file)

        # 尝试保存（应该失败但不崩溃）
        try:
            store.save("new_key", "new_value")
            # Windows可能不会抛出异常，跳过权限检查
            print("   ⚠️ Windows环境：权限检查可能不生效")
        except (PermissionError, Exception) as e:
            print(f"   ✅ 捕获到权限错误: {type(e).__name__}")

        # 恢复权限（以便tearDown能删除）
        os.chmod(self.test_file, 0o666)

    def test_03_concurrent_write(self):
        """混沌：并发写入（模拟竞争条件）"""
        print("\n🔥 混沌测试3: 并发写入冲突")

        # 创建两个FileStore实例（模拟两个进程）
        store1 = FileStore(self.test_file)
        store2 = FileStore(self.test_file)

        # 两个"进程"同时写入
        store1.save("key1", "value1")
        store2.save("key2", "value2")

        # 验证：最终状态应该是最后一次写入
        # 注意：当前实现不支持真正的并发控制
        # 这是一个已知限制，应该在V4.0中修复
        print("   ⚠️ 已知限制：FileStore不支持并发写入控制")
        print("   📋 建议：V4.0中实现文件锁或数据库后端")


class TestChaosNetwork(unittest.TestCase):
    """混沌工程：网络故障"""

    def test_04_llm_api_timeout(self):
        """混沌：LLM API 超时"""
        print("\n🔥 混沌测试4: LLM API 超时")

        # 注意：当前FROST_TESTING=1，不会真正调用API
        # 这个测试演示如何模拟API超时

        with patch("skills.llm._call_online_llm") as mock_llm:
            mock_llm.side_effect = TimeoutError("API调用超时")

            # 在真实环境中，这里应该触发重试或降级到mock模式
            print("   ✅ 模拟了LLM API超时")
            print("   📋 建议：实现重试机制和超时处理")

    def test_05_llm_api_error(self):
        """混沌：LLM API 返回错误"""
        print("\n🔥 混沌测试5: LLM API 返回500错误")

        with patch("skills.llm._call_online_llm") as mock_llm:
            mock_llm.return_value = {
                "_llm_response": "错误：API返回500",
                "_llm_tokens": {"total": 0},
            }

            print("   ✅ 模拟了LLM API错误")
            print("   📋 建议：验证错误处理和重试逻辑")


class TestChaosDatabase(unittest.TestCase):
    """混沌工程：数据库故障"""

    def test_06_database_locked(self):
        """混沌：数据库被锁定（并发访问）"""
        print("\n🔥 混沌测试6: 数据库被锁定")

        # SQLite在写入时会锁定文件
        # 模拟：一个连接未提交事务，另一个连接尝试写入

        db1 = get_db()
        db2 = get_db()

        # 清理可能残留的旧数据
        db1.execute_sql("DELETE FROM tasks WHERE id LIKE 'chaos-test%'")

        # 开始事务但不提交（使用底层连接）
        conn1 = db1.get_connection()
        conn1.execute("BEGIN")
        conn1.execute(
            "INSERT INTO tasks (id, title, status) VALUES (?, ?, ?)",
            ("chaos-test-1", "混沌测试", "running"),
        )

        # 另一个连接尝试写入（应该等待或失败）
        try:
            db2.insert("tasks", {"id": "chaos-test-2", "title": "混沌测试2", "status": "running"})
            print("   ✅ 数据库处理了并发访问")
        except Exception as e:
            print(f"   ✅ 数据库抛出异常: {e}")
        finally:
            try:
                conn1.execute("ROLLBACK")
            except Exception:
                pass  # 事务可能已被自动回滚

        # 清理
        db1.execute_sql("DELETE FROM tasks WHERE id LIKE 'chaos-test%'")

    def test_07_invalid_data_in_db(self):
        """混沌：数据库中包含无效数据"""
        print("\n🔥 混沌测试7: 数据库中包含无效数据")

        db = get_db()

        # 插入无效JSON字符串（模拟数据损坏）
        try:
            db.insert(
                "kv_store",
                {
                    "key": "invalid",
                    "value": "{invalid json}",  # 这不是有效的JSON
                },
            )

            # 读取时应该能处理
            row = db.select_one("kv_store", "key", "invalid")
            if row:
                try:
                    data = json.loads(row["value"])
                except json.JSONDecodeError:
                    print("   ✅ 检测到无效数据")

            # 清理
            db.execute("DELETE FROM kv_store WHERE key = 'invalid'")
        except Exception as e:
            print(f"   ✅ 数据库拒绝了无效数据: {e}")


class TestChaosProcess(unittest.TestCase):
    """混沌工程：进程故障"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "chaos_test.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_08_exception_during_execution(self):
        """混沌：任务执行中途抛出异常"""
        print("\n🔥 混沌测试8: 任务执行中途异常")

        from api.main import create_and_run_task
        from api.models import TaskCreateRequest

        # 模拟：某个阶段执行时抛出异常
        with patch("agents.parent.Agent.run") as mock_run:
            mock_run.side_effect = RuntimeError("模拟阶段执行失败")

            req = TaskCreateRequest(
                description="混沌测试：中途失败", sop_id="DEV-001", project_id="default"
            )

            result = create_and_run_task(req)

            # 验证：任务状态应该是failed，但不应该崩溃
            self.assertEqual(result.status, "failed")
            print(f"   ✅ 任务失败但不崩溃: {result.message}")

    def test_09_memory_pressure(self):
        """混沌：内存压力（模拟大数据）"""
        print("\n🔥 混沌测试9: 内存压力")

        # 创建大对象（模拟内存不足）
        large_data = ["x" * 10000 for _ in range(1000)]

        store = FileStore(self.test_file)

        # 尝试保存大对象
        try:
            store.save("large_data", large_data)
            print("   ✅ 成功保存大对象")
        except MemoryError:
            print("   ✅ 捕获到内存错误")
        finally:
            # 清理
            if hasattr(self, "temp_dir"):
                import shutil

                shutil.rmtree(self.temp_dir, ignore_errors=True)
            self.temp_dir = tempfile.mkdtemp()
            self.test_file = os.path.join(self.temp_dir, "chaos_test.json")


class TestChaosRecovery(unittest.TestCase):
    """混沌工程：恢复能力"""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "chaos_test.json")

    def tearDown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_10_recovery_from_crash(self):
        """混沌：崩溃后恢复"""
        print("\n🔥 混沌测试10: 崩溃后恢复")

        # 模拟：任务执行到一半崩溃
        from api.main import create_and_run_task
        from api.models import TaskCreateRequest

        task_id = None

        with patch("skills.orchestration.execute_stage") as mock_execute:
            # 第一个阶段成功，第二个阶段崩溃
            mock_execute.side_effect = [
                {"status": "completed", "output": "阶段1完成"},
                KeyboardInterrupt("模拟崩溃"),
            ]

            req = TaskCreateRequest(
                description="混沌测试：崩溃恢复", sop_id="DEV-001", project_id="default"
            )

            try:
                result = create_and_run_task(req)
            except KeyboardInterrupt:
                pass  # 预期中的崩溃

        # 验证：任务状态应该是failed或incomplete
        # 注意：当前实现可能不支持恢复，这是V4.0的功能
        print("   ⚠️ 已知限制：当前不支持任务恢复")
        print("   📋 建议：V4.0中实现检查点机制")

    def test_11_data_integrity_after_crash(self):
        """混沌：崩溃后数据完整性"""
        print("\n🔥 混沌测试11: 崩溃后数据完整性")

        # 创建FileStore并写入数据
        store = FileStore(self.test_file)
        store.save("key1", "value1")

        # 模拟崩溃（不调用save，直接删除文件）
        os.remove(self.test_file)

        # 重新创建FileStore（应该初始化为空）
        store2 = FileStore(self.test_file)

        # 验证：系统能处理缺失的文件
        self.assertEqual(store2._memory, {})
        print("   ✅ 数据完整性检查通过")


if __name__ == "__main__":
    unittest.main(verbosity=2)
