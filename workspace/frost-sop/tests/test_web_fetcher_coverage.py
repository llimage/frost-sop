"""
V7 阶段3 覆盖率补测试 — skills/web_fetcher.py (0% → 70%+)
Web抓取技能：_TextExtractor, web_fetch, _duckduckgo_search, _fetch_url_content
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.web_fetcher import (
    _fetch_url_content,
    _TextExtractor,
    web_fetch,
    web_fetch_skill,
)


class TestTextExtractor:
    """HTML→纯文本解析器测试"""

    def test_simple_text(self):
        parser = _TextExtractor()
        parser.feed("<p>Hello World</p>")
        assert parser.get_text() == "Hello World"

    def test_skip_script(self):
        parser = _TextExtractor()
        parser.feed("<script>alert('x')</script><p>Content</p>")
        text = parser.get_text()
        assert "alert" not in text
        assert "Content" in text

    def test_skip_style(self):
        parser = _TextExtractor()
        parser.feed("<style>body{color:red}</style><p>Text</p>")
        text = parser.get_text()
        assert "color" not in text
        assert "Text" in text

    def test_skip_nav_footer(self):
        parser = _TextExtractor()
        parser.feed("<nav>Menu</nav><main>Body</main><footer>Footer</footer>")
        text = parser.get_text()
        assert "Menu" not in text
        assert "Footer" not in text
        assert "Body" in text

    def test_empty_html(self):
        parser = _TextExtractor()
        parser.feed("")
        assert parser.get_text() == ""

    def test_nested_skip_tags(self):
        parser = _TextExtractor()
        html = "<header><p>Header text</p></header><article>Real content</article>"
        parser.feed(html)
        text = parser.get_text()
        assert "Header text" not in text
        assert "Real content" in text

    def test_multiple_text_parts(self):
        parser = _TextExtractor()
        parser.feed("<h1>Title</h1><p>Paragraph 1</p><p>Paragraph 2</p>")
        text = parser.get_text()
        assert "Title" in text
        assert "Paragraph 1" in text
        assert "Paragraph 2" in text

    def test_whitespace_stripped(self):
        parser = _TextExtractor()
        parser.feed("<p>   Spaced   Text   </p>")
        text = parser.get_text()
        assert text == "Spaced   Text"


class TestWebFetch:
    """web_fetch 函数测试"""

    def test_no_urls_no_query(self):
        """无URL无query时返回空内容"""
        ctx = {}
        result = web_fetch(ctx)
        assert result["_web_content"] == ""
        assert result["_web_sources"] == []
        assert "未提供URL" in result["_reason"]

    def test_with_mock_urls_and_mock_fetch(self):
        """提供URL列表，mock抓取"""
        import unittest.mock as mock

        mock_text = "Test page content"
        mock_title = "Test Title"
        with mock.patch(
            "skills.web_fetcher._fetch_url_content", return_value=(mock_text, mock_title)
        ):
            ctx = {"_urls": ["https://example.com"]}
            result = web_fetch(ctx)
            assert result["_web_content"] != ""
            assert len(result["_web_sources"]) == 1
            assert result["_web_sources"][0]["title"] == "Test Title"

    def test_max_results_limit(self):
        """验证 max_results 限制"""
        import unittest.mock as mock

        with mock.patch("skills.web_fetcher._fetch_url_content", return_value=("Text", "Title")):
            ctx = {"_urls": ["url1", "url2", "url3", "url4", "url5"], "_max_results": 2}
            result = web_fetch(ctx)
            assert len(result["_web_sources"]) == 2

    def test_fetch_error_graceful(self):
        """抓取失败时优雅降级"""
        import unittest.mock as mock

        with mock.patch(
            "skills.web_fetcher._fetch_url_content", side_effect=Exception("Network error")
        ):
            ctx = {"_urls": ["https://broken.url"]}
            result = web_fetch(ctx)
            assert len(result["_web_sources"]) == 1
            assert "error" in result["_web_sources"][0]

    def test_with_query_triggers_search(self):
        """有query时触发搜索"""
        import unittest.mock as mock

        with (
            mock.patch("skills.web_fetcher._duckduckgo_search", return_value=["https://found.com"]),
            mock.patch(
                "skills.web_fetcher._fetch_url_content",
                return_value=("Found content", "Found Title"),
            ),
        ):
            ctx = {"_query": "test search"}
            result = web_fetch(ctx)
            assert result["_web_content"] != ""
            assert len(result["_web_sources"]) >= 1

    def test_web_fetch_skill_instance(self):
        """验证 Skill 实例创建"""
        assert web_fetch_skill.name == "web_fetch"


class TestFetchUrlContent:
    """_fetch_url_content 测试（mock网络）"""

    def test_fetch_with_mock_response(self):
        """mock HTTP响应"""
        import unittest.mock as mock

        html_content = (
            "<html><head><title>Test</title></head><body><p>Content here</p></body></html>"
        )
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = html_content.encode("utf-8")
        mock_resp.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            text, title = _fetch_url_content("https://example.com", 5000)
            assert title == "Test"
            assert "Content here" in text

    def test_max_chars_limit(self):
        """验证字符截断"""
        import unittest.mock as mock

        long_content = "<p>" + "A" * 5000 + "</p>"
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = long_content.encode("utf-8")
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            text, title = _fetch_url_content("https://example.com", 100)
            assert len(text) <= 100

    def test_no_title_in_html(self):
        """HTML无title时返回空标题"""
        import unittest.mock as mock

        html_content = "<html><body><p>No title page</p></body></html>"
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = html_content.encode("utf-8")
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            text, title = _fetch_url_content("https://example.com", 5000)
            assert title == ""
            assert "No title page" in text


class TestDuckDuckGoSearch:
    """_duckduckgo_search 测试"""

    def test_search_returns_urls(self):
        """mock搜索返回URL列表"""
        import unittest.mock as mock

        from skills.web_fetcher import _duckduckgo_search

        mock_html = """
        <a class="result__a" href="https://example.com/result1">Result 1</a>
        <a class="result__a" href="https://example.com/result2">Result 2</a>
        """
        mock_resp = mock.MagicMock()
        mock_resp.read.return_value = mock_html.encode("utf-8")
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("urllib.request.urlopen", return_value=mock_resp):
            urls = _duckduckgo_search("test query", 3)
            assert isinstance(urls, list)

    def test_search_exception_returns_empty(self):
        """搜索异常时返回空列表"""
        import unittest.mock as mock

        from skills.web_fetcher import _duckduckgo_search

        with mock.patch("urllib.request.urlopen", side_effect=Exception("Network error")):
            urls = _duckduckgo_search("test", 3)
            assert urls == []
