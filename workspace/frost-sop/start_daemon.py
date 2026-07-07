"""
FROST-SOP V7.4 — 自启动守护进程（武器清单版）

双击 start.bat 启动后，本脚本自动：
1. 初始化事件总线守护线程
2. 启动计划调度器
3. 从武器清单注册所有武器到武器库
4. 注册府兵 Agent、父辈 Agent、审计 Agent
5. 进入运行状态，等待事件触发

PHILOSOPHY: 武器清单驱动。新增武器只需修改 core/weapon_manifest.py，
无需修改启动脚本。
"""

import logging
import sys
import time
import signal
import threading

from core.armory import ArmoryRegistry
from core.armory_lifecycle import ArmoryDispatcher
from core.event_bus_daemon import EventBusDaemon
from core.plan_scheduler import PlanScheduler
from core.store import Store
from core.weapon_manifest import register_all_weapons, get_weapon_manifest
from agents.footman import FootmanAgent
from agents.auditor import AuditorAgent

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


def main():
    """
    FROST-SOP 守护进程主入口。

    启动顺序：
    1. 事件总线守护线程
    2. 计划调度器
    3. 武器库注册（从武器清单）
    4. 府兵 Agent
    5. 审计 Agent
    6. 进入主循环
    """
    logger.info("=" * 60)
    logger.info("FROST-SOP V7.4 守护进程启动")
    logger.info("PHILOSOPHY: 武器清单驱动，祖辈→父辈→府兵")
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

    # 4. 从武器清单注册所有武器（V7.4: 集中管理）
    registered_count = register_all_weapons(registry)
    logger.info("✅ 武器库已初始化: %d 件武器", registered_count)

    # 显示武器清单摘要
    manifest = get_weapon_manifest()
    for category, weapons in manifest.items():
        logger.info("  [%s] %d 件: %s", category, len(weapons), ", ".join(w["id"] for w in weapons))

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
