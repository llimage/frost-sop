"""
FROST-SOP V8.0 代码审查规范检查 Skill
硬性要求自动化检查：异常清单先行、零静默失败、防御式编程、可观测性、代码分层
"""

import ast
from typing import Any

from core.skill import Skill


class ReviewAuditorSkill(Skill):
    """
    代码审查规范检查 Skill - 对代码变更进行 V8.0 硬性要求审计
    """

    def __init__(self):
        super().__init__("review_auditor", self.audit_code)

    def audit_code(self, code: str, filename: str = "<unknown>") -> dict[str, Any]:
        """
        对代码进行审查级审计
        """
        violations = []

        # 1. 检查每个函数是否有异常清单
        v = self._audit_exception_manifest(code, filename)
        violations.extend(v)

        # 2. 检查零静默失败
        v = self._audit_no_silent_failures(code, filename)
        violations.extend(v)

        # 3. 检查防御式编程
        v = self._audit_defensive_programming(code, filename)
        violations.extend(v)

        # 4. 检查可观测性
        v = self._audit_observability(code, filename)
        violations.extend(v)

        # 5. 检查代码分层
        v = self._audit_layer_boundary(code, filename)
        violations.extend(v)

        score = max(0, 100 - len(violations) * 5)
        passed = score >= 80

        return {
            "passed": passed,
            "score": score,
            "violations": violations,
            "summary": f"审查审计 {filename}: {len(violations)} 项违规, 得分 {score}/100",
            "recommendation": "通过" if passed else "需修复后重新审查",
        }

    def _audit_exception_manifest(self, code: str, filename: str) -> list[dict]:
        """审计异常清单完整性"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return [{"rule": "exception_manifest", "line": 0, "message": "语法错误"}]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                docstring = ast.get_docstring(node)
                if not docstring:
                    violations.append({
                        "rule": "exception_manifest",
                        "line": node.lineno,
                        "severity": "CRITICAL",
                        "message": f"函数 '{node.name}' 完全缺少文档字符串",
                    })
                    continue

                # 检查 4 类失败场景是否都有覆盖
                required_scenarios = ["输入非法", "依赖服务失败", "并发冲突", "资源耗尽"]
                missing = [s for s in required_scenarios if s not in docstring]
                if missing:
                    violations.append({
                        "rule": "exception_manifest",
                        "line": node.lineno,
                        "severity": "HIGH",
                        "message": f"函数 '{node.name}' 缺少失败场景: {', '.join(missing)}",
                    })

                # 检查处理策略是否对应
                if "处理策略" not in docstring:
                    violations.append({
                        "rule": "exception_manifest",
                        "line": node.lineno,
                        "severity": "HIGH",
                        "message": f"函数 '{node.name}' 缺少处理策略部分",
                    })

        return violations

    def _audit_no_silent_failures(self, code: str, filename: str) -> list[dict]:
        """审计零静默失败"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    body = handler.body
                    if len(body) == 0:
                        violations.append({
                            "rule": "no_silent_failure",
                            "line": handler.lineno,
                            "severity": "CRITICAL",
                            "message": "完全空的 except 块 - 严重违规",
                        })
                    elif len(body) == 1 and isinstance(body[0], ast.Pass):
                        violations.append({
                            "rule": "no_silent_failure",
                            "line": handler.lineno,
                            "severity": "CRITICAL",
                            "message": "except: pass - 静默失败，严重违规",
                        })
                    else:
                        # 检查是否有错误码
                        body_str = ast.dump(body)
                        has_error_code = "ErrorCode" in body_str or "error_code" in body_str
                        has_log = any(
                            kw in body_str
                            for kw in ["log_error", "logger", "logging"]
                        )
                        if not (has_error_code and has_log):
                            violations.append({
                                "rule": "no_silent_failure",
                                "line": handler.lineno,
                                "severity": "HIGH",
                                "message": "except 块缺少错误码或结构化日志",
                            })

        return violations

    def _audit_defensive_programming(self, code: str, filename: str) -> list[dict]:
        """审计防御式编程"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 检查外部调用是否有超时
                for child in ast.walk(node):
                    if isinstance(child, ast.Call):
                        call_str = ast.dump(child)
                        # 启发式：requests.get, urllib, socket 等应该有 timeout
                        if any(kw in call_str for kw in ["requests.get", "requests.post", "urlopen"]):
                            if "timeout" not in call_str:
                                violations.append({
                                    "rule": "defensive_programming",
                                    "line": child.lineno,
                                    "severity": "MEDIUM",
                                    "message": "外部 HTTP 调用缺少 timeout 参数",
                                })

        return violations

    def _audit_observability(self, code: str, filename: str) -> list[dict]:
        """审计可观测性"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.Try):
                for handler in node.handlers:
                    body_str = ast.dump(handler.body)
                    has_audit = any(
                        kw in body_str
                        for kw in ["audit", "log_error", "ErrorCode"]
                    )
                    if not has_audit:
                        violations.append({
                            "rule": "observability",
                            "line": handler.lineno,
                            "severity": "HIGH",
                            "message": "异常路径缺少审计痕迹",
                        })

        return violations

    def _audit_layer_boundary(self, code: str, filename: str) -> list[dict]:
        """审计代码分层"""
        violations = []
        # API 层不应直接暴露原始异常
        if "api/" in filename or "api\\" in filename:
            try:
                tree = ast.parse(code)
            except SyntaxError:
                return []

            for node in ast.walk(tree):
                if isinstance(node, ast.Raise):
                    if isinstance(node.exc, ast.Name) and node.exc.id == "Exception":
                        violations.append({
                            "rule": "layer_boundary",
                            "line": node.lineno,
                            "severity": "HIGH",
                            "message": "API 层抛出裸 Exception，应转换为领域错误",
                        })

        return violations


# 全局实例
review_auditor_skill = ReviewAuditorSkill()
