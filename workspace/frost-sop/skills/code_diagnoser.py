"""
SELF-HEAL-001 Phase 2: 代码诊断Skill
读取相关代码文件，匹配已知问题模式，分析根因。

PHILOSOPHY: 诊断优先于修复。先定位，再动手。
"""

import os
import re

# ── 已知问题模式库（本地缓存，减少LLM调用） ─────────────────────────
KNOWN_PATTERNS = {
    "PATTERN-001": {
        "name": "Hardcoded temperature",
        "description": "代码中硬编码了temperature值，未使用配置中心",
        "regex": r"temperature\s*=\s*(0\.\d+|1\.0)",
        "example_match": "temperature = 0.7",
        "fix_strategy": "读取配置文件或环境变量替换硬编码值",
        "severity": "medium",
    },
    "PATTERN-002": {
        "name": "Bare except clause",
        "description": "使用裸except捕获所有异常，隐藏真实错误",
        "regex": r"except\s*:\s*$|except\s+Exception\s*:\s*$",
        "example_match": "except Exception:",
        "fix_strategy": "捕获具体异常类型，或至少使用except Exception as e并记录日志",
        "severity": "high",
    },
    "PATTERN-003": {
        "name": "Missing error handling in Skill",
        "description": "Skill.execute()没有try/catch，异常直接上抛",
        "regex": r"def execute\(self, context\):\s*\n\s*return self\._func\(context\)",
        "example_match": "def execute(self, context):\n    return self._func(context)",
        "fix_strategy": "添加try/except包装，错误写入context而非抛异常",
        "severity": "critical",
    },
    "PATTERN-004": {
        "name": "SQL injection via format string",
        "description": "SQL语句使用字符串格式化拼接，存在注入风险",
        "regex": r'f".*SELECT.*\{.*\}.*"|f".*INSERT.*\{.*\}.*"',
        "example_match": 'f"SELECT * FROM {table}"',
        "fix_strategy": "使用参数化查询",
        "severity": "critical",
    },
    "PATTERN-005": {
        "name": "Mock-only tests",
        "description": "测试全部使用mock，未验证真实LLM调用路径",
        "regex": r'FROST_TESTING\s*=\s*["\']1["\']',
        "example_match": 'FROST_TESTING = "1"',
        "fix_strategy": "拆分为mock测试+真实冒烟测试",
        "severity": "medium",
    },
    "PATTERN-006": {
        "name": "Hardcoded fake data",
        "description": "模块返回硬编码的模拟数据而非从数据库读取",
        "regex": r"(revenue_monthly|cost|price)\s*:\s*\d{3,}",
        "example_match": "revenue_monthly: 34200",
        "fix_strategy": "从数据库或配置文件读取真实数据，添加TODO注释",
        "severity": "low",
    },
}


def _read_file_segment(
    filepath: str, target_line: int | None = None, context_lines: int = 10
) -> str:
    """读取文件片段，支持指定行号上下文。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return f"[ERROR reading {filepath}: {e}]"

    if target_line is None:
        return "".join(lines[:100])  # 默认前100行

    start = max(0, target_line - 1 - context_lines)
    end = min(len(lines), target_line - 1 + context_lines + 1)
    return "".join(lines[start:end])


def _match_patterns(code_text: str) -> list[dict]:
    """匹配已知问题模式，返回匹配结果（零Token成本）。"""
    matches = []
    for pattern_id, pattern in KNOWN_PATTERNS.items():
        for match in re.finditer(pattern["regex"], code_text, re.MULTILINE):
            matches.append(
                {
                    "pattern_id": pattern_id,
                    "pattern_name": pattern["name"],
                    "severity": pattern["severity"],
                    "match": match.group(0)[:80],
                    "line_hint": match.start(),
                    "fix_strategy": pattern["fix_strategy"],
                }
            )
    return matches


def diagnose(context: dict) -> dict:
    """
    SELF-HEAL-001 Phase 2 执行入口。

    Args:
        context: {
            "_symptoms": [...],           # Phase 1 输出
            "_affected_modules": [...],   # 涉及模块
            "_pattern_library": {...},  # 可扩展的模式库
        }

    Returns:
        更新后的context，包含诊断报告
    """
    symptoms = context.get("_symptoms", [])
    affected_modules = context.get("_affected_modules", [])

    # 如果未指定模块，从症状推断
    if not affected_modules and symptoms:
        for s in symptoms:
            loc = s.get("location", "")
            if ":" in loc:
                filepath = loc.split(":")[0]
                if filepath not in affected_modules:
                    affected_modules.append(filepath)

    # 读取相关代码
    code_segments = {}
    for filepath in affected_modules:
        full_path = os.path.join(os.getcwd(), filepath) if not os.path.isabs(filepath) else filepath
        if os.path.exists(full_path):
            code_segments[filepath] = _read_file_segment(full_path)

    # 模式匹配（零Token成本）
    pattern_matches = []
    for filepath, code in code_segments.items():
        matches = _match_patterns(code)
        for m in matches:
            m["file"] = filepath
        pattern_matches.extend(matches)

    # 构建诊断报告
    affected_files = list(code_segments.keys())
    diagnosis_report = {
        "root_causes": [],
        "pattern_matches": pattern_matches,
        "affected_files": affected_files,
        "confidence": "high" if pattern_matches else "medium",
        "needs_llm_analysis": len(pattern_matches) == 0,  # 无模式匹配时需LLM分析
        "relevant_code": {k: v[:2000] for k, v in code_segments.items()},  # 截断避免过大
    }

    # 如果有症状但未匹配到模式，用LLM补充分析（消耗Token）
    if diagnosis_report["needs_llm_analysis"] and symptoms:
        from skills.llm import call_llm

        llm_prompt = _build_diagnosis_prompt(symptoms, code_segments)
        llm_result = call_llm(
            {
                "_prompt": llm_prompt,
                "_llm_profile": "review",
                "_max_tokens": 1500,
            }
        )
        llm_analysis = llm_result.get("_llm_response", "")
        diagnosis_report["llm_analysis"] = llm_analysis
        diagnosis_report["confidence"] = "medium"

    context["_diagnosis_report"] = diagnosis_report
    context["_reason"] = (
        f"诊断完成：发现 {len(pattern_matches)} 个已知模式匹配，涉及 {len(affected_files)} 个文件"
    )
    return context


def _build_diagnosis_prompt(symptoms: list, code_segments: dict) -> str:
    """构建LLM诊断Prompt（仅在模式匹配失败时使用）。"""
    lines = ["请分析以下代码问题：\n"]
    for s in symptoms:
        lines.append(
            f"- [{s.get('severity', 'unknown')}] {s.get('message', '')} @ {s.get('location', '')}"
        )
    lines.append("\n相关代码片段：\n")
    for filepath, code in code_segments.items():
        lines.append(f"\n--- {filepath} ---\n{code[:1500]}\n")
    lines.append("\n请输出：\n1. 根因分析（50字以内）\n2. 涉及的代码位置\n3. 修复建议（简要）")
    return "\n".join(lines)
