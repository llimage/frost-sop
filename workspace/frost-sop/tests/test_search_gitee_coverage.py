"""
V7 阶段3 覆盖率补测试 — skills/search_gitee.py (0% → 80%+)
Gitee搜索技能
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.search_gitee import search_gitee, search_gitee_skill


class TestSearchGitee:
    """Gitee搜索测试"""

    def test_no_token_returns_empty(self):
        """无GITEE_TOKEN时跳过搜索"""
        os.environ.pop("GITEE_TOKEN", None)
        ctx = {"_search_query": "test"}
        result = search_gitee(ctx)
        assert result["_search_results"] == []
        assert "GITEE_TOKEN" in result["_reason"]

    def test_with_token_mock_api(self):
        """有Token时mock API调用"""
        import unittest.mock as mock

        os.environ["GITEE_TOKEN"] = "mock_token_123"
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "content": {
                "repos": [
                    {
                        "full_name": "user/frost-sop",
                        "description": "A test repo",
                        "html_url": "https://gitee.com/user/frost-sop",
                    },
                    {
                        "full_name": "user/other",
                        "description": "Another repo",
                        "html_url": "https://gitee.com/user/other",
                    },
                ]
            }
        }

        with mock.patch("requests.get", return_value=mock_resp):
            ctx = {"_search_query": "FROST-SOP"}
            result = search_gitee(ctx)
            assert len(result["_search_results"]) == 2
            assert result["_search_results"][0]["source"] == "gitee"

        os.environ.pop("GITEE_TOKEN", None)

    def test_api_error_returns_empty(self):
        """API返回非200时"""
        import unittest.mock as mock

        os.environ["GITEE_TOKEN"] = "mock_token"
        mock_resp = mock.MagicMock()
        mock_resp.status_code = 500

        with mock.patch("requests.get", return_value=mock_resp):
            ctx = {"_search_query": "test"}
            result = search_gitee(ctx)
            assert result["_search_results"] == []
            assert "500" in result["_reason"]

        os.environ.pop("GITEE_TOKEN", None)

    def test_network_exception(self):
        """网络异常时"""
        import unittest.mock as mock

        os.environ["GITEE_TOKEN"] = "mock_token"
        with mock.patch("requests.get", side_effect=Exception("Connection failed")):
            ctx = {"_search_query": "test"}
            result = search_gitee(ctx)
            assert result["_search_results"] == []

        os.environ.pop("GITEE_TOKEN", None)

    def test_skill_instance(self):
        assert search_gitee_skill.name == "search_gitee"
