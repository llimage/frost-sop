"""
F7 生产加固 - ChromaDB 集成（向量记忆持久化）
PHILOSOPHY: Agent 的向量记忆从内存换成 ChromaDB 持久化存储。

core/memory.py - 向量记忆管理模块
提供 MemoryStore 类，负责向量记忆的存储和检索。
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# ChromaDB 数据目录
CHROMADB_DIR = "data/chromadb"


class MemoryStore:
    """
    向量记忆存储

    使用 ChromaDB 进行向量存储和检索。
    如果 ChromaDB 不可用或 embedding 失败，则降级为简单的关键词匹配。
    """

    def __init__(self, agent_id: str, persist_directory: str = CHROMADB_DIR):
        """
        初始化向量记忆存储

        Args:
            agent_id: Agent ID，用于创建独立的 Collection
            persist_directory: ChromaDB 数据目录
        """
        self.agent_id = agent_id
        self.persist_directory = persist_directory
        self.collection_name = f"agent_{agent_id}_memory"

        # 确保数据目录存在
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # 初始化 ChromaDB
        self.chroma_client = None
        self.collection = None
        self.fallback_mode = False  # 是否使用降级模式

        self._init_chromadb()

        # 降级模式：使用简单的关键词匹配
        self._memory_keywords = []  # 用于存储关键词索引

    def _init_chromadb(self):
        """初始化 ChromaDB 客户端和 Collection"""
        try:
            import chromadb
            from chromadb.config import Settings

            # 创建持久化客户端
            self.chroma_client = chromadb.PersistentClient(
                path=self.persist_directory,
                settings=Settings(
                    allow_reset=True,
                    anonymized_telemetry=False
                )
            )

            # 获取或创建 Collection
            try:
                self.collection = self.chroma_client.get_collection(
                    name=self.collection_name
                )
                logger.info(f"✅ 已加载 ChromaDB Collection: {self.collection_name}")
            except Exception:
                self.collection = self.chroma_client.create_collection(
                    name=self.collection_name,
                    metadata={"agent_id": self.agent_id}
                )
                logger.info(f"✅ 已创建 ChromaDB Collection: {self.collection_name}")

        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 初始化失败，使用降级模式: {e}")
            self.fallback_mode = True

    def add_memory(self, text: str, metadata: Optional[Dict[str, Any]] = None) -> str:
        """
        添加记忆

        Args:
            text: 记忆文本
            metadata: 元数据（可选）

        Returns:
            记忆 ID
        """
        if self.fallback_mode:
            # 降级模式：使用简单的关键词索引
            memory_id = f"mem_{len(self._memory_keywords)}"
            self._memory_keywords.append({
                "id": memory_id,
                "text": text,
                "metadata": metadata or {}
            })
            return memory_id

        try:
            # ChromaDB 模式
            import uuid
            memory_id = str(uuid.uuid4())

            # 准备元数据
            if metadata is None:
                metadata = {}

            # 添加记忆
            self.collection.add(
                documents=[text],
                metadatas=[metadata],
                ids=[memory_id]
            )

            return memory_id

        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 添加记忆失败，使用降级模式: {e}")
            self.fallback_mode = True
            return self.add_memory(text, metadata)  # 递归调用，使用降级模式

    def search_memory(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        搜索记忆

        Args:
            query: 查询文本
            top_k: 返回的最相关记忆数量

        Returns:
            记忆列表，每个记忆包含 text, metadata, score
        """
        if self.fallback_mode:
            # 降级模式：简单的关键词匹配
            results = []
            query_words = set(query.lower().split())

            for mem in self._memory_keywords:
                text_words = set(mem["text"].lower().split())
                overlap = len(query_words & text_words)
                if overlap > 0:
                    results.append({
                        "id": mem["id"],
                        "text": mem["text"],
                        "metadata": mem["metadata"],
                        "score": overlap / len(query_words)
                    })

            # 按分数排序
            results.sort(key=lambda x: x["score"], reverse=True)
            return results[:top_k]

        try:
            # ChromaDB 模式
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k
            )

            # 格式化结果
            formatted = []
            if results and results["ids"]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted.append({
                        "id": results["ids"][0][i],
                        "text": doc,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                        "score": 1.0  # ChromaDB 不返回分数，这里使用默认值
                    })

            return formatted

        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 搜索失败，使用降级模式: {e}")
            self.fallback_mode = True
            return self.search_memory(query, top_k)  # 递归调用，使用降级模式

    def delete_memory(self, memory_id: str) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            是否删除成功
        """
        if self.fallback_mode:
            # 降级模式
            self._memory_keywords = [m for m in self._memory_keywords if m["id"] != memory_id]
            return True

        try:
            # ChromaDB 模式
            self.collection.delete(ids=[memory_id])
            return True
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 删除失败: {e}")
            return False

    def get_all_memories(self) -> List[Dict[str, Any]]:
        """
        获取所有记忆

        Returns:
            所有记忆的列表
        """
        if self.fallback_mode:
            return self._memory_keywords

        try:
            results = self.collection.get()
            formatted = []
            if results and results["ids"]:
                for i, doc in enumerate(results["documents"]):
                    formatted.append({
                        "id": results["ids"][i],
                        "text": doc,
                        "metadata": results["metadatas"][i] if results["metadatas"] else {}
                    })
            return formatted
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 获取所有记忆失败: {e}")
            return []

    def clear(self):
        """清空所有记忆"""
        if self.fallback_mode:
            self._memory_keywords = []
            return

        try:
            # 删除 Collection
            self.chroma_client.delete_collection(name=self.collection_name)
            # 重新创建
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                metadata={"agent_id": self.agent_id}
            )
        except Exception as e:
            logger.warning(f"⚠️ ChromaDB 清空失败: {e}")


# 全局记忆存储字典（按 agent_id 缓存）
_memory_stores = {}


def get_memory_store(agent_id: str) -> MemoryStore:
    """
    获取记忆存储（单例模式，按 agent_id 缓存）

    Args:
        agent_id: Agent ID

    Returns:
        MemoryStore 实例
    """
    if agent_id not in _memory_stores:
        _memory_stores[agent_id] = MemoryStore(agent_id)
    return _memory_stores[agent_id]


def test_memory_store():
    """测试 MemoryStore 功能"""
    print("=" * 60)
    print("测试 MemoryStore (ChromaDB 集成)")
    print("=" * 60)

    # 创建记忆存储
    memory = MemoryStore("test_agent")

    # 添加记忆
    print("\n[1] 添加记忆...")
    id1 = memory.add_memory(
        "完成了一个 Python 项目的开发",
        {"project": "FROST-SOP", "type": "task"}
    )
    id2 = memory.add_memory(
        "修复了登录页面的 Bug",
        {"project": "FROST-SOP", "type": "bugfix"}
    )
    print(f"  添加记忆: {id1}, {id2}")

    # 搜索记忆
    print("\n[2] 搜索记忆...")
    results = memory.search_memory("Python 开发", top_k=3)
    print(f"  搜索结果: {len(results)} 条")
    for r in results:
        print(f"  - {r['text']} (score={r['score']:.2f})")

    # 获取所有记忆
    print("\n[3] 获取所有记忆...")
    all_mem = memory.get_all_memories()
    print(f"  共 {len(all_mem)} 条记忆")

    # 删除记忆
    print("\n[4] 删除记忆...")
    success = memory.delete_memory(id1)
    print(f"  删除结果: {success}")

    print("\n✅ MemoryStore 测试完成")
    return True


if __name__ == "__main__":
    test_memory_store()
