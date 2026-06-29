"""
FROST V5.0 Panel 端到端演示

演示流程：
1. 创建模拟任务（task:auth_001）
2. 面板生成器自动生成面板
3. CLI 渲染引擎渲染面板到终端
4. 模拟用户交互（决策输入）

运行方式：
    cd workspace/frost-sop
    python examples/panel_demo.py
"""

import sys
from datetime import datetime

# 添加项目路径
sys.path.insert(0, '.')

from core.panel import PanelDefinition, PanelType, ComponentType
from core.panel_generator import generate_panel
from renderers.cli_renderer import CliRenderer, CliDataProvider
from core.panel_decision import DecisionFlow, DecisionStatus


def create_mock_task():
    """
    创建模拟任务——模拟 FROST 中从 Store 读取的任务数据。

    任务类型：新功能开发（需要决策）
    SOP 阶段：需求分析 → 代码实现 → 质量审核（决策点）→ 部署
    """
    return {
        "task_id": "auth_001",
        "name": "Add user authentication",
        "description": "实现用户登录、注册、密码重置功能",
        "status": "waiting",  # 等待决策
        "priority": "high",
        "current_stage_index": 2,
        "current_stage": {
            "name": "质量审核",
            "is_decision_point": True,
            "inputs": [
                {"label": "审核意见", "required": True, "type": "textarea"}
            ],
            "outputs": [
                {"name": "审核报告", "type": "document"},
                {"name": "代码覆盖率", "type": "code", "language": "python"}
            ],
            "decision_options": ["确认", "驳回", "修改"]
        },
        "stages": [
            {"name": "需求分析", "status": "completed"},
            {"name": "代码实现", "status": "completed"},
            {"name": "质量审核", "status": "waiting"},
            {"name": "部署", "status": "pending"}
        ],
        "quality_score": {
            "customer": 85,
            "parent": 80,
            "child": 70
        },
        "cost": 0.15,
        "requires_briefing": True,
    }


def create_mock_data():
    """创建模拟数据——用于 CLI 渲染引擎的数据提供者"""
    return {
        # 任务状态
        "task.status": "waiting",
        "task.quality_score": {"customer": 85, "parent": 80, "child": 70},
        "task.cost": 0.15,

        # 家族健康度
        "family:health_overview": {
            "财务": 85,
            "运营": 72,
            "治理": 90,
            "客户": 68
        },

        # 待审批任务
        "family:pending_decisions": [
            {"任务名称": "auth_001", "阶段": "质量审核", "等待时长": "30分钟", "紧急度": "高"},
            {"任务名称": "api_002", "阶段": "代码审查", "等待时长": "2小时", "紧急度": "中"}
        ],

        # 军师简报
        "intel:latest_strategist_brief": """
## 军师简报（2026-06-28）

### 任务进展
- **auth_001**：质量审核阶段，代码覆盖率 87%，超过阈值 80%
- **api_002**：代码审查中，发现 2 个潜在安全漏洞

### 建议
- auth_001 建议 **确认**，质量评分达标
- api_002 建议 **修改**，先修复安全漏洞
""",

        # 告警
        "immune:active_alerts": [
            {"level": "high", "message": "api_002 发现安全漏洞 CVE-2026-1234"},
            {"level": "medium", "message": "任务 auth_001 等待决策超过 30 分钟"}
        ],

        # 最近任务
        "family:recent_tasks": [
            {"timestamp": "2026-06-28 09:00", "description": "创建任务 auth_001"},
            {"timestamp": "2026-06-28 09:30", "description": "完成阶段：需求分析"},
            {"timestamp": "2026-06-28 11:00", "description": "完成阶段：代码实现"},
            {"timestamp": "2026-06-28 14:00", "description": "进入决策点：质量审核"},
        ],
    }


def demo_task_panel():
    """演示 1：任务面板（决策点）"""
    print("=" * 60)
    print("演示 1：任务面板（决策点）")
    print("=" * 60)
    print()

    # 1. 创建模拟任务
    task = create_mock_task()
    print(f"[模拟] 创建任务：{task['name']} (ID: {task['task_id']})")
    print()

    # 2. 生成面板
    print("[生成] 调用 generate_panel() 自动生成面板...")
    panel = generate_panel(task)
    print(f"  面板 ID: {panel.panel_id}")
    print(f"  面板类型: {panel.panel_type.value}")
    print(f"  组件数量: {len(panel.components)}")
    print()

    # 3. 渲染面板
    print("[渲染] 使用 CliRenderer 渲染面板到终端...")
    print()

    data_provider = CliDataProvider(data=create_mock_data())
    renderer = CliRenderer(data_provider=data_provider)
    renderer.render(panel)

    print()
    print("[交互] 模拟 Human Agent 决策输入...")
    print("  请输入选项编号（1-3）: 1")
    print("  → 决策结果：确认")
    print()


def demo_cockpit_panel():
    """演示 2：驾驶舱面板"""
    print()
    print("=" * 60)
    print("演示 2：驾驶舱面板（家族概览）")
    print("=" * 60)
    print()

    # 1. 创建驾驶舱任务（特殊格式）
    task = {
        "task_id": "monitor_001",
        "name": "Family Monitor",
        "status": "running",
    }

    # 2. 手动创建驾驶舱面板
    from core.panel import LayoutType, Region, Theme
    from core.panel_generator import PanelGenerator

    generator = PanelGenerator()
    panel = generator.generate(task)
    panel.panel_type = PanelType.COCKPIT
    panel.title = "家族驾驶舱"
    panel.subtitle = "实时概览"
    panel.layout = generator._generate_layout(PanelType.COCKPIT, task)
    panel.components = generator._create_cockpit_components(task)

    print(f"[生成] 驾驶舱面板：{panel.title}")
    print(f"  组件数量: {len(panel.components)}")
    print()

    # 3. 渲染面板
    print("[渲染] 使用 CliRenderer 渲染驾驶舱...")
    print()

    data_provider = CliDataProvider(data=create_mock_data())
    renderer = CliRenderer(data_provider=data_provider)
    renderer.render(panel)


def demo_decision_flow():
    """演示 3：决策流程状态机"""
    print()
    print("=" * 60)
    print("演示 3：决策流程状态机（DecisionFlow）")
    print("=" * 60)
    print()

    # 1. 创建决策流程
    flow = DecisionFlow()
    print("[创建] DecisionFlow 状态机")

    # 2. 创建决策记录（模拟 SOP 遇到决策点）
    task = create_mock_task()
    record = flow.create_decision(
        task_id=task["task_id"],
        stage_id="stage_3",
        stage_name=task["current_stage"]["name"],
        context_before={
            "outputs": task["current_stage"]["outputs"],
            "quality_score": task["quality_score"],
        }
    )

    print(f"  决策 ID: {record.decision_id}")
    print(f"  状态: {record.status.value}")
    print()

    # 3. 模拟 Human Agent 决策
    print("[决策] 模拟 Human Agent 输入...")
    print("  选择：确认")
    print("  理由：（无，直接确认）")
    print()

    updated = flow.submit_decision(
        decision_id=record.decision_id,
        decision="确认",
        human_agent_id="monarch"
    )

    print(f"  更新后状态: {updated.status.value}")
    print(f"  决策时间: {updated.decided_at}")
    print()

    # 4. 显示决策统计
    stats = flow.get_decision_stats()
    print("[统计] 决策统计：")
    for key, value in stats.items():
        print(f"  {key}: {value}")


def main():
    """主函数——运行所有演示"""
    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 12 + "FROST V5.0 Panel 端到端演示" + " " * 19 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    # 演示 1：任务面板
    demo_task_panel()

    # 演示 2：驾驶舱面板
    demo_cockpit_panel()

    # 演示 3：决策流程
    demo_decision_flow()

    print()
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 18 + "演示完成" + " " * 27 + "║")
    print("╚" + "═" * 58 + "╝")
    print()
    print("[OK] 总结：")
    print("  [OK] 面板生成器能根据任务自动生成 PanelDefinition")
    print("  [OK] CLI 渲染引擎能将 PanelDefinition 渲染到终端")
    print("  [OK] 决策流程状态机完整实现了 Human Agent 决策流程")
    print()
    print("下一步：")
    print("  - 实现 Streamlit 渲染引擎（renderers/streamlit_renderer.py）")
    print("  - 与 SOP 执行引擎集成（SOP 遇到决策点时自动生成面板）")
    print("  - 与事件系统集成（面板交互触发事件）")
    print()


if __name__ == "__main__":
    main()
