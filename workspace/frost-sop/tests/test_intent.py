"""
P1-7 自验收测试：意图解析结构化 JSON

测试内容：
1. 关键词匹配：开发 → DEV-001
2. 关键词匹配：修复 → DEV-002
3. 关键词匹配：推广文案 → MT-001
4. 关键词匹配：财务 → OPS-001
5. 低 confidence 时返回 None SOP
6. 未知类型回退为通用任务
"""

import os
import sys

import pytest

os.environ["FROST_TESTING"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.intent import list_all_sops, parse_intent


class TestIntentParsing:
    """测试意图解析功能"""

    def test_parse_dev_task(self):
        """测试：开发任务匹配 DEV-001"""
        result = parse_intent("开发登录功能")
        assert result["sop_id"] == "DEV-001", f"应匹配 DEV-001, 实际: {result['sop_id']}"
        assert result["confidence"] > 0.5, f"置信度应 > 0.5, 实际: {result['confidence']}"
        print(f"  ✅ test_parse_dev_task: sop={result['sop_id']} conf={result['confidence']}")

    def test_parse_dev_alternative_phrasing(self):
        """测试：开发任务的替代表述"""
        for phrase in ["新增用户管理模块", "实现支付功能", "构建消息系统", "创建管理后台"]:
            result = parse_intent(phrase)
            assert result["sop_id"] == "DEV-001", (
                f"'{phrase}' 应匹配 DEV-001, 实际: {result['sop_id']}"
            )
        print("  ✅ test_parse_dev_alternative_phrasing 通过")

    def test_parse_bug_fix(self):
        """测试：Bug修复匹配 DEV-002"""
        result = parse_intent("修复登录页面崩溃问题")
        assert result["sop_id"] == "DEV-002", f"应匹配 DEV-002, 实际: {result['sop_id']}"
        print(f"  ✅ test_parse_bug_fix: sop={result['sop_id']}")

    def test_parse_content_marketing(self):
        """测试：内容任务匹配 MT-001"""
        result = parse_intent("写一篇关于AI的推广文案")
        assert result["sop_id"] == "MT-001", f"应匹配 MT-001, 实际: {result['sop_id']}"
        print(f"  ✅ test_parse_content_marketing: sop={result['sop_id']}")

    def test_parse_finance(self):
        """测试：财务任务匹配 OPS-001"""
        result = parse_intent("处理本月报销和财务对账")
        assert result["sop_id"] == "OPS-001", f"应匹配 OPS-001, 实际: {result['sop_id']}"
        print(f"  ✅ test_parse_finance: sop={result['sop_id']}")

    def test_parse_knowledge(self):
        """测试：知识管理匹配 OPS-006"""
        result = parse_intent("归档产品知识库文档")
        assert result["sop_id"] == "OPS-006", f"应匹配 OPS-006, 实际: {result['sop_id']}"
        print(f"  ✅ test_parse_knowledge: sop={result['sop_id']}")

    def test_parse_project_init(self):
        """测试：项目立项匹配 STR-001"""
        result = parse_intent("调研市场需求并做项目可行性分析")
        assert result["sop_id"] == "STR-001", f"应匹配 STR-001, 实际: {result['sop_id']}"
        print(f"  ✅ test_parse_project_init: sop={result['sop_id']}")

    def test_parse_unknown_type(self):
        """测试：未知任务类型返回 None SOP"""
        result = parse_intent("今天天气怎么样")
        assert result["sop_id"] is None, f"无对应SOP时应为 None, 实际: {result['sop_id']}"
        assert result["confidence"] < 0.5, f"低置信度应 < 0.5, 实际: {result['confidence']}"
        print(f"  ✅ test_parse_unknown_type: sop={result['sop_id']} conf={result['confidence']}")

    def test_parse_multi_keyword(self):
        """测试：多关键词时匹配最高优先级"""
        result = parse_intent("修复财务系统开发中的问题")
        # "修复" → DEV-002, "财务" → OPS-001, "开发" → DEV-001
        # 应按关键词匹配数决定
        assert result["sop_id"] in ["DEV-001", "DEV-002", "OPS-001"], (
            f"应匹配其中一个 SOP, 实际: {result['sop_id']}"
        )
        print(f"  ✅ test_parse_multi_keyword: sop={result['sop_id']}")

    def test_all_sops_listed(self):
        """测试：至少有 7 个 SOP"""
        sops = list_all_sops()
        assert len(sops) >= 7, f"应有至少7个SOP, 实际: {len(sops)}"
        print(f"  ✅ test_all_sops_listed: {len(sops)} SOPs")

    def test_llm_mode_fallback(self):
        """
        测试：use_llm=True 模式下 _call_llm_raw 导入成功，
        mock 模式下 LLM 返回非 JSON 能正确回退到关键词匹配。
        """
        result = parse_intent("开发登录功能", use_llm=True)
        # 在 mock 模式下，LLM 返回非 JSON 会 fallback → method="keyword"
        assert result["sop_id"] == "DEV-001", (
            f"LLM fallback 应匹配 DEV-001, 实际: {result['sop_id']}"
        )
        assert result["confidence"] > 0.3, f"置信度 > 0.3, 实际: {result['confidence']}"
        print(f"  ✅ test_llm_mode_fallback: method={result['method']} sop={result['sop_id']}")


class TestCallLlmRaw:
    """测试 _call_llm_raw 简易 LLM 调用接口"""

    def test_raw_call_basic(self):
        """测试：_call_llm_raw 基本调用返回非空字符串"""
        from skills.llm import _call_llm_raw

        r = _call_llm_raw(prompt="开发登录功能")
        assert isinstance(r, str), f"返回值应为 str, 实际: {type(r)}"
        assert len(r) > 0, "mock 模式下应返回非空响应"
        print(f"  ✅ test_raw_call_basic: {len(r)} chars")

    def test_raw_call_with_system_prompt(self):
        """测试：_call_llm_raw 带 system_prompt 正常"""
        from skills.llm import _call_llm_raw

        r = _call_llm_raw(
            system_prompt="你是一个JSON解析器",
            prompt="分析以下任务",
            temperature=0.1,
            max_tokens=256,
        )
        assert isinstance(r, str)
        assert len(r) > 0
        print(f"  ✅ test_raw_call_with_system_prompt: {len(r)} chars")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
