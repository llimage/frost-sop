"""
PHILOSOPHY:
掘金发布是 FROST 运营能力的关键一环。
不依赖浏览器，使用 sessionid/cookie 模拟 API 调用。

安全原则：
- cookie 必须走 core/secrets.py 加密存储
- 不硬编码凭据
- 失败不暴露 cookie
- 默认 draft 模式，人工确认后发布
"""

import logging
import os

from core.skill import Skill

logger = logging.getLogger(__name__)


def publish_juejin(context: dict) -> dict:
    """
    发布文章到掘金平台（draft 模式）。

    输入 context 键：
        _article_title: str —— 文章标题
        _article_content: str —— 文章正文（Markdown）
        _article_tags: list（可选）—— 标签
        _article_category: str（可选）—— 分类 ID

    输出 context 键：
        _publish_result: dict —— {success, draft_id, message}
        _publish_url: str —— 文章链接（如有）
    """
    title = context.get("_article_title", "")
    content = context.get("_article_content", "")
    tags = context.get("_article_tags", ["FROST", "AI"])
    category = context.get("_article_category", "backend")

    if not title or not content:
        context["_publish_result"] = {
            "success": False,
            "message": "标题或内容为空",
        }
        context["_reason"] = "publish_juejin: 缺少标题或内容"
        return context

    # 检查测试模式
    if os.getenv("FROST_TESTING") == "1":
        context["_publish_result"] = {
            "success": True,
            "draft_id": "mock_draft_12345",
            "message": "[TEST] draft 已创建",
        }
        context["_publish_url"] = "https://juejin.cn/post/mock_12345"
        context["_reason"] = "[TEST] publish_juejin: mock draft 已创建"
        return context

    # 从 secrets 获取 cookie
    sessionid = _get_sessionid()
    if not sessionid:
        context["_publish_result"] = {
            "success": False,
            "message": "未配置掘金 sessionid（需要存入 secrets）",
        }
        context["_reason"] = "publish_juejin: 缺少 sessionid"
        return context

    # 发布草稿
    result = _create_juejin_draft(title, content, tags, category, sessionid)

    context["_publish_result"] = result
    context["_publish_url"] = result.get("url", "")
    context["_reason"] = (
        f"publish_juejin: {'成功' if result.get('success') else '失败'} "
        f"- {result.get('message', '')}"
    )
    return context


def _get_sessionid() -> str | None:
    """安全获取掘金 sessionid"""
    try:
        from core.secrets import get_decrypted_key

        return get_decrypted_key("JUEJIN_SESSIONID", prompt_if_missing=False)
    except Exception as e:
        logger.warning("[publish_juejin] 获取 sessionid 失败: %s", e)
        return None


def _create_juejin_draft(
    title: str,
    content: str,
    tags: list,
    category: str,
    sessionid: str,
) -> dict:
    """调用掘金 API 创建草稿（McCabe复杂度<10）"""
    import requests

    headers = {
        "Cookie": f"sessionid={sessionid}",
        "Content-Type": "application/json",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
    }

    # 掘金创作平台 API（draft 创建）
    # 注意：此 API 可能随掘金更新而变化
    api_url = "https://api.juejin.cn/content_api/v1/article_draft/create"

    payload = {
        "category_id": _category_id(category),
        "tag_ids": _tag_ids(tags),
        "title": title,
        "brief_content": content[:200],
        "mark_content": content,
        "edit_type": 10,  # Markdown 编辑器
    }

    try:
        resp = requests.post(
            api_url,
            headers=headers,
            json=payload,
            timeout=30,
        )
        data = resp.json()

        if data.get("err_no") == 0:
            draft_id = data.get("data", {}).get("id", "")
            return {
                "success": True,
                "draft_id": draft_id,
                "message": "draft 已创建，请在掘金后台确认发布",
                "url": f"https://juejin.cn/editor/drafts/{draft_id}",
            }
        else:
            err_msg = data.get("err_msg", "未知错误")
            logger.warning(
                "[publish_juejin] API 返回错误: err_no=%s, err_msg=%s",
                data.get("err_no"),
                err_msg,
            )
            return {
                "success": False,
                "message": f"掘金 API 错误: {err_msg}",
            }

    except requests.exceptions.Timeout:
        logger.warning("[publish_juejin] API 请求超时")
        return {"success": False, "message": "请求掘金 API 超时"}
    except requests.exceptions.ConnectionError:
        logger.warning("[publish_juejin] API 连接失败")
        return {"success": False, "message": "无法连接掘金 API"}
    except Exception as e:
        logger.warning("[publish_juejin] API 调用异常: %s", e)
        return {"success": False, "message": f"发布异常: {type(e).__name__}"}


def _category_id(category: str) -> str:
    """掘金分类映射"""
    mapping = {
        "backend": "6809637767543259144",
        "frontend": "6809637767543259143",
        "android": "6809635626879549454",
        "ios": "6809635626661445640",
        "ai": "6809637769959178254",
        "freebie": "6809637771511070734",
        "article": "6809637772874219534",
        "career": "6809637770178035719",
        "人工智能": "6809637769959178254",
    }
    return mapping.get(category, mapping["article"])


def _tag_ids(tags: list) -> list:
    """标签映射（常用标签）"""
    mapping = {
        "FROST": "6809640408794333198",
        "AI": "6809640408794333198",
        "Python": "6809640445009133576",
        "自动化": "6809640408794333198",
        "架构": "6809640442579320840",
        "开源": "6809640424289337357",
    }
    return [mapping.get(t, mapping["Python"]) for t in tags]


# Skill 实例
publish_juejin_skill = Skill("publish_juejin", publish_juejin)
