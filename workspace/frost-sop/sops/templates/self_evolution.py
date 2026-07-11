"""
FROST-SOP V9.1: 自进化 SOP
流程: 错误记录 → 教训归档 → 复盘分析 → 系统进化

PHILOSOPHY: 系统从自己的失败中学习，持续改进。
"""

from core.sop import SOP, SOPStage


# 自进化 SOP 定义
SELF_EVOLUTION_SOP = SOP(
    sop_id="SELF-EVOLUTION-001",
    name="系统自进化",
    description="从错误中学习，持续改进系统能力和流程",
    version="1.0.0",
    stages=[
        SOPStage(
            id="SE-001",
            name="错误检测与记录",
            description="检测系统运行中的错误和异常，记录到错误日志",
            agent_type="monitor",
            required_keys=["_error_record"],
            output_keys=["_error_logged"],
            timeout_minutes=5,
        ),
        SOPStage(
            id="SE-002",
            name="教训归档",
            description="将错误记录转化为结构化教训，存入知识库",
            agent_type="lesson_archivist",
            required_keys=["_error_record"],
            output_keys=["_lesson_id", "_lesson"],
            timeout_minutes=10,
        ),
        SOPStage(
            id="SE-003",
            name="趋势分析",
            description="分析历史错误和教训，识别模式和趋势",
            agent_type="analyst",
            required_keys=["_lesson_history"],
            output_keys=["_trends", "_insights"],
            timeout_minutes=15,
        ),
        SOPStage(
            id="SE-004",
            name="复盘决策",
            description="基于趋势分析，生成系统优化建议，等待创始人确认",
            agent_type="ceo",
            required_keys=["_trends", "_insights"],
            output_keys=["_optimization_proposals"],
            timeout_minutes=30,  # 人类府兵超时: 30分钟
            human_decision=True,
        ),
        SOPStage(
            id="SE-005",
            name="系统进化",
            description="执行批准的优化建议，更新 SOP/Skill/配置",
            agent_type="executor",
            required_keys=["_approved_proposals"],
            output_keys=["_evolution_applied", "_version_bump"],
            timeout_minutes=20,
        ),
        SOPStage(
            id="SE-006",
            name="验证与回滚",
            description="验证进化后的系统是否正常工作，失败则回滚",
            agent_type="tester",
            required_keys=["_evolution_applied"],
            output_keys=["_validation_result", "_rollback_triggered"],
            timeout_minutes=15,
        ),
    ],
)


def create_self_evolution_task(error_record: dict) -> dict:
    """
    创建自进化任务。
    
    Args:
        error_record: 错误记录，包含:
            - error_type: 错误类型
            - error_message: 错误信息
            - component: 出错的组件
            - context: 上下文信息
    
    Returns:
        任务上下文
    """
    return {
        "_sop_id": "SELF-EVOLUTION-001",
        "_error_record": error_record,
        "_task_type": "self_evolution",
    }


# 导出 SOP 实例
__all__ = ["SELF_EVOLUTION_SOP", "create_self_evolution_task"]
