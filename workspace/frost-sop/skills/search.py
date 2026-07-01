"""
FROST-SOP Search Skills
PHILOSOPHY: Parent Agents search for SOPs and Skills from the outside world.
This is Phase 3 (External Discovery) in action.
Search is a Skill, not a privileged component.
"""

from core.json_safety import safe_json_parse
from core.skill import Skill
from skills.llm import call_llm_skill


def search_sop(context: dict) -> dict:
    """
    搜索 SOP 模板。先查家族资产Store，再通过LLM搜索外部资源。

    输入 context 键：
        _search_query: str —— 搜索关键词（如 "DEV-001"、"新功能开发SOP"）
        _asset_store: Store（可选）—— 家族资产Store引用
        _search_external: bool（可选）—— 是否搜索外部资源，默认 True

    输出 context 键：
        _search_results: list —— 搜索结果列表
            [{"source": "asset_store"|"web", "sop_id": str, "name": str, "content": dict}, ...]
        _reason: str —— 搜索推理痕迹（用于审计）
    """

    query = context.get("_search_query", "")
    asset_store = context.get("_asset_store")
    search_external = context.get("_search_external", True)
    results = []

    # 第一步：搜索家族资产Store
    if asset_store:
        template = asset_store.load(f"sop_template:{query}")
        if template:
            results.append(
                {
                    "source": "asset_store",
                    "sop_id": query,
                    "name": template.get("name", query),
                    "content": template,
                }
            )
        else:
            # 模糊匹配
            all_keys = asset_store.list_keys()
            for key in all_keys:
                if key.startswith("sop_template:") and query.lower() in key.lower():
                    template = asset_store.load(key)
                    if template:
                        sop_id = key.replace("sop_template:", "")
                        results.append(
                            {
                                "source": "asset_store",
                                "sop_id": sop_id,
                                "name": template.get("name", sop_id),
                                "content": template,
                            }
                        )

    # 第二步：通过LLM搜索外部资源
    if search_external and not results:
        search_prompt = f"""你是一个SOP模板搜索助手。用户正在寻找与以下关键词相关的SOP模板：
关键词：{query}

请返回一个JSON格式的搜索结果。如果找到合适的模板，返回模板的完整结构。
如果找不到，返回 {{"found": false, "results": []}}。

返回格式示例：
{{
    "found": true,
    "results": [
        {{
            "source": "web",
            "sop_id": "模板ID",
            "name": "模板名称",
            "content": {{
                "sop_id": "模板ID",
                "name": "模板名称",
                "version": "1.0",
                "stages": [
                    {{"name": "需求分析", "agent": "product_manager", "skills": ["analyze_requirements"]}},
                    {{"name": "技术设计", "agent": "architect", "skills": ["design_architecture"]}},
                    {{"name": "代码实现", "agent": "developer", "skills": ["generate_code"]}},
                    {{"name": "测试验证", "agent": "tester", "skills": ["run_tests"]}},
                    {{"name": "审查交付", "agent": "auditor", "skills": ["audit_code"]}}
                ],
                "required_stages": ["审查交付"],
                "forbidden_skills": ["direct_db_write"]
            }}
        }}
    ]
}}

注意：如果关键词是"DEV-001"或"新功能开发"，请返回一个新功能开发的SOP模板，包含5个阶段。
只返回JSON，不要有任何其他文字。
"""

        llm_context = call_llm_skill.execute(
            {
                "_prompt": search_prompt,
                "_system_prompt": "你是一个SOP模板搜索助手。只返回有效的JSON，不要有任何其他说明文字。",
                "_temperature": 0.3,
            }
        )

        llm_response = llm_context.get("_llm_response", "")

        try:
            json_start = llm_response.find("{")
            json_end = llm_response.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                json_str = llm_response[json_start:json_end]
                search_result, err = safe_json_parse(json_str)
                if err is None and search_result.get("found") and search_result.get("results"):
                    for result in search_result["results"]:
                        result["source"] = "web"
                        results.append(result)
        except (KeyError, ValueError):
            pass

    context["_search_results"] = results
    context["_reason"] = f"搜索'{query}'：找到 {len(results)} 个结果"
    return context


def search_skill(context: dict) -> dict:
    """
    搜索 Skill 实现。与 search_sop 类似，但搜索对象为 Skill。

    输入 context 键：
        _search_query: str —— 搜索关键词

    输出 context 键：
        _search_results: list —— 搜索结果列表
    """

    query = context.get("_search_query", "")

    search_prompt = f"""你是一个Skill搜索助手。用户正在寻找与以下关键词相关的Skill：
关键词：{query}

Skill是FROST框架中的无状态能力单元，接收context dict，返回更新后的context dict。

请返回JSON格式的结果。如果找不到，返回 {{"found": false, "results": []}}。

返回格式示例：
{{
    "found": true,
    "results": [
        {{
            "source": "web",
            "skill_name": "技能名称",
            "description": "技能描述",
            "input_keys": ["_prompt"],
            "output_keys": ["_llm_response"]
        }}
    ]
}}

只返回JSON，不要有任何其他文字。
"""

    llm_context = call_llm_skill.execute(
        {
            "_prompt": search_prompt,
            "_system_prompt": "你是一个Skill搜索助手。只返回有效的JSON，不要有任何其他说明文字。",
            "_temperature": 0.3,
        }
    )

    llm_response = llm_context.get("_llm_response", "")
    results = []

    try:
        json_start = llm_response.find("{")
        json_end = llm_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            json_str = llm_response[json_start:json_end]
            search_result, err = safe_json_parse(json_str)
            if err is None and search_result.get("found") and search_result.get("results"):
                results = search_result["results"]
    except (KeyError, ValueError):
        pass

    context["_search_results"] = results
    context["_reason"] = f"搜索Skill'{query}'：找到 {len(results)} 个结果"
    return context


# 导出为 Skill 实例
search_sop_skill = Skill("search_sop", search_sop)
search_skill_skill = Skill("search_skill", search_skill)
