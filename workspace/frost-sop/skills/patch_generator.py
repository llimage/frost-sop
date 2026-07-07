"""
SELF-HEAL-001 Phase 3: 修复方案生成Skill
基于诊断报告，生成diff格式的修复方案。

PHILOSOPHY: 方案先给人看，不直接执行。安全优先。
"""

import json

from skills.llm import call_llm


def generate_patch(context: dict) -> dict:
    """
    SELF-HEAL-001 Phase 3 执行入口。

    Args:
        context: {
            "_diagnosis_report": {...},  # Phase 2 输出
        }

    Returns:
        更新后的context，包含修复方案（diff格式）
    """
    diagnosis = context.get("_diagnosis_report", {})
    pattern_matches = diagnosis.get("pattern_matches", [])
    affected_files = diagnosis.get("affected_files", [])
    relevant_code = diagnosis.get("relevant_code", {})

    # 如果匹配了已知模式，用模板化修复（低Token消耗）
    if pattern_matches:
        patches = _generate_template_patches(pattern_matches, relevant_code)
    else:
        # 需要LLM生成修复方案（高Token消耗，但仅当模式匹配失败时）
        patches = _generate_llm_patch(diagnosis, relevant_code)

    patch_summary = {
        "patches": patches,
        "total_files": len(patches),
        "total_risk_score": sum(p.get("risk_score", 1) for p in patches),
        "estimated_tokens": sum(p.get("llm_tokens_used", 0) for p in patches),
    }

    context["_patch_summary"] = patch_summary
    context["_reason"] = (
        f"生成 {len(patches)} 个补丁，预估风险分 {patch_summary['total_risk_score']}"
    )
    return context


def _generate_template_patches(pattern_matches: list, code_segments: dict) -> list[dict]:
    """基于已知模式，用模板生成修复方案（零Token成本）。"""
    patches = []
    for match in pattern_matches:
        pid = match["pattern_id"]
        filepath = match["file"]

        patch = {
            "file": filepath,
            "pattern_id": pid,
            "risk_score": 1 if match["severity"] in ("low", "medium") else 2,
            "llm_tokens_used": 0,  # 模板化，无Token消耗
            "description": match["fix_strategy"],
            "diff": _build_diff_for_pattern(pid, filepath, code_segments.get(filepath, "")),
        }
        patches.append(patch)
    return patches


def _build_diff_for_pattern(pattern_id: str, filepath: str, code: str) -> str:
    """为已知模式构建标准diff。"""
    # 这里简化处理：实际应用中可以用ast/line-diff做精确匹配
    # 当前版本返回描述性diff，供人工确认
    diffs = {
        "PATTERN-001": f'--- a/{filepath}\n+++ b/{filepath}\n@@ -283,1 +283,5 @@\n-    temperature = context.get("_temperature", 0.7)\n+    # 读取配置中心的temperature\n+    from core.config import FROSTConfig\n+    config = FROSTConfig.load()\n+    temperature = context.get("_temperature", config.llm.temperature)',
        "PATTERN-003": f'--- a/{filepath}\n+++ b/{filepath}\n@@ -25,3 +25,15 @@\n     def execute(self, context: dict) -> dict:\n-        return self._func(context)\n+        try:\n+            result = self._func(context)\n+            if not isinstance(result, dict):\n+                raise TypeError(f"Skill must return dict, got {{type(result)}}")\n+            return result\n+        except Exception as e:\n+            context["_skill_error"] = str(e)\n+            context["_skill_error_name"] = {{self.name}}\n+            context["_skill_failed"] = True\n+            return context',
        "PATTERN-006": f'--- a/{filepath}\n+++ b/{filepath}\n@@ -30,1 +30,4 @@\n-        "revenue_monthly": 34200,\n+        # TODO: 从数据库读取真实数据（当前为硬编码演示值）\n+        # 参见：https://github.com/user/project/issues/123\n+        "revenue_monthly": 34200,  # HARDCODED: 需替换为真实数据源',
    }
    return diffs.get(pattern_id, f"# 暂无标准diff模板，需LLM生成\n# Pattern: {pattern_id}")


def _generate_llm_patch(diagnosis: dict, code_segments: dict) -> list[dict]:
    """LLM生成修复方案（模式匹配失败时的fallback）。"""
    prompt = f"""基于以下诊断报告，生成代码修复方案（diff格式）。

## 诊断报告
{json.dumps(diagnosis, ensure_ascii=False, indent=2)[:2000]}

## 相关代码
{json.dumps({k: v[:1000] for k, v in code_segments.items()}, ensure_ascii=False, indent=2)[:3000]}

## 输出要求
请输出：
1. 修改的文件列表
2. 每个文件的diff（统一diff格式）
3. 每个修改的风险等级（low/medium/high）
4. 回滚命令

注意：只修改与问题相关的代码，不要"顺手优化"其他部分。
"""
    result = call_llm(
        {
            "_prompt": prompt,
            "_llm_profile": "execute",
            "_max_tokens": 3000,
        }
    )

    # 解析LLM输出（简化版：实际可用更严格的解析）
    response = result.get("_llm_response", "")
    return [
        {
            "file": "unknown",
            "pattern_id": "LLM-GENERATED",
            "risk_score": 2,
            "llm_tokens_used": result.get("_llm_tokens", {}).get("total", 0),
            "description": "LLM生成的修复方案，需人工仔细审核",
            "diff": response,
        }
    ]
