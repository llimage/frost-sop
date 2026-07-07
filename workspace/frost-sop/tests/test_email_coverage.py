"""
V7 阶段3 覆盖率补测试 — skills/publish/email.py (37% → 80%+)
邮件发布技能
"""

import os
import sys

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.publish.email import send_email, send_email_skill


class TestSendEmail:
    """邮件发送测试"""

    def test_testing_mode_returns_mock(self):
        """FROST_TESTING=1 返回mock结果"""
        ctx = {"_email_subject": "测试邮件", "_email_body": "这是测试内容"}
        result = send_email(ctx)
        assert result["_send_result"]["success"] is True
        assert result["_send_result"]["draft_id"] == "mock_draft_67890"

    def test_empty_subject_fails(self):
        """空主题失败"""
        ctx = {"_email_subject": "", "_email_body": "内容"}
        result = send_email(ctx)
        assert result["_send_result"]["success"] is False
        assert (
            "主题" in result["_send_result"]["message"]
            or "为空" in result["_send_result"]["message"]
        )

    def test_empty_body_fails(self):
        """空正文失败"""
        ctx = {"_email_subject": "主题", "_email_body": ""}
        result = send_email(ctx)
        assert result["_send_result"]["success"] is False

    def test_both_empty_fails(self):
        """主题和正文都空"""
        ctx = {"_email_subject": "", "_email_body": ""}
        result = send_email(ctx)
        assert result["_send_result"]["success"] is False

    def test_with_preview_text(self):
        """带预览文本"""
        ctx = {
            "_email_subject": "周报",
            "_email_body": "本周工作总结",
            "_email_preview": "本周亮点",
        }
        result = send_email(ctx)
        assert result["_send_result"]["success"] is True

    def test_no_api_key_fails(self):
        """测试模式关闭时，无API key失败"""
        import unittest.mock as mock

        # 临时关闭测试模式
        old_testing = os.environ.get("FROST_TESTING")
        os.environ["FROST_TESTING"] = "0"

        with mock.patch("skills.publish.email._get_api_key", return_value=None):
            ctx = {"_email_subject": "测试", "_email_body": "内容"}
            result = send_email(ctx)
            assert result["_send_result"]["success"] is False
            assert "API key" in result["_send_result"]["message"]

        os.environ["FROST_TESTING"] = old_testing or "1"

    def test_skill_instance(self):
        assert send_email_skill.name == "send_email"
