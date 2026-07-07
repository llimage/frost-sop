FROST-SOP 初始化流水线编码指令
WorkBuddy 全量开发、测试、审计指南

========== 文档版本 ==========
版本：INIT-001
触发：v3.0 初始化套件需要代码实现
日期：2026-07-02

========== 一、设计目标 ==========

目标：将 v3.0 文档中的"初始化问卷 → 缺口分析 → 狩猎任务生成"流程代码化。

三层流水线：
  问卷采集 → 缺口分析 → 任务生成 → 写入调度器 → 触发首个狩猎

关键设计决策：
  1. 不使用新建数据库表（避免修改 core/db.py 的 ALLOWED_TABLES 白名单）
  2. 使用现有 tasks 表存储初始化任务，project_id="INIT" 为标记
  3. 问卷模块不依赖数据库，纯输入采集+缺口分析
  4. 任务触发器负责数据库写入和事件发布
  5. 所有新增文件，不修改已有文件（向后兼容）

========== 二、新建文件清单 ==========

文件1：skills/init/__init__.py
文件2：skills/init/questionnaire.py    — 问卷模块
文件3：skills/init/task_trigger.py     — 任务触发器
文件4：sops/templates/INIT-001.yaml    — 初始化SOP模板
文件5：tests/test_init_questionnaire.py — 问卷测试
文件6：tests/test_init_task_trigger.py  — 触发器测试

========== 三、文件 1：skills/init/__init__.py ==========

用途：Python 包标记，导出公共接口。

内容：

"""FROST-SOP 初始化模块"""
from skills.init.questionnaire import InitQuestionnaire, run_questionnaire
from skills.init.task_trigger import InitTaskTrigger, run_trigger

__all__ = ["InitQuestionnaire", "run_questionnaire", "InitTaskTrigger", "run_trigger"]

========== 四、文件 2：skills/init/questionnaire.py ==========

4.1 设计约束

- 不依赖数据库（SQLite）
- 不依赖外部 API（DeepSeek 等）
- 纯 Python 标准库 + dataclasses
- 交互式输入（input()）
- 支持非交互模式（程序化调用）
- 复杂度：所有函数 McCabe < 10

4.2 完整代码

"""
FROST-SOP 初始化问卷模块
Seed User 版本 v1.0 — 2026-07-02

PHILOSOPHY: 问卷不是配置单，是狩猎任务的种子。
每个问题的答案中，都藏着需要被狩猎的能力缺口。

三层流水线：
  问卷采集 → 缺口分析 → 任务生成
"""

import json
import logging
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class VisionAnswer:
    """愿景问卷答案（8个问题）"""
    identity: str = ""
    destination_6m: str = ""
    destination_12m: str = ""
    destination_36m: str = ""
    assets: str = ""
    constraints: str = ""
    content_strategy: str = ""
    growth_flywheel: str = ""


@dataclass
class GapItem:
    """能力缺口项"""
    gap_id: str = ""
    description: str = ""
    source_question: str = ""  # 来自哪个问题
    priority: str = "P1"  # P0/P1/P2
    suggested_hunt_target: str = ""  # 建议狩猎目标


@dataclass
class InitTask:
    """初始化狩猎任务"""
    task_id: str = ""
    title: str = ""
    target_skill: str = ""
    priority: str = "P1"
    status: str = "pending"  # pending/running/done
    created_at: str = ""
    gap_id: str = ""  # 关联的缺口


# ============================================================
# 问卷定义
# ============================================================

QUESTION_DEFINITIONS = [
    {
        "id": "identity",
        "prompt": (
            "\n【问题1】你是谁？\n"
            "描述你的身份、背景、核心特征（如：IT小白、一人公司创业者、社恐）\n> "
        ),
        "gap_keywords": ["不懂", "不会", "小白", "零基础", "没经验", "缺"],
    },
    {
        "id": "destination_6m",
        "prompt": (
            "\n【问题2-1】6个月后，你在哪里？\n"
            "具体、可衡量的目标（如：月入5000、1000粉丝、产品上线）\n> "
        ),
        "gap_keywords": ["零", "没有", "未", "待", "找", "探索"],
    },
    {
        "id": "destination_12m",
        "prompt": (
            "\n【问题2-2】12个月后，你在哪里？\n> "
        ),
        "gap_keywords": ["零", "没有", "未", "待", "找", "探索", "稳定"],
    },
    {
        "id": "destination_36m",
        "prompt": (
            "\n【问题2-3】36个月后，你在哪里？\n> "
        ),
        "gap_keywords": ["零", "没有", "未", "待", "找", "探索"],
    },
    {
        "id": "assets",
        "prompt": (
            "\n【问题3】你现在有什么资产？\n"
            "方法论、产品、内容、技术、人脉等（如：FROST框架、小红书账号）\n> "
        ),
        "gap_keywords": ["无", "没有", "空白", "待建"],
    },
    {
        "id": "constraints",
        "prompt": (
            "\n【问题4】你的硬约束是什么？\n"
            "预算、时间、技能、人脉（如：零预算、每天2小时、不懂代码）\n> "
        ),
        "gap_keywords": ["零", "没有", "有限", "不懂", "不会", "缺"],
    },
    {
        "id": "content_strategy",
        "prompt": (
            "\n【问题5】你的内容策略是什么？\n"
            "做什么内容、触达谁、怎么触达（如：小红书知识笔记、Newsletter）\n> "
        ),
        "gap_keywords": ["不明确", "模糊", "探索", "未确定", "空白"],
    },
    {
        "id": "growth_flywheel",
        "prompt": (
            "\n【问题6】你的增长飞轮是什么？\n"
            "什么带来用户？什么带来收入？什么带来复利？（不知道就写不知道）\n> "
        ),
        "gap_keywords": ["不知道", "不明确", "没有", "待设计", "探索"],
    },
]


# ============================================================
# 缺口识别规则库
# ============================================================

GAP_RULES = {
    "identity": [
        (["不懂技术", "IT小白", "不会代码", "零基础"], "tech_execution", "技术执行能力", "P0"),
        (["社恐", "不喜欢社交", "内向"], "social_bypass", "社交网络替代方案", "P1"),
        (["一人", " solo", "独自", "单干"], "solo_ops", "一人公司运营能力", "P0"),
    ],
    "destination_6m": [
        (["零收入", "零读者", "零用户", "零粉丝"], "monetization_path", "变现路径设计", "P0"),
        (["稳定现金流", "盈利", "月入"], "revenue_model", "收入模型设计", "P0"),
    ],
    "constraints": [
        (["零预算", "没钱", "无资金", "穷"], "zero_budget_tools", "零预算工具栈", "P0"),
        (["不懂代码", "不会编程", "不会写代码"], "no_code_automation", "无代码自动化", "P0"),
        (["时间有限", "每天", "小时", "时间不够"], "time_efficiency", "时间效率优化", "P1"),
    ],
    "content_strategy": [
        (["小红书", "redbook", "xhs", "笔记"], "redbook_ops", "小红书运营能力", "P0"),
        (["newsletter", "邮件", "email", "news letter"], "email_ops", "邮件系统运营", "P1"),
        (["掘金", "juejin", "技术博客", "开发者"], "juejin_ops", "掘金内容运营", "P1"),
        (["不明确", "模糊", "不知道", "未确定", "空白"], "content_strategy_design", "内容策略设计", "P0"),
    ],
    "growth_flywheel": [
        (["不知道", "不明确", "没有", "待设计", "探索"], "flywheel_design", "增长飞轮设计", "P0"),
    ],
}


# ============================================================
# 核心类：初始化问卷
# ============================================================

class InitQuestionnaire:
    """
    V1.0: 交互式初始化问卷。

    两种使用模式：
    1. 交互模式：run_interactive() → 通过 input() 采集答案
    2. 程序模式：run_programmatic(answers_dict) → 直接传入字典

    输出：缺口诊断报告 + 初始化狩猎任务列表
    """

    def __init__(self, non_interactive: bool = False, mock_inputs: Optional[Dict[str, str]] = None):
        """
        Args:
            non_interactive: 是否非交互模式（用于测试）
            mock_inputs: 非交互模式下的预置答案
        """
        self.non_interactive = non_interactive
        self.mock_inputs = mock_inputs or {}
        self.answers: Dict[str, Dict[str, Any]] = {}
        self.gaps: List[GapItem] = []
        self.tasks: List[InitTask] = []

    # ----------------------------------------------------------
    # 阶段 1：问卷采集
    # ----------------------------------------------------------

    def run_interactive(self) -> VisionAnswer:
        """运行交互式问卷（或程序模式）"""
        if self.non_interactive:
            logger.info("[InitQuestionnaire] 程序模式：使用预置答案")
        else:
            self._print_banner()

        for q in QUESTION_DEFINITIONS:
            answer = self._ask_question(q)
            self.answers[q["id"]] = {
                "text": answer,
                "keywords": q["gap_keywords"],
            }

        return self._build_vision_answer()

    def _print_banner(self) -> None:
        """打印问卷欢迎语"""
        print("=" * 60)
        print("FROST-SOP 初始化问卷")
        print("这不是配置单，是狩猎任务的种子")
        print("=" * 60)

    def _ask_question(self, q_def: Dict[str, Any]) -> str:
        """
        提问并获取回答。

        交互模式：input() 从终端读取
        程序模式：从 mock_inputs 读取
        """
        if self.non_interactive:
            return self.mock_inputs.get(q_def["id"], "")

        try:
            return input(q_def["prompt"]).strip()
        except EOFError:
            # 管道输入或重定向时，读取 sys.stdin
            line = sys.stdin.readline().strip()
            return line

    def _build_vision_answer(self) -> VisionAnswer:
        """从原始答案构建 VisionAnswer"""
        return VisionAnswer(
            identity=self.answers.get("identity", {}).get("text", ""),
            destination_6m=self.answers.get("destination_6m", {}).get("text", ""),
            destination_12m=self.answers.get("destination_12m", {}).get("text", ""),
            destination_36m=self.answers.get("destination_36m", {}).get("text", ""),
            assets=self.answers.get("assets", {}).get("text", ""),
            constraints=self.answers.get("constraints", {}).get("text", ""),
            content_strategy=self.answers.get("content_strategy", {}).get("text", ""),
            growth_flywheel=self.answers.get("growth_flywheel", {}).get("text", ""),
        )

    # ----------------------------------------------------------
    # 阶段 2：缺口分析
    # ----------------------------------------------------------

    def analyze_gaps(self, answer: VisionAnswer) -> List[GapItem]:
        """
        基于规则识别能力缺口。

        规则逻辑：
        1. 遍历 GAP_RULES 中每个问题的规则
        2. 检查答案文本是否包含关键词
        3. 匹配则生成 GapItem
        4. 去重：同 target 只保留一次
        5. 添加通用规则（资产变现）
        6. 按优先级排序
        """
        self.gaps = []
        gap_id_counter = 1

        # 基于规则识别缺口
        for qid, rules in GAP_RULES.items():
            answer_text = getattr(answer, qid, "").lower()
            for keywords, target, desc, priority in rules:
                if self._match_keywords(answer_text, keywords):
                    gap = GapItem(
                        gap_id=f"GAP-{gap_id_counter:03d}",
                        description=desc,
                        source_question=qid,
                        priority=priority,
                        suggested_hunt_target=target,
                    )
                    # 去重：同 target 只保留一次
                    if not self._has_gap_with_target(target):
                        self.gaps.append(gap)
                        gap_id_counter += 1

        # 通用规则：资产变现缺口
        self._add_asset_monetization_gap(answer, gap_id_counter)
        gap_id_counter = len(self.gaps) + 1

        # 按优先级排序
        self._sort_gaps_by_priority()
        logger.info("[InitQuestionnaire] 缺口分析完成: %d 个缺口", len(self.gaps))
        return self.gaps

    def _match_keywords(self, text: str, keywords: List[str]) -> bool:
        """检查文本是否包含任一关键词"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

    def _has_gap_with_target(self, target: str) -> bool:
        """检查是否已有相同 target 的缺口"""
        return any(g.suggested_hunt_target == target for g in self.gaps)

    def _add_asset_monetization_gap(self, answer: VisionAnswer, counter: int) -> None:
        """通用规则：如果目标涉及变现且拥有资产，添加资产变现缺口"""
        dest_6m = answer.destination_6m.lower()
        has_monetization_goal = "变现" in dest_6m or "收入" in dest_6m or "盈利" in dest_6m
        has_assets = bool(answer.assets) and answer.assets.lower() not in ["无", "没有", "空白", ""]

        if has_monetization_goal and has_assets:
            if not self._has_gap_with_target("asset_monetization"):
                self.gaps.append(GapItem(
                    gap_id=f"GAP-{counter:03d}",
                    description="资产变现路径",
                    source_question="assets",
                    priority="P1",
                    suggested_hunt_target="asset_monetization",
                ))

    def _sort_gaps_by_priority(self) -> None:
        """按优先级排序：P0 > P1 > P2"""
        priority_order = {"P0": 0, "P1": 1, "P2": 2}
        self.gaps.sort(key=lambda g: priority_order.get(g.priority, 99))

    # ----------------------------------------------------------
    # 阶段 3：任务生成
    # ----------------------------------------------------------

    def generate_tasks(self) -> List[InitTask]:
        """从缺口生成初始化狩猎任务"""
        self.tasks = []
        for i, gap in enumerate(self.gaps, 1):
            task = InitTask(
                task_id=f"INIT-HUNT-{i:03d}",
                title=f"初始狩猎：{gap.description}",
                target_skill=gap.suggested_hunt_target,
                priority=gap.priority,
                status="pending",
                created_at=datetime.now().isoformat(),
                gap_id=gap.gap_id,
            )
            self.tasks.append(task)
        logger.info("[InitQuestionnaire] 任务生成完成: %d 个任务", len(self.tasks))
        return self.tasks

    # ----------------------------------------------------------
    # 报告与导出
    # ----------------------------------------------------------

    def print_report(self) -> None:
        """打印缺口诊断报告到终端"""
        print("\n" + "=" * 60)
        print("初始化缺口诊断报告")
        print("=" * 60)
        print(f"\n识别到 {len(self.gaps)} 个能力缺口：")

        for gap in self.gaps:
            icon = "🔴" if gap.priority == "P0" else "🟡" if gap.priority == "P1" else "🟢"
            print(f"\n{icon} [{gap.priority}] {gap.gap_id}")
            print(f"   缺口：{gap.description}")
            print(f"   来源：{gap.source_question}")
            print(f"   建议狩猎：{gap.suggested_hunt_target}")

        print(f"\n生成 {len(self.tasks)} 个初始化狩猎任务：")
        for task in self.tasks:
            print(f"   📋 {task.task_id} → {task.title} (优先级: {task.priority})")

        print("\n" + "=" * 60)
        print("下一步：执行 python -m skills.init.task_trigger")
        print("=" * 60)

    def export_results(self, filepath: str = "init_results.json") -> Dict[str, Any]:
        """导出结果到 JSON 文件"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "answers": {k: v["text"] for k, v in self.answers.items()},
            "gaps": [asdict(g) for g in self.gaps],
            "tasks": [asdict(t) for t in self.tasks],
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info("[InitQuestionnaire] 结果已导出: %s", filepath)
        return data

    def run_full_pipeline(self, answers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """
        运行完整流水线（一键初始化）。

        Args:
            answers: 可选，预置答案字典（程序模式）。为 None 则交互模式。

        Returns:
            完整结果字典
        """
        if answers is not None:
            self.non_interactive = True
            self.mock_inputs = answers

        answer = self.run_interactive()
        self.analyze_gaps(answer)
        self.generate_tasks()
        self.print_report()
        return self.export_results()


# ============================================================
# CLI 入口
# ============================================================

def run_questionnaire() -> Dict[str, Any]:
    """CLI 入口：运行交互式问卷"""
    q = InitQuestionnaire()
    return q.run_full_pipeline()


if __name__ == "__main__":
    run_questionnaire()

========== 五、文件 3：skills/init/task_trigger.py ==========

5.1 设计约束

- 使用现有 tasks 表（不新建表）
- project_id="INIT" 标记初始化任务
- 使用 DBManager 的 insert/select_all 方法
- 使用 EventBus 发布 HUNT_COMPLETED 事件
- 发布 FrostScheduler 调度任务（可选，如果 scheduler 可用）
- 降级：如果核心模块不可用，使用本地 JSON 存储
- 复杂度：所有函数 McCabe < 10

5.2 完整代码

"""
FROST-SOP 初始化任务触发器
将问卷生成的任务写入调度系统

PHILOSOPHY: 缺口不是终点，是狩猎的起点。
问卷识别的每一个缺口，都自动转化为一个可执行的狩猎任务。
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 核心模块可用性检测（软依赖）
HAS_CORE = False
try:
    # 优先使用项目根目录作为导入基准
    _project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    if _project_root not in sys.path:
        sys.path.insert(0, _project_root)

    from core.db import DBManager, get_db
    from core.event_bus import EventBus, Event, EventType
    from core.scheduler import FrostScheduler

    HAS_CORE = True
    logger.info("[InitTaskTrigger] 核心模块已加载")
except ImportError as e:
    logger.warning("[InitTaskTrigger] 核心模块未加载: %s", e)
    HAS_CORE = False


# ============================================================
# 常量定义
# ============================================================

INIT_PROJECT_ID = "INIT"  # 初始化任务标记
DEFAULT_DB_PATH = "data/frost_sop.db"
DEFAULT_INIT_RESULTS_PATH = "init_results.json"


# ============================================================
# 核心类：任务触发器
# ============================================================

class InitTaskTrigger:
    """
    V1.0: 初始化任务触发器。

    职责：
    1. 从问卷结果加载任务
    2. 将任务写入数据库（tasks 表，project_id="INIT"）
    3. 发布 HUNT_COMPLETED 事件（触发首个 P0 狩猎）
    4. 生成初始化 SOP 文档
    5. 可选：调度首个狩猎任务到 FrostScheduler

    降级模式：如果核心模块不可用，使用本地 JSON 存储。
    """

    def __init__(
        self,
        db_path: str = DEFAULT_DB_PATH,
        init_results_path: str = DEFAULT_INIT_RESULTS_PATH,
    ):
        self.db_path = db_path
        self.init_results_path = init_results_path
        self.tasks: List[Dict[str, Any]] = []
        self._db: Optional[DBManager] = None
        self._event_bus: Optional[EventBus] = None
        self._scheduler: Optional[FrostScheduler] = None

        if HAS_CORE:
            try:
                self._db = get_db()
                self._event_bus = EventBus()
                self._scheduler = FrostScheduler()
            except Exception as e:
                logger.warning("[InitTaskTrigger] 核心模块初始化失败: %s", e)

    # ----------------------------------------------------------
    # 阶段 1：加载问卷结果
    # ----------------------------------------------------------

    def load_from_questionnaire(self) -> List[Dict[str, Any]]:
        """从问卷结果 JSON 文件加载任务"""
        if not os.path.exists(self.init_results_path):
            logger.error("[InitTaskTrigger] 未找到 %s，请先运行问卷", self.init_results_path)
            return []

        with open(self.init_results_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.tasks = data.get("tasks", [])
        logger.info("[InitTaskTrigger] 加载到 %d 个初始化任务", len(self.tasks))
        return self.tasks

    # ----------------------------------------------------------
    # 阶段 2：写入数据库
    # ----------------------------------------------------------

    def save_to_database(self) -> bool:
        """将任务写入 tasks 表（project_id="INIT" 标记）"""
        if not self.tasks:
            logger.warning("[InitTaskTrigger] 没有任务可保存")
            return False

        if HAS_CORE and self._db:
            self._save_to_tasks_table()
            logger.info("[InitTaskTrigger] 已写入 tasks 表 (project_id=INIT)")
        else:
            self._save_to_json_fallback()

        return True

    def _save_to_tasks_table(self) -> None:
        """使用 DBManager 写入 tasks 表"""
        for task in self.tasks:
            task_id = task["task_id"]
            # 检查是否已存在（避免重复）
            existing = self._db.select_one("tasks", "id", task_id)  # type: ignore[union-attr]
            if existing:
                logger.debug("[InitTaskTrigger] 任务已存在，跳过: %s", task_id)
                continue

            # 构造 tasks 表数据
            task_data = {
                "id": task_id,
                "title": task["title"],
                "description": (
                    f"来源缺口: {task.get('gap_id', '')} | "
                    f"优先级: {task['priority']} | "
                    f"目标技能: {task['target_skill']}"
                ),
                "project_id": INIT_PROJECT_ID,
                "status": task.get("status", "pending"),
                "created_at": task.get("created_at", datetime.now().isoformat()),
                "updated_at": datetime.now().isoformat(),
                "result_summary": json.dumps(
                    {
                        "gap_id": task.get("gap_id", ""),
                        "target_skill": task["target_skill"],
                        "priority": task["priority"],
                        "source": "init_questionnaire",
                    },
                    ensure_ascii=False,
                ),
            }
            self._db.insert("tasks", task_data)  # type: ignore[union-attr]
            logger.info("[InitTaskTrigger] 任务已创建: %s", task_id)

    def _save_to_json_fallback(self) -> None:
        """降级：本地 JSON 存储"""
        fallback_path = "init_tasks.json"
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump(self.tasks, f, ensure_ascii=False, indent=2)
        logger.info("[InitTaskTrigger] 已保存到本地: %s", fallback_path)

    # ----------------------------------------------------------
    # 阶段 3：触发首个狩猎
    # ----------------------------------------------------------

    def trigger_first_hunt(self) -> Optional[Dict[str, Any]]:
        """
        触发第一个 P0 狩猎任务。

        1. 找到第一个 P0 任务
        2. 发布 HUNT_COMPLETED 事件（供 event_subscribers 处理）
        3. 可选：调度到 FrostScheduler
        4. 返回触发信息
        """
        p0_tasks = [t for t in self.tasks if t.get("priority") == "P0"]
        if not p0_tasks:
            logger.warning("[InitTaskTrigger] 没有 P0 任务，跳过首个狩猎触发")
            return None

        first_task = p0_tasks[0]
        target = first_task["target_skill"]
        task_id = first_task["task_id"]

        logger.info("[InitTaskTrigger] 触发首个狩猎任务: %s → %s", task_id, target)

        # 发布事件（如果核心模块可用）
        if HAS_CORE and self._event_bus:
            try:
                event = Event(
                    event_type=EventType.HUNT_COMPLETED,
                    source="init_task_trigger",
                    data={
                        "task_id": task_id,
                        "target": target,
                        "trigger": "init_questionnaire",
                        "priority": "P0",
                        "is_first_hunt": True,
                    },
                )
                self._event_bus.publish(event)
                logger.info("[InitTaskTrigger] 已发布 HUNT_COMPLETED 事件")
            except Exception as e:
                logger.warning("[InitTaskTrigger] 事件发布失败: %s", e)

        # 可选：调度到 FrostScheduler
        if HAS_CORE and self._scheduler:
            try:
                job_id = self._scheduler.schedule_hunt(
                    skill_id=target,
                    cron_expr="0 2 * * *",  # 每日02:00（可调整）
                )
                logger.info("[InitTaskTrigger] 已调度狩猎任务: %s", job_id)
                first_task["scheduled_job_id"] = job_id
            except Exception as e:
                logger.warning("[InitTaskTrigger] 调度失败: %s", e)

        return {
            "task_id": task_id,
            "target": target,
            "command": f"python main.py --hunt --hunt-target {target}",
            "event_published": HAS_CORE and self._event_bus is not None,
        }

    # ----------------------------------------------------------
    # 阶段 4：生成初始化 SOP 文档
    # ----------------------------------------------------------

    def generate_init_sop(self) -> str:
        """生成初始化 SOP Markdown 文档"""
        sop_dir = "sops/generated"
        os.makedirs(sop_dir, exist_ok=True)

        lines = [
            "# 初始化任务 SOP",
            f"",
            f"生成时间: {datetime.now().isoformat()}",
            f"来源: 初始化问卷自动触发",
            f"",
            "## 任务清单",
            "",
        ]

        for task in self.tasks:
            status_icon = "⬜" if task.get("status") == "pending" else "✅"
            lines.append(f"{status_icon} [{task.get('priority', 'P1')}] {task['task_id']}: {task['title']}")
            lines.append(f"   目标技能: {task['target_skill']}")
            lines.append(f"   执行命令: `python main.py --hunt --hunt-target {task['target_skill']}`")
            lines.append("")

        lines.extend([
            "## 执行顺序",
            "",
            "1. 按优先级执行（P0 → P1 → P2）",
            "2. 每个任务完成后更新状态",
            "3. 所有 P0 完成后进入常规运营",
            "",
            "---",
            "",
            "本文件由 InitTaskTrigger 自动生成，请勿手动修改。",
        ])

        sop_path = os.path.join(sop_dir, "init_task_sop.md")
        with open(sop_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info("[InitTaskTrigger] 初始化 SOP 已生成: %s", sop_path)
        return sop_path

    # ----------------------------------------------------------
    # 阶段 5：更新任务状态
    # ----------------------------------------------------------

    def update_task_status(self, task_id: str, new_status: str) -> bool:
        """更新任务状态（pending → running → done）"""
        if not HAS_CORE or not self._db:
            logger.warning("[InitTaskTrigger] 数据库不可用，无法更新状态")
            return False

        try:
            self._db.update(  # type: ignore[union-attr]
                "tasks",
                "id",
                task_id,
                {
                    "status": new_status,
                    "updated_at": datetime.now().isoformat(),
                },
            )
            logger.info("[InitTaskTrigger] 任务状态更新: %s → %s", task_id, new_status)
            return True
        except Exception as e:
            logger.error("[InitTaskTrigger] 状态更新失败: %s, %s", task_id, e)
            return False

    # ----------------------------------------------------------
    # 阶段 6：获取初始化任务列表
    # ----------------------------------------------------------

    def get_init_tasks(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """从数据库获取初始化任务列表"""
        if not HAS_CORE or not self._db:
            logger.warning("[InitTaskTrigger] 数据库不可用，返回内存中的任务")
            return self.tasks

        try:
            if status:
                rows = self._db.select_all(  # type: ignore[union-attr]
                    "tasks",
                    where="project_id = ? AND status = ?",
                    params=[INIT_PROJECT_ID, status],
                )
            else:
                rows = self._db.select_all(  # type: ignore[union-attr]
                    "tasks",
                    where="project_id = ?",
                    params=[INIT_PROJECT_ID],
                )
            return rows
        except Exception as e:
            logger.error("[InitTaskTrigger] 查询失败: %s", e)
            return self.tasks

    # ----------------------------------------------------------
    # 完整流水线
    # ----------------------------------------------------------

    def run_full_pipeline(self) -> Dict[str, Any]:
        """运行完整触发流水线"""
        logger.info("=" * 60)
        logger.info("FROST-SOP 初始化任务触发器")
        logger.info("=" * 60)

        self.load_from_questionnaire()
        self.save_to_database()
        sop_path = self.generate_init_sop()
        trigger_info = self.trigger_first_hunt()

        result = {
            "tasks_count": len(self.tasks),
            "p0_count": len([t for t in self.tasks if t.get("priority") == "P0"]),
            "sop_path": sop_path,
            "trigger_info": trigger_info,
            "database_mode": HAS_CORE and self._db is not None,
        }

        logger.info("=" * 60)
        logger.info("初始化流水线完成: %d 个任务, %d 个 P0", result["tasks_count"], result["p0_count"])
        logger.info("=" * 60)
        return result


# ============================================================
# CLI 入口
# ============================================================

def run_trigger() -> Dict[str, Any]:
    """CLI 入口：运行完整触发流水线"""
    trigger = InitTaskTrigger()
    return trigger.run_full_pipeline()


if __name__ == "__main__":
    run_trigger()

========== 六、文件 4：sops/templates/INIT-001.yaml ==========

用途：初始化 SOP 模板，对齐现有 SOP 模板格式（REDBOOK-001.yaml 等）。

完整内容：

# INIT-001: FROST-SOP 初始化问卷执行
# V6.0 初始化流水线
sop_id: "INIT-001"
name: "FROST-SOP 初始化问卷执行"
version: "1.0"
category: "initialization"
description: "种子用户首次初始化，从问卷采集到狩猎任务触发"
trigger:
  schedule: "none"  # 手动触发，非定时
  manual: true

stages:
  - phase_id: "i1_questionnaire"
    name: "问卷采集"
    agent: "init_questionnaire"
    skills:
      - "run_questionnaire"
    requirement: "通过8个问题识别用户身份、目标、资产、约束、内容策略、增长飞轮"
    inputs: []
    outputs: ["_vision_answer", "_init_results_json"]
    output_type: "document"
    decision_options: ["确认", "重新填写"]

  - phase_id: "i2_gap_analysis"
    name: "缺口分析"
    agent: "gap_analyzer"
    skills:
      - "analyze_gaps"
    requirement: "基于规则库识别能力缺口，生成 GapItem 列表"
    inputs: ["_vision_answer"]
    outputs: ["_gap_list"]
    output_type: "document"

  - phase_id: "i3_task_generation"
    name: "任务生成"
    agent: "task_generator"
    skills:
      - "generate_init_tasks"
    requirement: "将缺口转化为可执行的狩猎任务（INIT-HUNT-xxx）"
    inputs: ["_gap_list"]
    outputs: ["_init_task_list"]
    output_type: "document"

  - phase_id: "i4_database_persist"
    name: "数据库持久化"
    agent: "task_persistor"
    skills:
      - "save_to_database"
    requirement: "将任务写入 tasks 表（project_id=INIT），不新建表"
    inputs: ["_init_task_list"]
    outputs: ["_persist_result"]
    output_type: "document"

  - phase_id: "i5_sop_generation"
    name: "SOP文档生成"
    agent: "sop_generator"
    skills:
      - "generate_init_sop"
    requirement: "生成 init_task_sop.md 供人工参考"
    inputs: ["_init_task_list"]
    outputs: ["_sop_document_path"]
    output_type: "document"

  - phase_id: "i6_first_hunt_trigger"
    name: "首个狩猎触发"
    agent: "hunt_trigger"
    skills:
      - "trigger_first_hunt"
    requirement: "找到第一个 P0 任务，发布 HUNT_COMPLETED 事件，可选调度到 FrostScheduler"
    inputs: ["_init_task_list"]
    outputs: ["_hunt_trigger_info"]
    output_type: "document"
    requires_confirmation: true

  - phase_id: "i7_human_confirm"
    name: "人工确认"
    agent: "human"
    skills: []
    requirement: "检查生成的任务是否符合预期，如有遗漏手动增补，确认首个狩猎目标"
    inputs: ["_init_task_list", "_sop_document_path"]
    outputs: ["_human_confirmation"]
    output_type: "decision"
    decision_options: ["确认并开始狩猎", "修改任务", "暂停"]

required_stages:
  - "i1_questionnaire"
  - "i2_gap_analysis"
  - "i3_task_generation"
  - "i4_database_persist"

forbidden_skills:
  - "direct_db_write"

content_constraints:
  max_word_count: 500
  min_word_count: 50

========== 七、文件 5：tests/test_init_questionnaire.py ==========

7.1 测试设计

测试策略：
- 不测试交互式 input()（使用 non_interactive + mock_inputs）
- 测试缺口识别规则（核心逻辑）
- 测试任务生成
- 测试导出功能
- 所有测试不依赖外部 API 或数据库

7.2 完整代码

"""
FROST-SOP 初始化问卷测试
"""

import json
import os
import tempfile
import unittest

from skills.init.questionnaire import (
    InitQuestionnaire,
    VisionAnswer,
    GapItem,
    InitTask,
    GAP_RULES,
)


class TestInitQuestionnaire(unittest.TestCase):
    """初始化问卷测试套件"""

    def setUp(self):
        """每个测试前的准备"""
        self.sample_answers = {
            "identity": "IT小白，一人公司创业者，社恐",
            "destination_6m": "零收入零读者，想建立稳定现金流",
            "destination_12m": "收入稳定，找到PMF",
            "destination_36m": "FROST平台成熟，能养活自己",
            "assets": "FROST框架，FROST-SOP平台，白皮书",
            "constraints": "零预算，每天2小时，不懂代码",
            "content_strategy": "想做小红书，但完全不知道怎么开始",
            "growth_flywheel": "不知道，还在探索",
        }

    # ----------------------------------------------------------
    # TC-001: 问卷采集（程序模式）
    # ----------------------------------------------------------

    def test_run_programmatic(self):
        """TC-001: 程序模式问卷能正常采集"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()

        self.assertEqual(answer.identity, self.sample_answers["identity"])
        self.assertEqual(answer.destination_6m, self.sample_answers["destination_6m"])
        self.assertEqual(answer.constraints, self.sample_answers["constraints"])

    # ----------------------------------------------------------
    # TC-002: 缺口识别 - 身份类
    # ----------------------------------------------------------

    def test_gap_identity_tech(self):
        """TC-002: IT小白 → 识别技术执行能力缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("tech_execution", targets)
        self.assertIn("solo_ops", targets)

    # ----------------------------------------------------------
    # TC-003: 缺口识别 - 约束类
    # ----------------------------------------------------------

    def test_gap_constraints_budget(self):
        """TC-003: 零预算 → 识别零预算工具栈缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("zero_budget_tools", targets)
        self.assertIn("no_code_automation", targets)

    # ----------------------------------------------------------
    # TC-004: 缺口识别 - 内容策略类
    # ----------------------------------------------------------

    def test_gap_content_strategy(self):
        """TC-004: 小红书 → 识别小红书运营能力缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("redbook_ops", targets)
        self.assertIn("content_strategy_design", targets)

    # ----------------------------------------------------------
    # TC-005: 缺口识别 - 增长飞轮
    # ----------------------------------------------------------

    def test_gap_flywheel(self):
        """TC-005: 不知道增长飞轮 → 识别增长飞轮设计缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertIn("flywheel_design", targets)

    # ----------------------------------------------------------
    # TC-006: 缺口去重
    # ----------------------------------------------------------

    def test_gap_deduplication(self):
        """TC-006: 同 target 的缺口只保留一次"""
        # 构造一个会触发重复的答案
        answers = {
            "identity": "IT小白",
            "destination_6m": "",
            "destination_12m": "",
            "destination_36m": "",
            "assets": "",
            "constraints": "",
            "content_strategy": "",
            "growth_flywheel": "",
        }
        q = InitQuestionnaire(non_interactive=True, mock_inputs=answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        targets = [g.suggested_hunt_target for g in gaps]
        self.assertEqual(len(targets), len(set(targets)), "存在重复 target")

    # ----------------------------------------------------------
    # TC-007: 优先级排序
    # ----------------------------------------------------------

    def test_gap_priority_sorting(self):
        """TC-007: P0 排在 P1 前面"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)

        if len(gaps) >= 2:
            priorities = [g.priority for g in gaps]
            # P0 应该在 P1 前面
            for i in range(len(priorities) - 1):
                self.assertLessEqual(
                    {"P0": 0, "P1": 1, "P2": 2}[priorities[i]],
                    {"P0": 0, "P1": 1, "P2": 2}[priorities[i + 1]],
                    f"优先级排序错误: {priorities[i]} 在 {priorities[i+1]} 之后",
                )

    # ----------------------------------------------------------
    # TC-008: 任务生成
    # ----------------------------------------------------------

    def test_task_generation(self):
        """TC-008: 缺口正确转化为任务"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        self.assertGreater(len(tasks), 0, "至少生成1个任务")

        # 检查第一个任务的结构
        first = tasks[0]
        self.assertTrue(first.task_id.startswith("INIT-HUNT-"))
        self.assertEqual(first.status, "pending")
        self.assertTrue(first.title.startswith("初始狩猎："))

    # ----------------------------------------------------------
    # TC-009: 任务与缺口关联
    # ----------------------------------------------------------

    def test_task_gap_association(self):
        """TC-009: 每个任务关联到正确的缺口"""
        q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        gap_ids = {g.gap_id for g in gaps}
        for task in tasks:
            self.assertIn(task.gap_id, gap_ids, f"任务 {task.task_id} 关联到不存在的缺口")

    # ----------------------------------------------------------
    # TC-010: 结果导出
    # ----------------------------------------------------------

    def test_export_results(self):
        """TC-010: 结果能正确导出为 JSON"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test_init_results.json")

            q = InitQuestionnaire(non_interactive=True, mock_inputs=self.sample_answers)
            q.run_full_pipeline()
            result = q.export_results(filepath)

            self.assertTrue(os.path.exists(filepath))

            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.assertIn("timestamp", data)
            self.assertIn("answers", data)
            self.assertIn("gaps", data)
            self.assertIn("tasks", data)
            self.assertGreater(len(data["gaps"]), 0)
            self.assertGreater(len(data["tasks"]), 0)

    # ----------------------------------------------------------
    # TC-011: 空答案处理
    # ----------------------------------------------------------

    def test_empty_answers(self):
        """TC-011: 空答案不会崩溃"""
        empty_answers = {q["id"]: "" for q in [
            {"id": "identity"}, {"id": "destination_6m"}, {"id": "destination_12m"},
            {"id": "destination_36m"}, {"id": "assets"}, {"id": "constraints"},
            {"id": "content_strategy"}, {"id": "growth_flywheel"},
        ]}
        q = InitQuestionnaire(non_interactive=True, mock_inputs=empty_answers)
        answer = q.run_interactive()
        gaps = q.analyze_gaps(answer)
        tasks = q.generate_tasks()

        # 空答案应该不产生崩溃，但可能识别不到任何缺口
        self.assertIsInstance(gaps, list)
        self.assertIsInstance(tasks, list)

    # ----------------------------------------------------------
    # TC-012: 全流水线一键运行
    # ----------------------------------------------------------

    def test_full_pipeline(self):
        """TC-012: run_full_pipeline 能完整运行"""
        q = InitQuestionnaire()
        result = q.run_full_pipeline(answers=self.sample_answers)

        self.assertIn("timestamp", result)
        self.assertIn("answers", result)
        self.assertIn("gaps", result)
        self.assertIn("tasks", result)
        self.assertGreater(len(result["gaps"]), 0)
        self.assertGreater(len(result["tasks"]), 0)


if __name__ == "__main__":
    unittest.main()

========== 八、文件 6：tests/test_init_task_trigger.py ==========

8.1 测试设计

测试策略：
- 使用临时 JSON 文件模拟问卷结果
- 测试数据库写入（使用真实 DBManager，但临时数据库路径）
- 测试事件发布（使用 EventBus 的 clear_subscribers）
- 测试降级模式（核心模块不可用时）
- 测试后清理数据库和文件

8.2 完整代码

"""
FROST-SOP 初始化任务触发器测试
"""

import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from skills.init.task_trigger import InitTaskTrigger, INIT_PROJECT_ID, HAS_CORE
from skills.init.questionnaire import InitQuestionnaire


class TestInitTaskTrigger(unittest.TestCase):
    """初始化任务触发器测试套件"""

    def setUp(self):
        """每个测试前准备临时环境"""
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "test_frost_sop.db")
        self.results_path = os.path.join(self.tmpdir.name, "test_init_results.json")

        # 生成样本问卷结果
        self.sample_questionnaire_result = {
            "timestamp": "2026-07-02T12:00:00",
            "answers": {
                "identity": "IT小白，一人公司",
                "destination_6m": "零收入，想盈利",
                "destination_12m": "收入稳定",
                "destination_36m": "平台成熟",
                "assets": "FROST框架",
                "constraints": "零预算",
                "content_strategy": "小红书",
                "growth_flywheel": "不知道",
            },
            "gaps": [
                {
                    "gap_id": "GAP-001",
                    "description": "技术执行能力",
                    "source_question": "identity",
                    "priority": "P0",
                    "suggested_hunt_target": "tech_execution",
                },
                {
                    "gap_id": "GAP-002",
                    "description": "零预算工具栈",
                    "source_question": "constraints",
                    "priority": "P0",
                    "suggested_hunt_target": "zero_budget_tools",
                },
                {
                    "gap_id": "GAP-003",
                    "description": "小红书运营能力",
                    "source_question": "content_strategy",
                    "priority": "P0",
                    "suggested_hunt_target": "redbook_ops",
                },
            ],
            "tasks": [
                {
                    "task_id": "INIT-HUNT-001",
                    "title": "初始狩猎：技术执行能力",
                    "target_skill": "tech_execution",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-001",
                },
                {
                    "task_id": "INIT-HUNT-002",
                    "title": "初始狩猎：零预算工具栈",
                    "target_skill": "zero_budget_tools",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-002",
                },
                {
                    "task_id": "INIT-HUNT-003",
                    "title": "初始狩猎：小红书运营能力",
                    "target_skill": "redbook_ops",
                    "priority": "P0",
                    "status": "pending",
                    "created_at": "2026-07-02T12:00:00",
                    "gap_id": "GAP-003",
                },
            ],
        }

        with open(self.results_path, "w", encoding="utf-8") as f:
            json.dump(self.sample_questionnaire_result, f, ensure_ascii=False, indent=2)

        # 如果核心模块可用，清理 EventBus 订阅者
        if HAS_CORE:
            from core.event_bus import EventBus
            EventBus.clear_subscribers(EventBus(), None)

    def tearDown(self):
        """测试后清理"""
        self.tmpdir.cleanup()

    # ----------------------------------------------------------
    # TC-001: 加载问卷结果
    # ----------------------------------------------------------

    def test_load_from_questionnaire(self):
        """TC-001: 能从 JSON 文件加载任务"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        tasks = trigger.load_from_questionnaire()

        self.assertEqual(len(tasks), 3)
        self.assertEqual(tasks[0]["task_id"], "INIT-HUNT-001")
        self.assertEqual(tasks[0]["target_skill"], "tech_execution")

    # ----------------------------------------------------------
    # TC-002: 文件不存在处理
    # ----------------------------------------------------------

    def test_load_missing_file(self):
        """TC-002: 文件不存在时返回空列表"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path="/nonexistent/path.json",
        )
        tasks = trigger.load_from_questionnaire()

        self.assertEqual(tasks, [])

    # ----------------------------------------------------------
    # TC-003: 任务数据结构
    # ----------------------------------------------------------

    def test_task_structure(self):
        """TC-003: 任务数据结构完整"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        first = trigger.tasks[0]

        required_keys = ["task_id", "title", "target_skill", "priority", "status", "gap_id"]
        for key in required_keys:
            self.assertIn(key, first, f"任务缺少 {key} 字段")

    # ----------------------------------------------------------
    # TC-004: 生成 SOP 文档
    # ----------------------------------------------------------

    def test_generate_sop(self):
        """TC-004: 能生成 SOP Markdown 文档"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        sop_path = trigger.generate_init_sop()

        self.assertTrue(os.path.exists(sop_path))
        with open(sop_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("初始化任务 SOP", content)
        self.assertIn("INIT-HUNT-001", content)

    # ----------------------------------------------------------
    # TC-005: 首个狩猎触发（P0 筛选）
    # ----------------------------------------------------------

    def test_trigger_first_hunt(self):
        """TC-005: 正确触发第一个 P0 任务"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        info = trigger.trigger_first_hunt()

        self.assertIsNotNone(info)
        self.assertEqual(info["target"], "tech_execution")  # 第一个 P0
        self.assertEqual(info["task_id"], "INIT-HUNT-001")
        self.assertIn("python main.py --hunt", info["command"])

    # ----------------------------------------------------------
    # TC-006: 无 P0 任务时
    # ----------------------------------------------------------

    def test_no_p0_tasks(self):
        """TC-006: 没有 P0 任务时返回 None"""
        # 构造只有 P1 任务的结果
        result = dict(self.sample_questionnaire_result)
        for t in result["tasks"]:
            t["priority"] = "P1"

        path = os.path.join(self.tmpdir.name, "no_p0.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f)

        trigger = InitTaskTrigger(db_path=self.db_path, init_results_path=path)
        trigger.load_from_questionnaire()
        info = trigger.trigger_first_hunt()

        self.assertIsNone(info)

    # ----------------------------------------------------------
    # TC-007: 数据库写入（如果核心模块可用）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_save_to_database(self):
        """TC-007: 任务能写入 tasks 表"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        result = trigger.save_to_database()

        self.assertTrue(result)

        # 验证数据库内容
        rows = trigger.get_init_tasks()
        self.assertGreater(len(rows), 0)

        # 验证 project_id 标记
        first = rows[0]
        self.assertEqual(first.get("project_id"), INIT_PROJECT_ID)

    # ----------------------------------------------------------
    # TC-008: 重复写入不重复（幂等性）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_idempotent_save(self):
        """TC-008: 重复保存不重复插入"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        trigger.save_to_database()
        trigger.save_to_database()  # 第二次

        rows = trigger.get_init_tasks()
        # 应该还是3条，不是6条
        self.assertEqual(len(rows), 3)

    # ----------------------------------------------------------
    # TC-009: 更新任务状态
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_update_task_status(self):
        """TC-009: 能更新任务状态"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        trigger.load_from_questionnaire()
        trigger.save_to_database()

        result = trigger.update_task_status("INIT-HUNT-001", "running")
        self.assertTrue(result)

        rows = trigger.get_init_tasks(status="running")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["id"], "INIT-HUNT-001")

    # ----------------------------------------------------------
    # TC-010: 完整流水线
    # ----------------------------------------------------------

    def test_full_pipeline(self):
        """TC-010: run_full_pipeline 完整运行"""
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path=self.results_path,
        )
        result = trigger.run_full_pipeline()

        self.assertEqual(result["tasks_count"], 3)
        self.assertEqual(result["p0_count"], 3)
        self.assertIsNotNone(result["sop_path"])
        self.assertIsNotNone(result["trigger_info"])
        self.assertTrue(os.path.exists(result["sop_path"]))

    # ----------------------------------------------------------
    # TC-011: 端到端（问卷 → 触发器）
    # ----------------------------------------------------------

    @unittest.skipUnless(HAS_CORE, "核心模块不可用")
    def test_end_to_end(self):
        """TC-011: 问卷 → 触发器 完整端到端"""
        # 1. 运行问卷
        q = InitQuestionnaire(non_interactive=True, mock_inputs={
            "identity": "IT小白",
            "destination_6m": "零收入",
            "destination_12m": "",
            "destination_36m": "",
            "assets": "FROST框架",
            "constraints": "零预算",
            "content_strategy": "小红书",
            "growth_flywheel": "不知道",
        })
        q.run_full_pipeline()

        # 2. 运行触发器
        trigger = InitTaskTrigger(
            db_path=self.db_path,
            init_results_path="init_results.json",
        )
        result = trigger.run_full_pipeline()

        self.assertGreater(result["tasks_count"], 0)
        self.assertGreater(result["p0_count"], 0)

        # 3. 验证数据库
        rows = trigger.get_init_tasks()
        self.assertGreater(len(rows), 0)


if __name__ == "__main__":
    unittest.main()

========== 九、审计标准（AD-001 ~ AD-012） ==========

AD-001. 新增文件数量 = 6 个（skills/init/__init__.py, questionnaire.py, task_trigger.py, sops/templates/INIT-001.yaml, tests/test_init_questionnaire.py, tests/test_init_task_trigger.py）
AD-002. 不修改已有文件（向后兼容）
AD-003. 问卷模块不依赖数据库（纯 Python 标准库）
AD-004. 任务触发器使用现有 tasks 表（project_id="INIT"），不新建表
AD-005. 任务触发器软依赖核心模块（降级到 JSON 存储）
AD-006. 所有函数 McCabe 复杂度 < 10
AD-007. 问卷测试 ≥ 12 个测试用例，全部通过
AD-008. 触发器测试 ≥ 11 个测试用例，核心模块可用时全部通过
AD-009. 端到端测试（问卷 → 触发器）通过
AD-010. 无硬编码密钥
AD-011. 可复现（提供 mock_inputs 支持程序化调用）
AD-012. 代码可运行（python -m skills.init.questionnaire 和 python -m skills.init.task_trigger）

========== 十、执行顺序 ==========

步骤1：创建目录（5分钟）
  mkdir skills/init
  echo. > skills/init/__init__.py
  mkdir sops/generated（如果缺失）

步骤2：创建文件（15分钟）
  按顺序写入 6 个文件

步骤3：运行测试（20分钟）
  python -m pytest tests/test_init_questionnaire.py -v
  python -m pytest tests/test_init_task_trigger.py -v

步骤4：手动验证（10分钟）
  python -m skills.init.questionnaire（交互式，用自己的真实答案）
  python -m skills.init.task_trigger（从问卷结果触发）

步骤5：审计（10分钟）
  验证 AD-001 ~ AD-012

总工作量：约1小时

========== 十一、已知限制（诚实声明） ==========

LIM-001. 缺口识别基于关键词规则，不是 LLM 智能分析。复杂缺口可能识别不全。
LIM-002. 任务触发器的 FrostScheduler 调度功能需要 apscheduler 已安装。
LIM-003. 事件发布依赖 EventBus 已初始化（首次运行时需要先初始化 DB）。
LIM-004. 问卷的交互模式在 Windows 终端可能有编码问题（建议使用 UTF-8）。
LIM-005. 没有前端界面（Streamlit），纯 CLI 交互。

========== 十二、向后兼容检查清单 ==========

[ ] skills/__init__.py 未被修改（保持空文件）
[ ] core/db.py 未被修改（ALLOWED_TABLES 未新增表）
[ ] core/event_bus.py 未被修改
[ ] core/scheduler.py 未被修改
[ ] 所有现有测试仍然通过

========== 结束 ==========
