"""
V6.0 测试: content-writer Skill
测试 DeepSeek API 调用（mock 模式）
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestWriteRedbookNote:
    """测试小红书笔记创作"""

    def test_basic_write(self):
        from skills.content.writer import write_redbook_note

        ctx = {"_topic": "AI如何提高工作效率"}
        result = write_redbook_note(ctx)

        assert "_generated_content" in result
        assert "_generated_word_count" in result
        assert "_cost" in result
        assert "_reason" in result

    def test_with_custom_style(self):
        from skills.content.writer import write_redbook_note

        ctx = {"_topic": "学习Python", "_style": "story"}
        result = write_redbook_note(ctx)

        assert "_generated_content" in result

    def test_without_topic(self):
        from skills.content.writer import write_redbook_note

        ctx = {}
        result = write_redbook_note(ctx)

        assert "_generated_content" in result
        assert "未指定话题" in result.get("_reason", "")

    def test_prompt_template(self):
        from skills.content.writer import _build_redbook_prompt

        prompt = _build_redbook_prompt("测试话题", "checklist")
        assert "小红书内容创作专家" in prompt
        assert "测试话题" in prompt
        assert "300-500字" in prompt

    def test_all_styles(self):
        from skills.content.writer import _build_redbook_prompt

        for style in ["checklist", "story", "tutorial"]:
            prompt = _build_redbook_prompt("test", style)
            assert len(prompt) > 0


class TestWriteTechArticle:
    """测试掘金技术文章创作"""

    def test_basic_write(self):
        from skills.content.writer import write_tech_article

        ctx = {"_topic": "Python异步编程"}
        result = write_tech_article(ctx)

        assert "_generated_content" in result
        assert "_article_title" in result
        assert "_article_tags" in result

    def test_with_outline(self):
        from skills.content.writer import write_tech_article

        ctx = {
            "_topic": "SQLite性能优化",
            "_outline": "1. 索引 2. WAL模式 3. 查询优化",
        }
        result = write_tech_article(ctx)

        assert "_generated_content" in result

    def test_tags_present(self):
        from skills.content.writer import write_tech_article

        ctx = {"_topic": "测试话题"}
        result = write_tech_article(ctx)

        assert isinstance(result["_article_tags"], list)
        assert len(result["_article_tags"]) > 0

    def test_extract_title_from_content(self):
        from skills.content.writer import _extract_article_title

        content = "# 深入理解FROST框架\n\n正文..."
        title = _extract_article_title(content, "fallback")
        assert title == "深入理解FROST框架"

    def test_extract_title_fallback(self):
        from skills.content.writer import _extract_article_title

        title = _extract_article_title("", "fallback")
        assert "fallback" in title


class TestWriteNewsletter:
    """测试 Newsletter 邮件创作"""

    def test_basic_write(self):
        from skills.content.writer import write_newsletter

        ctx = {"_topic": "本周AI精选"}
        result = write_newsletter(ctx)

        assert "_generated_content" in result
        assert "_email_subject" in result
        assert "_email_preview" in result
        assert "_cost" in result

    def test_with_outline(self):
        from skills.content.writer import write_newsletter

        ctx = {
            "_topic": "技术周报",
            "_outline": "1. 新工具 2. 文章推荐 3. 本周心得",
        }
        result = write_newsletter(ctx)

        assert "_generated_content" in result


class TestOptimizeTitle:
    """测试标题优化"""

    def test_basic_optimize(self):
        from skills.content.writer import optimize_title

        ctx = {
            "_content": "这是一篇关于AI工具的小红书笔记内容...",
            "_platform": "redbook",
        }
        result = optimize_title(ctx)

        assert "_optimized_titles" in result
        assert "_cost" in result

    def test_juejin_platform(self):
        from skills.content.writer import optimize_title

        ctx = {
            "_content": "Python异步编程最佳实践...",
            "_platform": "juejin",
        }
        result = optimize_title(ctx)

        assert "_optimized_titles" in result

    def test_email_platform(self):
        from skills.content.writer import optimize_title

        ctx = {
            "_content": "本周技术周报...",
            "_platform": "email",
        }
        result = optimize_title(ctx)

        assert "_optimized_titles" in result

    def test_empty_content(self):
        from skills.content.writer import optimize_title

        ctx = {"_content": ""}
        result = optimize_title(ctx)

        assert result["_optimized_titles"] == ["无标题"]

    def test_custom_num_variants(self):
        from skills.content.writer import optimize_title

        ctx = {
            "_content": "测试内容",
            "_num_variants": 5,
        }
        result = optimize_title(ctx)

        assert isinstance(result["_optimized_titles"], list)

    def test_parse_title_list(self):
        from skills.content.writer import _parse_title_list

        response = "1. 标题A\n2. 标题B\n3. 标题C"
        titles = _parse_title_list(response, 3)
        assert len(titles) == 3

    def test_parse_empty(self):
        from skills.content.writer import _parse_title_list

        titles = _parse_title_list("", 3)
        assert len(titles) == 3


class TestSelectTopic:
    """测试选题策划"""

    def test_basic_select(self):
        from skills.content.writer import select_topic

        ctx = {"_platform": "redbook"}
        result = select_topic(ctx)

        assert "_selected_topic" in result
        assert "_topic_angle" in result
        assert "_reason" in result

    def test_all_platforms(self):
        from skills.content.writer import select_topic

        for platform in ["redbook", "juejin", "email"]:
            ctx = {"_platform": platform}
            result = select_topic(ctx)
            assert "_selected_topic" in result

    def test_with_topic_pool(self):
        from skills.content.writer import select_topic

        ctx = {
            "_platform": "redbook",
            "_topic_pool": ["自定义话题1", "自定义话题2"],
        }
        result = select_topic(ctx)

        assert "_selected_topic" in result

    def test_default_topic_pool(self):
        from skills.content.writer import _default_topic_pool

        pool = _default_topic_pool("redbook")
        assert isinstance(pool, list)
        assert len(pool) > 0


class TestCostEstimation:
    """测试成本估算"""

    def test_estimate_with_tokens(self):
        from skills.content.writer import _estimate_cost

        cost = _estimate_cost({"prompt": 1000, "completion": 500})
        # 1000/1M * 1 + 500/1M * 2 = 0.001 + 0.001 = 0.002
        assert cost > 0

    def test_estimate_empty(self):
        from skills.content.writer import _estimate_cost

        cost = _estimate_cost({})
        assert cost == 0.0

    def test_cost_zero_in_test_mode(self):
        """测试模式下 cost 应该接近0（mock tokens）"""
        from skills.content.writer import write_redbook_note

        ctx = {"_topic": "test"}
        result = write_redbook_note(ctx)

        # mock 模式下 token 数是估算的，cost 应该非常小
        assert result["_cost"] < 0.01


class TestSkillInstances:
    """测试 Skill 实例注册"""

    def test_write_redbook_note_skill(self):
        from core.skill import Skill
        from skills.content.writer import write_redbook_note_skill

        assert isinstance(write_redbook_note_skill, Skill)

    def test_write_tech_article_skill(self):
        from core.skill import Skill
        from skills.content.writer import write_tech_article_skill

        assert isinstance(write_tech_article_skill, Skill)

    def test_write_newsletter_skill(self):
        from core.skill import Skill
        from skills.content.writer import write_newsletter_skill

        assert isinstance(write_newsletter_skill, Skill)

    def test_optimize_title_skill(self):
        from core.skill import Skill
        from skills.content.writer import optimize_title_skill

        assert isinstance(optimize_title_skill, Skill)

    def test_select_topic_skill(self):
        from core.skill import Skill
        from skills.content.writer import select_topic_skill

        assert isinstance(select_topic_skill, Skill)
