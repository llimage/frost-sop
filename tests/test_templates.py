"""
tests/test_templates.py - 快捷模板测试
Solo-Ops-Platform V0.9.0

覆盖：加载、保存、格式化、ID查找
"""
import pytest
import json
from pathlib import Path
from unittest.mock import patch


class TestLoadTemplates:
    """模板加载测试。"""

    def test_load_default_templates(self):
        """加载预置模板。"""
        from frontend.templates import load_templates
        templates = load_templates()
        assert isinstance(templates, list)
        assert len(templates) >= 3  # 至少3个预置模板

    def test_template_has_required_fields(self):
        """每个模板包含必要字段。"""
        from frontend.templates import load_templates
        templates = load_templates()
        required_fields = {"id", "name", "description", "category", "content"}
        for t in templates:
            assert required_fields.issubset(set(t.keys())), f"模板 {t.get('id')} 缺少字段"

    def test_template_ids_unique(self):
        """模板 ID 唯一。"""
        from frontend.templates import load_templates
        templates = load_templates()
        ids = [t["id"] for t in templates]
        assert len(ids) == len(set(ids))

    def test_load_templates_file_not_found(self):
        """模板文件不存在时返回空列表。"""
        from frontend.templates import load_templates, TEMPLATES_FILE
        with patch("frontend.templates.TEMPLATES_FILE", Path("/nonexistent/templates.json")):
            result = load_templates()
            assert result == []

    def test_load_templates_invalid_json(self):
        """模板文件 JSON 格式错误时返回空列表。"""
        from frontend.templates import load_templates
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", return_value="invalid json"):
            result = load_templates()
            assert result == []


class TestSaveTemplates:
    """模板保存测试。"""

    def test_save_templates_success(self, temp_dir):
        """成功保存模板。"""
        from frontend.templates import save_templates
        test_file = temp_dir / "test_templates.json"
        templates = [{"id": "test", "name": "测试模板", "content": "{topic}"}]
        with patch("frontend.templates.TEMPLATES_FILE", test_file):
            result = save_templates(templates)
        assert result is True
        saved = json.loads(test_file.read_text(encoding="utf-8"))
        assert len(saved) == 1

    def test_save_templates_failure(self):
        """保存失败（权限等）。"""
        from frontend.templates import save_templates
        with patch("frontend.templates.TEMPLATES_FILE", Path("/nonexistent/dir/templates.json")):
            # 不可写目录
            result = save_templates([{"id": "test"}])
            assert result is False


class TestFormatTemplate:
    """模板格式化测试。"""

    def test_format_with_kwargs(self):
        """使用参数格式化模板。"""
        from frontend.templates import format_template
        template = {"content": "主题：{topic}，目标：{goal}"}
        result = format_template(template, topic="AI工具", goal="竞品分析")
        assert "AI工具" in result
        assert "竞品分析" in result

    def test_format_missing_kwargs(self):
        """缺少参数时返回原内容。"""
        from frontend.templates import format_template
        template = {"content": "主题：{topic}，目标：{goal}"}
        result = format_template(template, topic="AI工具")
        # 缺少 goal 参数，应返回原内容
        assert "{topic}" in result or "AI工具" in result

    def test_format_empty_content(self):
        """空内容返回空字符串。"""
        from frontend.templates import format_template
        template = {"content": ""}
        result = format_template(template)
        assert result == ""

    def test_format_no_placeholders(self):
        """无占位符的模板。"""
        from frontend.templates import format_template
        template = {"content": "这是一个固定模板内容"}
        result = format_template(template)
        assert result == "这是一个固定模板内容"


class TestGetTemplateById:
    """按 ID 查找模板测试。"""

    def test_find_existing_template(self):
        """查找存在的模板。"""
        from frontend.templates import get_template_by_id
        with patch("frontend.templates.load_templates", return_value=[
            {"id": "doc-summary", "name": "文档总结"},
            {"id": "code-review", "name": "代码审查"},
        ]):
            result = get_template_by_id("code-review")
        assert result is not None
        assert result["name"] == "代码审查"

    def test_find_nonexistent_template(self):
        """查找不存在的模板返回 None。"""
        from frontend.templates import get_template_by_id
        with patch("frontend.templates.load_templates", return_value=[
            {"id": "doc-summary", "name": "文档总结"},
        ]):
            result = get_template_by_id("nonexistent")
        assert result is None
