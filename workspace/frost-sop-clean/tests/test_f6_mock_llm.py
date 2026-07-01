"""
F6 测试辅助：Mock LLM 响应生成器（v3）
通过 mock skils.llm.OpenAI 引用，使集成测试不依赖真实LLM调用。
"""

import unittest.mock as mock


def _make_mock_response(content: str):
    """构造模拟的 OpenAI API 响应对象"""
    mock_response = mock.MagicMock()
    mock_choice = mock.MagicMock()
    mock_message = mock.MagicMock()
    mock_message.content = content
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]
    mock_usage = mock.MagicMock()
    mock_usage.prompt_tokens = 100
    mock_usage.completion_tokens = len(content) // 4
    mock_usage.total_tokens = 100 + len(content) // 4
    mock_response.usage = mock_usage
    return mock_response


def _generate_mock_content(prompt: str) -> str:
    """根据 prompt 关键词生成合理的 mock 响应内容"""
    p = prompt.lower()

    if "需求" in prompt or "requirement" in p:
        return "# 需求分析\n\n## 功能需求\n- FR-001: 用户认证\n- FR-002: Token管理"
    if "设计" in prompt or "design" in p or "架构" in prompt:
        return "# 技术设计\n\n## 系统架构\n采用分层架构，认证模块独立部署。"
    if "代码" in prompt or "code" in p or "implement" in p:
        return "# 代码实现\n\n已完成代码生成，输出文件：auth.py, models.py, tests.py"
    if "测试" in prompt or "test" in p:
        return "# 测试验证\n\n| 用例 | 状态 |\n|------|------|\n| TC-001 | PASS |"
    if "审查" in prompt or "audit" in p or "review" in p:
        return "# 审查报告\n\n✅ 代码质量良好，无重大问题。"
    if "选题" in prompt or "topic" in p:
        return "# 选题策划\n\n主题：FROST框架——分形AI Agent"
    if "内容" in prompt or "文案" in prompt or "copy" in p:
        return "# FROST框架推广文案\n\nFROST是一个创新的分形AI Agent框架，支持家族式自治。主要特性：分形治理、SOP驱动、资产传承。"
    if "财务" in prompt or "financial" in p or "报表" in prompt:
        return "# 财务报告\n\n| 项目 | 金额 |\n|------|------|\n| 收入 | 200000 |\n| 支出 | 140000 |\n| 结余 | 60000 |"
    if "知识" in prompt or "knowledge" in p or "资产" in prompt:
        return "# 知识资产清单\n\n已盘点本周知识资产，共5项。"
    if "市场" in prompt or "market" in p or "调研" in prompt:
        return "# 市场调研报告\n\n目标用户：技术团队负责人。需求：Agent编排能力。"
    if "可行性" in prompt or "feasibility" in p:
        return "# 可行性分析\n\n技术可行性：高。资源需求：可接受。建议：立项。"
    if "方案" in prompt or "solution" in p:
        return "# 项目技术方案\n\n采用分形架构，核心模块：Agent编排引擎、SOP执行引擎。"
    if "资源" in prompt or "resource" in p or "时间" in p:
        return (
            "# 资源规划\n\n需要2名开发者，预计8周完成。里程碑：M1核心框架，M2 SOP库。"
        )
    if "历史" in prompt or "history" in p or "任务" in prompt:
        return '{"task-001": {"sop": "DEV-001", "status": "completed"}, "task-002": {"sop": "DEV-001", "status": "completed"}, "task-003": {"sop": "DEV-001", "status": "completed"}, "task-004": {"sop": "DEV-002", "status": "failed"}, "task-005": {"sop": "DEV-001", "status": "failed"}}'
    if "趋势" in prompt or "trend" in p:
        return '{"total": 5, "successful": 3, "failed": 2, "success_rate": 0.6, "suggestions": ["增加重试机制", "优化SOP结构"]}'
    if "建议" in prompt or "suggestion" in p:
        return "# 优化建议\n\n1. 增加LLM调用重试机制（高优先级）\n2. 优化DEV-002 SOP结构（中优先级）"
    if "批准" in prompt or "approval" in p or "确认" in p:
        return "# 审批结果\n\n✅ 建议1：批准（高优先级）\n✅ 建议2：批准（中优先级）"

    return f"[MOCK] 已完成任务：{prompt[:50]}"


def patch_openai():
    """
    返回一个 context manager，在 with 块内 mock skils.llm.OpenAI 引用。
    这样 call_llm 函数中的 OpenAI(...) 调用会使用 mock 客户端。

    用法：
    with patch_openai():
        # 在此范围内，所有 LLM API 调用均被 mock
        ...
    """
    # 创建一个 mock 客户端
    mock_response = _make_mock_response("default")

    mock_completions = mock.MagicMock()
    mock_completions.create.return_value = mock_response
    mock_chat = mock.MagicMock()
    mock_chat.completions = mock_completions
    mock_client = mock.MagicMock()
    mock_client.chat = mock_chat

    # 让 create 根据 messages 动态返回不同内容
    def side_effect(**kwargs):
        messages = kwargs.get("messages", [])
        last_msg = ""
        for m in messages:
            if m.get("role") == "user":
                last_msg = m.get("content", "")

        content = _generate_mock_content(last_msg)
        resp = _make_mock_response(content)
        return resp

    mock_completions.create.side_effect = side_effect

    # 关键：patch skils.llm.OpenAI（使用点），而非 openai.OpenAI
    return mock.patch("skills.llm.OpenAI", return_value=mock_client, create=True)
