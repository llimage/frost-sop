"""
PHILOSOPHY:
邮件发送是运营闭环的最后一步。
使用 Buttondown API（Markdown 友好，免费层 1000 订阅者）。

安全原则：
- API key 走 core/secrets.py 加密存储
- 默认 draft 模式，人工确认后发送
- 失败日志不暴露 API key
"""

import logging
import os

from core.skill import Skill

logger = logging.getLogger(__name__)


def send_email(context: dict) -> dict:
    """
    发送 Newsletter 邮件（draft 模式）。

    输入 context 键：
        _email_subject: str —— 邮件主题
        _email_body: str —— 邮件正文（Markdown）
        _email_preview: str（可选）—— 预览文本

    输出 context 键：
        _send_result: dict —— {success, draft_id, message}
    """
    subject = context.get("_email_subject", "")
    body = context.get("_email_body", "")
    preview = context.get("_email_preview", "")

    if not subject or not body:
        context["_send_result"] = {
            "success": False,
            "message": "邮件主题或正文为空",
        }
        context["_reason"] = "send_email: 缺少主题或正文"
        return context

    # 检查测试模式
    if os.getenv("FROST_TESTING") == "1":
        context["_send_result"] = {
            "success": True,
            "draft_id": "mock_draft_67890",
            "message": "[TEST] draft 邮件已创建",
        }
        context["_reason"] = "[TEST] send_email: mock draft 已创建"
        return context

    # 获取 API key
    api_key = _get_api_key()
    if not api_key:
        context["_send_result"] = {
            "success": False,
            "message": "未配置 Buttondown API key（需要存入 secrets）",
        }
        context["_reason"] = "send_email: 缺少 API key"
        return context

    # 创建 draft 邮件
    result = _create_buttondown_draft(subject, body, preview, api_key)

    context["_send_result"] = result
    context["_reason"] = (
        f"send_email: {'成功' if result.get('success') else '失败'} - {result.get('message', '')}"
    )
    return context


def _get_api_key() -> str | None:
    """安全获取 Buttondown API key"""
    try:
        from core.secrets import get_decrypted_key

        return get_decrypted_key("BUTTONDOWN_API_KEY", prompt_if_missing=False)
    except Exception as e:
        logger.warning("[publish_email] 获取 API key 失败: %s", e)
        return None


def _create_buttondown_draft(
    subject: str,
    body: str,
    preview: str,
    api_key: str,
) -> dict:
    """通过 Buttondown API 创建 draft 邮件"""
    import requests

    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "subject": subject,
        "body": body,
        "status": "draft",  # 先创建 draft，人工确认后发送
    }

    if preview:
        payload["excerpt"] = preview[:200]

    try:
        resp = requests.post(
            "https://api.buttondown.com/v1/emails",
            headers=headers,
            json=payload,
            timeout=30,
        )
        data = resp.json()

        if resp.status_code in (200, 201):
            draft_id = data.get("id", "")
            return {
                "success": True,
                "draft_id": draft_id,
                "message": "draft 邮件已创建，请在 Buttondown 后台确认发送",
                "url": f"https://buttondown.com/emails/{draft_id}",
            }
        else:
            err_msg = data.get("detail", str(data)) if isinstance(data, dict) else str(data)
            logger.warning(
                "[publish_email] API 错误: status=%s, msg=%s",
                resp.status_code,
                err_msg[:200],
            )
            return {
                "success": False,
                "message": f"Buttondown API 错误({resp.status_code}): {err_msg[:100]}",
            }

    except requests.exceptions.Timeout:
        logger.warning("[publish_email] API 请求超时")
        return {"success": False, "message": "请求 Buttondown API 超时"}
    except requests.exceptions.ConnectionError:
        logger.warning("[publish_email] API 连接失败")
        return {"success": False, "message": "无法连接 Buttondown API"}
    except Exception as e:
        logger.warning("[publish_email] API 调用异常: %s", e)
        return {"success": False, "message": f"发送异常: {type(e).__name__}"}


# Skill 实例
send_email_skill = Skill("send_email", send_email)
