"""
FROST-SOP V7.4 — 自启动守护进程

双击 start.bat 启动后，本脚本自动：
1. 初始化事件总线守护线程
2. 启动计划调度器
3. 注册武器到武器库（Skill + SOP）
4. 注册府兵 Agent（从武器库领取武器并执行）
5. 注册父辈 Agent（战术细化 + 并行识别）
6. 注册审计 Agent（检查计划漏洞）
7. 进入运行状态，等待事件触发

PHILOSOPHY: 一键启动，无人值守。启动后系统自己运转，不需要人工干预。
武器库驱动：所有能力（包括并行编排）都是武器，不是硬编码。

USAGE:
    python start_daemon.py

EXIT:
    Ctrl+C 或发送 SIGTERM 触发优雅退出
"""

import logging
import sys
import time
import signal
import threading

from core.armory import ArmoryRegistry, WeaponMetadata, WeaponType, WeaponCategory, WeaponState
from core.armory_lifecycle import ArmoryDispatcher
from core.event_bus_daemon import EventBusDaemon
from core.plan_scheduler import PlanScheduler
from core.store import Store
from agents.footman import FootmanAgent
from agents.auditor import AuditorAgent
from agents.parent import plan_refiner_skill, parallel_orchestrator_skill

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("frost.daemon")

# 全局状态
_daemon_running = threading.Event()
_daemon_running.set()


def _setup_signal_handlers():
    """设置信号处理器，支持优雅退出。"""
    def _on_signal(signum, frame):
        logger.info("收到信号 %d，开始优雅退出...", signum)
        _daemon_running.clear()

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    try:
        signal.signal(signal.SIGBREAK, _on_signal)
    except AttributeError:
        pass


def register_weapons(registry: ArmoryRegistry):
    """
    V7.4: 注册武器到武器库。

    所有能力都是武器，包括：
    - plan_refiner: 父辈的计划细化能力
    - parallel_orchestrator: 并行编排能力
    """
    weapons = [
        WeaponMetadata(
            id="skill:plan_refiner",
            name="计划细化器",
            type=WeaponType.SKILL,
            category=WeaponCategory.STRATEGY,
            description="父辈核心武器：将祖辈的战略计划细化为可执行计划，识别并行机会",
            applicable_scenarios=["计划细化", "并行识别", "战术规划"],
            tags=["parent", "planning", "parallel"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
        WeaponMetadata(
            id="skill:parallel_orchestrator",
            name="并行编排器",
            type=WeaponType.SKILL,
            category=WeaponCategory.ORCHESTRATE,
            description="解析 parallel_group 并调度并行执行",
            applicable_scenarios=["并行执行", "组调度", "协同编排"],
            tags=["parallel", "orchestrate", "coordinator"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
        WeaponMetadata(
            id="skill:plan_generator",
            name="计划生成器",
            type=WeaponType.SKILL,
            category=WeaponCategory.STRATEGY,
            description="祖辈核心武器：将需求拆解为结构化计划",
            applicable_scenarios=["需求拆解", "战略计划", "商业闭环"],
            tags=["grandparent", "planning", "strategy"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
        WeaponMetadata(
            id="skill:ceo_assessment",
            name="CEO评估器",
            type=WeaponType.SKILL,
            category=WeaponCategory.GOVERNANCE,
            description="执行前评估资源/法规/竞争/退出路径",
            applicable_scenarios=["风险评估", "可行性分析", "GO/NO-GO决策"],
            tags=["assessment", "risk", "governance"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
        WeaponMetadata(
            id="skill:auditor",
            name="审计器",
            type=WeaponType.SKILL,
            category=WeaponCategory.GOVERNANCE,
            description="Devil's Advocate：检查计划漏洞",
            applicable_scenarios=["计划审计", "漏洞检查", "质量把关"],
            tags=["audit", "quality", "governance"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
        WeaponMetadata(
            id="skill:lesson_archivist",
            name="教训归档器",
            type=WeaponType.SKILL,
            category=WeaponCategory.COMMUNICATION,
            description="自动记录执行教训",
            applicable_scenarios=["复盘", "知识管理", "持续改进"],
            tags=["lesson", "archive", "learning"],
            state=WeaponState.ACTIVE,
            is_active=True,
            is_preset=True,
        ),
    ]

    for weapon in weapons:
        registry.register(weapon)
        logger.info("[武器库] 注册: %s (%s)", weapon.id, weapon.category.value)

    logger.info("[武器库] 注册完成: %d 件武器", len(weapons))


def main():
    """
    FROST-SOP 守护进程主入口。

    启动顺序：
    1. 事件总线守护线程
    2. 计划调度器
    3. 武器库注册（V7.4: 所有能力武器化）
    4. 府兵 Agent
    5. 父辈 Agent（V7.4: 战术细化）
    6. 审计 Agent
    7. 进入主循环
    """
    logger.info("=" * 60)
    logger.info("FROST-SOP V7.4 守护进程启动")
    logger.info("PHILOSOPHY: 武器库驱动，祖辈→父辈→府兵")
    logger.info("=" * 60)

    _setup_signal_handlers()

    # 1. 初始化基础设施
    store = Store()
    registry = ArmoryRegistry()

    # 2. 启动事件总线守护线程
    daemon = EventBusDaemon()
    daemon.start()
    logger.info("✅ 事件总线守护线程已启动")

    # 3. 启动计划调度器
    scheduler = PlanScheduler(daemon=daemon)
    scheduler.start()
    logger.info("✅ 计划调度器已启动")

    # 4. 注册武器到武器库（V7.4: 能力武器化）
    register_weapons(registry)
    logger.info("✅ 武器库已初始化")

    # 5. 注册府兵 Agent
    footman = FootmanAgent(registry=registry, store=store, daemon=daemon)
    footman.start()
    logger.info("✅ 府兵 Agent 已注册")

    # 6. 注册审计 Agent
    auditor = AuditorAgent(daemon=daemon)
    auditor.start()
    logger.info("✅ 审计 Agent 已注册")

    # 7. 主循环
    logger.info("=" * 60)
    logger.info("系统运行中，按 Ctrl+C 退出")
    logger.info("=" * 60)

    while _daemon_running.is_set():
        time.sleep(1.0)

    # 8. 优雅退出
    logger.info("开始关闭...")
    scheduler.stop()
    daemon.stop()
    logger.info("✅ 守护进程已安全关闭")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
