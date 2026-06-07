"""
tests/test_sensitivity.py - 敏感信息阻塞测试
Solo-Ops-Platform V0.9.0

覆盖：各级别敏感信息检测、阻塞逻辑、patterns字段
"""
import pytest
from unittest.mock import patch, MagicMock


class TestSensitivityLevels:
    """敏感级别检测测试。"""

    def test_high_level_triggers(self):
        """高敏感（身份证号）触发。"""
        from knowledge.document_processor import _scan_sensitivity
        result = _scan_sensitivity("身份证号：110101199001011234")
        assert result["level"] == "high"
        assert result["confidence"] >= 0.8

    def test_medium_level_triggers(self):
        """中敏感（密码）触发。"""
        from knowledge.document_processor import _scan_sensitivity
        # 密码 confidence=0.6，满足 >0.5
        result = _scan_sensitivity("密码：password=MySecret123")
        assert result["level"] == "medium"

    def test_low_level_triggers(self):
        """低敏感（手机号/邮箱）触发。"""
        from knowledge.document_processor import _scan_sensitivity
        result = _scan_sensitivity("手机号：13800138000")
        assert result["level"] == "low"

    def test_none_level(self):
        """无敏感信息。"""
        from knowledge.document_processor import _scan_sensitivity
        result = _scan_sensitivity("这是普通文本，没有任何敏感信息。")
        assert result["level"] == "none"
        assert result["confidence"] == 0.0


class TestSensitivityPatterns:
    """敏感模式检测测试。"""

    def test_patterns_contain_type_not_content(self):
        """patterns 字典只记录模式类型和数量，不记录具体匹配内容。"""
        from knowledge.document_processor import _scan_sensitivity
        result = _scan_sensitivity("身份证号：110101199001011234，手机号：13800138000")
        assert "身份证号" in result["patterns"]
        assert "手机号" in result["patterns"]
        assert isinstance(result["patterns"]["身份证号"], int)

    def test_multiple_same_pattern(self):
        """同类型多次匹配。"""
        from knowledge.document_processor import _scan_sensitivity
        result = _scan_sensitivity("手机号1：13800138000，手机号2：13900139000")
        assert "手机号" in result["patterns"]
        assert result["patterns"]["手机号"] == 2


class TestSensitivityBlocking:
    """导入时敏感阻塞测试。"""

    def test_high_sensitivity_blocked_in_import(self):
        """高敏感信息在 import_document 中被阻塞。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            mock_vs = MagicMock()
            knowledge._vector_store = mock_vs
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_proc:
                mock_proc.return_value = {
                    "metadata": {"file_name": "secret.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "身份证号1234"}],
                    "sensitivity": {
                        "level": "high",
                        "confidence": 0.9,
                        "patterns": {"身份证号": 1},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "secret.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/secret.txt")

                assert result["status"] == "blocked"
                assert result["sensitivity"]["level"] == "high"
                # 不应该调用 add_chunks（阻塞在向量化之前）
                mock_vs.add_chunks.assert_not_called()
        finally:
            knowledge._vector_store = original_vs

    def test_medium_sensitivity_not_blocked(self):
        """中敏感信息不被阻塞，正常导入。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            mock_vs = MagicMock()
            mock_vs.add_chunks.return_value = 1
            knowledge._vector_store = mock_vs
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_proc, \
             patch("knowledge._load_index", return_value={"documents": {}}), \
             patch("knowledge._save_index"):
                mock_proc.return_value = {
                    "metadata": {"file_name": "warning.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "邮箱test@example.com"}],
                    "sensitivity": {
                        "level": "medium",
                        "confidence": 0.6,
                        "patterns": {"密码": 1},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "warning.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/warning.txt")

                assert result["status"] == "success"
        finally:
            knowledge._vector_store = original_vs

    def test_blocked_error_includes_pattern_names(self):
        """阻塞错误信息包含检测到的模式类型。"""
        import knowledge
        original_vs = knowledge._vector_store
        try:
            knowledge._vector_store = MagicMock()
            with patch("knowledge._check_capacity_limit", return_value={
                "allowed": True, "used_mb": 100.0, "limit_mb": 1024, "warning_80": False
            }), \
             patch("knowledge.document_processor.process_document") as mock_proc:
                mock_proc.return_value = {
                    "metadata": {"file_name": "multi.txt", "import_time": "2026-01-01", "file_size": 100, "doc_type": "standard"},
                    "chunks": [{"chunk_id": 0, "content": "content"}],
                    "sensitivity": {
                        "level": "high",
                        "confidence": 0.9,
                        "patterns": {"身份证号": 2, "银行卡号": 1},
                    },
                }
                with patch("knowledge.Path") as mock_path_cls:
                    mock_path = MagicMock()
                    mock_path.exists.return_value = True
                    mock_path.name = "multi.txt"
                    mock_path_cls.return_value = mock_path

                    result = knowledge.import_document("/fake/multi.txt")

                assert result["status"] == "blocked"
                assert "身份证号" in result["error"]
                assert "银行卡号" in result["error"]
        finally:
            knowledge._vector_store = original_vs
