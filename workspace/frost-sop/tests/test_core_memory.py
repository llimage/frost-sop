"""
core/memory.py 单元测试

测试 MemoryStore — 回退模式和 ChromaDB 模式。
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FROST_TESTING", "1")

import pytest


class TestMemoryStoreFallback:
    """测试 MemoryStore 回退模式 — 绕过 __init__ 直接设置 fallback"""

    @pytest.fixture
    def store(self, tmp_path):
        """创建回退模式的 MemoryStore（绕过 chromadb 初始化）"""
        from core.memory import MemoryStore

        # 使用 object.__new__ 绕过 __init__，手动设置 fallback 状态
        ms = object.__new__(MemoryStore)
        ms.agent_id = "test_fallback"
        ms.persist_directory = str(tmp_path / "chroma")
        ms.collection_name = "agent_test_fallback_memory"
        ms.chroma_client = None
        ms.collection = None
        ms.fallback_mode = True
        ms._memory_keywords = []
        return ms

    def test_fallback_mode_set(self, store):
        assert store.fallback_mode is True

    def test_add_memory(self, store):
        mem_id = store.add_memory("这是一条测试记忆")
        assert mem_id.startswith("mem_")

    def test_search_memory(self, store):
        store.add_memory("Python is a programming language")
        store.add_memory("Testing is important for code quality")

        results = store.search_memory("Python testing", top_k=3)
        assert len(results) >= 1

    def test_search_memory_no_match(self, store):
        store.add_memory("Python")
        results = store.search_memory("zzzxxxccc", top_k=5)
        assert isinstance(results, list)

    def test_get_all_memories(self, store):
        store.add_memory("Memory 1")
        store.add_memory("Memory 2")
        all_mems = store.get_all_memories()
        assert len(all_mems) == 2

    def test_delete_memory(self, store):
        mem_id = store.add_memory("To be deleted")
        assert store.delete_memory(mem_id) is True

    def test_delete_nonexistent(self, store):
        # 回退模式下 delete_memory 始终返回 True（因为只过滤列表）
        result = store.delete_memory("nonexistent_id")
        assert result is True  # fallback 模式行为

    def test_clear(self, store):
        store.add_memory("M1")
        store.add_memory("M2")
        store.clear()
        assert len(store.get_all_memories()) == 0

    def test_search_with_chinese(self, store):
        store.add_memory("中文记忆测试")
        results = store.search_memory("中文记忆")
        assert isinstance(results, list)

    def test_add_memory_with_metadata(self, store):
        meta = {"source": "user", "priority": 1}
        mem_id = store.add_memory("Test with metadata", metadata=meta)
        assert mem_id is not None


class TestMemoryStoreChromaDB:
    """测试 ChromaDB 模式 — 直接赋值 mock collection"""

    def test_add_memory_chroma(self, tmp_path):
        """add_memory 在 ChromaDB 模式下正常工作"""
        from core.memory import MemoryStore

        store = object.__new__(MemoryStore)
        store.agent_id = "c"
        store.persist_directory = str(tmp_path)
        store.collection_name = "agent_c_memory"
        store.chroma_client = MagicMock()
        store.fallback_mode = False
        store._memory_keywords = []

        mock_collection = MagicMock()
        store.collection = mock_collection

        mem_id = store.add_memory("ChromaDB test")
        assert len(mem_id) > 0

    def test_search_memory_chroma(self, tmp_path):
        """search_memory 在 ChromaDB 模式下返回正确结果"""
        from core.memory import MemoryStore

        store = object.__new__(MemoryStore)
        store.agent_id = "c2"
        store.persist_directory = str(tmp_path)
        store.collection_name = "agent_c2_memory"
        store.chroma_client = MagicMock()
        store.fallback_mode = False
        store._memory_keywords = []

        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "ids": [["id1", "id2"]],
            "documents": [["doc1", "doc2"]],
            "metadatas": [[{}, {}]],
            "distances": [[0.1, 0.3]],
        }
        store.collection = mock_collection

        results = store.search_memory("query", top_k=2)
        assert len(results) == 2
        assert results[0]["id"] == "id1"


class TestGetMemoryStore:
    """测试 get_memory_store 工厂函数"""

    def test_creates_and_caches(self, tmp_path):
        from core.memory import get_memory_store

        ms1 = get_memory_store("agent_cache_test")
        ms2 = get_memory_store("agent_cache_test")
        assert ms1 is ms2
