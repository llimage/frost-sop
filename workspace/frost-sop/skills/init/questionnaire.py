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
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any

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

QUESTION_DEFINITIONS: list[dict[str, Any]] = [
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
        "prompt": ("\n【问题2-2】12个月后，你在哪里？\n> "),
        "gap_keywords": ["零", "没有", "未", "待", "找", "探索", "稳定"],
    },
    {
        "id": "destination_36m",
        "prompt": ("\n【问题2-3】36个月后，你在哪里？\n> "),
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
        (
            ["不明确", "模糊", "不知道", "未确定", "空白"],
            "content_strategy_design",
            "内容策略设计",
            "P0",
        ),
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

    def __init__(self, non_interactive: bool = False, mock_inputs: dict[str, str] | None = None):
        """
        Args:
            non_interactive: 是否非交互模式（用于测试）
            mock_inputs: 非交互模式下的预置答案
        """
        self.non_interactive = non_interactive
        self.mock_inputs = mock_inputs or {}
        self.answers: dict[str, dict[str, Any]] = {}
        self.gaps: list[GapItem] = []
        self.tasks: list[InitTask] = []

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

    def _ask_question(self, q_def: dict[str, Any]) -> str:
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

    def analyze_gaps(self, answer: VisionAnswer) -> list[GapItem]:
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

        # 按优先级排序
        self._sort_gaps_by_priority()
        logger.info("[InitQuestionnaire] 缺口分析完成: %d 个缺口", len(self.gaps))
        return self.gaps

    def _match_keywords(self, text: str, keywords: list[str]) -> bool:
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

        if (
            has_monetization_goal
            and has_assets
            and not self._has_gap_with_target("asset_monetization")
        ):
            self.gaps.append(
                GapItem(
                    gap_id=f"GAP-{counter:03d}",
                    description="资产变现路径",
                    source_question="assets",
                    priority="P1",
                    suggested_hunt_target="asset_monetization",
                )
            )

    def _sort_gaps_by_priority(self) -> None:
        """按优先级排序：P0 > P1 > P2"""
        priority_order = {"P0": 0, "P1": 1, "P2": 2}
        self.gaps.sort(key=lambda g: priority_order.get(g.priority, 99))

    # ----------------------------------------------------------
    # 阶段 3：任务生成
    # ----------------------------------------------------------

    def generate_tasks(self) -> list[InitTask]:
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

    def export_results(self, filepath: str = "init_results.json") -> dict[str, Any]:
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

    def run_full_pipeline(self, answers: dict[str, str] | None = None) -> dict[str, Any]:
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


def run_questionnaire() -> dict[str, Any]:
    """CLI 入口：运行交互式问卷"""
    q = InitQuestionnaire()
    return q.run_full_pipeline()


if __name__ == "__main__":
    run_questionnaire()
