FROST-SOP 选择B：完整闭环补全 + 运营能力扩展
开发、测试与第三方审计全量指令

========== 文档版本 ==========
版本：v1.0
选择：B（步骤1同时补全执行闭环+狩猎闭环，步骤2扩展运营能力）
日期：2026-07-02
执行者：WorkBuddy

========== 一、总体范围 ==========

选择B的范围：
  Phase 1（3-5天）：补全两条闭环
    - 1A. 执行→复盘闭环（finalize_task触发链补全）
    - 1B. 狩猎→进化闭环（hunt_and_evolve入口+事件连接）
    - 1C. APScheduler定时器集成
    - 1D. 事件总线订阅链完整化

  Phase 2（3-5天）：运营能力扩展
    - 2A. 运营SOP模板（REDBOOK-001, JUEJIN-001, EMAIL-001）
    - 2B. content-writer Skill（DeepSeek API）
    - 2C. 掘金发布 Skill（cookie-based）
    - 2D. 邮件发送 Skill（Buttondown/Resend）
    - 2E. 运营基因初始化

  Phase 3（2-3天）：测试与验证
    - 3A. 单元测试（新增模块）
    - 3B. 集成测试（端到端闭环）
    - 3C. 回归测试（确保不破坏现有功能）
    - 3D. 性能测试（定时器负载）
    - 3E. 安全审计（新增API密钥管理）

  Phase 4（1天）：第三方审计包
    - 4A. 审计文档
    - 4B. 审计数据包

总工作量：9-14天（瀑布式）

========== 二、技术约束清单 ==========

CT-001. Python 版本：3.13.x（已验证）
CT-002. 测试串行：pytest-xdist不可用，必须串行执行
CT-003. pytest 参数：需要 -s 参数（capture模块兼容）
CT-004. SQLite 并发：单线程/WAL模式，busy_timeout=5000
CT-005. Token预算：月度¥300，单次调用成本需监控
CT-006. 外部API密钥：
  - DeepSeek API：sk-a85a27ed0a224f709de978601d93e69a（已提供）
  - 掘金：sessionid=7c15996405f758a3c9e32e8975a99b3d（已提供）
  - 邮件：Buttondown/Resend（后续配置）
CT-007. 安全：所有新密钥必须走 core/secrets.py 加密存储
CT-008. 代码风格：ruff 0.15.20，行长120，中文注释
CT-009. 复杂度：子函数复杂度<10，McCabe cyclomatic
CT-010. 向后兼容：所有V2/V3/V4事件订阅保持可用

========== 三、Phase 1A：执行→复盘闭环补全 ==========

目标：让 finalize_task 在任务完成后自动触发完整的分析+进化链。

3.1 修改文件：skills/orchestration.py

修改点1：finalize_task() 函数（第807行附近）
  在现有代码的 audit_thread.start() 之后，添加：

  a) 军师分析后台线程：
  analytics_thread = threading.Thread(
      target=_trigger_analytics_briefing,
      args=(task_id, asset_store, constitution_store),
      daemon=True,
      name=f"analytics_{task_id[:8]}",
  )
  analytics_thread.start()

  b) 自进化后台线程：
  evolution_thread = threading.Thread(
      target=_trigger_evolution_analysis,
      args=(task_id, asset_store),
      daemon=True,
      name=f"evolution_{task_id[:8]}",
  )
  evolution_thread.start()

  并将两个线程引用存入 context，供测试验证：
  context["_analytics_thread"] = analytics_thread
  context["_evolution_thread"] = evolution_thread

新增函数：_trigger_analytics_briefing()
  位置：skills/orchestration.py，在 finalize_task 之后
  复杂度：拆分为3个子函数（每个<10）

  流程：
  1. 从 asset_store 加载所有 collector 数据
  2. 调用 skills.analytics 的6个分析函数（light模式）
  3. 调用 integrate_briefings() 生成整合简报
  4. 将简报保存到 asset_store："briefing:{task_id}"
  5. 将简报内容写入 audit_log（供审计）
  6. 如果预算使用率>80%，记录 warning

  失败处理：每个步骤失败仅记录日志，不影响主流程

  具体实现：
  def _trigger_analytics_briefing(task_id, asset_store, constitution_store):
      """后台线程：触发军师分析"""
      try:
          from skills.analytics import (
              analyze_finance, analyze_skill, analyze_task,
              analyze_audit, analyze_heartbeat, analyze_hunt,
              integrate_briefings,
          )
          from skills.collectors import _write_collected_data

          logger.info("[Analytics] 后台分析开始: %s", task_id)

          # 构造分析上下文
          ctx = {"_asset_store": asset_store, "_analysis_depth": "light"}

          # 顺序执行6个分析（light模式不调用LLM，成本0）
          ctx = analyze_finance(ctx)
          ctx = analyze_skill(ctx)
          ctx = analyze_task(ctx)
          ctx = analyze_audit(ctx)
          ctx = analyze_heartbeat(ctx)
          ctx = analyze_hunt(ctx)

          # 整合简报
          ctx = integrate_briefings(ctx)
          briefing = ctx.get("_integrated_briefing", {})

          # 保存到 Store
          if asset_store:
              asset_store.save(f"briefing:{task_id}", briefing)

          # 写入 audit_log
          from core.db import get_db
          db = get_db()
          db.log_audit({
              "agent_id": f"analytics_{task_id[:8]}",
              "action": "briefing_generated",
              "details": str(briefing)[:500],
              "level": "info",
          })

          # 检查预算预警
          finance = ctx.get("_analytics_finance", {})
          if finance.get("budget_usage_rate", 0) > 0.8:
              logger.warning("[Analytics] 预算使用率超过80%%")
              db.log_audit({
                  "agent_id": "system",
                  "action": "budget_alert",
                  "details": f"budget_usage={finance['budget_usage_rate']:.1%}",
                  "level": "warning",
              })

          logger.info("[Analytics] 后台分析完成: %s", task_id)

      except Exception as e:
          logger.warning("[Analytics] 后台分析失败（不影响任务）: %s", e)
          try:
              from core.db import get_db
              get_db().log_audit({
                  "agent_id": "analytics",
                  "action": "briefing_failed",
                  "details": str(e)[:200],
                  "level": "warning",
              })
          except Exception:
              pass

新增函数：_trigger_evolution_analysis()
  位置：skills/orchestration.py，在 _trigger_analytics_briefing 之后
  复杂度：拆分为2个子函数（每个<10）

  流程：
  1. 从 asset_store 加载任务历史
  2. 调用 analyze_trends() 分析趋势
  3. 调用 generate_suggestions() 生成建议
  4. 如果建议非空，调用 present_for_approval() 生成报告
  5. 将报告保存到 asset_store："evolution:{task_id}"
  6. 如果建议涉及 SOP 优化，自动调用 manage_sop_version()

  具体实现：
  def _trigger_evolution_analysis(task_id, asset_store):
      """后台线程：触发自进化分析"""
      try:
          from skills.evolution import (
              load_task_history, analyze_trends,
              generate_suggestions, present_for_approval,
              manage_sop_version,
          )

          logger.info("[Evolution] 后台进化分析开始: %s", task_id)

          ctx = {"_asset_store": asset_store, "_history_limit": 20}

          # 加载历史 → 分析趋势 → 生成建议
          ctx = load_task_history(ctx)
          ctx = analyze_trends(ctx)
          ctx = generate_suggestions(ctx)

          suggestions = ctx.get("_suggestions", [])

          if suggestions:
              # 生成报告
              ctx = present_for_approval(ctx)
              report = ctx.get("_approval_report", "")

              # 保存
              if asset_store:
                  asset_store.save(f"evolution:{task_id}", {
                      "report": report,
                      "suggestions": suggestions,
                      "timestamp": datetime.now().isoformat(),
                  })

              # 如果有 SOP 优化建议，自动创建 v2
              for s in suggestions:
                  if s.get("type") == "sop_optimization":
                      ctx["_sop_optimization"] = s
                      ctx = manage_sop_version(ctx)
                      if ctx.get("_sop_version_created"):
                          logger.info("[Evolution] 自动创建 SOP v2")

          logger.info("[Evolution] 后台进化分析完成: %s", task_id)

      except Exception as e:
          logger.warning("[Evolution] 后台进化分析失败（不影响任务）: %s", e)

3.2 新增事件订阅（EventBus连接）

修改点：core/event_bus.py
  在现有事件类型基础上，新增：
  HUNT_COMPLETED = "hunt_completed"
  BRIEFING_INTEGRATED = "briefing_integrated"
  EVOLUTION_SUGGESTED = "evolution_suggested"
  SCHEDULED_EXECUTED = "scheduled_executed"

  这些事件类型供狩猎链使用。

========== 四、Phase 1B：狩猎→进化闭环 ==========

目标：创建 hunt_and_evolve() 入口，让狩猎完成后自动触发分析+进化。

4.1 新增文件：skills/hunt_orchestration.py

PHILOSOPHY：狩猎不是孤立动作，是闭环的起点。

代码结构：
  - hunt_and_evolve() — 主入口，复杂度<15
  - _run_hunt_phase() — 狩猎阶段
  - _run_analysis_phase() — 分析阶段
  - _run_integration_phase() — 整合阶段
  - _run_evolution_phase() — 进化阶段
  - _run_execution_schedule() — 执行安排阶段

完整实现：
"""
import logging
import threading
from datetime import datetime

from core.skill import Skill
from skills.hunt import hunt_sop
from skills.analytics import integrate_briefings
from skills.evolution import (
    load_task_history, analyze_trends,
    generate_suggestions, present_for_approval, manage_sop_version,
    update_skill_graph,
)
from skills.knowledge import archive_sop

logger = logging.getLogger(__name__)


def _run_hunt_phase(context: dict) -> dict:
    """子函数：执行狩猎阶段"""
    logger.info("[HuntOrchestration] Phase 1: 狩猎")
    context = hunt_sop(context)
    hunt_result = context.get("_hunt_sop_result", {})
    logger.info("[HuntOrchestration] 狩猎完成: absorbed=%s, rejected=%s",
                hunt_result.get("absorbed_count", 0),
                hunt_result.get("rejected_count", 0))
    return context


def _run_analysis_phase(context: dict) -> dict:
    """子函数：执行分析阶段（使用light模式，0成本）"""
    logger.info("[HuntOrchestration] Phase 2: 分析")

    # 先调用6个单维度分析（light模式）
    from skills.analytics import (
        analyze_finance, analyze_skill, analyze_task,
        analyze_audit, analyze_heartbeat, analyze_hunt,
    )

    ctx = dict(context)
    ctx["_analysis_depth"] = "light"

    ctx = analyze_finance(ctx)
    ctx = analyze_skill(ctx)
    ctx = analyze_task(ctx)
    ctx = analyze_audit(ctx)
    ctx = analyze_heartbeat(ctx)
    ctx = analyze_hunt(ctx)

    # 整合简报
    ctx = integrate_briefings(ctx)

    # 合并回主context
    context["_analytics_finance"] = ctx.get("_analytics_finance")
    context["_analytics_skill"] = ctx.get("_analytics_skill")
    context["_analytics_task"] = ctx.get("_analytics_task")
    context["_analytics_audit"] = ctx.get("_analytics_audit")
    context["_analytics_heartbeat"] = ctx.get("_analytics_heartbeat")
    context["_analytics_hunt"] = ctx.get("_analytics_hunt")
    context["_integrated_briefing"] = ctx.get("_integrated_briefing")

    briefing = ctx.get("_integrated_briefing", {})
    logger.info("[HuntOrchestration] 分析完成: correlations=%s",
                len(briefing.get("correlations", [])))
    return context


def _run_integration_phase(context: dict) -> dict:
    """子函数：整合吸收阶段"""
    logger.info("[HuntOrchestration] Phase 3: 整合")

    hunt_result = context.get("_hunt_sop_result", {})
    asset_store = context.get("_asset_store")
    actions = []

    # 3.1 归档狩猎结果
    if hunt_result.get("absorbed_count", 0) > 0:
        # 将狩猎结果归档为 SOP 知识
        sop_data = {
            "sop_id": f"hunt_{datetime.now().strftime('%Y%m%d')}",
            "name": "狩猎结果",
            "content": hunt_result,
        }
        archive_ctx = {
            "_sop_to_archive": sop_data,
            "_sop_source": "hunt",
            "_asset_store": asset_store,
        }
        archive_ctx = archive_sop(archive_ctx)
        if archive_ctx.get("_archive_result", {}).get("success"):
            actions.append("归档狩猎结果")

    # 3.2 更新技能图
    absorb_results = hunt_result.get("absorb_results", [])
    for result in absorb_results:
        if result.get("action") == "absorbed":
            skill_id = result.get("new_skill_id")
            if skill_id:
                context["_new_skill_id"] = skill_id
                context = update_skill_graph(context)
                actions.append(f"更新技能图: {skill_id}")

    # 3.3 保存简报到知识库
    briefing = context.get("_integrated_briefing", {})
    if briefing and asset_store:
        asset_store.save(
            f"briefing:hunt_{datetime.now().strftime('%Y%m%d')}",
            briefing
        )
        actions.append("保存整合简报")

    context["_integration_actions"] = actions
    logger.info("[HuntOrchestration] 整合完成: %s", actions)
    return context


def _run_evolution_phase(context: dict) -> dict:
    """子函数：进化阶段"""
    logger.info("[HuntOrchestration] Phase 4: 进化")

    asset_store = context.get("_asset_store")
    ctx = dict(context)
    ctx["_history_limit"] = 20

    # 4.1 加载历史 → 分析趋势
    ctx = load_task_history(ctx)
    ctx = analyze_trends(ctx)
    ctx = generate_suggestions(ctx)

    suggestions = ctx.get("_suggestions", [])
    evolution_actions = []

    if suggestions:
        # 4.2 生成报告
        ctx = present_for_approval(ctx)
        report = ctx.get("_approval_report", "")

        # 4.3 如果有SOP优化建议，创建v2
        for s in suggestions:
            if s.get("type") == "sop_optimization":
                ctx["_sop_optimization"] = s
                ctx = manage_sop_version(ctx)
                if ctx.get("_sop_version_created"):
                    evolution_actions.append(
                        f"SOP优化: {s.get('target')} → v2"
                    )

        # 保存进化报告
        if asset_store:
            asset_store.save(
                f"evolution:hunt_{datetime.now().strftime('%Y%m%d')}",
                {
                    "report": report,
                    "suggestions": suggestions,
                    "actions": evolution_actions,
                }
            )

    context["_evolution_suggestions"] = suggestions
    context["_evolution_actions"] = evolution_actions
    logger.info("[HuntOrchestration] 进化完成: %s条建议", len(suggestions))
    return context


def _run_execution_schedule(context: dict) -> dict:
    """子函数：执行安排阶段（如果设置了自动执行）"""
    logger.info("[HuntOrchestration] Phase 5: 执行安排")

    if not context.get("_auto_execute", False):
        logger.info("[HuntOrchestration] 自动执行关闭，跳过")
        context["_scheduled_actions"] = ["自动执行关闭"]
        return context

    # 检查是否有新创建的SOP版本
    evolution_actions = context.get("_evolution_actions", [])
    scheduled = []

    for action in evolution_actions:
        if "SOP优化" in action:
            # 安排下周执行新SOP
            try:
                from core.scheduler import FrostScheduler
                scheduler = FrostScheduler(context.get("_asset_store"))
                scheduler.schedule_sop(
                    sop_id=action.split("→")[0].strip().replace("SOP优化: ", ""),
                    cron_expr="0 9 * * 1"  # 下周一9:00
                )
                scheduled.append(action)
            except Exception as e:
                logger.warning("[HuntOrchestration] 安排执行失败: %s", e)

    context["_scheduled_actions"] = scheduled
    logger.info("[HuntOrchestration] 安排完成: %s", scheduled)
    return context


def hunt_and_evolve(context: dict) -> dict:
    """
    狩猎→分析→整合→进化→执行安排 完整闭环入口。

    输入 context 键：
        _hunt_targets: 狩猎目标列表（可选，默认从配置文件加载）
        _hunt_mode: 狩猎模式（"continuous" / "predictive"）
        _asset_store: Store
        _auto_execute: bool — 是否自动执行新SOP（默认False）

    输出 context 键：
        _hunt_evolution_result: dict — 完整闭环结果
    """
    start_time = datetime.now()
    logger.info("=" * 60)
    logger.info("[HuntOrchestration] 狩猎进化闭环开始")
    logger.info("=" * 60)

    # Phase 1: 狩猎
    context = _run_hunt_phase(context)

    # Phase 2: 分析
    context = _run_analysis_phase(context)

    # Phase 3: 整合
    context = _run_integration_phase(context)

    # Phase 4: 进化
    context = _run_evolution_phase(context)

    # Phase 5: 执行安排
    context = _run_execution_schedule(context)

    # 汇总结果
    duration = (datetime.now() - start_time).total_seconds()
    result = {
        "status": "completed",
        "duration_seconds": duration,
        "hunt": context.get("_hunt_sop_result", {}),
        "briefing": context.get("_integrated_briefing", {}),
        "integration": context.get("_integration_actions", []),
        "evolution": {
            "suggestions": len(context.get("_evolution_suggestions", [])),
            "actions": context.get("_evolution_actions", []),
        },
        "schedule": context.get("_scheduled_actions", []),
    }

    context["_hunt_evolution_result"] = result
    context["_reason"] = f"狩猎进化闭环完成: {duration:.1f}s, {result['evolution']['suggestions']}条建议"

    logger.info("=" * 60)
    logger.info("[HuntOrchestration] 闭环完成: %s", result["_reason"])
    logger.info("=" * 60)

    return context


# Skill 实例
hunt_and_evolve_skill = Skill("hunt_and_evolve", hunt_and_evolve)
"""

4.2 CLI入口修改

修改文件：main.py

在 main_cli() 的 argparse 中添加：
  parser.add_argument("--hunt", action="store_true", help="触发狩猎进化闭环")
  parser.add_argument("--hunt-target", type=str, default=None, help="狩猎目标Skill ID")
  parser.add_argument("--hunt-mode", type=str, default="continuous",
                      choices=["continuous", "predictive"])
  parser.add_argument("--auto-execute", action="store_true",
                      help="自动执行狩猎产生的新SOP")

在 args 处理中添加：
  if args.hunt:
      from skills.hunt_orchestration import hunt_and_evolve
      from stores.asset import create_asset_store

      asset_store = create_asset_store()
      context = {
          "_asset_store": asset_store,
          "_hunt_targets": [{"skill_id": args.hunt_target}] if args.hunt_target else None,
          "_hunt_mode": args.hunt_mode,
          "_auto_execute": args.auto_execute,
      }
      result = hunt_and_evolve(context)
      print(json.dumps(result.get("_hunt_evolution_result"),
                       indent=2, ensure_ascii=False))
      return

========== 五、Phase 1C：APScheduler定时器集成 ==========

目标：让系统能定时自动执行SOP和狩猎。

5.1 新增文件：core/scheduler.py

依赖：pip install apscheduler

代码结构：
  - FrostScheduler 类
  - schedule_sop() — 定时执行SOP
  - schedule_hunt() — 定时狩猎
  - schedule_daily_snapshot() — 每日快照
  - schedule_weekly_retrospective() — 周度复盘
  - start() / stop() / get_jobs()
  - 所有操作记录到 audit_log

完整实现要求：
  - 使用 BackgroundScheduler（非BlockingScheduler）
  - 所有任务在后台线程执行
  - 任务失败记录 audit_log，不阻塞调度器
  - 支持从数据库加载持久化任务（调度器重启不丢失）
  - 提供 REST API：/api/schedule（已有list/add），新增 /api/scheduler/jobs

5.2 数据库表扩展

在 core/db.py 的初始化中添加：
  CREATE TABLE IF NOT EXISTS scheduled_jobs (
      id TEXT PRIMARY KEY,
      job_type TEXT NOT NULL, -- "sop" / "hunt" / "snapshot" / "retrospective"
      target_id TEXT, -- SOP ID 或 Skill ID
      cron_expr TEXT NOT NULL,
      enabled INTEGER DEFAULT 1,
      last_run TEXT,
      next_run TEXT,
      run_count INTEGER DEFAULT 0,
      fail_count INTEGER DEFAULT 0,
      created_at TEXT,
      updated_at TEXT
  );

5.3 定时任务配置示例

在 constitution_store 中预置：
  "const.schedule.redbook": "0 9 * * 1",     # 每周一9:00
  "const.schedule.juejin": "0 10 * * 3",     # 每周三10:00
  "const.schedule.email": "0 14 * * 3",       # 每周三14:00
  "const.schedule.snapshot": "0 22 * * *",     # 每日22:00
  "const.schedule.retrospective": "0 20 * * 0", # 每周日20:00
  "const.schedule.hunt": "0 2 * * *",          # 每日凌晨2:00

========== 六、Phase 1D：事件总线订阅链完整化 ==========

目标：让事件能跨模块自动触发。

6.1 新增事件类型

在 core/event_bus.py 的 EventType 中添加：
  HUNT_COMPLETED = "hunt_completed"
  BRIEFING_INTEGRATED = "briefing_integrated"
  EVOLUTION_SUGGESTED = "evolution_suggested"
  SCHEDULED_EXECUTED = "scheduled_executed"
  DAILY_SNAPSHOT_COMPLETED = "daily_snapshot_completed"
  WEEKLY_RETROSPECTIVE_COMPLETED = "weekly_retrospective_completed"

6.2 事件订阅注册

新增文件：core/event_subscribers.py

该文件集中注册所有跨模块的事件订阅：
  - 狩猎完成 → 触发分析
  - 简报整合 → 触发知识归档
  - 进化建议 → 触发SOP版本管理
  - 定时执行 → 触发SOP运行
  - 任务完成 → 触发审计（已有）

实现原则：
  - 每个订阅者独立注册，失败不影响其他
  - 使用 try/except 包裹所有回调
  - 所有事件持久化到 event_log

========== 七、Phase 2A：运营SOP模板 ==========

目标：创建可执行的内容运营SOP。

7.1 REDBOOK-001：小红书笔记创作

文件：sops/templates/REDBOOK-001.yaml

sop_id: "REDBOOK-001"
name: "小红书笔记创作"
version: "1.0"
category: "content"
stages:
  - name: "选题策划"
    agent: "content_planner"
    skills: ["select_topic"]
    requirement: "根据热点库、选题池、差异化评估选择今日话题"
    output_type: "document"
    decision_options: ["确认", "换题", "跳过"]

  - name: "内容撰写"
    agent: "content_writer"
    skills: ["write_redbook_note"]
    requirement: "按清单体结构撰写300-500字小红书笔记，含痛点共鸣、方法清单、互动引导"
    output_type: "copywriting"

  - name: "标题优化"
    agent: "title_optimizer"
    skills: ["optimize_title"]
    requirement: "标题格式：数字+痛点+钩子，确保首图点击率"
    output_type: "copywriting"

  - name: "封面设计"
    agent: "cover_designer"
    skills: ["create_cover_image"]
    requirement: "生成大字报风格封面图，统一品牌色系"
    output_type: "document"

  - name: "发布执行"
    agent: "publisher"
    skills: ["publish_redbook"]
    requirement: "发布到小红书，发布后1小时内引导3-5条评论"
    output_type: "document"
    requires_confirmation: true

  - name: "数据归档"
    agent: "archivist"
    skills: ["archive_content"]
    requirement: "将笔记内容、标题、数据保存到知识库"
    output_type: "document"

required_stages: ["内容撰写"]
forbidden_skills: ["direct_db_write"]

7.2 JUEJIN-001：掘金技术文章

文件：sops/templates/JUEJIN-001.yaml

sop_id: "JUEJIN-001"
name: "掘金技术文章发布"
version: "1.0"
category: "content"
stages:
  - name: "选题确定"
    agent: "topic_selector"
    skills: ["select_tech_topic"]
    requirement: "选择FROST相关技术话题，确保有价值输出"
    output_type: "document"

  - name: "文章撰写"
    agent: "article_writer"
    skills: ["write_tech_article"]
    requirement: "撰写2000-3000字技术文章，含代码示例、架构图"
    output_type: "document"

  - name: "代码验证"
    agent: "code_validator"
    skills: ["validate_code"]
    requirement: "验证文章中所有代码可运行"
    output_type: "code"

  - name: "掘金发布"
    agent: "juejin_publisher"
    skills: ["publish_juejin"]
    requirement: "使用sessionid发布到掘金，选择正确分类和标签"
    output_type: "document"
    requires_confirmation: true

required_stages: ["文章撰写"]
forbidden_skills: ["direct_db_write"]

7.3 EMAIL-001：Newsletter发送

文件：sops/templates/EMAIL-001.yaml

sop_id: "EMAIL-001"
name: "Newsletter邮件发送"
version: "1.0"
category: "content"
stages:
  - name: "内容策划"
    agent: "newsletter_planner"
    skills: ["plan_newsletter"]
    requirement: "确定本周Newsletter主题和内容大纲"
    output_type: "document"

  - name: "邮件撰写"
    agent: "email_writer"
    skills: ["write_newsletter"]
    requirement: "撰写Markdown格式邮件，含摘要、正文、CTA"
    output_type: "document"

  - name: "邮件发送"
    agent: "email_sender"
    skills: ["send_email"]
    requirement: "使用Buttondown发送邮件，检查送达率"
    output_type: "document"
    requires_confirmation: true

required_stages: ["邮件撰写"]
forbidden_skills: ["direct_db_write"]

========== 八、Phase 2B：content-writer Skill ==========

目标：调用DeepSeek API，按平台风格生成内容。

8.1 新增文件：skills/content/writer.py

PHILOSOPHY：内容创作不是通用能力，是平台特异的能力。

功能模块：
  - write_redbook_note() — 小红书笔记
  - write_tech_article() — 掘金技术文章
  - write_newsletter() — Newsletter邮件
  - optimize_title() — 标题优化
  - select_topic() — 选题策划

每个函数：
  - 接收 context dict
  - 构造平台特定的 prompt
  - 调用 skills.llm.call_llm()
  - 返回 _generated_content
  - 记录成本（cost_tracker）
  - 失败时记录到 data/tool_calls/

8.2 小红书 prompt 模板示例

```
你是小红书内容创作专家。请为以下话题撰写一篇小红书笔记。

话题：{topic}
风格：清单体（数字+痛点+解决方案）
要求：
- 300-500字
- 开篇50字痛点共鸣
- 主体3-5个方法点，每点配emoji
- 结尾20字互动引导（提问式）
- 语气：亲切、实用、不贩卖焦虑
- 避免AI腔：不用"在当今时代"、不用"众所周知"

输出格式：直接输出笔记正文，不要加任何元说明。
```

8.3 成本预算

月度¥300 ≈ 约 300万 tokens（DeepSeek-chat）
- 小红书笔记：每篇约 500 input + 500 output = 1000 tokens ≈ ¥0.1
- 掘金文章：每篇约 2000 input + 1500 output = 3500 tokens ≈ ¥0.35
- Newsletter：每篇约 1500 input + 1000 output = 2500 tokens ≈ ¥0.25
- 每周3篇小红书 + 1篇掘金 + 1篇Newsletter ≈ ¥1.8/周 ≈ ¥7.2/月

**预算内，有充足余量。**

========== 九、Phase 2C：掘金发布 Skill ==========

目标：用你提供的掘金cookie，自动化发布文章。

9.1 新增文件：skills/publish/juejin.py

技术方案：
  - 使用 requests + session（模拟浏览器）
  - 使用提供的 sessionid/cookie
  - 调用掘金创作平台 API（需调研具体接口）
  - 备选：使用 selenium/playwright（如果API受限）

安全要求：
  - cookie 必须走 core/secrets.py 加密存储
  - 不硬编码在代码中
  - 失败时记录日志，不暴露cookie

9.2 关键实现

```python
def publish_juejin(context: dict) -> dict:
    """发布文章到掘金"""
    title = context.get("_article_title", "")
    content = context.get("_article_content", "")
    tags = context.get("_article_tags", ["FROST", "AI"])

    # 从 secrets 获取 cookie
    from core.secrets import get_decrypted_key
    sessionid = get_decrypted_key("JUEJIN_SESSIONID")

    # 调用掘金 API
    headers = {
        "Cookie": f"sessionid={sessionid}",
        "Content-Type": "application/json",
    }

    # 发布逻辑（需根据实际API调整）
    ...
```

9.3 风险

- 掘金 API 可能变更（需要监控）
- cookie 可能过期（需要定期更新）
- 平台反爬机制（需要控制频率）

**建议：先实现手动确认发布（requires_confirmation=true），稳定后再考虑全自动。**

========== 十、Phase 2D：邮件发送 Skill ==========

目标：使用 Buttondown/Resend 发送邮件。

10.1 技术方案

Buttondown（推荐）：
  - 免费层：1000订阅者
  - Markdown友好
  - 有API：https://buttondown.com/api/
  - 需要 API key

Resend（备选）：
  - 免费层：1000封/天
  - 事务邮件专用
  - 有SDK：resend-python

10.2 实现

```python
def send_email(context: dict) -> dict:
    """发送Newsletter"""
    subject = context.get("_email_subject", "")
    body = context.get("_email_body", "")

    from core.secrets import get_decrypted_key
    api_key = get_decrypted_key("BUTTONDOWN_API_KEY")

    import requests
    resp = requests.post(
        "https://api.buttondown.com/v1/emails",
        headers={"Authorization": f"Token {api_key}"},
        json={
            "subject": subject,
            "body": body,
            "status": "draft",  # 先draft，人工确认后再发送
        }
    )
    ...
```

10.3 同样建议：先 draft，人工确认后再发送。

========== 十一、Phase 3：测试计划 ==========

11.1 测试原则

TP-001. 所有新增模块必须有单元测试（覆盖率≥90%）
TP-002. 所有闭环必须有端到端测试
TP-003. 现有测试必须全部通过（回归测试）
TP-004. 新增属性测试（Hypothesis）验证边界条件
TP-005. 新增安全测试（密钥不泄漏、SQL注入防护）
TP-006. 测试串行执行，禁用pytest-xdist
TP-007. 测试使用 mock LLM（FROST_TESTING=1）
TP-008. 成本测试：验证所有LLM调用在light模式下不消耗真实token

11.2 测试文件清单

单元测试（新增）：
  tests/test_scheduler.py — APScheduler集成测试
  tests/test_scheduler_coverage.py — 覆盖率补测
  tests/test_hunt_orchestration.py — 狩猎闭环测试
  tests/test_hunt_orchestration_coverage.py — 覆盖率
  tests/test_event_subscribers.py — 事件订阅测试
  tests/test_content_writer.py — 内容创作测试
  tests/test_content_writer_coverage.py — 覆盖率
  tests/test_publish_juejin.py — 掘金发布测试（mock）
  tests/test_publish_email.py — 邮件发送测试（mock）
  tests/test_sop_redbook.py — 小红书SOP测试
  tests/test_sop_juejin.py — 掘金SOP测试
  tests/test_sop_email.py — 邮件SOP测试
  tests/test_security_scheduler.py — 安全测试
  tests/test_performance_scheduler.py — 性能测试（定时器负载）

集成测试（新增）：
  tests/test_e2e_hunt_evolution.py — 端到端：狩猎→分析→进化
  tests/test_e2e_content_pipeline.py — 端到端：选题→撰写→发布→归档
  tests/test_e2e_scheduled_execution.py — 端到端：定时触发→执行→复盘
  tests/test_e2e_full_loop.py — 完整闭环：狩猎→执行→复盘→进化

回归测试（现有）：
  所有现有测试文件必须继续通过（1030+测试）
  特别关注：
    - tests/test_v2_event_bus.py
    - tests/test_v3_event_loop_blocking.py
    - tests/test_v4_p0_a_acceptance.py
    - tests/test_v4_p0_b_acceptance.py
    - tests/test_v4_p1_acceptance.py
    - tests/test_v4_p2_acceptance.py

11.3 关键测试用例

TC-001. 定时器触发SOP
  Given：FrostScheduler.schedule_sop(REDBOOK-001, "* * * * *")
  When：等待1分钟
  Then：任务被创建，阶段被创建，SOP执行
  And：finalize_task被触发，审计完成

TC-002. 狩猎闭环
  Given：hunt_and_evolve(_hunt_targets=[{"skill_id": "test_skill"}])
  When：执行
  Then：hunt_sop完成，integrate_briefings完成，evolution完成
  And：asset_store中有briefing和evolution记录

TC-003. 内容创作
  Given：write_redbook_note(topic="FROST框架")
  When：FROST_TESTING=1
  Then：返回mock内容，不调用真实API
  And：成本=0

TC-004. 安全：密钥不泄漏
  Given：publish_juejin被调用
  When：检查日志输出
  Then：日志中不包含sessionid明文
  And：context中不包含sessionid

TC-005. 回归：现有SOP仍可用
  Given：main(task="test", sop="DEV-001")
  When：执行
  Then：所有阶段完成，finalize_task触发审计
  And：测试通过

11.4 测试覆盖率目标

模块 | 目标覆盖率 | 最低覆盖率
---|---|---
core/scheduler.py | 95% | 90%
skills/hunt_orchestration.py | 90% | 85%
skills/content/writer.py | 95% | 90%
skills/publish/juejin.py | 90% | 85%
skills/publish/email.py | 90% | 85%
core/event_subscribers.py | 85% | 80%

========== 十二、Phase 4：第三方审计文件 ==========

12.1 审计包内容

文件：audit_package_v6.0.zip（替换现有 audit_package）
包含：
  1. AUDIT_REPORT_v6.0.md — 完整审计报告
  2. BASELINE_v6.0.md — 基线验证文档
  3. TEST_RESULTS_v6.0.md — 全量测试结果
  4. COVERAGE_REPORT_v6.0.html — 覆盖率报告
  5. SECURITY_AUDIT_v6.0.md — 安全审计
  6. PERFORMANCE_AUDIT_v6.0.md — 性能审计
  7. ARCHITECTURE_v6.0.md — 架构文档（新增闭环+运营模块）
  8. 代码快照（git diff + 完整代码）
  9. 测试数据（SQLite DB备份）
  10. 执行日志样本

12.2 审计报告章节

第一章：项目概述
  - 选择B的范围说明
  - 瀑布式开发阶段划分
  - 关键决策记录

第二章：代码质量审计
  - ruff/pylint/flake8 结果
  - 复杂度分析（McCabe）
  - 重复代码检测
  - 新增代码 vs 修改代码统计

第三章：安全审计
  - 新增API密钥管理（secrets.py使用）
  - 定时器任务注入防护
  - 事件总线订阅安全
  - 外部平台凭据保护（掘金cookie、邮件API）
  - bandit/safety/detect-secrets 扫描结果

第四章：测试审计
  - 测试覆盖率（按模块）
  - 回归测试结果（新旧测试全部通过）
  - 端到端测试记录
  - 边界条件测试
  - 属性测试（Hypothesis）

第五章：架构审计
  - 闭环架构图（执行→复盘→狩猎→进化）
  - 定时器架构图
  - 运营模块架构图
  - 事件流图
  - 数据流图

第六章：性能审计
  - 定时器开销（BackgroundScheduler资源占用）
  - 事件总线吞吐量
  - SQLite并发性能（单线程）
  - LLM调用成本（实际 vs 预算）
  - 内存使用（ChromaDB + Store）

第七章：功能审计
  - 闭环完整性验证
  - 运营SOP可执行性验证
  - 定时调度准确性验证
  - 知识库自动归档验证
  - 跨模块事件触发验证

第八章：已知限制
  - 定时器依赖系统时间（无NTP校验）
  - 外部平台API变更风险
  - 掘金cookie过期风险
  - LLM内容质量不可控
  - 运营SOP需要人工确认发布（安全设计）
  - 知识库分类算法简单（无NLP）
  - 能力图谱无可视化

第九章：建议
  - 短期（1-2周）：运营SOP手动运行验证
  - 中期（1-2月）：外部平台API稳定性监控
  - 长期：多平台内容矩阵扩展（抖音/B站）

12.3 审计交付标准

AD-001. 所有测试通过（exit code 0）
AD-002. 新增覆盖率≥90%，总体覆盖率≥85%
AD-003. 安全扫描无高危漏洞
AD-004. 复杂度≤10（新增函数）
AD-005. 文档完整（每模块有PHILOSOPHY注释）
AD-006. 无硬编码密钥
AD-007. 向后兼容（V2/V3/V4事件订阅仍可用）
AD-008. 成本可控（月度<¥300）
AD-009. 审计包可复现（提供复现步骤）
AD-010. 审计报告有数字签名（时间戳）

========== 十三、执行顺序与里程碑 ==========

Week 1：Phase 1（闭环补全）
  Day 1-2：1A + 1B（finalize_task + hunt_and_evolve）
  Day 3：1C（APScheduler集成）
  Day 4：1D（事件订阅）+ 测试（3A部分）
  Day 5：代码审查 + 修复 + 回归测试
  里程碑：执行闭环和狩猎闭环能手动触发并自动运行

Week 2：Phase 2（运营能力）
  Day 1：2A（SOP模板）+ 2B（content-writer框架）
  Day 2：2B（小红书/掘金/Newsletter具体实现）
  Day 3：2C（掘金发布）+ 2D（邮件发送）
  Day 4：运营基因初始化 + 测试（3B部分）
  Day 5：代码审查 + 修复 + 回归测试
  里程碑：运营SOP能手动执行，产出内容可验证

Week 3：Phase 3-4（测试+审计）
  Day 1-2：全量测试（单元+集成+回归+安全）
  Day 3：性能测试 + 成本验证
  Day 4：审计文档编写
  Day 5：审计包打包 + 交付
  里程碑：审计包就绪，所有交付标准满足

========== 十四、风险与缓解 ==========

RISK-001. APScheduler与现有事件循环冲突
  缓解：使用BackgroundScheduler（独立线程），不干扰主事件循环
  验证：TC-005回归测试通过

RISK-002. 定时器任务堆积
  缓解：每个任务执行时检查是否已有相同任务在运行（misfire_grace_time=300）
  验证：性能测试

RISK-003. 掘金API变更导致发布失败
  缓解：所有发布API有fallback到manual模式
  验证：mock测试 + 真实测试（手动确认）

RISK-004. 成本超预算
  缓解：所有LLM调用走cost_tracker，light模式不调用LLM
  验证：月度成本统计

RISK-005. 测试串行导致执行时间长
  缓解：分批次运行，优先运行新增模块测试
  验证：总执行时间<5分钟

RISK-006. 向后兼容破坏
  缓解：所有新增事件类型为可选，不修改现有事件常量
  验证：所有V2/V3/V4测试通过

========== 十五、WorkBuddy指令检查清单 ==========

执行此指令前，WorkBuddy必须确认：

[ ] 已理解选择B的范围（两条闭环+运营能力+测试+审计）
[ ] 已确认技术约束（Python 3.13, SQLite, 串行测试, ¥300预算）
[ ] 已确认外部凭据（DeepSeek API, 掘金cookie, 邮件API待配置）
[ ] 已确认向后兼容要求（V2/V3/V4事件订阅保持可用）
[ ] 已确认测试标准（新增覆盖率≥90%，总体≥85%，1030+测试通过）
[ ] 已确认审计交付标准（10项AD标准）
[ ] 已确认瀑布式开发（3周，每周有里程碑）
[ ] 已确认安全要求（密钥加密，无硬编码，audit_log记录）
[ ] 已确认成本监控（所有LLM调用走cost_tracker）
[ ] 已确认人工确认点（发布到外部平台需要requires_confirmation）

========== 结束 ==========

此指令为最细致、最严谨、最全量的版本。
任何偏离此指令的改动必须经OPC确认。
