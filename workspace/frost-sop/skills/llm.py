"""
FROST-SOP LLM Skill
PHILOSOPHY: LLM is the shared nervous system. It is called as a Skill,
not hardwired into Agent. This preserves the fractal purity of the architecture.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# F7 新增：导入成本追踪器
from core.cost import BudgetExceededError, get_cost_tracker
from core.skill import Skill

# 加载 .env 文件中的环境变量
load_dotenv()

# ── 失败日志目录 ──────────────────────────────────────────────────────
_TOOL_CALLS_DIR = Path(__file__).resolve().parent.parent / "data" / "tool_calls"
_TOOL_CALLS_DIR.mkdir(parents=True, exist_ok=True)


def _write_failure_log(
    tool_name: str, error: str, context: dict | None = None, duration_ms: int = 0
):
    """LLM 调用失败时写 JSON 日志到 data/tool_calls/，供 scan_failed_calls 消费。

    格式: {call_id, tool_name, success: False, error, timestamp, agent_id, task_id, duration_ms}
    """
    ctx = context or {}
    ts = datetime.now(timezone.utc)
    record = {
        "call_id": f"llm_{ts.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}",
        "tool_name": tool_name,
        "success": False,
        "error": str(error),
        "timestamp": ts.isoformat(),
        "agent_id": ctx.get("_agent_id", ""),
        "task_id": ctx.get("_task_id", ""),
        "duration_ms": duration_ms,
    }
    try:
        filepath = _TOOL_CALLS_DIR / f"{record['call_id']}.json"
        filepath.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # best-effort logging; never crash the caller


# ── 离线模型全局变量 ──────────────────────────────────────────────────
_local_llm = None
_local_model_path = "models/Qwen3-4B-Q4_K_M.gguf"
# 备选：SmolLM2-1.7B-Q4_K_M.gguf（1.1GB，硬件更友好）
_local_fallback_model = "models/SmolLM2-1.7B-Q4_K_M.gguf"


def _init_local_llm():
    """初始化本地 LLM 模型（懒加载，首次调用时加载）。"""
    global _local_llm
    if _local_llm is not None:
        return _local_llm
    try:
        from llama_cpp import Llama
    except ImportError:
        print("[离线模式] llama-cpp-python 未安装，请运行: pip install llama-cpp-python")
        return None

    # 优先使用主模型，不存在则尝试备选
    model_path = _local_model_path
    if not Path(model_path).exists():
        model_path = _local_fallback_model
        if not Path(model_path).exists():
            print("[离线模式] 未找到 GGUF 模型文件，请放入 models/ 目录")
            return None

    print(f"[离线模式] 正在加载模型: {model_path} ...")
    _local_llm = Llama(model_path=model_path, n_ctx=4096, n_threads=4, verbose=False)
    print("[离线模式] 模型加载完成")
    return _local_llm


def call_local_llm(prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> dict:
    """使用本地 GGUF 模型进行推理。
    返回: {"text": str} 或 {"error": str}
    """
    llm = _init_local_llm()
    if llm is None:
        return {"error": "模型未加载，请检查 models/ 目录或安装 llama-cpp-python"}
    try:
        result = llm(prompt, max_tokens=max_tokens, temperature=temperature, echo=False)
        return {"text": result["choices"][0]["text"]}
    except Exception as e:
        return {"error": f"本地推理失败: {str(e)}"}


def _mock_response_for_prompt(prompt: str) -> str:
    """测试模式：根据 prompt 关键词返回预置 mock 响应。

    路由优先级（从高到低）：
      1. Agent组装分析（必须最先，因为 prompt 中含"需求"等通用词）
      2. Skill合成分析（也含"需求"等通用词）
      3. Skill匹配分析（技能匹配专家）
      4. LLM产出生成（call_llm_for_output，含各种领域关键词）
      5. 各业务域关键词路由
    """
    p = prompt.lower()

    # ── 优先级1：Agent 组装分析（assemble.py 第54行）──────────────────
    # prompt 开头是"分析以下Agent需求，返回JSON格式的配置方案："
    if "分析以下Agent需求" in prompt or "返回JSON格式的配置方案" in prompt:
        return json.dumps(
            {
                "agent_name": "mock_assembled_agent",
                "required_skills": ["执行任务"],
                "sop_steps": ["执行任务"],
                "system_prompt": "你是通用执行Agent，完成指定任务并输出结果。",
                "output_type": "document",
            },
            ensure_ascii=False,
        )

    # ── 优先级2：Skill 合成分析（assemble.py synthesize_skill）──────────
    # prompt 格式："你是一个Skill设计助手。请为以下需求生成一个Skill的执行描述：\n\n需求：..."
    if "Skill设计助手" in prompt or "需要合成的Skill" in prompt:
        # 从 prompt 中尽量提取 skill_name
        skill_name = "通用技能"
        for line in prompt.split("\n"):
            if "需要合成的Skill：" in line:
                skill_name = line.split("：", 1)[-1].strip()
                break
        return json.dumps(
            {
                "name": skill_name,
                "type": "functional",
                "description": f"执行{skill_name}的能力，产出完整的工作成果。",
                "input_keys": ["_task_description"],
                "output_keys": ["_generated_content"],
            },
            ensure_ascii=False,
        )

    # ── 优先级3：Skill 语义匹配（assemble.py 技能匹配专家）──────────────
    # prompt 包含"技能匹配专家"或"selected_templates"
    if "技能匹配专家" in prompt or "selected_templates" in prompt:
        return json.dumps(
            {"selected_templates": [], "reason": "测试模式：不匹配基因库，使用LLM合成"},
            ensure_ascii=False,
        )

    # ── 优先级4：LLM产出生成（tools.py call_llm_for_output）─────────────
    # prompt 格式："{task_description}\n\n请生成结构化的文档..." 或 "请生成完整的、可运行的代码..."
    # 特征：prompt 中包含"请生成"并且含有具体的输出类型指导
    if "请生成完整的、可运行的代码" in prompt:
        task = prompt.split("\n")[0].strip()[:60]
        return f"# 代码实现成果\n\n针对任务「{task}」，已生成完整代码：\n```python\n# 实现代码\nprint('任务完成')\n```"
    if "请生成结构化的文档" in prompt:
        task = prompt.split("\n")[0].strip()[:60]
        return f"# 文档成果\n\n## 任务概述\n任务：{task}\n\n## 执行结果\n任务已完成，产出符合要求。\n\n## 详细内容\n- 分析完成\n- 方案设计完成\n- 验收标准满足"
    if "请生成符合要求的文案内容" in prompt:
        task = prompt.split("\n")[0].strip()[:60]
        return (
            f"# 文案成果\n\n"
            f"🚀 **FROST框架——分形AI Agent智能体平台**\n\n"
            f"任务「{task}」文案已生成：\n\n"
            f"FROST是新一代分形AI Agent框架，让每个智能体都拥有家族式自治能力。\n"
            f"核心优势：SOP驱动执行、基因传承、Agent自进化。\n"
            f"分形架构 × 智能体协作 × 无限扩展"
        )

    # ── 优先级5：各业务域关键词路由 ───────────────────────────────────
    if "需求" in prompt or "requirement" in p:
        return "# 需求分析\n\n## 功能需求\n- FR-001: 用户认证\n- FR-002: Token管理\n\n## 验收标准\n- 登录成功率 > 99%"
    if "设计" in prompt or "design" in p or "架构" in prompt:
        return "# 技术设计\n\n## 系统架构\n采用分层架构，认证模块独立部署。\n\n## 核心模块\n- AuthService\n- TokenManager"
    if "代码" in prompt or "code" in p or "implement" in p:
        return "# 代码实现\n\n已完成代码生成，输出：auth.py, models.py, test_auth.py\n\n所有单元测试通过。"
    if "测试" in prompt or "test" in p:
        return "# 测试验证\n\n| 用例 | 状态 |\n|------|------|\n| TC-001 登录 | PASS |\n| TC-002 登出 | PASS |"
    if "审查" in prompt or "audit" in p or "review" in p:
        return "# 审查报告\n\n✅ 代码质量良好，无重大问题。\n\n覆盖率：85%"
    if "选题" in prompt or "topic" in p:
        return "# 选题策划\n\n主题：FROST框架——分形AI Agent智能体平台推广"
    if "内容" in prompt or "文案" in prompt or "copy" in p:
        return (
            "# FROST框架推广文案\n\n"
            "FROST是一个创新的分形AI Agent框架，支持家族式自治。\n"
            "主要特性：分形治理、SOP驱动、基因传承。\n"
            "FROST让每个智能体都能像Agent一样自主演进，实现真正的分形智能。"
        )
    if (
        "财务" in prompt
        or "financial" in p
        or "报表" in prompt
        or "收支" in prompt
        or "月结" in prompt
        or "核算" in prompt
    ):
        return (
            "# 财务月结报告\n\n"
            "## 收支汇总\n"
            "| 项目 | 金额(元) |\n|------|----------|\n"
            "| 收入 | 200,000 |\n| 支出 | 140,000 |\n| 结余 | 60,000 |\n\n"
            "## 说明\n本月财务数据已完成核算，账目清晰，收支平衡。"
        )
    if "知识" in prompt or "knowledge" in p or "资产" in prompt:
        return "# 知识资产清单\n\n已盘点本周知识资产，共5项：\n1. FROST架构文档\n2. SOP模板库\n3. Agent基因库\n4. 测试报告\n5. 部署指南"
    if "市场" in prompt or "market" in p or "调研" in prompt:
        return "# 市场调研报告\n\n目标用户：技术团队负责人。\n市场规模：大型企业AI工程化需求旺盛。"
    if "可行" in prompt or "feasibility" in p:
        return "# 可行性分析\n\n技术可行性：高。资源可行性：可控。建议：立项推进。"
    if "方案" in prompt or "solution" in p:
        return "# 项目技术方案\n\n采用分形架构，核心模块：Agent编排引擎。预计8周完成。"
    if "资源" in prompt or "resource" in p:
        return "# 资源规划\n\n需要2名开发者，预计8周完成。预算：合理范围内。"
    if "历史" in prompt or "history" in p or "任务" in prompt:
        return (
            '{"task-001": {"sop": "DEV-001", "status": "completed"}, '
            '"task-002": {"sop": "DEV-001", "status": "completed"}, '
            '"task-003": {"sop": "DEV-001", "status": "completed"}, '
            '"task-004": {"sop": "DEV-002", "status": "failed"}, '
            '"task-005": {"sop": "DEV-001", "status": "failed"}}'
        )
    if "趋势" in prompt or "trend" in p:
        return '{"total": 5, "successful": 3, "failed": 2, "success_rate": 0.6, "suggestions": ["增加重试机制", "优化SOP结构"]}'
    if "建议" in prompt or "suggestion" in p:
        return "# 优化建议\n\n1. 增加LLM调用重试机制\n2. 优化DEV-002 SOP结构\n3. 完善测试覆盖"
    if "批准" in prompt or "approval" in p or "确认" in prompt:
        return "# 审批结果\n\n✅ 建议1：批准（高优先级）\n✅ 建议2：批准（中优先级）"

    # ── 兜底响应 ──────────────────────────────────────────────────────
    return f"[MOCK] 已完成任务：{prompt[:50]}"


def _call_online_llm(context: dict) -> dict:
    """
    在线调用 DeepSeek API（内部函数，含成本检查和 API 调用）。
    由 call_llm() 在 mode="online" 或 mode="auto" 时调度。
    失败时直接修改 context 返回错误信息，不抛出异常。
    """
    # 成本检查
    try:
        cost_tracker = get_cost_tracker()
        estimated_tokens = len(context.get("_prompt", "")) // 4 + context.get("_max_tokens", 2048)
        cost_tracker.check_and_throw(
            agent_id=context.get("_agent_id", "unknown"),
            tokens=estimated_tokens,
            model=context.get("_model", "deepseek-chat"),
        )
    except BudgetExceededError as e:
        _write_failure_log("call_llm", f"预算超支: {e}", context)
        context["_llm_response"] = f"预算已用完：{str(e)}"
        context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
        context["_reason"] = f"预算检查失败：{str(e)}"
        return context
    except Exception:
        # 成本检查失败不影响 LLM 调用（容错）
        pass

    api_key = os.getenv("DEEPSEEK_API_KEY")
    # P0-5: 优先使用加密存储的密钥
    if not api_key:
        try:
            from core.secrets import get_decrypted_key

            api_key = get_decrypted_key("DEEPSEEK_API_KEY", prompt_if_missing=True)
        except ImportError:
            pass

    if not api_key:
        _write_failure_log("call_llm", "缺少API密钥", context)
        context["_llm_response"] = "错误：未配置 DEEPSEEK_API_KEY 环境变量"
        context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
        context["_reason"] = "LLM调用失败：缺少API密钥"
        return context

    prompt = context.get("_prompt", "")
    system_prompt = context.get("_system_prompt", "你是一个AI助手，负责协助完成任务拆解和执行。")
    model = context.get("_model", "deepseek-chat")
    temperature = context.get("_temperature", 0.7)
    max_tokens = context.get("_max_tokens", 2048)

    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    response = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    content = response.choices[0].message.content
    usage = response.usage

    context["_llm_response"] = content
    context["_llm_tokens"] = {
        "prompt": usage.prompt_tokens,
        "completion": usage.completion_tokens,
        "total": usage.total_tokens,
    }
    context["_llm_model"] = model
    context["_reason"] = f"LLM调用成功，消耗 {usage.total_tokens} tokens"

    # 追踪成本
    try:
        cost_tracker = get_cost_tracker()
        cost_tracker.track_cost(
            agent_id=context.get("_agent_id", "unknown"),
            tokens=usage.total_tokens,
            model=model,
            task_id=context.get("_task_id"),
            input_tokens=usage.prompt_tokens,
            output_tokens=usage.completion_tokens,
        )
    except Exception:
        # 成本追踪失败不影响主流程（容错）
        pass

    return context


def call_llm(context: dict, mode: str = "auto") -> dict:
    """
    调用 LLM 进行推理，支持在线/离线/自动模式。

    输入 context 键：
        _prompt: str（必填）—— 发送给 LLM 的用户提示词
        _system_prompt: str（可选）—— 系统提示词
        _model: str（可选）—— 模型名称，默认 "deepseek-chat"
        _temperature: float（可选）—— 温度参数，默认 0.7
        _max_tokens: int（可选）—— 最大 Token 数，默认 2048
        _llm_mode: str（可选）—— 模式覆盖："online" | "offline" | "auto"

    参数 mode:
        "online"  — 仅在线（DeepSeek API）
        "offline" — 仅离线（本地 GGUF 模型）
        "auto"    — 优先在线，失败时自动降级到离线

    输出 context 键：
        _llm_response: str —— LLM 返回的文本内容
        _llm_tokens: dict —— Token 使用统计
        _llm_model: str —— 实际使用的模型名称
        _reason: str —— 推理痕迹（用于审计）
        _llm_backend: str —— "online" | "offline" | "mock"
    """
    # context 中的 _llm_mode 优先级最高
    effective_mode = context.get("_llm_mode", mode)

    # 测试模式：直接返回 mock 响应，不调用真实 API
    if os.getenv("FROST_TESTING") == "1":
        prompt = context.get("_prompt", "")
        total_tokens = len(prompt) // 4 + 100
        context["_llm_response"] = _mock_response_for_prompt(prompt)
        context["_llm_tokens"] = {
            "prompt": len(prompt) // 4,
            "completion": 100,
            "total": total_tokens,
        }
        context["_llm_model"] = context.get("_model", "deepseek-chat")
        context["_reason"] = "[TEST_MODE] LLM调用已跳过，使用mock响应"
        context["_llm_backend"] = "mock"

        # F14: 即使在 mock 模式也写入 cost_log
        try:
            from core.db import get_db

            db = get_db()
            estimated_cost = (total_tokens / 1000) * 0.001
            db.insert(
                "cost_log",
                {
                    "task_id": context.get("_task_id") or None,
                    "agent_id": context.get("_agent_id", "mock_agent"),
                    "model": context.get("_model", "deepseek-chat"),
                    "input_tokens": len(prompt) // 4,
                    "output_tokens": 100,
                    "total_tokens": total_tokens,
                    "estimated_cost": estimated_cost,
                },
            )
        except Exception:
            pass

        return context

    # ── 离线模式 ──
    if effective_mode == "offline":
        resp = call_local_llm(
            context.get("_prompt", ""),
            max_tokens=context.get("_max_tokens", 500),
            temperature=context.get("_temperature", 0.7),
        )
        if "error" in resp:
            _write_failure_log("call_local_llm", resp["error"], context)
            context["_llm_response"] = resp["error"]
            context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            context["_reason"] = "离线推理失败：{}".format(resp["error"])
            context["_llm_backend"] = "offline"
        else:
            context["_llm_response"] = resp["text"]
            context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            context["_llm_model"] = "local-gguf"
            context["_reason"] = "离线推理完成（本地GGUF）"
            context["_llm_backend"] = "offline"
        return context

    # ── 在线模式 ──
    if effective_mode == "online":
        try:
            context = _call_online_llm(context)
            context["_llm_backend"] = "online"
        except Exception as e:
            _write_failure_log("call_llm_online", str(e), context)
            context["_llm_response"] = f"LLM调用失败：{str(e)}"
            context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            context["_reason"] = f"LLM调用失败：{str(e)}"
            context["_llm_backend"] = "online"
        return context

    # ── auto 模式：优先在线，失败时降级到离线 ──
    try:
        context = _call_online_llm(context)
        context["_llm_backend"] = "online"
        return context
    except Exception as e:
        _write_failure_log("call_llm_auto_online", str(e), context)
        print(f"Online LLM 失败，降级到离线模式: {e}")
        resp = call_local_llm(
            context.get("_prompt", ""),
            max_tokens=context.get("_max_tokens", 500),
            temperature=context.get("_temperature", 0.7),
        )
        if "error" in resp:
            _write_failure_log("call_llm_auto_fallback", resp["error"], context)
            context["_llm_response"] = resp["error"]
            context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            context["_reason"] = "在线失败且离线降级也失败：{}".format(resp["error"])
            context["_llm_backend"] = "offline"
        else:
            context["_llm_response"] = resp["text"]
            context["_llm_tokens"] = {"prompt": 0, "completion": 0, "total": 0}
            context["_llm_model"] = "local-gguf-fallback"
            context["_reason"] = "在线失败，已降级到本地GGUF模型"
            context["_llm_backend"] = "offline"
        return context


def _call_llm_raw(
    system_prompt: str = "", prompt: str = "", temperature: float = 0.7, max_tokens: int = 2048
) -> str:
    """
    简易 LLM 调用接口：直接传入参数，返回原始文本。

    供内部模块（如 intent.py）使用，封装了 call_llm 的 dict 入参/出参模式。
    在 FROST_TESTING=1 时自动走 mock 路由。
    """
    ctx = {
        "_system_prompt": system_prompt,
        "_prompt": prompt,
        "_temperature": temperature,
        "_max_tokens": max_tokens,
    }
    ctx = call_llm(ctx)
    return str(ctx.get("_llm_response", ""))


# 导出为 Skill 实例
call_llm_skill = Skill("call_llm", call_llm)
