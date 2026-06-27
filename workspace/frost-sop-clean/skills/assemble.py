"""
FROST-SOP Assemble Agent Skill
PHILOSOPHY: 孙辈Agent不是预定义的，而是由父辈根据任务需求动态组装。
能力基因存储在家族资产Store中，找不到时由LLM合成并归档。
"""

import json
import os
from core.skill import Skill
from core.agent import Agent
from core.store import Store
from skills.llm import call_llm_skill
from skills.tools import call_llm_for_output_skill

# V2.0: 延迟导入 event_bus，避免循环依赖
def _get_event_bus():
    try:
        from core.event_bus import get_event_bus, EventType
        return get_event_bus(), EventType
    except Exception:
        return None, None


def _make_output_skill_func(name, desc, reason_prefix, output_type="document"):
    """Helper: create a skill function that calls call_llm_for_output_skill."""
    def skill_func(ctx):
        ctx["_task_description"] = f"{desc}：{ctx.get('stage_name', '')}"
        ctx["_output_type"] = output_type
        ctx["_output_path"] = f"output/{name}.md"
        result_ctx = call_llm_for_output_skill.execute(ctx)
        ctx["_result"] = result_ctx.get("_generated_content", f"[{name}] {desc}：任务执行完成")
        ctx["_reason"] = f"{reason_prefix}: {name}"
        return ctx
    return skill_func


def assemble_agent(context: dict) -> dict:
    """
    根据需求描述，动态组装一个孙辈Agent。
    
    输入 context 键：
        _agent_requirement: str —— 需求描述，如"需要一个会写小红书文案的人"
        _asset_store: Store —— 家族资产Store（查询能力基因库）
        _parent_agent: Agent —— 父辈Agent引用（用于spawn）
    
    输出 context 键：
        _assembled_agent: Agent —— 组装完成的孙辈Agent实例
        _agent_config: dict —— Agent的配置详情（Skills列表、SOP、来源）
        _reason: str
    """
    
    requirement = context.get("_agent_requirement", "")
    asset_store = context.get("_asset_store")
    parent_agent = context.get("_parent_agent")
    
    if not requirement:
        context["_assembled_agent"] = None
        context["_reason"] = "组装失败：缺少需求描述"
        return context
    
    # 1. LLM分析需求，输出需要的Skills和SOP
    analysis_prompt = f"""分析以下Agent需求，返回JSON格式的配置方案：

需求：{requirement}

返回格式：
{{
    "agent_name": "Agent名称",
    "required_skills": ["技能名称1", "技能名称2"],
    "sop_steps": ["技能名称1", "技能名称2"],
    "system_prompt": "Agent的系统提示词",
    "output_type": "code|document|copywriting"
}}

注意：
- required_skills 列出完成需求所需的能力名称（中文，2-5个，每个名称2-6个字，不要加编号或描述）
- sop_steps 列出执行步骤（就是required_skills中的技能名称，按执行顺序排列）
- system_prompt 简要描述Agent的角色定位（20字以内）
- **output_type 必须明确指定**：
  * 如果需求是"写代码/生成页面/开发功能/写脚本"→ output_type="code"
  * 如果需求是"写文档/分析报告/总结"→ output_type="document"
  * 如果需求是"写文案/文章/内容/帖子"→ output_type="copywriting"
- **重要**：指定了output_type后，在生成system_prompt时必须明确告知Agent：
  * code类型：直接输出代码，不使用代码块标记，代码可直接运行
  * document类型：直接输出文档内容，不是文档模板
  * copywriting类型：直接输出文案内容，不是写作指南
"""
    
    llm_context = call_llm_skill.execute({
        "_prompt": analysis_prompt,
        "_system_prompt": "你是一个Agent配置分析师。请返回有效的JSON。",
        "_temperature": 0.3,
    })
    
    llm_response = llm_context.get("_llm_response", "")
    
    try:
        json_start = llm_response.find("{")
        json_end = llm_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            config = json.loads(llm_response[json_start:json_end])
        else:
            config = {"agent_name": "generic_agent", "required_skills": [], "sop_steps": [], "system_prompt": ""}
    except (json.JSONDecodeError, KeyError):
        config = {"agent_name": "generic_agent", "required_skills": [], "sop_steps": [], "system_prompt": ""}
    
    required_skills = config.get("required_skills", [])
    sop_steps = config.get("sop_steps", [])
    system_prompt = config.get("system_prompt", "")
    output_type = config.get("output_type", "document")  # 解析output_type
    
    # 2. 搜索家族资产Store中的能力基因库（智能匹配升级）
    assembled_skills = {}
    skill_sources = {}  # 记录每个Skill的来源
    matched_template = None

    if asset_store:
        # 2.1 收集所有教练模板
        all_templates = []
        for key in asset_store.list_keys():
            if key.startswith("skill_gene:"):
                gene = asset_store.load(key)
                if gene:
                    all_templates.append(gene)
        
        # 2.2 如果模板数量 > 10，使用语义匹配
        use_semantic_match = len(all_templates) > 10
        
        if use_semantic_match and required_skills:
            # 构建语义匹配提示词
            template_list = []
            for t in all_templates[:50]:  # 限制候选数量
                template_list.append({
                    "name": t.get("name", ""),
                    "description": t.get("description", "")[:100],
                    "category": t.get("category", "unknown"),
                })
            
            match_prompt = """你是一个技能匹配专家。请从以下教练模板中选择最匹配任务需求的模板。

任务需求：{}

候选模板：
{}

请返回JSON格式：
{{
    "selected_templates": ["模板名称1", "模板名称2"],
    "reason": "选择理由"
}}

注意：
- 选择1-3个最匹配的模板
- 优先选择专业领域与任务需求一致的模板
- 如果没有完全匹配的，选择最接近的
""".format(requirement, json.dumps(template_list, ensure_ascii=False, indent=2))
            
            llm_context = call_llm_skill.execute({
                "_prompt": match_prompt,
                "_system_prompt": "你是一个技能匹配专家。请返回有效的JSON。",
                "_temperature": 0.3,
            })
            
            llm_response = llm_context.get("_llm_response", "")
            
            try:
                json_start = llm_response.find("{")
                json_end = llm_response.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    match_result = json.loads(llm_response[json_start:json_end])
                    selected_names = match_result.get("selected_templates", [])
                    
                    for name in selected_names:
                        gene = asset_store.load("skill_gene:{}".format(name))
                        if gene:
                            skill_func = create_skill_from_gene(gene, output_type)
                            assembled_skills[name] = Skill(name, skill_func)
                            skill_sources[name] = "gene_library(semantic)"
                            matched_template = gene
            except (json.JSONDecodeError, KeyError):
                pass
        
        # 2.3 如果语义匹配未找到，回退到关键词匹配
        if not assembled_skills:
            for skill_name in required_skills:
                gene = asset_store.load("skill_gene:{}".format(skill_name))
                if gene:
                    # 找到已有能力基因，复用
                    skill_func = create_skill_from_gene(gene, output_type)
                    assembled_skills[skill_name] = Skill(skill_name, skill_func)
                    skill_sources[skill_name] = "gene_library(keyword)"
    
    # 3. 未找到的能力基因，通过LLM合成
    missing_skills = [s for s in required_skills if s not in assembled_skills]
    for skill_name in missing_skills:
        synthesized = synthesize_skill(skill_name, requirement, asset_store, output_type)
        assembled_skills[skill_name] = synthesized
        skill_sources[skill_name] = "llm_synthesized"
    
    # 4. 组装孙辈Agent
    child_store = Store()
    child_store.save("_system_prompt", system_prompt)
    child_store.save("_requirement", requirement)
    
    if parent_agent:
        child = parent_agent.spawn(
            name=config.get("agent_name", "assembled_agent"),
            store=child_store,
            skills=assembled_skills,
            sop_steps=sop_steps,
        )
    else:
        child = Agent(
            name=config.get("agent_name", "assembled_agent"),
            store=child_store,
            skills=assembled_skills,
            sop_steps=sop_steps,
            generation=2,
        )
    
    context["_assembled_agent"] = child
    context["_agent_config"] = {
        "agent_name": child.name,
        "skills": list(assembled_skills.keys()),
        "skill_sources": skill_sources,
        "sop_steps": sop_steps,
        "generation": child.generation,
    }
    context["_reason"] = f"Agent组装完成: {child.name}，{len(assembled_skills)}个Skill（基因库:{len(assembled_skills)-len(missing_skills)} 合成:{len(missing_skills)}）"

    # V2.0: 孙辈组装完成后发布 AGENT_CREATED 事件（fail-safe）
    try:
        bus, EventType = _get_event_bus()
        if bus is not None and EventType is not None:
            from core.event_bus import Event
            bus.publish(Event(
                event_type=EventType.AGENT_CREATED,
                source="assemble:agent_creator",
                data={
                    "agent_name": child.name,
                    "generation": child.generation,
                    "skill_count": len(assembled_skills),
                    "task_id": context.get("_task_id", ""),
                },
            ))
    except Exception as e:
        # fail-safe: 事件发布失败不影响主流程
        import warnings
        warnings.warn(f"[assemble] AGENT_CREATED 事件发布失败（已忽略）: {e}")

    return context


def create_skill_from_gene(gene: dict, output_type: str = "document"):
    """从能力基因创建Skill执行函数（使用helper）"""
    skill_name = gene.get("name", "unknown")
    skill_desc = gene.get("description", "")
    return _make_output_skill_func(skill_name, skill_desc, "使用基因库Skill", output_type)


def synthesize_skill(skill_name: str, requirement: str, asset_store=None, output_type: str = "document") -> Skill:
    """通过LLM合成新Skill，并归档到能力基因库"""
    
    synthesize_prompt = f"""你是一个Skill设计助手。请为以下需求生成一个Skill的执行描述：

需求：{requirement}
需要合成的Skill：{skill_name}

请返回JSON格式：
{{
    "name": "{skill_name}",
    "type": "functional",
    "description": "Skill的功能描述（一句话）",
    "input_keys": ["需要的context键"],
    "output_keys": ["输出的context键"]
}}
"""
    
    llm_context = call_llm_skill.execute({
        "_prompt": synthesize_prompt,
        "_system_prompt": "你是一个Skill设计助手。请返回有效的JSON。",
        "_temperature": 0.3,
    })
    
    llm_response = llm_context.get("_llm_response", "")
    
    try:
        json_start = llm_response.find("{")
        json_end = llm_response.rfind("}") + 1
        if json_start >= 0 and json_end > json_start:
            gene_data = json.loads(llm_response[json_start:json_end])
        else:
            gene_data = {"name": skill_name, "type": "functional", "description": f"执行{skill_name}的能力"}
    except (json.JSONDecodeError, KeyError):
        gene_data = {"name": skill_name, "type": "functional", "description": f"执行{skill_name}的能力"}
    
    # 归档到能力基因库
    if asset_store:
        asset_store.save(f"skill_gene:{skill_name}", gene_data)
    
    # 创建Skill（使用helper）
    skill_func = _make_output_skill_func(
        skill_name,
        gene_data.get("description", skill_name),
        "使用LLM合成Skill",
        output_type
    )
    return Skill(skill_name, skill_func)


assemble_agent_skill = Skill("assemble_agent", assemble_agent)
