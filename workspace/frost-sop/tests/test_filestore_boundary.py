"""
FileStore 边界条件测试

测试 FileStore 在异常情况下的行为：
1. 空文件（0字节）
2. 损坏的JSON文件
3. 无读取权限的文件
4. 部分写入的文件（模拟崩溃）

确保所有异常情况都能优雅处理，不崩溃。
"""

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

# 确保 frost-sop 在 Python 路径中
sys_path = Path(__file__).parent.parent
import sys

sys.path.insert(0, str(sys_path))

from stores.asset import FileStore


class TestFileStoreBoundary(unittest.TestCase):
    """FileStore 边界条件测试"""

    def setUp(self):
        """每个测试前创建临时文件"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_store.json")

    def tearDown(self):
        """每个测试后清理临时文件"""
        import shutil

        # 确保文件可删除（Windows权限问题）
        if os.path.exists(self.test_file):
            os.chmod(self.test_file, stat.S_IWRITE)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_01_empty_file(self):
        """测试：文件存在但是空的（0字节）"""
        # 创建空文件
        with open(self.test_file, "w") as f:
            pass  # 文件为空

        # 验证文件存在且为空
        self.assertTrue(os.path.exists(self.test_file))
        self.assertEqual(os.path.getsize(self.test_file), 0)

        # 创建 FileStore（应该不崩溃）
        store = FileStore(self.test_file)

        # 验证：初始化为空字典
        self.assertEqual(store._memory, {})
        print("✅ 空文件测试通过")

    def test_02_corrupted_json(self):
        """测试：文件包含无效的JSON"""
        # 写入无效JSON
        with open(self.test_file, "w") as f:
            f.write("{invalid json content")

        # 创建 FileStore（应该不崩溃）
        store = FileStore(self.test_file)

        # 验证：初始化为空字典
        self.assertEqual(store._memory, {})
        print("✅ 损坏JSON测试通过")

    def test_03_partial_json(self):
        """测试：文件包含部分JSON（模拟写入中断）"""
        # 写入部分JSON（未闭合）
        with open(self.test_file, "w") as f:
            f.write('{"key": "value"')  # 缺少 closing }

        # 创建 FileStore（应该不崩溃）
        store = FileStore(self.test_file)

        # 验证：初始化为空字典
        self.assertEqual(store._memory, {})
        print("✅ 部分JSON测试通过")

    def test_04_valid_json(self):
        """测试：文件包含有效JSON（快乐路径）"""
        # 写入有效JSON
        valid_data = {"key1": "value1", "key2": {"nested": "data"}}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(valid_data, f, ensure_ascii=False)

        # 创建 FileStore
        store = FileStore(self.test_file)

        # 验证：正确加载数据
        self.assertEqual(store._memory, valid_data)
        print("✅ 有效JSON测试通过")

    def test_05_unicode_content(self):
        """测试：文件包含Unicode字符"""
        # 写入包含中文的JSON
        unicode_data = {"任务": "测试", "描述": "包含中文和emoji 🔮"}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(unicode_data, f, ensure_ascii=False)

        # 创建 FileStore
        store = FileStore(self.test_file)

        # 验证：正确加载Unicode数据
        self.assertEqual(store._memory, unicode_data)
        print("✅ Unicode内容测试通过")

    def test_06_save_and_reload(self):
        """测试：保存后重新加载"""
        # 创建 FileStore（新文件）
        store = FileStore(self.test_file)
        store.save("test_key", "test_value")

        # 验证文件已写入
        self.assertTrue(os.path.exists(self.test_file))

        # 创建新的 FileStore（重新加载）
        store2 = FileStore(self.test_file)

        # 验证：数据正确重新加载
        self.assertEqual(store2._memory.get("test_key"), "test_value")
        print("✅ 保存并重新加载测试通过")

    def test_07_file_not_exists(self):
        """测试：文件不存在（应该创建空字典）"""
        # 确保文件不存在
        self.assertFalse(os.path.exists(self.test_file))

        # 创建 FileStore（应该不崩溃）
        store = FileStore(self.test_file)

        # 验证：初始化为空字典
        self.assertEqual(store._memory, {})
        print("✅ 文件不存在测试通过")

    def test_08_large_file(self):
        """测试：大文件（性能边界）"""
        # 创建大JSON（1MB）
        large_data = {"data": ["x" * 1000 for _ in range(1000)]}
        with open(self.test_file, "w", encoding="utf-8") as f:
            json.dump(large_data, f, ensure_ascii=False)

        # 创建 FileStore（应该能处理大文件）
        store = FileStore(self.test_file)

        # 验证：正确加载
        self.assertEqual(len(store._memory["data"]), 1000)
        print("✅ 大文件测试通过")


if __name__ == "__main__":
    unittest.main(verbosity=2)
