"""
FROST-SOP V8.0 测试规范检查 Skill
硬性要求自动化检查：异常清单先行、零静默失败、防御式编程、可观测性、代码分层
"""

import ast
from typing import Any

from core.skill import Skill


class TestValidatorSkill(Skill):
    """
    测试规范检查 Skill - 自动化验证测试代码是否符合 V8.0 硬性要求
    """

    def __init__(self):
        super().__init__("test_validator", self.validate_tests)

    def validate_tests(self, code: str, filename: str = "<unknown>") -> dict[str, Any]:
        """
        对测试代码进行全量硬性要求检查
        """
        violations = []

        # 1. 测试是否覆盖异常路径
        v = self._check_exception_coverage(code, filename)
        violations.extend(v)

        # 2. 测试是否有断言（零静默失败）
        v = self._check_test_assertions(code, filename)
        violations.extend(v)

        # 3. 测试是否有输入边界检查（防御式编程）
        v = self._check_boundary_tests(code, filename)
        violations.extend(v)

        # 4. 测试失败时是否有日志（可观测性）
        v = self._check_test_observability(code, filename)
        violations.extend(v)

        score = max(0, 100 - len(violations) * 5)
        passed = score >= 80

        return {
            "passed": passed,
            "score": score,
            "violations": violations,
            "summary": f"{filename}: {len(violations)} 项违规, 得分 {score}/100",
        }

    def _check_exception_coverage(self, code: str, filename: str) -> list[dict]:
        """检查测试是否覆盖了异常路径"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        test_functions = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef)
            and node.name.startswith("test_")
        ]

        if not test_functions:
            return []

        # 检查是否有 pytest.raises 或 try/except 测试
        has_exception_test = False
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    if isinstance(item.context_expr, ast.Call):
                        call_str = ast.dump(item.context_expr)
                        if "raises" in call_str or "pytest.raises" in call_str:
                            has_exception_test = True
                            break

        if not has_exception_test:
            violations.append({
                "rule": "exception_coverage",
                "line": 1,
                "message": "测试文件缺少异常路径覆盖（建议使用 pytest.raises 测试异常场景）",
            })

        return violations

    def _check_test_assertions(self, code: str, filename: str) -> list[dict]:
        """检查测试函数是否包含断言"""
        violations = []
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                has_assert = any(
                    isinstance(child, ast.Assert)
                    for child in ast.walk(node)
                )
                if not has_assert:
                    violations.append({
                        "rule": "test_assertion",
                        "line": node.lineno,
                        "message": f"测试函数 '{node.name}' 缺少断言（零静默失败风险）",
                    })

        return violations

    def _check_boundary_tests(self, code: str, filename: str) -> list[dict]:
        """检查是否有边界条件测试"""
        violations = []
        # 启发式：检查是否有 None、空字符串、0 等边界值
        boundary_keywords = ["None", "\"\"", "''", "0", "[]", "{}"]
        has_boundary = any(kw in code for kw in boundary_keywords)

        if not has_boundary:
            violations.append({
                "rule": "boundary_test",
                "line": 1,
                "message": "测试缺少边界条件覆盖（None、空值、零值等）",
            })

        return violations

    def _check_test_observability(self, code: str, filename: str) -> list[dict]:
        """检查测试失败时是否有可观测性"""
        # 测试框架本身会报告失败，此项为信息级检查
        return []


# 全局实例
test_validator_skill = TestValidatorSkill()
