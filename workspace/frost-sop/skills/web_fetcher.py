"""
FROST-SOP Web Fetch Skill
为LLM提供真实网页内容，解决无真实信息源导致的主题偏移问题。
只用Python标准库，无第三方依赖。
"""

import re
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

from core.skill import Skill


class _TextExtractor(HTMLParser):
    """从HTML中提取纯文本的简易解析器。"""

    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.skip_tags = {"script", "style", "nav", "footer", "header", "aside"}
        self.current_skip = None

    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self.current_skip = tag

    def handle_endtag(self, tag):
        if tag == self.current_skip:
            self.current_skip = None

    def handle_data(self, data):
        if self.current_skip is None:
            text = data.strip()
            if text:
                self.text_parts.append(text)

    def get_text(self) -> str:
        return "\n".join(self.text_parts)


def web_fetch(context: dict) -> dict:
    """
    获取指定URL的网页内容，提取纯文本返回。
    如果提供query，先通过DuckDuckGo搜索获取相关URL列表，再抓取内容。

    输入 context 键：
        _urls: list（可选）—— 要抓取的URL列表
        _query: str（可选）—— 搜索关键词，自动获取URL列表
        _max_results: int（可选）—— 最多返回几个结果，默认3
        _max_chars_per_url: int（可选）—— 每个URL最多返回多少字符，默认3000

    输出 context 键：
        _web_content: str —— 抓取到的网页内容（纯文本，已合并）
        _web_sources: list —— 来源列表 [{"url": ..., "title": ..., "chars": ...}, ...]
        _reason: str —— 执行痕迹
    """

    urls = context.get("_urls", [])
    query = context.get("_query", "")
    max_results = context.get("_max_results", 3)
    max_chars = context.get("_max_chars_per_url", 3000)

    sources = []
    all_text = ""

    # 如果没有提供URL但有query，先搜索获取URL列表
    if not urls and query:
        search_urls = _duckduckgo_search(query, max_results)
        urls = search_urls

    if not urls:
        context["_web_content"] = ""
        context["_web_sources"] = []
        context["_reason"] = "未提供URL且无搜索结果"
        return context

    for url in urls[:max_results]:
        try:
            text, title = _fetch_url_content(url, max_chars)
            if text:
                sources.append(
                    {
                        "url": url,
                        "title": title,
                        "chars": len(text),
                    }
                )
                all_text += f"\n\n---\n来源: {title}\nURL: {url}\n\n{text}\n"
        except Exception as e:
            sources.append(
                {
                    "url": url,
                    "title": "抓取失败",
                    "chars": 0,
                    "error": str(e),
                }
            )

    context["_web_content"] = all_text.strip()
    context["_web_sources"] = sources
    context["_reason"] = f"抓取了 {len(sources)} 个来源，共 {len(all_text)} 字符"
    return context


def _duckduckgo_search(query: str, max_results: int) -> list:
    """
    使用DuckDuckGo HTML搜索获取URL列表。
    无需API密钥。
    """
    try:
        search_url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(
            search_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # 简易解析：提取搜索结果链接
        urls = []
        # DuckDuckGo HTML搜索结果链接在 class="result__a" 的 <a> 标签中
        # 格式: <a class="result__a" href="...">
        pattern = r'<a class="result__a"[^>]+href="([^"]+)"'
        matches = re.findall(pattern, html)
        for match in matches[:max_results]:
            # DuckDuckGo使用重定向URL，需要解码
            if match.startswith("//duckduckgo.com/l/?"):
                # 解码重定向URL
                parsed = urllib.parse.urlparse(match)
                params = urllib.parse.parse_qs(parsed.query)
                if "uddg" in params:
                    urls.append(params["uddg"][0])
            else:
                if match.startswith("http"):
                    urls.append(match)
        return urls
    except Exception:
        return []


def _fetch_url_content(url: str, max_chars: int) -> tuple:
    """
    获取单个URL的内容，提取纯文本。
    返回 (text, title)。
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        content = resp.read()
        # 尝试检测编码
        encoding = "utf-8"
        if hasattr(resp, "headers"):
            ct = resp.headers.get("Content-Type", "")
            if "charset=" in ct:
                enc = ct.split("charset=")[-1].strip()
                if enc:
                    encoding = enc

        html = content.decode(encoding, errors="ignore")

    # 提取标题
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    title = title_match.group(1).strip() if title_match else ""
    title = re.sub(r"\s+", " ", title)

    # 使用HTMLParser提取文本
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        pass
    text = parser.get_text()

    # 清理多余空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text[:max_chars]

    return text, title


# 导出为Skill实例
web_fetch_skill = Skill("web_fetch", web_fetch)
