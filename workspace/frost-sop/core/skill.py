"""
PHILOSOPHY:
Skill is a stateless capability unit (like a protein).
Receives context dict, returns updated context dict.

V2.0: 增加错误处理、输入验证、输出验证、超时控制
"""

import logging

logger = logging.getLogger(__name__)


class Skill:
    """
    PHILOSOPHY: A protein. Stateless capability unit.
    Receives context dict, returns updated context dict.

    V2.0: 增加容错机制，确保 Skill 错误不中断任务链。
    """

    def __init__(
        self,
        name: str,
        func,
        required_keys: list[str] | None = None,
        output_schema: dict[str, type] | None = None,
        timeout_seconds: int = 60,
    ):
        """
        Initialize a Skill.

        Args:
            name: The name of the skill
            func: A pure function with signature func(context: dict) -> dict
            required_keys: 必需的输入 context 键列表（可选）
            output_schema: 期望的输出类型检查 {key: type}（可选）
            timeout_seconds: 执行超时（秒），默认 60
        """
        self.name = name
        self._func = func
        self._required_keys = required_keys or []
        self._output_schema = output_schema or {}
        self._timeout_seconds = timeout_seconds

    def execute(self, context: dict) -> dict:
        """
        Execute the skill function with full error handling.

        执行流程：
        1. 输入验证（检查必需键）
        2. 超时保护执行
        3. 输出验证（检查是否为 dict）
        4. 输出 schema 验证（检查类型）
        5. 错误记录到 context，不抛异常

        Args:
            context: The input context dictionary

        Returns:
            Updated context dictionary. On error, returns context with _skill_error keys.
        """
        # 1. 输入验证
        for key in self._required_keys:
            if key not in context:
                logger.error("[%s] 缺少必需输入: %s", self.name, key)
                context["_skill_error"] = f"缺少必需输入: {key}"
                context["_skill_error_name"] = self.name
                context["_skill_failed"] = True
                return context

        # 2. 执行（带超时保护）
        try:
            # Unix 系统使用 signal 设置超时
            import signal

            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Skill {self.name} 执行超过 {self._timeout_seconds} 秒")

            old_handler = None
            try:
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(self._timeout_seconds)
            except (AttributeError, ValueError):
                pass  # Windows 不支持 signal.SIGALRM

            try:
                result = self._func(context)
            finally:
                try:
                    signal.alarm(0)
                    if old_handler is not None:
                        signal.signal(signal.SIGALRM, old_handler)
                except (AttributeError, ValueError):
                    pass

        except TimeoutError as e:
            logger.error("[%s] 执行超时: %s", self.name, e)
            context["_skill_error"] = f"执行超时: {e}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context
        except Exception as e:
            logger.error("[%s] 执行异常: %s", self.name, e, exc_info=True)
            context["_skill_error"] = f"执行异常: {type(e).__name__}: {e}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context

        # 3. 输出验证：必须是 dict
        if not isinstance(result, dict):
            logger.error(
                "[%s] 返回值类型错误: 期望 dict, 实际 %s",
                self.name,
                type(result).__name__,
            )
            context["_skill_error"] = f"返回值类型错误: 期望 dict, 实际 {type(result).__name__}"
            context["_skill_error_name"] = self.name
            context["_skill_failed"] = True
            return context

        # 4. 输出 schema 检查
        for key, expected_type in self._output_schema.items():
            if key in result and not isinstance(result[key], expected_type):
                logger.error(
                    "[%s] 输出类型不匹配: %s 期望 %s, 实际 %s",
                    self.name,
                    key,
                    expected_type.__name__,
                    type(result[key]).__name__,
                )
                context["_skill_error"] = f"输出类型不匹配: {key}"
                context["_skill_error_name"] = self.name
                context["_skill_failed"] = True
                return context

        # 5. 成功：合并结果
        if "_skill_failed" in context:
            del context["_skill_failed"]
        context.update(result)
        context["_reason"] = result.get("_reason", f"Skill {self.name} 执行成功")
        return context
