"""
FROST-SOP 长老Agent
PHILOSOPHY: 长老是退休的祖辈。它保留独立审计权，
不参与任务执行，不干预决策。只审计，只报告。
长老是普通Agent，不是特权组件。

V2.0: 长老可订阅 TASK_COMPLETED 事件，自动执行 audit_family（fail-safe）。
V3.1: audit_family 拆分为 _scan_store / _compute_statistics /
       _generate_report / _log_audit_result 四个子函数。
"""

import logging
from datetime import datetime
from core.agent import Agent
from core.skill import Skill

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 重构子函数: audit_family 拆分为4个子函数（每个复杂度<10）
# ---------------------------------------------------------------------------


def _scan_store(asset_store) -> dict:
    """扫描资产Store，收集原始数据（tasks、lessons、键列表）"""
    raw = {
        "all_keys": [],
        "tasks": [],
        "lessons": [],
    }
    if hasattr(asset_store, 'list_keys'):
        raw["all_keys"] = asset_store.list_keys()
    for key in raw["all_keys"]:
        if key.startswith("task:"):
            data = asset_store.load(key)
            if data is not None:
                raw["tasks"].append(data)
        elif key.startswith("lesson:"):
            data = asset_store.load(key)
            if data is not None:
                raw["lessons"].append(data)
    return raw


def _compute_statistics(raw: dict) -> dict:
    """计算统计指标（成功/失败、任务数、错题本数）"""
    tasks = raw["tasks"]
    successful = 0
    failed = 0

    for task in tasks:
        if not isinstance(task, dict):
            failed += 1
            continue
        status = task.get("status", "")
        stage_results = task.get("stage_results", task.get("stages", []))
        all_completed = all(
            isinstance(s, dict) and s.get("status", "")
            in ("completed", "success")
            for s in stage_results
        )
        if status in ("completed", "success") or all_completed:
            successful += 1
        else:
            failed += 1

    return {
        "total_tasks": len(tasks),
        "successful_tasks": successful,
        "failed_tasks": failed,
        "total_lessons": len(raw["lessons"]),
    }


def _generate_report(stats: dict, tasks: list,
        lessons: list, budget=None) -> dict:
    """生成审计报告（发现和建议）"""
    total = stats["total_tasks"]
    successful = stats["successful_tasks"]
    failed = stats["failed_tasks"]
    report = {
        "status": "healthy",
        "findings": [],
        "recommendations": [],
        "statistics": dict(stats),
        # 顶层兼容字段（供测试直接读取）
        "total_tasks": total,
        "successful_tasks": successful,
        "failed_tasks": failed,
        "total_lessons": stats["total_lessons"],
    }

    if budget:
        report["statistics"]["monthly_budget"] = budget

    if total > 0:
        report["findings"].append(
            f"家族共执行{total}个任务，成功{successful}个，失败{failed}个")
    else:
        report["findings"].append("家族尚未执行任何任务")

    if stats["total_lessons"] > 0:
        report["findings"].append(
            f"错题本积累{stats['total_lessons']}条教训")

    if total > 20:
        report["recommendations"].append(
            "任务数量较多，建议考虑增加父辈Agent")

    if failed > successful * 0.3 and total >= 5:
        report["recommendations"].append(
            f"失败率较高（{failed}/{total}），建议进行SOP优化回顾")

    return report


def _log_audit_result(context: dict, report: dict, stats: dict) -> dict:
    """写入审计日志到context"""
    context["_audit_report"] = report
    context["_reason"] = (
        f"审计完成：共{stats['total_tasks']}个任务，"
        f"成功{stats['successful_tasks']}，失败{stats['failed_tasks']}，"
        f"错题本{stats['total_lessons']}条")
    return context


def check_ancestor_alive(context: dict) -> dict:
    """
    V3.2b: Dead Man's Watch — 检查祖辈是否存活。

    不依赖祖辈自我报告，直接读取 Store 中的活动记录。
    在 audit_family 中作为第一步调用。

    输入 context 键：
        _store: Store —— 资产 Store（读取祖先活动记录）
        _heartbeat_timeout_minutes: int —— 心跳超时分钟数（默认15）

    输出 context 键：
        _dead_mans_watch_report: dict —— 存活检查报告
            {
                "status": "HEALTHY" | "WARNING",
                "report": "描述文本",
                "last_heartbeat_minutes_ago": float | None,
                "last_design_minutes_ago": float | None,
            }
    """
    store = context.get("_store") or context.get("_asset_store")
    timeout_minutes = context.get("_heartbeat_timeout_minutes", 15)
    now = datetime.now()

    report_data = {
        "status": "HEALTHY",
        "report": "",
        "last_heartbeat_minutes_ago": None,
        "last_design_minutes_ago": None,
    }

    if store is None:
        report_data["status"] = "WARNING"
        report_data["report"] = "家族警告：无法读取 Store，Dead Man's Watch 无法执行。"
        context["_dead_mans_watch_report"] = report_data
        return context

    # 读取祖辈活动记录
    try:
        last_heartbeat = store.load("ancestor:last_heartbeat")
        last_task_design = store.load("ancestor:last_task_design_time")
    except Exception as e:
        logger.error("[DeadManWatch] 读取 Store 失败: %s", e)
        report_data["status"] = "WARNING"
        report_data["report"] = f"家族警告：读取祖先活动记录失败: {e}"
        context["_dead_mans_watch_report"] = report_data
        return context

    if last_heartbeat is None and last_task_design is None:
        report_data["status"] = "WARNING"
        report_data["report"] = "家族警告：无法读取祖辈活动记录，Store 可能故障。"
        context["_dead_mans_watch_report"] = report_data
        logger.warning("[DeadManWatch] %s", report_data["report"])
        return context

    # 计算空闲时间
    heartbeat_idle = None
    design_idle = None

    if last_heartbeat is not None:
        if isinstance(last_heartbeat, datetime):
            heartbeat_idle = (now - last_heartbeat).total_seconds() / 60
            report_data["last_heartbeat_minutes_ago"] = heartbeat_idle

    if last_task_design is not None:
        if isinstance(last_task_design, datetime):
            design_idle = (now - last_task_design).total_seconds() / 60
            report_data["last_design_minutes_ago"] = design_idle

    max_idle = max(
        heartbeat_idle if heartbeat_idle is not None else 0,
        design_idle if design_idle is not None else 0,
    )

    if max_idle > timeout_minutes:
        report_data["status"] = "WARNING"
        report_data["report"] = (
            f"家族警告：祖辈心跳超时，最近一次活动记录于 {max_idle:.0f} 分钟前。"
        )
        logger.warning("[DeadManWatch] %s", report_data["report"])
    else:
        hb_msg = f"心跳 {heartbeat_idle:.0f} 分钟前" if heartbeat_idle is not None else "心跳记录缺失"
        ds_msg = f"任务拆解 {design_idle:.0f} 分钟前" if design_idle is not None else "任务拆解记录缺失"
        report_data["report"] = f"家族运转正常。祖辈{hb_msg}，{ds_msg}。"
        logger.info("[DeadManWatch] %s", report_data["report"])

    context["_dead_mans_watch_report"] = report_data
    return context


def audit_family(context: dict) -> dict:
    """
    长老审计家族健康度。

    V3.2b: 增加 Dead Man's Watch（存活检查）作为第一步。

    输入 context 键：
        _asset_store: Store —— 资产Store
        _constitution_store: Store —— 宪法Store
        _store: Store —— 通用 Store（供 check_ancestor_alive 读取）

    输出 context 键：
        _audit_report: dict —— 审计报告（含 _dead_mans_watch_report）
    """

    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")

    if not asset_store:
        context["_audit_report"] = {"status": "error", "reason": "无资产Store"}
        return context

    # V3.2b: Dead Man's Watch — 第一步：检查祖辈是否存活
    context_with_store = dict(context)
    context_with_store["_store"] = asset_store  # check_ancestor_alive 读取 _store
    context_with_store = check_ancestor_alive(context_with_store)
    dead_mans_report = context_with_store.get("_dead_mans_watch_report", {})

    # 1. 扫描资产Store
    raw = _scan_store(asset_store)

    # 2. 计算统计指标
    stats = _compute_statistics(raw)

    # 3. 获取预算并生成审计报告
    budget = None
    if constitution_store:
        budget = constitution_store.load("const.budget_monthly")
    report = _generate_report(stats, raw["tasks"], raw["lessons"], budget)

    # V3.2b: 将 Dead Man's Watch 结果并入审计报告
    if dead_mans_report:
        report["dead_mans_watch"] = dead_mans_report
        if dead_mans_report.get("status") == "WARNING":
            report["status"] = "warning"
            report["findings"].append(dead_mans_report.get("report", ""))

    # 4. 写入审计日志
    return _log_audit_result(context, report, stats)


# ================================================================
# V4.0 P2: 体检监控增强
# ================================================================

def audit_health(context: dict) -> dict:
    """
    体检监控：长老健康检查增强。
    包含：方向漂移检测、宪法规则效果追踪。
    
    输入 context 键：
        _asset_store: Store —— 资产 Store
        _constitution_store: Store —— 宪法 Store
        _health_check_type: str —— 检查类型（routine / drift / rule_effect）
    
    输出 context 键：
        _health_report: dict —— 健康检查报告
        _drift_detected: bool —— 是否检测到方向漂移
        _rule_effects: dict —— 宪法规则效果分析
    """
    asset_store = context.get("_asset_store")
    constitution_store = context.get("_constitution_store")
    check_type = context.get("_health_check_type", "routine")
    
    health_report = {
        "checked_at": datetime.now().isoformat(),
        "check_type": check_type,
        "status": "healthy",
        "findings": [],
    }
    
    # 1. 常规健康检查
    if asset_store:
        # 检查任务成功率
        tasks = []
        for key in asset_store.list_keys():
            if key.startswith("task:"):
                task_data = asset_store.load(key)
                if task_data:
                    tasks.append(task_data)
        
        if tasks:
            recent = tasks[:20]  # 最近20个任务
            success = sum(1 for t in recent if t.get("status") in ("completed", "success"))
            success_rate = success / len(recent)
            
            health_report["recent_tasks"] = len(recent)
            health_report["success_rate"] = success_rate
            
            if success_rate < 0.5:
                health_report["status"] = "warning"
                health_report["findings"].append(f"最近 {len(recent)} 个任务成功率仅 {success_rate:.0%}")
    
    # 2. 方向漂移检测（军师方向漂移检测）
    if check_type in ("drift", "full"):
        drift_detected = _detect_direction_drift(context)
        health_report["drift_detected"] = drift_detected
        context["_drift_detected"] = drift_detected
        
        if drift_detected:
            health_report["status"] = "warning"
            health_report["findings"].append("检测到分析方向漂移，建议审查军师参数")
    
    # 3. 宪法规则效果追踪
    if check_type in ("rule_effect", "full"):
        rule_effects = _track_constitution_rule_effects(context)
        health_report["rule_effects"] = rule_effects
        context["_rule_effects"] = rule_effects
        
        # 检查是否有规则效果异常
        for rule_id, effect in rule_effects.items():
            if effect.get("trigger_count", 0) > 10 and effect.get("failure_rate", 0) > 0.3:
                health_report["status"] = "warning"
                health_report["findings"].append(
                    f"规则 {rule_id} 触发 {effect['trigger_count']} 次，失败率 {effect['failure_rate']:.0%}"
                )
    
    context["_health_report"] = health_report
    context["_reason"] = f"健康检查完成（{check_type}）：{health_report['status']}"
    return context


def _detect_direction_drift(context: dict) -> bool:
    """
    检测军师分析方向是否漂移。
    方法：对比最近3次分析结果的主题一致性。
    """
    asset_store = context.get("_asset_store")
    if not asset_store:
        return False
    
    # 读取最近3次军师分析简报
    briefings = []
    for key in asset_store.list_keys():
        if key.startswith("briefing:"):
            briefing = asset_store.load(key)
            if briefing:
                briefings.append(briefing)
    
    if len(briefings) < 3:
        return False  # 数据不足
    
    # 简化：检查是否有连续不同的建议主题
    recent = briefings[-3:]
    topics = [b.get("main_topic", "") for b in recent]
    
    # 如果3次主题都不同，认为是漂移
    if len(set(topics)) == 3:
        return True
    
    return False


def _track_constitution_rule_effects(context: dict) -> dict:
    """
    追踪宪法规则效果。
    返回：{rule_id: {trigger_count, success_count, failure_rate}}
    """
    constitution_store = context.get("_constitution_store")
    asset_store = context.get("_asset_store")
    
    if not constitution_store or not asset_store:
        return {}
    
    # 读取宪法规则
    rules = constitution_store.load("constitution:rules") or []
    
    # 统计每个规则的触发效果
    effects = {}
    for rule in rules:
        rule_id = rule.get("id", "unknown")
        effects[rule_id] = {
            "trigger_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "failure_rate": 0.0,
        }
    
    # 扫描任务历史，统计规则效果
    for key in asset_store.list_keys():
        if key.startswith("task:"):
            task_data = asset_store.load(key)
            if not task_data:
                continue
            
            # 检查任务是否触发了宪法规则
            triggered_rules = task_data.get("triggered_rules", [])
            for rule_id in triggered_rules:
                if rule_id in effects:
                    effects[rule_id]["trigger_count"] += 1
                    if task_data.get("status") in ("completed", "success"):
                        effects[rule_id]["success_count"] += 1
                    else:
                        effects[rule_id]["failure_count"] += 1
    
    # 计算失败率
    for rule_id in effects:
        total = effects[rule_id]["trigger_count"]
        if total > 0:
            effects[rule_id]["failure_rate"] = effects[rule_id]["failure_count"] / total
    
    return effects


# ================================================================
# V4.0 P2: 治理系统数据驱动修订
# ================================================================

def track_rule_effects(context: dict) -> dict:
    """
    追踪宪法规则效果（增强版）。
    
    每个宪法规则关联：
    - trigger_count: 触发次数
    - success_count: 成功次数
    - failure_count: 失败次数
    - failure_rate: 失败率
    - complaint_count: 投诉次数（用户反馈）
    
    输入 context 键：
        _constitution_store: Store —— 宪法 Store
        _asset_store: Store —— 资产 Store
    
    输出 context 键：
        _rule_effects: dict —— 规则效果统计
        _rules_need_revision: list —— 需要修订的规则ID列表
    """
    constitution_store = context.get("_constitution_store")
    asset_store = context.get("_asset_store")
    
    if not constitution_store or not asset_store:
        context["_rule_effects"] = {}
        context["_rules_need_revision"] = []
        return context
    
    # 读取宪法规则（增强：包含 complaint_count）
    rules = constitution_store.load("constitution:rules") or []
    
    # 初始化规则效果统计
    effects = {}
    for rule in rules:
        rule_id = rule.get("id", "unknown")
        effects[rule_id] = {
            "rule_id": rule_id,
            "rule_text": rule.get("text", ""),
            "trigger_count": rule.get("trigger_count", 0),
            "success_count": rule.get("success_count", 0),
            "failure_count": rule.get("failure_count", 0),
            "complaint_count": rule.get("complaint_count", 0),
            "failure_rate": 0.0,
            "complaint_rate": 0.0,
        }
    
    # 扫描任务历史，统计规则效果
    for key in asset_store.list_keys():
        if key.startswith("task:"):
            task_data = asset_store.load(key)
            if not task_data:
                continue
            
            # 检查任务是否触发了宪法规则
            triggered_rules = task_data.get("triggered_rules", [])
            for rule_id in triggered_rules:
                if rule_id in effects:
                    effects[rule_id]["trigger_count"] += 1
                    if task_data.get("status") in ("completed", "success"):
                        effects[rule_id]["success_count"] += 1
                    else:
                        effects[rule_id]["failure_count"] += 1
    
    # 扫描投诉记录（从 lesson: 键读取）
    for key in asset_store.list_keys():
        if key.startswith("lesson:"):
            lesson_data = asset_store.load(key)
            if not lesson_data:
                continue
            
            # 检查是否与宪法规则相关
            related_rule = lesson_data.get("related_rule", "")
            if related_rule and related_rule in effects:
                effects[related_rule]["complaint_count"] += 1
    
    # 计算失败率和投诉率
    for rule_id in effects:
        total = effects[rule_id]["trigger_count"]
        if total > 0:
            effects[rule_id]["failure_rate"] = effects[rule_id]["failure_count"] / total
            effects[rule_id]["complaint_rate"] = effects[rule_id]["complaint_count"] / total
    
    # 识别需要修订的规则（失败率 > 30% 或 投诉率 > 20%）
    rules_need_revision = []
    for rule_id, effect in effects.items():
        if effect["trigger_count"] >= 5:  # 至少触发5次才统计
            if effect["failure_rate"] > 0.3 or effect["complaint_rate"] > 0.2:
                rules_need_revision.append(rule_id)
    
    # 更新到 constitution store（持久化统计）
    try:
        for rule_id, effect in effects.items():
            rule_key = f"constitution:rule_effect:{rule_id}"
            constitution_store.save(rule_key, effect)
    except Exception as e:
        logger.warning("[Governance] 持久化规则效果失败: %s", e)
    
    context["_rule_effects"] = effects
    context["_rules_need_revision"] = rules_need_revision
    return context


def generate_revision_suggestions(context: dict) -> dict:
    """
    生成规则修订建议。
    
    当规则导致 > 30% 相关任务失败时，长老自动生成修订建议。
    
    输入 context 键：
        _rule_effects: dict —— 规则效果统计（来自 track_rule_effects）
        _constitution_store: Store —— 宪法 Store
    
    输出 context 键：
        _revision_suggestions: list —— 修订建议列表
            [{
                "rule_id": "rule_xxx",
                "rule_text": "原规则文本",
                "problem": "问题描述",
                "suggestion": "修订建议",
                "risk_level": "low" | "medium" | "high",
                "auto_apply": bool,  # 是否自动生效
            }]
    """
    rule_effects = context.get("_rule_effects", {})
    constitution_store = context.get("_constitution_store")
    
    suggestions = []
    
    for rule_id, effect in rule_effects.items():
        if rule_id not in context.get("_rules_need_revision", []):
            continue  # 不需要修订
        
        # 生成修订建议
        problem = ""
        suggestion = ""
        risk_level = "medium"
        
        if effect["failure_rate"] > 0.5:
            problem = f"规则失败率过高（{effect['failure_rate']:.0%}）"
            suggestion = f"建议放宽规则约束，或拆分为多个子规则"
            risk_level = "high"
        elif effect["failure_rate"] > 0.3:
            problem = f"规则失败率偏高（{effect['failure_rate']:.0%}）"
            suggestion = f"建议优化规则表述，减少歧义"
            risk_level = "medium"
        
        if effect["complaint_rate"] > 0.2:
            problem += f"；投诉率偏高（{effect['complaint_rate']:.0%}）"
            suggestion += f"；建议收集用户反馈，调整规则优先级"
            if risk_level == "low":
                risk_level = "medium"
        
        if problem:
            # 判断是否需要君主审批
            auto_apply = False
            if risk_level == "low":
                auto_apply = True
            elif risk_level == "medium":
                # 低风险调整自动生效（如预算预警比例从80%→85%）
                if "预算" in effect["rule_text"] or "预警" in effect["rule_text"]:
                    auto_apply = True
            
            suggestions.append({
                "rule_id": rule_id,
                "rule_text": effect["rule_text"],
                "problem": problem,
                "suggestion": suggestion,
                "failure_rate": effect["failure_rate"],
                "complaint_rate": effect["complaint_rate"],
                "risk_level": risk_level,
                "auto_apply": auto_apply,
                "created_at": datetime.now().isoformat(),
            })
    
    # 按风险等级排序（high → medium → low）
    risk_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: risk_order.get(x["risk_level"], 1))
    
    context["_revision_suggestions"] = suggestions
    return context


def apply_revision(context: dict) -> dict:
    """
    应用规则修订。
    
    分级修订权限：
    - 低风险调整（如预算预警比例从80%→85%）自动生效
    - 高风险调整（如新增合规约束）需要君主审批
    
    输入 context 键：
        _revision_suggestions: list —— 修订建议列表
        _monarch_approved: list —— 君主已批准的建议ID列表
        _constitution_store: Store —— 宪法 Store
    
    输出 context 键：
        _applied_revisions: list —— 已应用的修订
        _pending_approvals: list —— 等待审批的修订
    """
    suggestions = context.get("_revision_suggestions", [])
    monarch_approved = context.get("_monarch_approved", [])
    constitution_store = context.get("_constitution_store")
    
    applied = []
    pending = []
    
    for suggestion in suggestions:
        if suggestion["auto_apply"]:
            # 自动生效
            applied.append({
                "rule_id": suggestion["rule_id"],
                "suggestion": suggestion["suggestion"],
                "applied_at": datetime.now().isoformat(),
                "applied_by": "auto",
            })
            
            # 更新宪法规则
            if constitution_store:
                try:
                    rules = constitution_store.load("constitution:rules") or []
                    for rule in rules:
                        if rule.get("id") == suggestion["rule_id"]:
                            rule["text"] = suggestion["suggestion"]
                            rule["last_revised_at"] = datetime.now().isoformat()
                            rule["revision_history"] = rule.get("revision_history", [])
                            rule["revision_history"].append({
                                "from": suggestion["rule_text"],
                                "to": suggestion["suggestion"],
                                "reason": suggestion["problem"],
                                "applied_at": datetime.now().isoformat(),
                            })
                            break
                    constitution_store.save("constitution:rules", rules)
                except Exception as e:
                    logger.warning("[Governance] 应用规则修订失败: %s", e)
        
        elif suggestion["rule_id"] in monarch_approved:
            # 君主已批准
            applied.append({
                "rule_id": suggestion["rule_id"],
                "suggestion": suggestion["suggestion"],
                "applied_at": datetime.now().isoformat(),
                "applied_by": "monarch",
            })
            
            # 更新宪法规则（同上）
            if constitution_store:
                try:
                    rules = constitution_store.load("constitution:rules") or []
                    for rule in rules:
                        if rule.get("id") == suggestion["rule_id"]:
                            rule["text"] = suggestion["suggestion"]
                            rule["last_revised_at"] = datetime.now().isoformat()
                            break
                    constitution_store.save("constitution:rules", rules)
                except Exception as e:
                    logger.warning("[Governance] 应用规则修订失败: %s", e)
        
        else:
            # 等待审批
            pending.append({
                "rule_id": suggestion["rule_id"],
                "suggestion": suggestion["suggestion"],
                "risk_level": suggestion["risk_level"],
                "created_at": suggestion["created_at"],
            })
    
    context["_applied_revisions"] = applied
    context["_pending_approvals"] = pending
    return context


# ================================================================
# 长老 Agent 工厂
# ================================================================

def create_elder(name: str = "elder", asset_store=None,
        constitution_store=None) -> Agent:
    """创建长老Agent"""
    skills = {
        "audit_family": Skill("audit_family", audit_family),
        # V4.0 P2: 体检监控
        "audit_health": Skill("audit_health", audit_health),
        # V4.0 P2: 治理系统数据驱动修订
        "track_rule_effects": Skill("track_rule_effects", track_rule_effects),
        "generate_revision_suggestions": Skill("generate_revision_suggestions", generate_revision_suggestions),
        "apply_revision": Skill("apply_revision", apply_revision),
    }
    return Agent(
        name=name,
        store=asset_store,
        skills=skills,
        generation=0,
        max_spawn_generation=0,
    )


audit_family_skill = Skill("audit_family", audit_family)

# V4.0 P2: 体检监控
audit_health_skill = Skill("audit_health", audit_health)

# V4.0 P2: 治理系统数据驱动修订
track_rule_effects_skill = Skill("track_rule_effects", track_rule_effects)
generate_revision_suggestions_skill = Skill("generate_revision_suggestions", generate_revision_suggestions)
apply_revision_skill = Skill("apply_revision", apply_revision)


# ---------------------------------------------------------------------------
# V2.0: 长老事件驱动——订阅 TASK_COMPLETED，自动执行审计
# ---------------------------------------------------------------------------

def _make_elder_event_handler(elder_agent: "Agent"):
    """创建长老的 TASK_COMPLETED 事件处理函数。"""
    def _on_task_completed(event):
        try:
            ctx = {
                "_asset_store": elder_agent.store,
                "_constitution_store": None,
                "_triggered_by_event": True,
                "_event_task_id": (
                    event.data.get("task_id", "") if event.data else ""),
            }
            audit_family(ctx)
            logger.info("自动审计完成（事件触发）: %s",
                ctx.get('_reason', '已完成'))
        except Exception as e:
            import warnings
            warnings.warn(
                f"[Elder] TASK_COMPLETED 自动审计失败（已忽略）: {e}")

    return _on_task_completed


def subscribe_elder_to_events(elder_agent: "Agent") -> bool:
    """让长老订阅 TASK_COMPLETED 事件。"""
    try:
        from core.event_bus import get_event_bus, EventType
        bus = get_event_bus()
        handler = _make_elder_event_handler(elder_agent)
        bus.subscribe(EventType.TASK_COMPLETED, handler)
        elder_agent._event_handler = handler
        return True
    except Exception as e:
        import warnings
        warnings.warn(f"[Elder] 事件订阅失败（已忽略）: {e}")
        return False
