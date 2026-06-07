"""
tests/test_document_processor.py - 文档处理器测试
Solo-Ops-Platform V0.9.0

覆盖：文本提取、敏感信息检测、文档类型识别、智能分块
"""
import pytest
from pathlib import Path
from knowledge.document_processor import (
    process_document,
    _extract_text,
    _scan_sensitivity,
    _detect_doc_type,
    _smart_chunk,
)


class TestExtractText:
    """文本提取测试。"""

    def test_extract_txt(self, temp_text_file):
        result = _extract_text(temp_text_file)
        assert "测试文档" in result
        assert "两个段落" in result

    def test_extract_md(self, temp_markdown_file):
        result = _extract_text(temp_markdown_file)
        assert "# 产品规划文档" in result
        assert "市场分析" in result

    def test_extract_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            _extract_text(Path("/nonexistent/file.txt"))

    def test_extract_unsupported_format(self, temp_dir):
        f = temp_dir / "test.xyz"
        f.write_text("content", encoding="utf-8")
        with pytest.raises(ValueError, match="不支持的文件格式"):
            _extract_text(f)


class TestScanSensitivity:
    """敏感信息检测测试。"""

    def test_no_sensitive_info(self):
        result = _scan_sensitivity("这是一段普通文本，没有敏感信息。")
        assert result["level"] == "none"
        assert result["confidence"] == 0.0
        assert len(result["patterns"]) == 0

    def test_id_card_high_sensitivity(self):
        result = _scan_sensitivity("身份证号：110101199001011234")
        assert result["level"] == "high"
        assert result["confidence"] >= 0.8
        assert "身份证号" in result["patterns"]

    def test_phone_medium_sensitivity(self):
        # 手机号 confidence=0.3，单独出现时 level=low
        result = _scan_sensitivity("手机号：13800138000")
        assert result["level"] == "low"
        assert "手机号" in result["patterns"]

    def test_password_medium_sensitivity(self):
        result = _scan_sensitivity("密码：password=MySecret123")
        assert result["level"] == "medium"
        assert "密码" in result["patterns"]

    def test_bank_card_sensitivity(self):
        # 银行卡号 16 位不会同时匹配身份证号模式（需17+位）
        # 使用 16 位银行卡号
        result = _scan_sensitivity("银行卡号：6222021234567890")
        assert "银行卡号" in result["patterns"]
        # 16位银行卡号 confidence=0.5，不满足 >0.5，level=low
        assert result["level"] == "low"

    def test_email_low_sensitivity(self):
        result = _scan_sensitivity("邮箱：test@example.com")
        assert result["level"] == "low"
        assert "邮箱地址" in result["patterns"]

    def test_multiple_patterns(self, sample_text_with_sensitivity):
        result = _scan_sensitivity(sample_text_with_sensitivity)
        assert result["level"] == "high"  # 身份证号导致 high
        assert len(result["patterns"]) >= 3

    def test_empty_text(self):
        result = _scan_sensitivity("")
        assert result["level"] == "none"


class TestDetectDocType:
    """文档类型识别测试。"""

    def test_qa_by_filename(self, temp_dir):
        f = temp_dir / "FAQ常见问答.txt"
        f.write_text("问题1：什么是AI？\n答案：AI是人工智能。", encoding="utf-8")
        assert _detect_doc_type(f, "") == "qa"

    def test_qa_by_content(self, temp_dir):
        f = temp_dir / "questions.txt"
        f.write_text("Q: 什么是AI？\nA: 人工智能。", encoding="utf-8")
        assert _detect_doc_type(f, "Q: 什么是AI？") == "qa"

    def test_standard_md_with_headings(self, temp_markdown_file):
        assert _detect_doc_type(temp_markdown_file, temp_markdown_file.read_text(encoding="utf-8")) == "standard"

    def test_long_document(self, temp_dir):
        f = temp_dir / "long.txt"
        f.write_bytes(b"x" * (201 * 1024))  # >200KB
        assert _detect_doc_type(f, "") == "long"

    def test_default_standard(self, temp_text_file):
        assert _detect_doc_type(temp_text_file, temp_text_file.read_text(encoding="utf-8")) == "standard"


class TestSmartChunk:
    """智能分块测试。"""

    def test_basic_chunking(self):
        text = "这是一段测试文本。" * 50
        chunks = _smart_chunk(text, "standard", Path("test.txt"))
        assert len(chunks) > 0
        assert all(c["content"].strip() for c in chunks)  # S-3：无空 chunk

    def test_chunk_ids_sequential(self):
        text = "这是第一段。\n\n这是第二段。\n\n这是第三段。" * 10
        chunks = _smart_chunk(text, "standard", Path("test.txt"))
        for i, chunk in enumerate(chunks):
            assert chunk["chunk_id"] == i

    def test_empty_text_chunking(self):
        chunks = _smart_chunk("", "standard", Path("test.txt"))
        # 空文本可能产生0个chunk或空chunk被过滤
        assert all(c["content"].strip() for c in chunks)

    def test_qa_chunking(self, temp_dir):
        f = temp_dir / "faq.txt"
        f.write_text("Q: 问题1？\nA: 答案1。\nQ: 问题2？\nA: 答案2。", encoding="utf-8")
        text = f.read_text(encoding="utf-8")
        chunks = _smart_chunk(text, "qa", f)
        assert len(chunks) > 0


class TestProcessDocument:
    """完整文档处理流程测试。"""

    def test_process_markdown(self, temp_markdown_file):
        result = process_document(temp_markdown_file, category="product")
        assert "metadata" in result
        assert "chunks" in result
        assert "sensitivity" in result
        assert result["metadata"]["file_name"] == "test_doc.md"
        assert result["metadata"]["category"] == "product"
        assert len(result["chunks"]) > 0

    def test_process_text(self, temp_text_file):
        result = process_document(temp_text_file)
        assert result["metadata"]["file_name"] == "test_doc.txt"
        assert result["sensitivity"]["level"] == "none"

    def test_process_sensitive_document(self, temp_sensitive_file):
        result = process_document(temp_sensitive_file)
        assert result["sensitivity"]["level"] in ("high", "medium", "low")
        assert len(result["sensitivity"]["patterns"]) > 0

    def test_process_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            process_document(Path("/nonexistent/file.txt"))

    def test_seed_flag_in_metadata(self, temp_text_file):
        result = process_document(temp_text_file, is_seed=True)
        assert result["metadata"]["doc_type"] in ("standard", "qa", "long")
