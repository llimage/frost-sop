"""
FROST-SOP 真实工具 Skill
PHILOSOPHY: 孙辈Agent调用真实工具产出交付物。
文件写入、代码执行等能力作为普通Skill实现。
"""

import os

from core.skill import Skill


def write_file(context: dict) -> dict:
    """
    将内容写入文件。

    输入 context 键：
        _file_path: str —— 文件路径（相对于项目根目录）
        _file_content: str —— 文件内容

    输出 context 键：
        _file_result: dict —— 写入结果
    """

    file_path = context.get("_file_path", "")
    file_content = context.get("_file_content", "")

    if not file_path:
        context["_file_result"] = {"success": False, "reason": "缺少文件路径"}
        return context

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(file_content)
        context["_file_result"] = {"success": True, "path": file_path}
        context["_reason"] = f"文件写入成功: {file_path}"
    except Exception as e:
        context["_file_result"] = {"success": False, "reason": str(e)}
        context["_reason"] = f"文件写入失败: {e}"

    return context


def call_llm_for_output(context: dict) -> dict:
    """
    调用LLM生成真实产出内容（代码/文档/文案）。
    与skills/llm.py的call_llm相同，但专用于孙辈产出生成。

    输入 context 键：
        _task_description: str —— 任务描述
        _output_type: str —— 产出类型（"code", "document", "copywriting"）
        _output_path: str（可选）—— 如果提供，自动写入文件

    输出 context 键：
        _generated_content: str —— 生成的内容
        _file_result: dict（如果提供了_output_path）
    """

    from skills.llm import call_llm_skill

    task = context.get("_task_description", "")
    output_type = context.get("_output_type", "document")
    output_path = context.get("_output_path", "")

    type_prompts = {
        "code": (
            "请生成完整的、可运行的代码。\n"
            "重要规则：\n"
            "1. 只输出代码本身，不要使用代码块标记（如```html或```）\n"
            "2. 不要添加任何解释、说明或注释（除非是代码内的必要注释）\n"
            "3. 代码应该可以直接保存为文件并运行\n"
            "4. 如果是HTML，从<!DOCTYPE html>或<html>开始输出"
        ),
        "document": (
            "请生成结构化的文档，使用Markdown格式。\n"
            "重要规则：\n"
            "1. 文档应该是可以直接使用的完整内容，不是模板或说明\n"
            "2. 使用标题、列表、表格等Markdown元素组织内容\n"
            "3. 不要添加'这是一个模板'之类的元说明"
        ),
        "copywriting": (
            "请生成符合要求的文案内容。\n"
            "重要规则：\n"
            "1. 文案应该是可以直接发布的完整内容，不是写作指南或模板\n"
            "2. 根据平台特性调整语气和格式\n"
            "3. 不要添加'这是一篇文案'之类的元说明"
        ),
    }

    prompt = f"{task}\n\n{type_prompts.get(output_type, type_prompts['document'])}"

    # 从context读取temperature，默认0.1（确定性优先，减少思维飘逸）
    temperature = context.get("_temperature", 0.1)

    # P1: 强化system prompt — 禁止寒暄、禁止偏题、强制直接输出
    system_prompt = (
        "你是一个专业的内容生成引擎。严格遵守以下规则：\n"
        "1. 直接输出内容，禁止任何寒暄语（如'好的'、'我来'、'以下是'、'根据您的要求'）\n"
        "2. 输出必须以Markdown标题(##)或表格(|)开头\n"
        "3. 严格围绕给定主题生成内容，禁止自由发挥到无关话题\n"
        "4. 如果提供了前序阶段输出，必须基于前序内容继续，不要重新假设主题\n"
        "5. 输出必须是完整的、可直接使用的内容，不是模板或说明"
    )

    llm_context = call_llm_skill.execute(
        {
            "_prompt": prompt,
            "_system_prompt": system_prompt,
            "_temperature": temperature,
            "_task_id": context.get("_task_id"),  # F14: propagate for cost_log
            "_agent_id": context.get("_agent_id"),  # F14: propagate for cost_log
        }
    )

    content = llm_context.get("_llm_response", "")
    context["_generated_content"] = content

    if output_path:
        context["_file_path"] = output_path
        context["_file_content"] = content
        return write_file(context)

    context["_reason"] = f"LLM产出生成完成（类型: {output_type}）"
    return context


write_file_skill = Skill("write_file", write_file)
call_llm_for_output_skill = Skill("call_llm_for_output", call_llm_for_output)
