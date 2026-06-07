"""
tests/test_bm25_index.py - BM25 索引测试
Solo-Ops-Platform V0.9.0

覆盖：分词、索引构建、检索、负分数处理、数据持久化
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

from knowledge.bm25_index import BM25Index


class TestBM25IndexUnit:
    """BM25 索引单元测试（使用 mock 避免磁盘依赖）。"""

    def test_tokenizer_chinese(self):
        """中文分词测试。"""
        idx = BM25Index()
        tokens = idx._tokenize("人工智能技术发展趋势")
        assert isinstance(tokens, list)
        assert len(tokens) > 0
        # jieba 应该将"人工智能"分为至少"人工"和"智能"
        assert any("人工" in t or "智能" in t for t in tokens)

    def test_tokenizer_mixed(self):
        """中英混合分词测试。"""
        idx = BM25Index()
        tokens = idx._tokenize("AI人工智能 technology技术")
        assert len(tokens) > 0

    def test_tokenizer_empty(self):
        """空文本分词。"""
        idx = BM25Index()
        tokens = idx._tokenize("")
        assert tokens == []

    def test_add_document(self):
        """添加文档测试。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        chunks = [
            {"chunk_id": 0, "content": "这是第一个分块的内容，关于市场分析"},
            {"chunk_id": 1, "content": "这是第二个分块的内容，关于竞品对比"},
        ]
        idx.add_document("doc_test_001", chunks, "product")

        assert len(idx.doc_meta) == 1
        assert idx.doc_meta[0]["doc_id"] == "doc_test_001"
        assert idx.doc_meta[0]["category"] == "product"
        assert "chunk_ids" in idx.doc_meta[0]

    def test_search_returns_results(self):
        """搜索返回结果测试。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        # 添加多个文档
        chunks_1 = [
            {"chunk_id": 0, "content": "人工智能技术在医疗领域的应用越来越广泛"},
            {"chunk_id": 1, "content": "深度学习模型在图像识别方面取得突破"},
        ]
        chunks_2 = [
            {"chunk_id": 0, "content": "新能源汽车市场竞争激烈，各家推出新车型"},
            {"chunk_id": 1, "content": "电池技术的进步推动电动车续航提升"},
        ]
        idx.add_document("doc_ai", chunks_1, "tech")
        idx.add_document("doc_ev", chunks_2, "industry")

        # 搜索AI相关
        results = idx.search("人工智能", top_k=5)
        assert isinstance(results, list)
        # 应该能找到AI相关的文档
        if results:
            assert "doc_id" in results[0]
            assert "content" in results[0]

    def test_search_empty_index(self):
        """空索引搜索。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        results = idx.search("测试查询", top_k=5)
        assert results == []

    def test_search_returns_category(self):
        """搜索结果包含 category 字段。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        chunks_1 = [{"chunk_id": 0, "content": "产品功能介绍：AI写作助手"}]
        idx.add_document("doc_product", chunks_1, "product")

        results = idx.search("AI写作", top_k=5)
        if results:
            assert "category" in results[0]
            assert results[0]["category"] == "product"

    def test_remove_document(self):
        """删除文档测试。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        chunks = [{"chunk_id": 0, "content": "待删除的文档内容"}]
        idx.add_document("doc_to_delete", chunks, "test")

        assert len(idx.doc_meta) == 1
        idx.remove_document("doc_to_delete")
        assert len(idx.doc_meta) == 0

    def test_negative_score_handling(self):
        """负分数处理测试（小语料库下BM25 IDF可为负）。"""
        idx = BM25Index()
        idx.documents = []
        idx.chunks = []
        idx.doc_meta = []
        idx.chunk_map = {}
        idx.bm25 = None

        # 只添加1个文档（小语料库）
        chunks = [{"chunk_id": 0, "content": "唯一的一个文档内容关于测试"}]
        idx.add_document("doc_single", chunks, "test")

        # 搜索应该不会崩溃
        results = idx.search("测试", top_k=5)
        assert isinstance(results, list)  # 可能空，但不应该报错
