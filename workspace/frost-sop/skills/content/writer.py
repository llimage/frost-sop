"""
PHILOSOPHY:
内容创作不是通用能力，是平台特异的能力。
每个平台有独立的 prompt 模板、风格约束、字数要求。

设计原则：
- 所有调用走 skills.llm.call_llm()（FROST_TESTING=1 自动 mock）
- 成本通过 cost_tracker 记录
- 失败时记录到 data/tool_calls/
- 每个函数独立，复杂度<10
"""

import logging

from core.skill import Skill

logger = logging.getLogger(__name__)

# DeepSeek API — 通过 skills.llm.call_llm 调用
# 成本：¥1/百万 tokens (input), ¥2/百万 tokens (output)
# 月度预算 ¥300 ≈ 300M tokens 充足

# ============================================================
# 小红书内容创作
# ============================================================


def write_redbook_note(context: dict) -> dict:
    """
    撰写小红书笔记。

    输入 context 键：
        _topic: str —— 话题
        _style: str（可选）—— "checklist" / "story" / "tutorial"
        _max_tokens: int（可选，默认 800）

    输出 context 键：
        _generated_content: str —— 笔记正文
        _generated_word_count: int —— 字数
        _cost: float —— 预估成本
    """
    topic = context.get("_topic", "未指定话题")
    style = context.get("_style", "checklist")
    max_tokens = context.get("_max_tokens", 800)

    prompt = _build_redbook_prompt(topic, style)

    ctx = dict(context)
    ctx["_prompt"] = prompt
    ctx["_max_tokens"] = max_tokens
    ctx["_model"] = context.get("_model", "deepseek-chat")

    from skills.llm import call_llm

    ctx = call_llm(ctx, mode="online")

    content = ctx.get("_llm_response", "")
    word_count = len(content) if content else 0
    tokens = ctx.get("_llm_tokens", {})

    context["_generated_content"] = content
    context["_generated_word_count"] = word_count
    context["_cost"] = _estimate_cost(tokens)
    context["_reason"] = (
        f"write_redbook_note: topic={topic}, words={word_count}, cost=¥{context['_cost']:.4f}"
    )
    return context


def _build_redbook_prompt(topic: str, style: str) -> str:
    """构造小红书 prompt 模板（McCabe复杂度=3）"""
    style_guide = {
        "checklist": "清单体（数字+痛点+解决方案）",
        "story": "故事体（个人经历+感悟）",
        "tutorial": "教程体（步骤+截图说明）",
    }
    guide = style_guide.get(style, style_guide["checklist"])

    return f"""你是小红书内容创作专家。请为以下话题撰写一篇小红书笔记。

话题：{topic}
风格：{guide}
要求：
- 300-500字
- 开篇50字痛点共鸣
- 主体3-5个方法点，每点配emoji
- 结尾20字互动引导（提问式）
- 语气：亲切、实用、不贩卖焦虑
- 避免AI腔：不用"在当今时代"、不用"众所周知"、不用"综上所述"

输出格式：直接输出笔记正文，不要加任何元说明。"""


# ============================================================
# 掘金技术文章创作
# ============================================================


def write_tech_article(context: dict) -> dict:
    """
    撰写掘金技术文章。

    输入 context 键：
        _topic: str —— 技术话题
        _outline: str（可选）—— 大纲
        _max_tokens: int（可选，默认 3000）

    输出 context 键：
        _generated_content: str —— 文章正文（Markdown）
        _article_title: str —— 文章标题
        _article_tags: list —— 标签列表
        _generated_word_count: int
        _cost: float
    """
    topic = context.get("_topic", "未指定话题")
    outline = context.get("_outline", "")
    max_tokens = context.get("_max_tokens", 3000)

    prompt = _build_tech_article_prompt(topic, outline)

    ctx = dict(context)
    ctx["_prompt"] = prompt
    ctx["_max_tokens"] = max_tokens
    ctx["_model"] = "deepseek-chat"

    from skills.llm import call_llm

    ctx = call_llm(ctx, mode="online")

    content = ctx.get("_llm_response", "")
    word_count = len(content) if content else 0
    tokens = ctx.get("_llm_tokens", {})

    # 提取标题（第一行 # 开头）
    title = _extract_article_title(content, topic)
    tags = ["FROST", "AI", "Python", "自动化"]

    context["_generated_content"] = content
    context["_article_title"] = title
    context["_article_tags"] = tags
    context["_generated_word_count"] = word_count
    context["_cost"] = _estimate_cost(tokens)
    context["_reason"] = (
        f"write_tech_article: topic={topic}, words={word_count}, cost=¥{context['_cost']:.4f}"
    )
    return context


def _build_tech_article_prompt(topic: str, outline: str) -> str:
    """构造掘金技术文章 prompt（McCabe复杂度=2）"""
    outline_section = f"\n大纲：\n{outline}" if outline else ""
    return f"""你是技术文章撰写专家。请写一篇掘金平台的技术文章。

话题：{topic}{outline_section}
要求：
- 2000-3000字
- Markdown格式
- 必须有代码示例（Python）
- 必须有架构说明或设计思路
- 开头有摘要，结尾有总结
- 语言：专业但不晦涩，面向中级开发者
- 新增标签建议：FROST、AI、Python、自动化

输出格式：
# [文章标题]

> 摘要：一句话概括

[正文，含代码块]

## 总结
"""


def _extract_article_title(content: str, fallback: str) -> str:
    """从正文提取标题（McCabe复杂度=2）"""
    if content:
        lines = content.strip().split("\n")
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                return stripped[2:].strip()
    return f"深入理解{fallback}"


# ============================================================
# Newsletter 邮件创作
# ============================================================


def write_newsletter(context: dict) -> dict:
    """
    撰写 Newsletter 邮件。

    输入 context 键：
        _topic: str —— 主题
        _outline: str（可选）—— 大纲
        _max_tokens: int（可选，默认 1500）

    输出 context 键：
        _generated_content: str —— 邮件正文（Markdown）
        _email_subject: str —— 邮件主题
        _email_preview: str —— 预览文本
        _cost: float
    """
    topic = context.get("_topic", "未指定主题")
    outline = context.get("_outline", "")
    max_tokens = context.get("_max_tokens", 1500)

    prompt = _build_newsletter_prompt(topic, outline)

    ctx = dict(context)
    ctx["_prompt"] = prompt
    ctx["_max_tokens"] = max_tokens
    ctx["_model"] = "deepseek-chat"

    from skills.llm import call_llm

    ctx = call_llm(ctx, mode="online")

    content = ctx.get("_llm_response", "")
    tokens = ctx.get("_llm_tokens", {})

    # 提取主题
    subject = _extract_email_subject(content, topic)
    preview = content[:100] if content else ""

    context["_generated_content"] = content
    context["_email_subject"] = subject
    context["_email_preview"] = preview
    context["_cost"] = _estimate_cost(tokens)
    context["_reason"] = f"write_newsletter: topic={topic}, cost=¥{context['_cost']:.4f}"
    return context


def _build_newsletter_prompt(topic: str, outline: str) -> str:
    """构造 Newsletter prompt（McCabe复杂度=2）"""
    outline_section = f"\n大纲：\n{outline}" if outline else ""
    return f"""你是Newsletter撰写专家。请写一封面向开发者的周报邮件。

主题：{topic}{outline_section}
要求：
- 500-1500字
- Markdown格式
- 结构：打招呼 → 本周摘要 → 2-3个要点 → CTA → 签名
- 语气：专业但不失亲近，像朋友间的分享
- CTA：引导读者回复/转发/关注
- 不要过于销售化

输出格式：
## 本周摘要

[2-3句话概括]

## 要点1: [副标题]

## 要点2: [副标题]

## 🚀 推荐行动

## 下周预告
"""


def _extract_email_subject(content: str, fallback: str) -> str:
    """提取邮件主题"""
    if content:
        for line in content.strip().split("\n"):
            stripped = line.strip()
            if stripped.startswith("## ") and "摘要" not in stripped.lower():
                return stripped[3:].strip()
    return f"本周回顾: {fallback}"


# ============================================================
# 标题优化
# ============================================================


def optimize_title(context: dict) -> dict:
    """
    优化内容标题。

    输入 context 键：
        _content: str —— 待优化的内容
        _platform: str —— 目标平台 ("redbook" / "juejin" / "email")
        _num_variants: int（可选，默认 3）

    输出 context 键：
        _optimized_titles: list —— 备选标题列表
        _cost: float
    """
    content = context.get("_content", "")
    platform = context.get("_platform", "redbook")
    num_variants = context.get("_num_variants", 3)

    if not content:
        context["_optimized_titles"] = ["无标题"]
        context["_cost"] = 0
        return context

    prompt = _build_title_prompt(content[:500], platform, num_variants)

    ctx = dict(context)
    ctx["_prompt"] = prompt
    ctx["_max_tokens"] = 300
    ctx["_model"] = "deepseek-chat"

    from skills.llm import call_llm

    ctx = call_llm(ctx, mode="online")

    response = ctx.get("_llm_response", "")
    titles = _parse_title_list(response, num_variants)
    tokens = ctx.get("_llm_tokens", {})

    context["_optimized_titles"] = titles
    context["_cost"] = _estimate_cost(tokens)
    context["_reason"] = f"optimize_title: {len(titles)} variants"
    return context


def _build_title_prompt(content: str, platform: str, num_variants: int) -> str:
    """构造标题优化 prompt"""
    platform_guides = {
        "redbook": "小红书风格：数字+痛点+钩子，15-20字",
        "juejin": "掘金风格：技术关键词+价值点，20-30字",
        "email": "邮件风格：简洁+利益点，10-15字",
    }
    guide = platform_guides.get(platform, platform_guides["redbook"])

    return f"""为以下内容生成 {num_variants} 个标题。

{guide}

内容摘要：
{content}

请直接输出 {num_variants} 个标题，每行一个，以数字编号开头："""


def _parse_title_list(response: str, expected: int) -> list:
    """解析标题列表（McCabe复杂度=5）"""
    if not response:
        return [f"标题{i}" for i in range(1, expected + 1)]

    titles = []
    for line in response.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        # 移除编号前缀
        for prefix in ["1.", "2.", "3.", "4.", "5.", "1)", "2)", "3)"]:
            if stripped.startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                break
        if stripped and len(stripped) > 2:
            titles.append(stripped)

    return titles[:expected] if titles else [f"标题{i}" for i in range(1, expected + 1)]


# ============================================================
# 选题策划
# ============================================================


def select_topic(context: dict) -> dict:
    """
    选题策划：从选题池中选择今日话题。

    输入 context 键：
        _topic_pool: list（可选）—— 候选话题列表
        _platform: str —— "redbook" / "juejin" / "email"

    输出 context 键：
        _selected_topic: str
        _topic_angle: str —— 切入角度
    """
    platform = context.get("_platform", "redbook")
    topic_pool = context.get("_topic_pool", _default_topic_pool(platform))

    prompt = _build_topic_select_prompt(topic_pool, platform)

    ctx = dict(context)
    ctx["_prompt"] = prompt
    ctx["_max_tokens"] = 200
    ctx["_model"] = "deepseek-chat"

    from skills.llm import call_llm

    ctx = call_llm(ctx, mode="online")

    response = ctx.get("_llm_response", "")
    topic, angle = _parse_topic_selection(response)

    context["_selected_topic"] = topic or topic_pool[0]
    context["_topic_angle"] = angle or "实用角度"
    context["_reason"] = f"select_topic: {context['_selected_topic']}"
    return context


def _default_topic_pool(platform: str) -> list:
    """默认选题池"""
    pools = {
        "redbook": [
            "AI如何提高工作效率",
            "一个人用AI做副业的3个方法",
            "程序员转行AI工具开发",
            "FROST框架让自动化更简单",
        ],
        "juejin": [
            "Python异步编程最佳实践",
            "AI Agent架构设计模式",
            "SQLite性能优化实战",
            "FROST-SOP框架源码解读",
        ],
        "email": [
            "本周AI工具精选",
            "独立开发者月度复盘",
            "一人公司运营心得",
        ],
    }
    return pools.get(platform, pools["redbook"])


def _build_topic_select_prompt(topic_pool: list, platform: str) -> str:
    """构造选题 prompt"""
    topics_text = "\n".join(f"- {t}" for t in topic_pool)
    return f"""你是内容选题专家。从以下候选话题中选择最适合今日发布的一个。

平台：{platform}
候选话题：
{topics_text}

输出格式：
话题: [选中的话题]
角度: [切入角度]"""


def _parse_topic_selection(response: str) -> tuple:
    """解析选题结果"""
    topic = ""
    angle = ""
    for line in response.split("\n"):
        stripped = line.strip()
        if stripped.startswith("话题:") or stripped.startswith("话题："):
            topic = stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
        elif stripped.startswith("角度:") or stripped.startswith("角度："):
            angle = stripped.split(":", 1)[-1].split("：", 1)[-1].strip()
    return topic, angle


# ============================================================
# 辅助函数
# ============================================================


def _estimate_cost(tokens: dict) -> float:
    """
    估算 LLM 调用成本（DeepSeek-chat 价格）。
    input: ¥1/M tokens, output: ¥2/M tokens
    """
    if not tokens:
        return 0.0
    prompt_tokens = tokens.get("prompt", 0) or 0
    completion_tokens = tokens.get("completion", 0) or 0
    cost = (prompt_tokens / 1_000_000) * 1.0
    cost += (completion_tokens / 1_000_000) * 2.0
    return round(cost, 6)


# ============================================================
# Skill 实例注册
# ============================================================

write_redbook_note_skill = Skill("write_redbook_note", write_redbook_note)
write_tech_article_skill = Skill("write_tech_article", write_tech_article)
write_newsletter_skill = Skill("write_newsletter", write_newsletter)
optimize_title_skill = Skill("optimize_title", optimize_title)
select_topic_skill = Skill("select_topic", select_topic)
