"""
tests/test_knowledge.py - 知识库公开 API 测试
Solo-Ops-Platform V0.9.0

覆盖：init/import/search/stats/rebuild（需 mock 向量存储）
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestKnowledgePublicAPI:
    """知识库公开 API 测试（使用 mock 避免真实向量存储依赖）。"""

    def test_check_capacity_limit_under_limit(self):
        """容量检查：正常范围内。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=100.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is False
            assert cap["limit_mb"] == 1024

    def test_check_capacity_limit_over_limit(self):
        """容量检查：超限。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=1500.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is False
            assert cap["used_mb"] == 1500.0

    def test_check_capacity_limit_warning_80(self):
        """容量检查：80%预警。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=850.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is True

    def test_get_knowledge_dir_size_mb(self):
        """目录大小计算。"""
        from knowledge import _get_knowledge_dir_size_mb
        with patch("knowledge._dir_size_mb", return_value=42.5):
            size = _get_knowledge_dir_size_mb()
            assert size == 42.5

    def test_get_knowledge_dir_size_mb_cached_ttl(self):
        """缓存TTL测试：60秒内返回缓存值。"""
        from knowledge import _get_knowledge_dir_size_mb_cached
        import time
        with patch.dict("knowledge._capacity_cache", {"value": 99.9, "timestamp": time.time()}):
            size = _get_knowledge_dir_size_mb_cached()
            assert size == 99.9

    def test_get_knowledge_dir_size_mb_cached_expired(self):
        """缓存过期测试：超过60秒重新计算。"""
        from knowledge import _get_knowledge_dir_size_mb_cached
        import time
        with patch.dict("knowledge._capacity_cache", {"value": 99.9, "timestamp": time.time() - 120}):
            with patch("knowledge._get_knowledge_dir_size_mb", return_value=50.0):
                size = _get_knowledge_dir_size_mb_cached()
                assert size == 50.0

    def test_import_document_capacity_exceeded(self):
        """导入文档：容量超限拒绝。"""
        import knowledge
        # 设置 _vector_store 为 mock（通过 RuntimeError 检查）
        original_vs = knowledge._vector_store
        try:
            knowledge._vector_store = MagicMock()
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": False, "used_mb": 1500.0, "limit_mb": 1024, "warning_80": True
            }):
                result = knowledge.import_document("/fake/file.txt")
                assert result["status"] == "error"
                assert "容量已达上限" in result["error"]
        finally:
            knowledge._vector_store = original_vs

    def test_import_document_not_initialized(self):
        """导入文档：未初始化报错。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            knowledge._vector_store = None
            with pytest.raises(RuntimeError, match="知识库未初始化"):
                knowledge.import_document("/fake/file.txt")
        finally:
            knowledge._vector_store = original_vs


class TestKnowledgeSensitivityBlocking:
    """敏感信息阻塞测试（V0.9.0 新增）。"""

    def test_high_sensitivity_blocked(self):
        """高敏感信息拒绝导入。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            knowledge._vector_store = MagicMock()
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_process:
                mock_process.return_value = {
                    "metadata": {"file_name": "sensitive.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "some content"}],
                    "sensitivity": {
                        "level": "high",
                        "confidence": 0.9,
                        "patterns": {"身份证号": 1},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "sensitive.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/sensitive.txt", category="internal")

                assert result["status"] == "blocked"
                assert "高敏感信息" in result["error"]
                assert "身份证号" in result["error"]
        finally:
            knowledge._vector_store = original_vs

    def test_medium_sensitivity_allowed(self):
        """中敏感信息允许导入（仅标记）。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            mock_vs = MagicMock()
            mock_vs.add_chunks.return_value = 1
            knowledge._vector_store = mock_vs
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_process, \
             patch("knowledge._load_index", return_value={"documents": {}}), \
             patch("knowledge._save_index"):
                mock_process.return_value = {
                    "metadata": {"file_name": "medium.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "some content"}],
                    "sensitivity": {
                        "level": "medium",
                        "confidence": 0.6,
                        "patterns": {"密码": 1},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "medium.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/medium.txt", category="internal")

                assert result["status"] == "success"
        finally:
            knowledge._vector_store = original_vs

    def test_no_sensitivity_allowed(self):
        """无敏感信息正常导入。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            mock_vs = MagicMock()
            mock_vs.add_chunks.return_value = 1
            knowledge._vector_store = mock_vs
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_process, \
             patch("knowledge._load_index", return_value={"documents": {}}), \
             patch("knowledge._save_index"):
                mock_process.return_value = {
                    "metadata": {"file_name": "safe.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "some content"}],
                    "sensitivity": {
                        "level": "none",
                        "confidence": 0.0,
                        "patterns": {},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "safe.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/safe.txt", category="internal")

                assert result["status"] == "success"
        finally:
            knowledge._vector_store = original_vs
