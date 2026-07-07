"""
冒烟测试：3 分钟验证系统核心链路可用。
使用真实 LLM，消耗约 50-100 tokens。

运行方式：
    pytest tests/smoke/ -m smoke -v

注意：
- 需要 DEEPSEEK_API_KEY 环境变量
- 如果 API 不可用，测试自动跳过
"""

import os

import pytest


@pytest.mark.smoke
class TestSystemAlive:
    """3 分钟冒烟测试：验证系统核心链路可用。"""

    def test_llm_online_call(self):
        """真实 LLM 调用能工作。"""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY 未设置，跳过真实 LLM 测试")

        from skills.llm import call_llm

        result = call_llm(
            {
                "_prompt": "Say 'pong' only",
                "_llm_profile": "execute",
                "_max_tokens": 10,
            }
        )

        backend = result.get("_llm_backend")
        if backend != "online":
            pytest.skip(f"LLM API 不可用（backend={backend}），跳过真实 LLM 测试")

        assert result.get("_llm_response", "").strip() != "", "LLM 响应为空"
        print(f"  LLM 响应: {result.get('_llm_response', '')}")

    def test_temperature_profile_effective(self):
        """temperature profile 映射生效（execute=0.1 高确定性）。"""
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            pytest.skip("DEEPSEEK_API_KEY 未设置，跳过真实 LLM 测试")

        from skills.llm import call_llm

        # execute profile 应该使用 0.1，两次相同 prompt 应返回相同结果
        result1 = call_llm(
            {
                "_prompt": "Return the number 42 only",
                "_llm_profile": "execute",
                "_max_tokens": 10,
            }
        )
        result2 = call_llm(
            {
                "_prompt": "Return the number 42 only",
                "_llm_profile": "execute",
                "_max_tokens": 10,
            }
        )

        backend1 = result1.get("_llm_backend")
        backend2 = result2.get("_llm_backend")
        if backend1 != "online" or backend2 != "online":
            pytest.skip(f"LLM API 不可用（backend={backend1}/{backend2}），跳过真实 LLM 测试")

        # execute profile 下 temperature=0.1，两次应高度相似
        resp1 = result1.get("_llm_response", "").strip()
        resp2 = result2.get("_llm_response", "").strip()
        assert resp1 and resp2, "响应不应为空"
        assert resp1 == resp2, f"execute profile temperature 未生效（两次结果不同: '{resp1}' vs '{resp2}'）"

    def test_database_read_write(self):
        """数据库能读写。"""
        from core.db import DBManager

        db = DBManager(db_path=":memory:")
        db.insert(
            "projects",
            {
                "id": "smoke_test",
                "name": "冒烟测试",
                "status": "active",
            },
        )
        row = db.select_one("projects", "id", "smoke_test")
        assert row is not None
        assert row["name"] == "冒烟测试"

    def test_skill_v2_error_handling(self):
        """Skill V2 错误处理：异常不中断任务链。"""
        from core.skill import Skill

        def crash_skill(context):
            raise ValueError("intentional crash")

        skill = Skill("smoke_crash", crash_skill)
        result = skill.execute({})
        assert result.get("_skill_failed") is True
        assert "intentional crash" in result.get("_skill_error", "")

    def test_skill_v2_input_validation(self):
        """Skill V2 输入验证：缺少必需键时返回错误。"""
        from core.skill import Skill

        def dummy_skill(context):
            return {"output": context["input"]}

        skill = Skill("smoke_validate", dummy_skill, required_keys=["input"])
        result = skill.execute({})  # 缺少 input
        assert result.get("_skill_failed") is True
        assert "缺少必需输入" in result.get("_skill_error", "")

    def test_sop_load_and_validate(self):
        """SOP 能加载并通过基础验证。"""
        from pathlib import Path
        from core.sop import SOP

        sop_path = Path(__file__).parent.parent.parent / "sops" / "templates" / "OPS-007.yaml"
        sop = SOP.load_from_yaml(str(sop_path))
        assert sop.sop_id == "OPS-007"
        assert len(sop.stages) > 0
        assert sop.name is not None
