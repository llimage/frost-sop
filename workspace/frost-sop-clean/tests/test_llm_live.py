"""
真实LLM调用测试
PHILOSOPHY: 此测试验证LLM Skill能调用真实API。
手动运行，不纳入自动化测试套件（需要API Key和网络）。
"""

"""
真实LLM调用测试
PHILOSOPHY: 此测试验证LLM Skill能调用真实API。
手动运行，不纳入自动化测试套件（需要API Key和网络）。
"""
import sys
import os

# Windows 控制台编码修复：强制 UTF-8 输出
if sys.platform == "win32":
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.llm import call_llm_skill


def test_real_llm_call():
    """验证真实LLM调用"""
    print("=" * 60)
    print("真实LLM调用测试")
    print("=" * 60)

    context = {
        "_prompt": "请用一句话解释什么是FROST框架。",
        "_system_prompt": "你是一个AI架构师。回答要简洁准确。",
    }

    result = call_llm_skill.execute(context)

    response = result.get("_llm_response", "")
    tokens = result.get("_llm_tokens", {})

    print(f"\nLLM响应: {response}")
    print(f"Token消耗: {tokens}")
    print(f"使用模型: {result.get('_llm_model', '')}")
    print(f"推理痕迹: {result.get('_reason', '')}")

    assert any(kw in response for kw in ["FROST", "框架", "Agent", "阈值", "签名"]), (
        "响应内容应包含相关关键词"
    )
    assert tokens.get("total", 0) > 0, "应消耗Token"

    print("\n[PASS] 真实LLM调用成功")


if __name__ == "__main__":
    test_real_llm_call()
