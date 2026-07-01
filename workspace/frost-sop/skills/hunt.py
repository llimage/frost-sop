"""
V4.0 P0-b: 斥候持续狩猎

包含3个核心Skill：
1. search_external - 搜索外部来源
2. compare_skill - 与现有Skill比对
3. absorb_skill - 吸收新Skill并归档

两种触发模式：
- 持续优化搜索：每天定时触发，全量扫描兵器库
- 预测性搜索：军师分析完成后触发，定向搜索能力缺口
"""

import logging
import os
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)

# 狩猎配置目录
HUNT_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "hunt")
TARGET_LIST_FILE = os.path.join(HUNT_CONFIG_DIR, "target_list.yaml")


def _load_target_list() -> list[dict]:
    """
    加载狩猎目标清单。

    Returns:
        List[dict]: 目标列表，每个目标包含：
            - skill_id: Skill ID
            - health_score: 健康评分（0.0-1.0）
            - days_since_version: 距离上次版本更新的天数
            - priority: 优先级（high / medium / low）
    """
    if not os.path.exists(TARGET_LIST_FILE):
        logger.warning(f"[Hunt] 目标清单不存在: {TARGET_LIST_FILE}")
        return []

    try:
        from core.path_safety import safe_open

        with safe_open(TARGET_LIST_FILE, encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config.get("targets", [])  # type: ignore[no-any-return]
    except Exception as e:
        logger.error(f"[Hunt] 加载目标清单失败: {e}")
        return []


def _save_target_list(targets: list[dict]):
    """
    保存狩猎目标清单。
    """
    os.makedirs(os.path.dirname(TARGET_LIST_FILE), exist_ok=True)

    try:
        with open(TARGET_LIST_FILE, "w", encoding="utf-8") as f:
            yaml.dump({"targets": targets}, f, allow_unicode=True)
        logger.info(f"[Hunt] 目标清单已保存: {len(targets)} 个目标")
    except Exception as e:
        logger.error(f"[Hunt] 保存目标清单失败: {e}")


def _update_skill_health_in_store(store, skill_id: str, health_score: float, action: str):
    """
    更新Store中的Skill健康评分。

    Args:
        store: Asset Store
        skill_id: Skill ID
        health_score: 新的健康评分
        action: 操作描述（如 "hunt_searched", "hunt_absorbed"）
    """
    if store is None:
        return

    try:
        key = f"skill_gene:{skill_id}"
        skill_data = store.load(key)

        if skill_data and isinstance(skill_data, dict):
            skill_data["health_score"] = health_score
            skill_data["last_hunt_time"] = datetime.now().isoformat()
            skill_data["last_hunt_action"] = action
            store.store(key, skill_data)
            logger.debug(f"[Hunt] 已更新健康评分: {skill_id} = {health_score}")
    except Exception as e:
        logger.error(f"[Hunt] 更新健康评分失败: {e}")


def search_external(context: dict) -> dict:
    """
    搜索外部来源，寻找更好的Skill替代方案。

    输入 context 键：
        _hunt_target_skill_id: 目标Skill ID
        _hunt_search_query: 搜索查询词（可选，默认使用skill_id生成）
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_search_result: dict（搜索结果）
    """
    store = context.get("_asset_store")
    target_skill_id = context.get("_hunt_target_skill_id")
    search_query = context.get("_hunt_search_query", target_skill_id)

    if not target_skill_id:
        logger.error("[Hunt] 缺少 _hunt_target_skill_id")
        context["_hunt_search_result"] = {"error": "missing_target_skill_id"}
        return context

    logger.info(f"[Hunt] 开始外部搜索: {target_skill_id} (query={search_query})")

    # LLM 驱动的外部搜索：查询外部来源寻找 Skill 替代方案
    try:
        from skills.llm import call_llm_skill

        llm_response = call_llm_skill(  # type: ignore[operator]
            f"""你是技能搜索专家。请为以下技能搜索外部替代方案。

目标技能: {target_skill_id}
搜索查询: {search_query}

请返回 JSON 格式结果，如果找到替代方案则 found=true：
{{
    "found": true/false,
    "candidates": [
        {{
            "name": "技能名称",
            "source": "github/huggingface/pypi",
            "url": "来源URL",
            "health_score": 0.0-1.0,
            "version": "版本号"
        }}
    ]
}}

如果没有找到合适的替代方案，返回 found=false。""",
            skill_name="hunt_search_external",
        )

        from core.json_safety import safe_json_parse_or_default

        search_result = safe_json_parse_or_default(
            llm_response,
            default={
                "target_skill_id": target_skill_id,
                "search_query": search_query,
                "found": False,
                "candidates": [],
                "search_time": datetime.now().isoformat(),
            },
        )
    except Exception as e:
        logger.warning(f"[Hunt] LLM 搜索失败，使用空结果: {e}")
        search_result = {
            "target_skill_id": target_skill_id,
            "search_query": search_query,
            "found": False,
            "candidates": [],
            "search_time": datetime.now().isoformat(),
        }

    # 更新Store中的最后搜索时间
    if store:
        _update_skill_health_in_store(
            store, target_skill_id, context.get("_current_health_score", 0.5), "hunt_searched"
        )

    context["_hunt_search_result"] = search_result
    return context


def compare_skill(context: dict) -> dict:
    """
    与现有Skill比对，判断是否需要替换。

    输入 context 键：
        _hunt_search_result: 搜索结果（来自 search_external）
        _hunt_target_skill_id: 目标Skill ID
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_compare_result: dict（比对结果）
    """
    store = context.get("_asset_store")
    search_result = context.get("_hunt_search_result", {})
    target_skill_id = context.get("_hunt_target_skill_id")

    if not search_result.get("found"):
        logger.info("[Hunt] 未找到候选者，跳过比对")
        context["_hunt_compare_result"] = {"action": "skip", "reason": "no_candidates"}
        return context

    candidates = search_result.get("candidates", [])
    if not candidates:
        context["_hunt_compare_result"] = {"action": "skip", "reason": "empty_candidates"}
        return context

    logger.info(f"[Hunt] 开始比对: {target_skill_id} vs {len(candidates)} 个候选者")

    # 加载现有Skill
    existing_skill = None
    if store:
        try:
            existing_skill = store.load(f"skill_gene:{target_skill_id}")
        except Exception as e:
            logger.error(f"[Hunt] 加载现有Skill失败: {e}")

    existing_health = 0.0
    if existing_skill and isinstance(existing_skill, dict):
        existing_health = existing_skill.get("health_score", 0.0)

    # 比对每个候选者
    compare_results = []
    for candidate in candidates:
        candidate_health = candidate.get("health_score", 0.0)
        health_diff = candidate_health - existing_health

        compare_result = {
            "candidate_name": candidate.get("name"),
            "candidate_health": candidate_health,
            "existing_health": existing_health,
            "health_diff": health_diff,
            "should_replace": health_diff > 0.1,  # 健康评分提升超过0.1才替换
        }
        compare_results.append(compare_result)

    # 决定动作
    should_absorb = any(r["should_replace"] for r in compare_results)

    result = {
        "target_skill_id": target_skill_id,
        "existing_health": existing_health,
        "candidates_count": len(candidates),
        "compare_results": compare_results,
        "should_absorb": should_absorb,
        "compare_time": datetime.now().isoformat(),
    }

    logger.info(f"[Hunt] 比对完成: should_absorb={should_absorb}")

    context["_hunt_compare_result"] = result
    return context


def absorb_skill(context: dict) -> dict:
    """
    吸收新Skill并归档。

    输入 context 键：
        _hunt_compare_result: 比对结果（来自 compare_skill）
        _hunt_search_result: 搜索结果（来自 search_external）
        _hunt_target_skill_id: 目标Skill ID
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_absorb_result: dict（吸收结果）
    """
    store = context.get("_asset_store")
    compare_result = context.get("_hunt_compare_result", {})
    search_result = context.get("_hunt_search_result", {})
    target_skill_id = context.get("_hunt_target_skill_id")

    # 检查是否需要吸收
    if not compare_result.get("should_absorb"):
        reason = compare_result.get("reason", "health_not_improved")
        logger.info(f"[Hunt] 跳过吸收: {reason}")
        context["_hunt_absorb_result"] = {"action": "rejected", "reason": reason}
        return context

    candidates = search_result.get("candidates", [])
    if not candidates:
        context["_hunt_absorb_result"] = {"action": "rejected", "reason": "no_candidates"}
        return context

    logger.info(f"[Hunt] 开始吸收: {target_skill_id}")

    # 下载候选 Skill 代码并验证归档
    candidate = candidates[0]
    candidate_name = candidate.get("name", f"new_{target_skill_id}")
    candidate_url = candidate.get("url", "")

    # 尝试从 URL 下载 SKILL.md 定义（如有）
    downloaded_content = None
    if candidate_url and ("github.com" in candidate_url or "huggingface" in candidate_url):
        try:
            import urllib.request

            raw_url = candidate_url.replace("github.com", "raw.githubusercontent.com").replace(
                "/blob/", "/"
            )
            req = urllib.request.Request(raw_url, headers={"User-Agent": "FROST-SOP-Hunt/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                downloaded_content = resp.read().decode("utf-8", errors="replace")[:10000]
                logger.info(f"[Hunt] 已下载候选代码: {len(downloaded_content)} 字符")
        except Exception as e:
            logger.warning(f"[Hunt] 下载候选代码失败: {e}")

    # 归档到Store
    if store:
        try:
            new_skill_id = candidate_name
            skill_data = {
                "name": new_skill_id,
                "source": candidate.get("source", "unknown"),
                "url": candidate_url,
                "health_score": candidate.get("health_score", 0.0),
                "version": candidate.get("version", "1.0.0"),
                "absorbed_at": datetime.now().isoformat(),
                "replaces": target_skill_id,
            }
            if downloaded_content:
                skill_data["downloaded_content"] = downloaded_content

            store.store(f"skill_gene:{new_skill_id}", skill_data)
            logger.info(f"[Hunt] 已归档新Skill: {new_skill_id}")

            # 更新旧Skill的健康评分（标记为被替换）
            _update_skill_health_in_store(store, target_skill_id, 0.0, "hunt_replaced")  # type: ignore[arg-type]

            result = {
                "action": "absorbed",
                "new_skill_id": new_skill_id,
                "replaced_skill_id": target_skill_id,
                "absorb_time": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"[Hunt] 归档失败: {e}")
            result = {"action": "failed", "error": str(e)}
    else:
        result = {"action": "failed", "error": "store_not_available"}

    context["_hunt_absorb_result"] = result
    return context


def hunt_sop(context: dict) -> dict:
    """
    狩猎SOP：加载目标清单 → 并行搜索 → 比对结果 → 吸收或丢弃 → 记录结果。

    输入 context 键：
        _hunt_targets: 目标列表（可选，默认从配置文件加载）
        _hunt_mode: 狩猎模式（"continuous" / "predictive"）
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_sop_result: dict（狩猎结果）
    """
    store = context.get("_asset_store")
    mode = context.get("_hunt_mode", "continuous")

    logger.info(f"[Hunt] 狩猎SOP开始 (mode={mode})")

    # 1. 加载目标清单
    targets = context.get("_hunt_targets")
    if not targets:
        targets = _load_target_list()

    if not targets:
        logger.warning("[Hunt] 无狩猎目标，退出")
        context["_hunt_sop_result"] = {"status": "no_targets"}
        return context

    logger.info(f"[Hunt] 加载了 {len(targets)} 个狩猎目标")

    # 2. 并行搜索（简化版：顺序执行）
    search_results = []
    for target in targets:
        skill_id = target.get("skill_id")
        if not skill_id:
            continue

        # 搜索
        search_context = {"_asset_store": store, "_hunt_target_skill_id": skill_id}
        search_context = search_external(search_context)
        search_results.append(search_context.get("_hunt_search_result", {}))

    # 3. 比对结果
    compare_results = []
    for i, search_result in enumerate(search_results):
        target = targets[i]
        skill_id = target.get("skill_id")

        compare_context = {
            "_asset_store": store,
            "_hunt_search_result": search_result,
            "_hunt_target_skill_id": skill_id,
        }
        compare_context = compare_skill(compare_context)
        compare_results.append(compare_context.get("_hunt_compare_result", {}))

    # 4. 吸收或丢弃
    absorb_results = []
    for i, compare_result in enumerate(compare_results):
        target = targets[i]
        skill_id = target.get("skill_id")

        absorb_context = {
            "_asset_store": store,
            "_hunt_compare_result": compare_result,
            "_hunt_search_result": search_results[i],
            "_hunt_target_skill_id": skill_id,
        }
        absorb_context = absorb_skill(absorb_context)
        absorb_results.append(absorb_context.get("_hunt_absorb_result", {}))

    # 5. 记录结果
    result = {
        "mode": mode,
        "targets_count": len(targets),
        "search_results": search_results,
        "compare_results": compare_results,
        "absorb_results": absorb_results,
        "absorbed_count": sum(1 for r in absorb_results if r.get("action") == "absorbed"),
        "rejected_count": sum(1 for r in absorb_results if r.get("action") == "rejected"),
        "hunt_time": datetime.now().isoformat(),
    }

    logger.info(
        f"[Hunt] 狩猎SOP完成: absorbed={result['absorbed_count']}, rejected={result['rejected_count']}"
    )

    context["_hunt_sop_result"] = result
    return context


def trigger_continuous_hunt(context: dict) -> dict:
    """
    触发持续优化搜索（每天定时触发）。

    输入 context 键：
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_trigger_result: dict（触发结果）
    """
    logger.info("[Hunt] 触发持续优化搜索")

    # 加载所有Skill，筛选健康评分<0.7或版本>30天的
    store = context.get("_asset_store")
    targets = []

    if store:
        # 获取所有Skill键
        keys = [k for k in store.list_keys() if k.startswith("skill_gene:")]

        for key in keys:
            skill_data = store.load(key)
            if not skill_data or not isinstance(skill_data, dict):
                continue

            health_score = skill_data.get("health_score", 1.0)
            last_version_time = skill_data.get("last_version_time")

            # 判断是否需要狩猎
            should_hunt = False
            if health_score < 0.7:
                should_hunt = True
            elif last_version_time:
                try:
                    last_time = datetime.fromisoformat(last_version_time)
                    days_since = (datetime.now() - last_time).days
                    if days_since > 30:
                        should_hunt = True
                except Exception:
                    pass

            if should_hunt:
                skill_id = key.replace("skill_gene:", "")
                targets.append(
                    {
                        "skill_id": skill_id,
                        "health_score": health_score,
                        "days_since_version": days_since if last_version_time else 999,
                    }
                )

    # 执行狩猎SOP
    hunt_context = {"_asset_store": store, "_hunt_targets": targets, "_hunt_mode": "continuous"}
    hunt_context = hunt_sop(hunt_context)

    result = {
        "trigger_type": "continuous",
        "targets_found": len(targets),
        "hunt_result": hunt_context.get("_hunt_sop_result", {}),
    }

    logger.info(f"[Hunt] 持续优化搜索完成: {len(targets)} 个目标")

    context["_hunt_trigger_result"] = result
    return context


def trigger_predictive_hunt(context: dict) -> dict:
    """
    触发预测性搜索（军师分析完成后触发，定向搜索能力缺口）。

    输入 context 键：
        _integrated_briefing: 军师整合简报
        _asset_store: Asset Store 引用

    输出 context 键：
        _hunt_trigger_result: dict（触发结果）
    """
    logger.info("[Hunt] 触发预测性搜索")

    # 从军师简报中提取能力缺口（简化版）
    capability_gaps = []

    # 示例：如果Skill成功率低，则标记为缺口
    skill_analysis = context.get("_analytics_skill", {})
    if skill_analysis.get("success_rate", 1.0) < 0.8:
        capability_gaps.append(
            {
                "type": "low_success_rate",
                "description": "Skill成功率低于80%",
                "related_skills": [],  # 可从store中查询
            }
        )

    # 如果没有缺口，则退出
    if not capability_gaps:
        logger.info("[Hunt] 无能力缺口，跳过预测性搜索")
        context["_hunt_trigger_result"] = {"trigger_type": "predictive", "status": "no_gaps"}
        return context

    # 将缺口转换为狩猎目标：从 Store 中查找相关 Skill
    targets = []
    store = context.get("_asset_store")
    if store:
        for gap in capability_gaps:
            gap_type = gap.get("type", "")

            # 从 Store 查询相关 Skill
            for key in store.list_keys():
                if not key.startswith("skill_gene:"):
                    continue
                skill_id = key.replace("skill_gene:", "")
                skill_data = store.load(key)
                if not skill_data or not isinstance(skill_data, dict):
                    continue

                # 低成功率缺口：匹配所有 Skill
                if gap_type == "low_success_rate":
                    health = skill_data.get("health_score", 1.0)
                    if health < 0.8:
                        targets.append(
                            {
                                "skill_id": skill_id,
                                "health_score": health,
                                "days_since_version": 0,
                                "priority": "high",
                            }
                        )

            logger.info(f"[Hunt] 缺口 '{gap_type}' → {len(targets)} 个目标")

    # 执行狩猎SOP（如果有目标）
    if targets:
        hunt_context = {
            "_asset_store": context.get("_asset_store"),
            "_hunt_targets": targets,
            "_hunt_mode": "predictive",
        }
        hunt_context = hunt_sop(hunt_context)
        result = {
            "trigger_type": "predictive",
            "gaps_found": len(capability_gaps),
            "targets_found": len(targets),
            "hunt_result": hunt_context.get("_hunt_sop_result", {}),
        }
    else:
        result = {
            "trigger_type": "predictive",
            "gaps_found": len(capability_gaps),
            "targets_found": 0,
            "status": "no_targets",
        }

    logger.info(f"[Hunt] 预测性搜索完成: {len(capability_gaps)} 个缺口")

    context["_hunt_trigger_result"] = result
    return context


# 导出所有狩猎函数
__all__ = [
    "search_external",
    "compare_skill",
    "absorb_skill",
    "hunt_sop",
    "trigger_continuous_hunt",
    "trigger_predictive_hunt",
]
