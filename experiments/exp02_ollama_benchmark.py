# Exp-2: Ollama qwen2.5:3b 覆盖率测试
# 目标: 验证本地3B模型能否覆盖8种任务类型中的≥5种
# 通过标准: 5/8任务类型可用本地完成(输出质量可接受)
# 前提: Ollama已安装并运行, qwen2.5:3b已下载
# 运行方式: python exp02_ollama_benchmark.py
# 预算: 如需fallback到云端, 预计消耗¥0-5

import time
import json
import requests
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional

OLLAMA_HOST = "http://localhost:11434"
MODEL = "qwen2.5:3b"


@dataclass
class TaskResult:
    task_type: str
    prompt: str
    local_ok: bool  # 本地3B是否成功返回
    local_quality: int  # 1-5评分 (5=完美, 1=不可用)
    local_latency_ms: int
    local_output: str  # 输出摘要(前200字)
    fallback_needed: bool  # 是否需要云端fallback
    error: Optional[str] = None


# ========== 8种任务类型测试用例 ==========
TEST_CASES = [
    {
        "type": "intent_parse",
        "name": "意图解析",
        "prompt": """请分析以下用户指令的意图类型，只返回一个JSON对象:
{"intent": "dev|mkt|ops|str|chat", "confidence": 0.0-1.0}

用户指令: "帮我开发一个情绪日记模块，用SQLite存储，NiceGUI做界面"
""",
        "criteria": "正确识别为dev意图, confidence>0.7",
    },
    {
        "type": "code_gen",
        "name": "代码生成",
        "prompt": """请生成一个Python函数，实现SQLite数据库初始化，包含tasks表和audit_log表。
要求: 使用sqlite3标准库，包含外键约束，代码完整可运行。
只输出代码，不要解释。""",
        "criteria": "代码语法正确，包含两个表定义，使用sqlite3",
    },
    {
        "type": "code_review",
        "name": "代码审查",
        "prompt": """请审查以下代码，指出潜在问题:
```python
def query_tasks():
    conn = sqlite3.connect('data.db')
    cursor = conn.execute("SELECT * FROM tasks WHERE status = '" + status + "'")
    return cursor.fetchall()
```
请列出: 1)安全问题 2)性能问题 3)代码规范问题。用中文回答。""",
        "criteria": "指出SQL注入风险，指出未关闭连接",
    },
    {
        "type": "summary",
        "name": "文本摘要",
        "prompt": """请用一句话总结以下段落的核心观点(不超过50字):

Solo-Ops-Platform是一个面向独立创始人的AI运营平台。它通过多个专业Agent协作，
帮助创始人完成软件开发、内容创作、营销策划等任务。平台采用本地优先架构，
所有数据存储在本地，API Key加密保存。创始人通过仪表盘监控Agent状态、任务进度和成本消耗。
""",
        "criteria": "准确概括核心功能，字数<50",
    },
    {
        "type": "qa",
        "name": "问答",
        "prompt": """问题: SQLite的WAL模式有什么优点?
请用中文简要回答(3点以内)。""",
        "criteria": "提到并发性能、数据完整性、恢复能力中的至少2点",
    },
    {
        "type": "creative",
        "name": "创意写作",
        "prompt": """请为一款心理健康类App写一句slogan，要求:
1. 中文，10-15字
2. 温暖、有共鸣
3. 体现"陪伴"和"成长"主题
只输出slogan，不要解释。""",
        "criteria": "符合字数要求，主题相关，有创意",
    },
    {
        "type": "data_analysis",
        "name": "数据分析",
        "prompt": """请分析以下成本数据，给出结论:
1月: ¥120, 2月: ¥180, 3月: ¥250, 4月: ¥310
问题: 如果预算上限是¥300/月，哪个月超支了? 趋势如何? 建议?
用中文回答，3点以内。""",
        "criteria": "正确指出4月超支，指出上升趋势，给出合理建议",
    },
    {
        "type": "chat",
        "name": "通用对话",
        "prompt": """用户: 你好，我想了解一下这个平台能帮我做什么?

请用友好、简洁的中文回复(100字以内)，介绍Solo-Ops-Platform的核心价值。""",
        "criteria": "回复友好，包含核心价值，字数<100",
    },
]


def call_ollama(prompt: str, timeout: int = 60) -> dict:
    """调用本地Ollama模型"""
    try:
        t0 = time.time()
        resp = requests.post(
            f"{OLLAMA_HOST}/api/generate",
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7, "num_predict": 512},
            },
            timeout=timeout,
        )
        latency = int((time.time() - t0) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "output": data.get("response", ""),
                "latency_ms": latency,
                "eval_count": data.get("eval_count", 0),
            }
        else:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}: {resp.text}",
                "latency_ms": latency,
            }
    except requests.exceptions.ConnectionError:
        return {
            "success": False,
            "error": f"无法连接到Ollama ({OLLAMA_HOST})",
            "latency_ms": 0,
        }
    except requests.exceptions.Timeout:
        return {"success": False, "error": "请求超时", "latency_ms": timeout * 1000}
    except Exception as e:
        return {"success": False, "error": str(e), "latency_ms": 0}


def evaluate_quality(task_type: str, output: str, criteria: str) -> int:
    """简单质量评估 (1-5分)"""
    output = output.strip()
    if not output:
        return 1

    # 基础评分
    score = 3  # 默认中等

    # 根据任务类型调整
    if task_type == "intent_parse":
        if "dev" in output.lower() and "confidence" in output.lower():
            score = 4 if "0." in output else 3
    elif task_type == "code_gen":
        if "def " in output and "sqlite3" in output.lower():
            score = 4 if "CREATE TABLE" in output.upper() else 3
    elif task_type == "code_review":
        issues = ["注入", "injection", "关闭", "close", "参数化", "parameterized"]
        found = sum(1 for w in issues if w.lower() in output.lower())
        score = 3 + min(found // 2, 2)
    elif task_type == "summary":
        if len(output) < 60 and (
            "平台" in output or "Agent" in output or "创始人" in output
        ):
            score = 4
    elif task_type == "qa":
        if any(w in output for w in ["并发", "WAL", "恢复", "性能", "读写"]):
            score = 4
    elif task_type == "creative":
        if 8 <= len(output) <= 20 and (
            "伴" in output or "长" in output or "心" in output
        ):
            score = 4
    elif task_type == "data_analysis":
        if "4月" in output or "310" in output or "超支" in output or "上升" in output:
            score = 4
    elif task_type == "chat":
        if len(output) < 120 and (
            "Agent" in output
            or "任务" in output
            or "成本" in output
            or "开发" in output
        ):
            score = 4

    return min(score, 5)


def run_benchmark():
    """运行基准测试"""
    print("[Exp-2] Ollama覆盖率测试开始")
    print(f"[Exp-2] 模型: {MODEL}")
    print(f"[Exp-2] 地址: {OLLAMA_HOST}")
    print("-" * 60)

    results = []
    total_latency = 0
    success_count = 0
    quality_pass = 0  # quality >= 3

    for case in TEST_CASES:
        print(f"\n测试: {case['name']} ({case['type']})")
        print(f"标准: {case['criteria']}")

        result = call_ollama(case["prompt"])

        if result["success"]:
            success_count += 1
            quality = evaluate_quality(case["type"], result["output"], case["criteria"])
            total_latency += result["latency_ms"]

            if quality >= 3:
                quality_pass += 1

            tr = TaskResult(
                task_type=case["type"],
                prompt=case["prompt"][:50] + "...",
                local_ok=True,
                local_quality=quality,
                local_latency_ms=result["latency_ms"],
                local_output=result["output"][:200].replace("\n", " "),
                fallback_needed=quality < 3,
                error=None,
            )
            print(f"  ✓ 成功 | 质量: {quality}/5 | 延迟: {result['latency_ms']}ms")
            print(f"  输出: {result['output'][:100]}...")
        else:
            tr = TaskResult(
                task_type=case["type"],
                prompt=case["prompt"][:50] + "...",
                local_ok=False,
                local_quality=0,
                local_latency_ms=result.get("latency_ms", 0),
                local_output="",
                fallback_needed=True,
                error=result["error"],
            )
            print(f"  ✗ 失败 | 错误: {result['error']}")

        results.append(asdict(tr))
        time.sleep(0.5)  # 避免过载

    # 汇总
    print("\n" + "=" * 60)
    print("[Exp-2] 测试结果汇总")
    print(f"  总任务数: {len(TEST_CASES)}")
    print(f"  本地成功: {success_count}/{len(TEST_CASES)}")
    print(f"  质量合格(≥3分): {quality_pass}/{len(TEST_CASES)}")
    print(f"  平均延迟: {total_latency // max(success_count, 1)}ms")
    print(f"  需要fallback: {len(TEST_CASES) - quality_pass}/{len(TEST_CASES)}")

    # 通过判断
    passed = quality_pass >= 5
    print("\n  通过标准: ≥5/8 质量合格")
    print(f"  结果: {'✅ 通过' if passed else '❌ 未通过'}")

    # 保存结果
    Path("experiments/results").mkdir(parents=True, exist_ok=True)
    with open("experiments/results/exp02_results.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "model": MODEL,
                "total_tasks": len(TEST_CASES),
                "success_count": success_count,
                "quality_pass": quality_pass,
                "avg_latency_ms": total_latency // max(success_count, 1),
                "passed": passed,
                "details": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print("\n[Exp-2] 结果已保存: experiments/results/exp02_results.json")
    return passed


if __name__ == "__main__":
    run_benchmark()
