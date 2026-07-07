"""
V6.0.1 测试: skills/intent.py 运营SOP识别
验证 P0-001 修复：意图解析器能识别 REDBOOK-001/JUEJIN-001/EMAIL-001
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestIntentV601:
    """意图解析器运营SOP识别测试"""

    def test_redbook_note_direct(self):
        """TC-001: '帮我写小红书笔记' -> sop_id=REDBOOK-001"""
        from skills.intent import parse_intent

        result = parse_intent("帮我写小红书笔记")
        assert result["sop_id"] == "REDBOOK-001"
        assert result["confidence"] > 0
        assert result["method"] == "keyword"

    def test_juejin_article_direct(self):
        """TC-002: '发一篇掘金技术文章' -> sop_id=JUEJIN-001"""
        from skills.intent import parse_intent

        result = parse_intent("发一篇掘金技术文章")
        assert result["sop_id"] == "JUEJIN-001"
        assert result["confidence"] > 0

    def test_newsletter_direct(self):
        """TC-003: '发送Newsletter' -> sop_id=EMAIL-001"""
        from skills.intent import parse_intent

        result = parse_intent("发送Newsletter")
        assert result["sop_id"] == "EMAIL-001"
        assert result["confidence"] > 0

    def test_xiaohongshu_keyword(self):
        """TC-004: '小红书运营' -> sop_id=REDBOOK-001"""
        from skills.intent import parse_intent

        result = parse_intent("小红书运营")
        assert result["sop_id"] == "REDBOOK-001"

    def test_juejin_keyword(self):
        """TC-005: '掘金技术文章' -> sop_id=JUEJIN-001"""
        from skills.intent import parse_intent

        result = parse_intent("掘金技术文章")
        assert result["sop_id"] == "JUEJIN-001"

    def test_newsletter_keyword(self):
        """TC-006: 'newsletter' -> sop_id=EMAIL-001"""
        from skills.intent import parse_intent

        result = parse_intent("newsletter")
        assert result["sop_id"] == "EMAIL-001"

    def test_old_sop_still_works(self):
        """TC-007: 旧SOP仍可用 - '开发新功能' -> sop_id=DEV-001"""
        from skills.intent import parse_intent

        result = parse_intent("开发新功能")
        assert result["sop_id"] == "DEV-001"
        assert result["confidence"] > 0

    def test_tech_article_ambiguous(self):
        """TC-008: '写一篇技术分享' -> 匹配到MT-001或JUEJIN-001"""
        from skills.intent import parse_intent

        result = parse_intent("写一篇技术分享")
        # "技术" 匹配 JUEJIN-001，"写一篇" 匹配 MT-001
        # 关键词重叠时按分数决定
        assert result["sop_id"] in ("MT-001", "JUEJIN-001")

    def test_no_match(self):
        """TC-009: '随便做点什么' -> sop_id=None"""
        from skills.intent import parse_intent

        result = parse_intent("随便做点什么")
        assert result["sop_id"] is None
        assert result["confidence"] == 0.3

    def test_list_all_includes_new_sops(self):
        """TC-010: list_all_sops() 包含10个SOP（7旧+3新）"""
        from skills.intent import list_all_sops

        sops = list_all_sops()
        sop_ids = [s["id"] for s in sops]
        assert len(sops) == 10
        assert "REDBOOK-001" in sop_ids
        assert "JUEJIN-001" in sop_ids
        assert "EMAIL-001" in sop_ids
        assert "DEV-001" in sop_ids  # 旧SOP仍存在
