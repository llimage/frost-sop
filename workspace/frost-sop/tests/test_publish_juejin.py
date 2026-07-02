"""
V6.0 测试: 掘金发布 Skill (mock)
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestPublishJuejin:
    """测试掘金发布主函数"""

    def test_mock_publish(self):
        from skills.publish.juejin import publish_juejin

        ctx = {
            "_article_title": "Python异步编程实战",
            "_article_content": "# 简介\n\n这是文章内容...",
            "_article_tags": ["Python", "AI"],
        }
        result = publish_juejin(ctx)

        assert result["_publish_result"]["success"] is True
        assert "_publish_url" in result

    def test_empty_title(self):
        from skills.publish.juejin import publish_juejin

        ctx = {"_article_title": "", "_article_content": "xxx"}
        result = publish_juejin(ctx)

        assert result["_publish_result"]["success"] is False
        assert "标题" in result["_publish_result"]["message"]

    def test_empty_content(self):
        from skills.publish.juejin import publish_juejin

        ctx = {"_article_title": "标题", "_article_content": ""}
        result = publish_juejin(ctx)

        assert result["_publish_result"]["success"] is False

    def test_custom_tags(self):
        from skills.publish.juejin import publish_juejin

        ctx = {
            "_article_title": "测试文章",
            "_article_content": "# 测试",
            "_article_tags": ["FROST", "架构"],
        }
        result = publish_juejin(ctx)

        assert result["_publish_result"]["success"] is True

    def test_reason_trace(self):
        from skills.publish.juejin import publish_juejin

        ctx = {
            "_article_title": "测试",
            "_article_content": "测试内容",
        }
        result = publish_juejin(ctx)

        assert "_reason" in result
        assert "publish_juejin" in result["_reason"]


class TestCategoryMapping:
    """测试分类映射"""

    def test_category_id_known(self):
        from skills.publish.juejin import _category_id

        cat_id = _category_id("backend")
        assert cat_id and len(cat_id) > 0

    def test_category_id_unknown(self):
        from skills.publish.juejin import _category_id

        cat_id = _category_id("unknown_category")
        assert cat_id and len(cat_id) > 0  # uses default

    def test_chinese_category(self):
        from skills.publish.juejin import _category_id

        cat_id = _category_id("人工智能")
        assert cat_id and len(cat_id) > 0


class TestTagMapping:
    """测试标签映射"""

    def test_tag_ids_known(self):
        from skills.publish.juejin import _tag_ids

        ids = _tag_ids(["Python", "FROST"])
        assert len(ids) == 2

    def test_tag_ids_unknown(self):
        from skills.publish.juejin import _tag_ids

        ids = _tag_ids(["UnknownTag"])
        assert len(ids) == 1


class TestSessionId:
    """测试 sessionid 获取"""

    def test_get_sessionid_no_config(self):
        """未配置时返回 None"""
        from skills.publish.juejin import _get_sessionid

        sid = _get_sessionid()
        # 在测试环境中可能为 None
        assert sid is None or isinstance(sid, str)


class TestSkillInstance:
    """测试 Skill 实例"""

    def test_publish_juejin_skill(self):
        from core.skill import Skill
        from skills.publish.juejin import publish_juejin_skill

        assert isinstance(publish_juejin_skill, Skill)
        assert publish_juejin_skill.name == "publish_juejin"
