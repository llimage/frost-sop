"""
F7 生产加固 - 成本熔断（月度预算控制）
PHILOSOPHY: 月度预算 ¥300，80% 预警，100% 熔断。

core/cost.py - 成本追踪模块
提供 CostTracker 类，负责成本追踪和预算检查。
"""

import json
from datetime import date
from typing import Dict, Any

from core.db import get_db


class BudgetExceededError(Exception):
    """预算超支异常"""

    pass


class CostTracker:
    """
    成本追踪器

    负责：
    1. 追踪每次 LLM 调用的成本
    2. 检查预算使用率
    3. 在超预算时抛出 BudgetExceededError
    """

    def __init__(self, monthly_budget: float = 300.0, alert_ratio: float = 0.8):
        """
        初始化成本追踪器

        Args:
            monthly_budget: 月度预算（元），默认 ¥300
            alert_ratio: 预警比例，默认 80%
        """
        self.monthly_budget = monthly_budget
        self.alert_ratio = alert_ratio
        self._db = get_db()

    def track_cost(self, agent_id: str, tokens: int, model: str = "default") -> float:
        """
        追踪成本

        Args:
            agent_id: Agent ID
            tokens: 使用的 Token 数
            model: 模型名称

        Returns:
            本次调用的估算成本（元）
        """
        # 估算成本（简化版：假设 1K tokens = ¥0.001）
        # 实际应该根据模型的不同而不同
        cost_per_1k_tokens = 0.001
        estimated_cost = (tokens / 1000) * cost_per_1k_tokens

        # 写入成本日志
        self._db.insert(
            "cost_log",
            {
                "task_id": None,  # 可以在调用时传入
                "agent_id": agent_id,
                "model": model,
                "input_tokens": tokens,
                "output_tokens": 0,
                "total_tokens": tokens,
                "estimated_cost": estimated_cost,
            },
        )

        return estimated_cost

    def check_budget(self, year: int = None, month: int = None) -> Dict[str, Any]:
        """
        检查预算使用率

        Args:
            year: 年份（默认当前年份）
            month: 月份（默认当前月份）

        Returns:
            包含预算使用信息的字典
        """
        if year is None or month is None:
            today = date.today()
            year = today.year
            month = today.month

        # 获取本月总成本
        total_cost = self._db.get_monthly_cost(year, month)

        # 计算使用率
        usage_ratio = total_cost / self.monthly_budget if self.monthly_budget > 0 else 0

        # 确定状态
        if usage_ratio >= 1.0:
            status = "exceeded"  # 超预算
        elif usage_ratio >= self.alert_ratio:
            status = "warning"  # 预警
        else:
            status = "normal"  # 正常

        return {
            "monthly_budget": self.monthly_budget,
            "total_cost": total_cost,
            "usage_ratio": usage_ratio,
            "remaining": self.monthly_budget - total_cost,
            "status": status,
            "alert_ratio": self.alert_ratio,
        }

    def check_and_throw(self, agent_id: str, tokens: int, model: str = "default"):
        """
        检查预算，如果超预算则抛出 BudgetExceededError

        Args:
            agent_id: Agent ID
            tokens: 计划使用的 Token 数
            model: 模型名称

        Raises:
            BudgetExceededError: 如果预算已用完
        """
        budget_info = self.check_budget()

        if budget_info["status"] == "exceeded":
            raise BudgetExceededError(
                f"预算已用完！本月已使用 ¥{budget_info['total_cost']:.2f} / ¥{budget_info['monthly_budget']:.2f}"
            )

        # 追踪成本
        self.track_cost(agent_id, tokens, model)

    def update_budget_config(
        self, monthly_budget: float = None, alert_ratio: float = None
    ):
        """
        更新预算配置

        Args:
            monthly_budget: 新的月度预算
            alert_ratio: 新的预警比例
        """
        if monthly_budget is not None:
            self.monthly_budget = monthly_budget
        if alert_ratio is not None:
            self.alert_ratio = alert_ratio

        # 保存到配置表
        self._db.insert(
            "config",
            {
                "key": "cost_budget",
                "value": json.dumps(
                    {
                        "monthly_budget": self.monthly_budget,
                        "alert_ratio": self.alert_ratio,
                    }
                ),
                "description": "成本预算配置",
            },
        )


# 全局成本追踪器（单例）
_cost_tracker = None


def get_cost_tracker() -> CostTracker:
    """
    获取成本追踪器（单例）

    Returns:
        CostTracker 实例
    """
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = CostTracker()
    return _cost_tracker


def test_cost_tracker():
    """测试 CostTracker 功能"""
    print("=" * 60)
    print("测试 CostTracker (成本熔断)")
    print("=" * 60)

    # 创建成本追踪器（使用小预算进行测试）
    tracker = CostTracker(monthly_budget=0.01, alert_ratio=0.8)

    # 测试成本追踪
    print("\n[1] 测试成本追踪...")
    cost = tracker.track_cost("test_agent", 1000, "test_model")
    print(f"  本次成本: ¥{cost:.4f}")

    # 测试预算检查
    print("\n[2] 测试预算检查...")
    budget_info = tracker.check_budget()
    print(f"  预算: ¥{budget_info['monthly_budget']:.2f}")
    print(f"  已用: ¥{budget_info['total_cost']:.4f}")
    print(f"  使用率: {budget_info['usage_ratio'] * 100:.1f}%")
    print(f"  状态: {budget_info['status']}")

    # 测试预算熔断
    print("\n[3] 测试预算熔断...")
    try:
        tracker.check_and_throw("test_agent", 1000, "test_model")
        print("  ❌ 未触发熔断（预期外）")
    except BudgetExceededError as e:
        print(f"  ✅ 触发熔断: {e}")

    print("\n✅ CostTracker 测试完成")
    return True


if __name__ == "__main__":
    test_cost_tracker()
