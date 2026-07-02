"""
V6.0 测试: 邮件发送 Skill (mock)
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestSendEmail:
    """测试邮件发送"""

    def test_mock_send(self):
        from skills.publish.email import send_email

        ctx = {
            "_email_subject": "本周技术周报",
            "_email_body": "## 摘要\n\n这是本周的技术周报内容。",
        }
        result = send_email(ctx)

        assert result["_send_result"]["success"] is True
        assert "draft" in result["_send_result"]["message"].lower()

    def test_empty_subject(self):
        from skills.publish.email import send_email

        ctx = {"_email_subject": "", "_email_body": "xxx"}
        result = send_email(ctx)

        assert result["_send_result"]["success"] is False
        assert "主题" in result["_send_result"]["message"]

    def test_empty_body(self):
        from skills.publish.email import send_email

        ctx = {"_email_subject": "主题", "_email_body": ""}
        result = send_email(ctx)

        assert result["_send_result"]["success"] is False

    def test_with_preview(self):
        from skills.publish.email import send_email

        ctx = {
            "_email_subject": "周报",
            "_email_body": "内容",
            "_email_preview": "本周摘要预览",
        }
        result = send_email(ctx)

        assert result["_send_result"]["success"] is True

    def test_reason_trace(self):
        from skills.publish.email import send_email

        ctx = {
            "_email_subject": "测试",
            "_email_body": "测试内容",
        }
        result = send_email(ctx)

        assert "_reason" in result
        assert "send_email" in result["_reason"]


class TestApiKey:
    """测试 API key 获取"""

    def test_get_api_key_no_config(self):
        from skills.publish.email import _get_api_key

        key = _get_api_key()
        assert key is None or isinstance(key, str)


class TestSkillInstance:
    """测试 Skill 实例"""

    def test_send_email_skill(self):
        from core.skill import Skill
        from skills.publish.email import send_email_skill

        assert isinstance(send_email_skill, Skill)
        assert send_email_skill.name == "send_email"
