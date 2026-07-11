"""
FROST-SOP V8.0 编码规范检查 Skill
硬性要求自动化检查：异常清单先行、零静默失败、防御式编程、可观测性、代码分层
"""

import ast
import inspect
import re
from typing import Any

from core.skill import Skill


class CodeValidatorSkill(Skill):
    """
    编码规范检查 Skill - 自动化验证 V8.0 五大硬性要求
    """

    def __init__(self):
        super().__init__("code_validator", self.validate_code)

    # ──────────────────────────────────────────────────────────────────────────
    # 主入口
    # ──────────────────────────────────────────────────────────────────────────

    def validate_code(self, code: str, filename: str = "<unknown>") -> dict[str, Any]:
        """
        对代码进行全量硬性要求检查

        Args:
            code: 源代码字符串
            filename: 文件名（用于报告）

        Returns:
            {
                "passed": bool,
                "score": float,  # 0-100
                "violations": list[dict],
                "summary": str,
            }
        """
        violations = []

        # 1. 异常清单先行检查
        v = self._check_exception_manifest(code, filename)
        violations.extend(v)

        # 2. 零静默失败检查
        v = self._check_no_silent_failures(code, filename)
        violations.extend(v)

        # 3. 防御式编程检查
        v = self._check_defensive_programming(code, filename)
        violations.extend(v)

        # 4. 可观测性检查
        v = self._check_observability(code, filename)
        violations.extend(v)

        # 5. 代码分层检查
        v = self._check_layer_boundary(code, filename)
        violations.extend(v)

        score = max(0, 100 - len(violations) * 5)
        passed = score >= 80

        return {
            "passed": passed,
            "score": score,
            "violations": violations,
            "summary": f"{filename}: {len(violations)} 项违规, 得分 {score}/100",
        }

    # ──────────────────────────────────────────────────────────────────────────
    # 检查 1: 异常清单先行
    # ──────────────────────────────────────────────────────────────────────────

    def _check_exception_manifest(self, code: str, filename: str) -> list[dict]:
        """
        检查每个函数/方法是否包含异常清单文档（失败场景 + 处理策略）
        """
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [{"rule": "exception_manifest", "line": 0, "message": "语法错误，无法解析"}]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    violations.append({
                        "rule": "exception_manifest",
                        "line": node.lineno,
                        "message": f"函数 '{node.name}' 缺少文档字符串（应包含异常清单）",
                    })
                    continue

                # 检查是否包含失败场景和处理策略
                has_failure_scenarios = "失败场景" in docstring or "失败" in docstring
                has_handling_strategy = "处理策略" in docstring or "策略" in docstring

                if not (has_failure_scenarios and has_handling_strategy):
                    violations.append({
                        "rule": "exception_manifest",
                        "line": node.lineno,
                        "message": f"函数 '{node.name}' 文档字符串缺少异常清单（失败场景 + 处理策略）",
                    })

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # 检查 2: 零静默失败
    # ──────────────────────────────────────────────────────────────────────────

    def _check_no_silent_failures(self, code: str, filename: str) -> list[dict]:
        """
        检查是否存在空的 catch/except 块（静默失败）
        """
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    # 检查 except 块是否为空或只有 pass
                    if len(handler.body) == 0 or (
                        len(handler.body) == 1
                        and isinstance(handler.body[0], ast.Pass)
                    ):
                        violations.append({
                            "rule": "no_silent_failure",
                            "line": handler.lineno,
                            "message": "空的 except 块（静默失败）- 必须包含错误码、日志、处理策略",
                        })
                    # 检查 except 块是否只有简单的赋值/表达式而没有日志或处理
                    elif len(handler.body) == 1 and isinstance(
                        handler.body[0], (ast.Expr, ast.Assign)
                    ):
                        # 允许 log_error 调用
                        body_str = ast.dump(handler.body[0])
                        if "log_error" not in body_str and "logger" not in body_str:
                            violations.append({
                                "rule": "no_silent_failure",
                                "line": handler.lineno,
                                "message": "except 块缺少结构化日志记录",
                            })

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # 检查 3: 防御式编程
    # ──────────────────────────────────────────────────────────────────────────

    def _check_defensive_programming(self, code: str, filename: str) -> list[dict]:
        """
        检查外部输入校验和外部调用超时/熔断
        """
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 简单启发式：检查函数参数是否有类型注解
                for arg in node.args.args:
                    if arg.annotation is None and arg.arg not in ("self", "cls"):
                        # 放宽要求：不强制每个参数都有注解，但检查是否有前置校验
                        pass

                # 检查是否有输入校验（简单启发式：检查 if not / if x is None）
                has_input_check = False
                for child in ast.walk(node):
                    if isinstance(child, ast.If):
                        if_str = ast.dump(child.test)
                        if any(kw in if_str for kw in ["is None", "not ", "ValueError"]):
                            has_input_check = True
                            break

                if not has_input_check and len(node.args.args) > 1:
                    violations.append({
                        "rule": "defensive_programming",
                        "line": node.lineno,
                        "message": f"函数 '{node.name}' 缺少输入校验（建议添加参数类型/空值检查）",
                    })

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # 检查 4: 可观测性
    # ──────────────────────────────────────────────────────────────────────────

    def _check_observability(self, code: str, filename: str) -> list[dict]:
        """
        检查异常路径是否留下审计痕迹
        """
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    body_str = ast.dump(handler.body)
                    # 检查是否有日志记录
                    has_log = any(
                        kw in body_str
                        for kw in ["log_error", "logger", "logging", "audit"]
                    )
                    if not has_log:
                        violations.append({
                            "rule": "observability",
                            "line": handler.lineno,
                            "message": "异常处理路径缺少审计日志（log_error / audit_log）",
                        })

        return violations

    # ──────────────────────────────────────────────────────────────────────────
    # 检查 5: 代码分层
    # ──────────────────────────────────────────────────────────────────────────

    def _check_layer_boundary(self, code: str, filename: str) -> list[dict]:
        """
        检查异常是否在层边界处转换为领域错误
        启发式：检查 API 层函数是否直接抛出原始异常
        """
        violations = []

        # 如果文件在 api/ 目录下，检查是否直接 raise 原始异常
        if "api/" in filename or "api\\" in filename:
            try:
                tree = ast.parse(code)
            except SyntaxError:
                return []

            for node in ast.walk(tree):
                if isinstance(node, ast.Raise):
                    # 检查 raise 的是否是原始异常（如 Exception, ValueError）
                    if isinstance(node.exc, ast.Name) and node.exc.id in (
                        "Exception",
                        "ValueError",
                        "TypeError",
                    ):
                        violations.append({
                            "rule": "layer_boundary",
                            "line": node.lineno,
                            "message": "API 层直接抛出原始异常，应转换为领域错误（如 ErrorCode + HTTPException）",
                        })

        return violations


# 全局实例
code_validator_skill = CodeValidatorSkill()
