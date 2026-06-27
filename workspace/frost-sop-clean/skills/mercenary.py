"""
FROST-SOP 雇佣兵工厂
PHILOSOPHY: 雇佣兵是有确定输入输出公式的Agent。
它只有一个Skill，只有一步SOP，不依赖LLM，不进入家族谱系。
"""

from core.agent import Agent
from core.store import Store
from core.skill import Skill


def create_mercenary(name: str, skill_func, skill_name: str = None) -> Agent:
    """
    创建一个雇佣兵Agent。
    
    Args:
        name: 雇佣兵名称
        skill_func: 确定性函数，签名 func(context: dict) -> dict
        skill_name: Skill名称，默认与name相同
    
    Returns:
        一个瞬态Agent实例，generation=99（不进入家族谱系）
    """
    s_name = skill_name or name
    skill = Skill(s_name, skill_func)
    return Agent(
        name=name,
        store=Store(),  # 瞬态Store
        skills={s_name: skill},
        sop_steps=[s_name],
        generation=99,  # 标记为雇佣兵，不进入家族谱系
        max_spawn_generation=0,  # 雇佣兵不能再spawn
    )


# ================================================================
# 预置雇佣兵Skill（确定性函数）
# ================================================================

def markdown_to_html(context: dict) -> dict:
    """
    Markdown转HTML（简化版）。
    支持：标题(#)、粗体(**)、斜体(*)、段落、换行。
    """
    import re
    text = context.get("_content", context.get("_task_description", ""))
    
    # 逐行处理
    lines = text.split("\n")
    html_lines = []
    in_paragraph = False
    
    for line in lines:
        line = line.strip()
        
        # 空行结束当前段落
        if not line:
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            continue
        
        # 标题
        if line.startswith("# "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append("<h1>{}</h1>".format(line[2:]))
        elif line.startswith("## "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append("<h2>{}</h2>".format(line[3:]))
        elif line.startswith("### "):
            if in_paragraph:
                html_lines.append("</p>")
                in_paragraph = False
            html_lines.append("<h3>{}</h3>".format(line[4:]))
        else:
            # 段落文本
            if not in_paragraph:
                html_lines.append("<p>")
                in_paragraph = True
            else:
                html_lines.append("<br>")
            # 行内格式：粗体和斜体
            line = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', line)
            line = re.sub(r'\*(.+?)\*', r'<em>\1</em>', line)
            html_lines.append(line)
    
    # 关闭最后的段落
    if in_paragraph:
        html_lines.append("</p>")
    
    result = "\n".join(html_lines)
    context["_result"] = result
    context["_reason"] = "雇佣兵(Markdown→HTML)执行完成"
    return context


def extract_keywords(context: dict) -> dict:
    """从文本中提取有意义的独立关键词"""
    text = context.get("_content", context.get("_task_description", ""))

    import re

    # 通用词（停用词）列表，这些词不会被提取为关键词
    stopwords = {
        "一个", "一种", "这个", "那个", "什么", "怎么", "如何", "为什么",
        "可以", "能够", "应该", "需要", "已经", "正在", "将", "会", "是",
        "的", "了", "在", "和", "与", "或", "但", "而", "且", "也", "都",
        "这", "那", "它", "他", "她", "我", "你", "我们", "你们", "他们",
        "有", "没有", "被", "把", "让", "对", "从", "到", "向", "用",
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would",
        "can", "could", "may", "might", "shall", "should", "must",
        "this", "that", "these", "those", "it", "its", "of", "in",
        "on", "at", "to", "for", "with", "by", "from", "as", "and",
        "or", "but", "not", "no", "so", "if", "then", "than", "too",
    }

    # 先按标点和空格分割
    segments = re.split(r'[，。！？；：、\s,!.?;:\-()（）\[\]【】《》"\']+', text)

    # 过滤出有意义的词
    keywords = []
    for seg in segments:
        seg = seg.strip()
        # 中文词：长度2-6个字符，包含中文，不是停用词
        if 2 <= len(seg) <= 6 and re.search(r'[\u4e00-\u9fa5]', seg):
            if seg not in stopwords:
                keywords.append(seg)
        # 英文词：长度3-20个字符，纯字母，不是停用词
        elif 3 <= len(seg) <= 20 and re.match(r'^[a-zA-Z]+$', seg):
            if seg.lower() not in stopwords:
                keywords.append(seg)

    # 如果分割后关键词太少，尝试进一步细分长段落
    if len(keywords) <= 2:
        # 方法1：按常见词边界进一步分割
        for seg in segments:
            seg = seg.strip()
            if len(seg) > 6:
                sub_segments = re.split(r'(和|与|及|之|是|的)', seg)
                for sub in sub_segments:
                    sub = sub.strip()
                    if 2 <= len(sub) <= 6 and re.search(r'[\u4e00-\u9fa5]', sub):
                        if sub not in stopwords and sub not in keywords:
                            keywords.append(sub)

        # 方法2：提取英文单词
        if len(keywords) <= 2:
            english_words = re.findall(r'[a-zA-Z]+', text)
            for word in english_words:
                if 3 <= len(word) <= 20 and word.lower() not in stopwords:
                    if word not in keywords:
                        keywords.append(word)

        # 方法3：提取中文词组（按非中文字符分割后取2-6字片段）
        if len(keywords) <= 2:
            chinese_segments = re.split(r'[^\u4e00-\u9fa5]+', text)
            for seg in chinese_segments:
                seg = seg.strip()
                if 2 <= len(seg) <= 6 and seg not in stopwords and seg not in keywords:
                    keywords.append(seg)
                elif len(seg) > 6:
                    # 尝试滑动窗口提取2-4字词组
                    for n in [2, 3, 4]:
                        for i in range(len(seg) - n + 1):
                            word = seg[i:i+n]
                            if word not in stopwords and word not in keywords:
                                keywords.append(word)

    # 去重，保留原始顺序
    seen = set()
    unique_keywords = []
    for kw in keywords:
        if kw.lower() not in seen:
            seen.add(kw.lower())
            unique_keywords.append(kw)

    context["_result"] = unique_keywords[:15]
    context["_reason"] = f"雇佣兵(关键词提取)执行完成，提取{len(context['_result'])}个关键词"
    return context


def format_date(context: dict) -> dict:
    """日期格式化"""
    from datetime import datetime
    date_str = context.get("_content", str(datetime.now()))
    
    try:
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00").split("+")[0])
        formatted = dt.strftime("%Y年%m月%d日 %H:%M")
    except (ValueError, AttributeError):
        formatted = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    
    context["_result"] = formatted
    context["_reason"] = "雇佣兵(日期格式化)执行完成"
    return context


# 预置雇佣兵实例（导出用）
mercenary_md2html = create_mercenary("Markdown转HTML", markdown_to_html, "md2html")
mercenary_keywords = create_mercenary("关键词提取", extract_keywords, "extract_keywords")
mercenary_date = create_mercenary("日期格式化", format_date, "format_date")


if __name__ == "__main__":
    # 简单测试
    print("=== 雇佣兵工厂测试 ===")
    
    # 测试Markdown转HTML
    ctx1 = {"_content": "# 标题\n这是**粗体**和*斜体*"}
    result1 = markdown_to_html(ctx1)
    print("Markdown→HTML:", result1["_result"][:100])
    
    # 测试关键词提取
    ctx2 = {"_content": "这是一段测试文本，包含一些关键词如FROST、AI、Agent"}
    result2 = extract_keywords(ctx2)
    print("关键词提取:", result2["_result"])
    
    # 测试日期格式化
    ctx3 = {"_content": "2026-06-20T10:30:00"}
    result3 = format_date(ctx3)
    print("日期格式化:", result3["_result"])
    
    print("\n=== 雇佣兵Agent创建测试 ===")
    agent1 = create_mercenary("测试雇佣兵", markdown_to_html)
    print("雇佣兵名称:", agent1.name)
    print("雇佣兵generation:", agent1.generation)
    print("雇佣兵skills:", list(agent1.skills.keys()))
