"""
V7 阶段3 覆盖率补测试 — skills/search.py (8.6% → 80%+)
搜索技能：search_sop, search_skill
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.search import search_skill, search_skill_skill, search_sop, search_sop_skill


class MockStore:
    """模拟资产Store"""

    def __init__(self):
        self._data = {}

    def save(self, key, value):
        self._data[key] = value

    def load(self, key):
        return self._data.get(key)

    def list_keys(self):
        return list(self._data.keys())


class TestSearchSop:
    """search_sop 函数测试"""

    def test_search_with_asset_store_match(self):
        """Store中有匹配SOP"""
        store = MockStore()
        store.save("sop_template:DEV-001", {"name": "新功能开发", "sop_id": "DEV-001"})
        ctx = {"_search_query": "DEV-001", "_asset_store": store, "_search_external": False}
        result = search_sop(ctx)
        assert len(result["_search_results"]) == 1
        assert result["_search_results"][0]["source"] == "asset_store"
        assert result["_search_results"][0]["sop_id"] == "DEV-001"

    def test_search_with_asset_store_fuzzy(self):
        """Store中模糊匹配"""
        store = MockStore()
        store.save("sop_template:DEV-001", {"name": "新功能开发", "sop_id": "DEV-001"})
        ctx = {"_search_query": "dev", "_asset_store": store, "_search_external": False}
        result = search_sop(ctx)
        assert len(result["_search_results"]) >= 1

    def test_search_no_store_no_external(self):
        """无Store无外部搜索"""
        ctx = {"_search_query": "test", "_search_external": False}
        result = search_sop(ctx)
        assert result["_search_results"] == []

    def test_search_empty_query(self):
        """空查询"""
        ctx = {"_search_query": "", "_search_external": False}
        result = search_sop(ctx)
        assert result["_search_results"] == []

    def test_search_skill_instance(self):
        """验证 Skill 实例"""
        assert search_sop_skill.name == "search_sop"


class TestSearchSkill:
    """search_skill 函数测试"""

    def test_search_skill_returns_results(self):
        """搜索Skill（mock LLM响应）"""
        import unittest.mock as mock

        # Mock LLM返回JSON结果
        mock_llm_context = {
            "_llm_response": '{"found": true, "results": [{"skill_name": "test_skill", "description": "A test skill", "input_keys": ["_prompt"], "output_keys": ["_output"]}]}'
        }
        mock_skill = mock.MagicMock()
        mock_skill.execute.return_value = mock_llm_context

        with mock.patch("skills.search.call_llm_skill", mock_skill):
            ctx = {"_search_query": "数据分析"}
            result = search_skill(ctx)
            assert "_search_results" in result
            assert "_reason" in result

    def test_search_skill_no_results(self):
        """搜索Skill无结果"""
        import unittest.mock as mock

        mock_llm_context = {"_llm_response": '{"found": false, "results": []}'}
        mock_skill = mock.MagicMock()
        mock_skill.execute.return_value = mock_llm_context

        with mock.patch("skills.search.call_llm_skill", mock_skill):
            ctx = {"_search_query": "不存在的东西"}
            result = search_skill(ctx)
            assert result["_search_results"] == []

    def test_search_skill_invalid_json(self):
        """搜索Skill LLM返回无效JSON"""
        import unittest.mock as mock

        mock_llm_context = {"_llm_response": "不是JSON的文本"}
        mock_skill = mock.MagicMock()
        mock_skill.execute.return_value = mock_llm_context

        with mock.patch("skills.search.call_llm_skill", mock_skill):
            ctx = {"_search_query": "test"}
            result = search_skill(ctx)
            assert result["_search_results"] == []

    def test_search_skill_skill_instance(self):
        """验证 Skill 实例"""
        assert search_skill_skill.name == "search_skill"

    def test_search_sop_external_llm(self):
        """search_sop 外部搜索（mock LLM）"""
        import unittest.mock as mock

        store = MockStore()
        mock_llm_context = {
            "_llm_response": '{"found": true, "results": [{"sop_id": "EXT-001", "name": "外部SOP", "content": {"stages": []}}]}'
        }
        mock_skill_inst = mock.MagicMock()
        mock_skill_inst.execute.return_value = mock_llm_context

        with mock.patch("skills.search.call_llm_skill", mock_skill_inst):
            ctx = {"_search_query": "外部SOP", "_asset_store": store, "_search_external": True}
            result = search_sop(ctx)
            # Store没匹配到 → 触发外部搜索
            assert len(result["_search_results"]) >= 1
