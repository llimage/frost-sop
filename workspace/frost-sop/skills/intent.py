"""
P1-7: 意图解析 — 结构化 JSON 输出
解析用户输入，自动匹配 SOP 模板。

使用方式：
    from skills.intent import parse_intent
    result = parse_intent("开发登录功能")
    # {"task_type": "开发", "confidence": 0.95, "sop_id": "DEV-001", ...}
"""

import json
import os
from typing import Dict, Optional

# 已知 SOP 模板列表（与 sops/templates/ 同步）
_KNOWN_SOPS = {
    "DEV-001": {
        "id": "DEV-001",
        "name": "新功能开发",
        "trigger_keywords": ["开发", "实现", "构建", "创建", "新增", "添加功能", "写代码", "开发功能"],
    },
    "DEV-002": {
        "id": "DEV-002",
        "name": "Bug修复",
        "trigger_keywords": ["修复", "bug", "错误", "缺陷", "崩溃", "异常", "修bug", "解决bug"],
    },
    "MT-001": {
        "id": "MT-001",
        "name": "内容发布",
        "trigger_keywords": ["发布", "推文", "文章", "内容", "推广", "营销", "文案", "写一篇", "选题"],
    },
    "OPS-001": {
        "id": "OPS-001",
        "name": "财务月结",
        "trigger_keywords": ["财务", "报销", "发票", "对账", "月结", "结算", "核算"],
    },
    "OPS-006": {
        "id": "OPS-006",
        "name": "知识资产管理",
        "trigger_keywords": ["知识", "文档", "归档", "资产", "知识库", "分类"],
    },
    "STR-001": {
        "id": "STR-001",
        "name": "项目立项",
        "trigger_keywords": ["立项", "新项目", "可行性", "调研", "方案", "规划"],
    },
    "STR-002": {
        "id": "STR-002",
        "name": "自进化验证",
        "trigger_keywords": ["优化", "进化", "改进", "提升", "自学习"],
    },
}

_INTENT_SYSTEM_PROMPT = """你是一个任务意图解析器。分析用户的任务描述，返回结构化的 JSON。

输出格式：
{
    "task_type": "任务类型（开发/Bug修复/内容发布/财务/运维/知识管理/项目管理/其他）",
    "confidence": 0.0-1.0,
    "sop_id": "匹配的SOP ID（DEV-001/DEV-002/MT-001/OPS-001/OPS-006/STR-001/STR-002），无匹配填null",
    "task_summary": "一句话任务摘要",
    "complexity": "低/中/高",
    "estimated_stages": 预估阶段数(int)
}

已知SOP模板：
- DEV-001 新功能开发：开发新功能、实现需求
- DEV-002 Bug修复：修复软件缺陷和错误
- MT-001 内容发布：内容创作、营销推广、文章发布
- OPS-001 财务月结：财务对账、报销结算
- OPS-006 知识资产管理：文档归档、知识分类
- STR-001 项目立项：项目规划、方案设计
- STR-002 自进化验证：系统优化、能力进化

注意：
1. 只返回纯 JSON，不要任何其他文字
2. confidence 基于关键词匹配度和语义理解
3. 优先匹配最相关的 SOP ID"""


def parse_intent(user_input: str, use_llm: bool = False) -> Dict:
    """
    解析用户意图，匹配 SOP 模板。

    Args:
        user_input: 用户输入的任务描述
        use_llm: 是否使用 LLM 进行语义解析（False 时用关键词匹配）

    Returns:
        {
            "task_type": str,
            "confidence": float,
            "sop_id": str or None,
            "task_summary": str,
            "complexity": str,
            "estimated_stages": int,
            "method": "keyword" or "llm",
        }
    """
    if use_llm and os.getenv("FROST_TESTING") != "1":
        return _parse_intent_with_llm(user_input)
    return _parse_intent_keyword(user_input)


def _parse_intent_keyword(user_input: str) -> Dict:
    """
    基于关键词匹配的意图解析（无需 LLM 调用）。
    快速、可靠、适合日常使用。
    """
    user_lower = user_input.lower()

    # 计算每个 SOP 的匹配分数
    scored = []
    for sop_id, sop_info in _KNOWN_SOPS.items():
        score = 0
        matched = []
        for keyword in sop_info["trigger_keywords"]:
            kw_lower = keyword.lower()
            if kw_lower in user_lower:
                # 完全匹配权重更高
                if len(kw_lower) >= 2:
                    score += 3
                else:
                    score += 1
                matched.append(keyword)
        if score > 0:
            scored.append((score, sop_id, matched))

    # 按分数排序
    scored.sort(key=lambda x: x[0], reverse=True)

    if scored:
        best_score, best_sop, matched = scored[0]
        # 分数映射到 confidence
        confidence = min(best_score / 5.0, 1.0)
        sop_info = _KNOWN_SOPS[best_sop]

        return {
            "task_type": sop_info["name"],
            "confidence": round(confidence, 2),
            "sop_id": best_sop,
            "task_summary": user_input[:50],
            "complexity": "中",
            "estimated_stages": 4,
            "method": "keyword",
            "matched_keywords": matched,
        }

    # 无匹配 — 返回通用结果
    return {
        "task_type": "通用任务",
        "confidence": 0.3,
        "sop_id": None,
        "task_summary": user_input[:50],
        "complexity": "低",
        "estimated_stages": 2,
        "method": "keyword",
        "matched_keywords": [],
    }


def _parse_intent_with_llm(user_input: str) -> Dict:
    """
    使用 LLM 进行语义意图解析（更准确但需要 API 调用）。
    """
    try:
        from skills.llm import _call_llm_raw
    except ImportError:
        return _parse_intent_keyword(user_input)

    response = _call_llm_raw(
        system_prompt=_INTENT_SYSTEM_PROMPT,
        prompt=user_input,
        temperature=0.1,
        max_tokens=256,
    )

    try:
        # 尝试解析 JSON
        result = json.loads(response)
        result.setdefault("task_type", "通用任务")
        result.setdefault("confidence", 0.5)
        result.setdefault("sop_id", None)
        result.setdefault("task_summary", user_input[:50])
        result.setdefault("complexity", "中")
        result.setdefault("estimated_stages", 3)
        result["method"] = "llm"
        return result
    except json.JSONDecodeError:
        # LLM 返回非 JSON，回退到关键词匹配
        return _parse_intent_keyword(user_input)


def get_sop_info(sop_id: Optional[str]) -> Optional[Dict]:
    """获取 SOP 模板详细信息。"""
    if sop_id and sop_id in _KNOWN_SOPS:
        return _KNOWN_SOPS[sop_id].copy()
    return None


def list_all_sops() -> list:
    """列出所有已知 SOP 模板。"""
    return [sop.copy() for sop in _KNOWN_SOPS.values()]
