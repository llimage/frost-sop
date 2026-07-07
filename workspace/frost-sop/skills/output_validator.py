"""
FROST-SOP Output Validator Skill
在每个SOP阶段完成后，验证输出是否主题一致、格式合规。
如果验证失败，注入纠正prompt并重试。
"""

from core.skill import Skill


def validate_output(context: dict) -> dict:
    """
    验证阶段输出是否合格。

    输入 context 键：
        _output_to_validate: str —— 待验证的输出文本
        _expected_topic: str —— 期望主题关键词（逗号分隔）
        _validation_type: str —— 验证类型（"topic"主题一致性 / "format"格式合规 / "both"两者）
        _stage_name: str —— 当前阶段名称（用于日志）

    输出 context 键：
        _validation_passed: bool —— 验证是否通过
        _validation_issues: list —— 发现的问题列表
        _correction_prompt: str —— 纠正prompt（如果验证失败）
    """

    output = context.get("_output_to_validate", "")
    expected_topic = context.get("_expected_topic", "")
    validation_type = context.get("_validation_type", "both")
    stage_name = context.get("_stage_name", "未知阶段")

    issues = []
    passed = True

    # 1. 主题一致性验证
    if validation_type in ("topic", "both"):
        if expected_topic:
            keywords = [kw.strip() for kw in expected_topic.split(",")]
            found_keywords = [kw for kw in keywords if kw in output]
            if not found_keywords:
                issues.append(f"主题偏移：输出中未找到期望关键词 {keywords}")
                passed = False
            else:
                # 检查是否包含无关主题（硬编码常见问题）
                drift_keywords = [
                    "微服务",
                    "Kubernetes",
                    "K8s",
                    "医疗影像",
                    "智能客服",
                    "Spring Cloud",
                ]
                found_drift = [dk for dk in drift_keywords if dk in output]
                if found_drift:
                    issues.append(f"主题偏移：输出包含无关关键词 {found_drift}")
                    passed = False

    # 2. 格式合规性验证
    if validation_type in ("format", "both"):
        # 必须以#开头
        if not output.strip().startswith(("#", "##")):
            issues.append("格式不合规：输出未以Markdown标题开头")
            passed = False
        # 禁止寒暄语
        if any(g in output[:50] for g in ["好的", "我来", "以下是", "根据您"]):
            issues.append("格式不合规：输出包含寒暄语")
            passed = False

    # 3. 构造纠正prompt（如果验证失败）
    correction_prompt = ""
    if not passed:
        correction_prompt = (
            f"【纠正指令】你刚才的输出存在问题：\n"
            f"{chr(10).join(['- ' + i for i in issues])}\n\n"
            f"请重新生成输出，严格遵守以下规则：\n"
            f"1. 必须围绕主题「{expected_topic}」展开，不要引入无关话题\n"
            f"2. 输出必须以Markdown标题(##)开头\n"
            f"3. 不要有任何寒暄语\n"
            f"4. 严格基于前序阶段的输出继续，不要重新假设主题\n"
        )

    context["_validation_passed"] = passed
    context["_validation_issues"] = issues
    context["_correction_prompt"] = correction_prompt
    context["_reason"] = (
        f"阶段'{stage_name}'验证{'通过' if passed else '失败'}：{len(issues)}个问题"
    )
    return context


# 导出为Skill实例
validate_output_skill = Skill("validate_output", validate_output)
