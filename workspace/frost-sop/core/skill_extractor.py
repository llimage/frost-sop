"""
F10 高级能力 - SkillExtractor
从工具调用日志中自动提取可复用的 Skill 模式。

PHILOSOPHY: 系统应该从实践中学习。每次成功的工具调用都可能
包含可复用的模式，提取并存储这些模式，让系统逐渐积累经验。
"""

import json
import os
import re
from datetime import datetime
from typing import Any

from core.db import get_db


class SkillExtractor:
    """
    技能提取器

    职责：
    1. 扫描 data/tool_calls/ 目录中的成功日志
    2. 从 skill_extraction_hints 提取 Skill 模式
    3. 生成 SKILL.md 草案并写入 SQLite

    用法：
        extractor = SkillExtractor()
        files = extractor.scan_and_extract_all()
    """

    def __init__(self, tool_calls_dir: str = "data/tool_calls"):
        self.tool_calls_dir = tool_calls_dir
        self.skills_dir = "skills"

    def scan_successful_calls(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        扫描 tool_calls 目录，返回所有 success=True 且有提取提示的日志。

        按时间倒序排列，最多返回 limit 条。
        """
        if not os.path.exists(self.tool_calls_dir):
            return []

        files = [f for f in os.listdir(self.tool_calls_dir) if f.endswith(".json")]
        calls = []
        for f in sorted(files, reverse=True)[:limit]:
            filepath = os.path.join(self.tool_calls_dir, f)
            try:
                with open(filepath, encoding="utf-8") as fp:
                    data = json.load(fp)
            except (OSError, json.JSONDecodeError):
                continue

            # 必须同时满足：success=True + 有提取提示
            if data.get("success") and data.get("skill_extraction_hints"):
                calls.append(data)
        return calls

    def _generate_skill_id(self, skill_name: str) -> str:
        """
        为 Skill 生成唯一 ID。

        格式：skill_extracted_{skill_name}_{timestamp}
        同时确保没有非法字符。
        """
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", skill_name.lower())
        safe_name = safe_name[:40]  # 限制长度
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"skill_ext_{safe_name}_{timestamp}"

    def extract_skill_from_call(self, call: dict[str, Any]) -> dict[str, Any] | None:
        """
        从单条调用日志提取 Skill 草案。

        Returns:
            包含 name/description/task_type/trigger_keywords/content 的字典，
            如果无法提取则返回 None。
        """
        hints = call.get("skill_extraction_hints", {})
        if not hints:
            return None

        # 提取核心字段
        skill_name = hints.get("suggested_skill_name", "")
        if not skill_name:
            skill_name = f"{call.get('tool_name', 'unknown')}_skill"

        extracted = hints.get("extracted_pattern", {})

        # 构造 SKILL.md 内容
        steps = extracted.get("analysis_dimensions", [])
        steps_text = (
            "\n".join([f"{i + 1}. {step}" for i, step in enumerate(steps)])
            if steps
            else "1. 执行任务\n2. 输出结果"
        )

        skill_md = f"""# {skill_name}

## 描述
{hints.get("description", "从历史工具调用中提取的 Skill")}

## 触发条件
- 任务类型：{hints.get("task_type", "unknown")}
- 关键词：{", ".join(hints.get("trigger_keywords", []))}

## 输入格式
```json
{json.dumps(extracted.get("input_types", []), ensure_ascii=False)}
```

## 执行步骤
{steps_text}

## 输出格式
{extracted.get("output_structure", "结构化报告")}

## 来源
- 原始调用 ID：{call.get("call_id")}
- 工具名称：{call.get("tool_name")}
- 提取时间：{datetime.now().isoformat()}
- 成功率参考：{hints.get("success_rate", "待验证")}
"""
        return {
            "name": skill_name,
            "description": hints.get("description", f"从 {call.get('tool_name')} 提取"),
            "task_type": hints.get("task_type", "unknown"),
            "trigger_keywords": hints.get("trigger_keywords", []),
            "content": skill_md,
            "source_call_id": call.get("call_id"),
        }

    def generate_skill_draft(self, call: dict[str, Any]) -> str | None:
        """
        生成 Skill 草案并保存到 skills/ 目录和 SQLite。

        Returns:
            保存的文件路径，失败返回 None。
        """
        draft = self.extract_skill_from_call(call)
        if not draft:
            return None

        # 确保目录存在
        os.makedirs(self.skills_dir, exist_ok=True)

        # 生成文件名
        safe_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", draft["name"].lower())
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_name}_draft_{timestamp}.md"
        filepath = os.path.join(self.skills_dir, filename)

        # 写入 SKILL.md 文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(draft["content"])

        # 写入 SQLite（使用 DBManager 的 insert 方法避免连接管理问题）
        skill_id = self._generate_skill_id(draft["name"])
        db = get_db()

        try:
            # 插入 skills 表
            db.insert(
                "skills",
                {
                    "id": skill_id,
                    "name": draft["name"],
                    "description": draft["description"],
                    "skill_type": draft["task_type"],
                    "task_type": draft["task_type"],
                    "trigger_keywords": json.dumps(draft["trigger_keywords"], ensure_ascii=False),
                    "success_rate": 0.0,
                    "status": "draft",
                    "version": "1.0",
                    "content": draft["content"],
                },
            )

            # 插入 skill_versions 表
            db.insert(
                "skill_versions",
                {
                    "skill_id": skill_id,
                    "version": "1.0",
                    "content": draft["content"],
                    "file_path": filepath,
                    "changelog": f"初始提取自 {draft['source_call_id']}",
                },
            )
        except Exception as e:
            print(f"⚠️ 写入数据库失败: {e}")

        return filepath

    def scan_and_extract_all(self) -> list[str]:
        """
        扫描所有成功日志，提取未处理的 Skill（按名称去重）。

        Returns:
            新创建的 SKILL.md 文件路径列表。
        """
        calls = self.scan_successful_calls()
        created_files = []

        for call in calls:
            hints = call.get("skill_extraction_hints", {})
            skill_name = hints.get("suggested_skill_name", "")
            if not skill_name:
                continue

            # 检查是否已存在同名 Skill（简单去重）
            db = get_db()
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM skills WHERE name = ?", (skill_name,))
            exists = cursor.fetchone()

            if exists:
                continue  # 已存在，跳过

            filepath = self.generate_skill_draft(call)
            if filepath:
                created_files.append(filepath)

        return created_files

    # ============================================================
    # 子任务2：Skill 验证与激活
    # ============================================================

    def validate_skill(self, skill_id: str, test_runs: int = 3) -> dict[str, Any]:
        """
        验证一个 draft Skill 的有效性。

        通过 mock LLM 调用测试 Skill 能否产生有效输出。
        成功率 >= 80% 则激活为 active，否则标记为 rejected。

        Args:
            skill_id: Skill 的 ID（skills 表中的 id）
            test_runs: 测试运行次数

        Returns:
            验证结果字典（skill_id, test_runs, success_count, success_rate, status）
        """
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, task_type, trigger_keywords, content FROM skills WHERE id = ?",
            (skill_id,),
        )
        row = cursor.fetchone()

        if not row:
            return {"success": False, "error": f"Skill {skill_id} not found"}

        skill_name = row["name"]
        task_type = row["task_type"]

        # 模拟测试：使用 FROST_TESTING=1 环境
        # 导入 call_llm，传入 context dict
        from skills.llm import call_llm

        success_count = 0
        for i in range(test_runs):
            test_prompt = (
                f"使用以下 Skill 完成任务：{skill_name}，"
                f"任务类型：{task_type}，"
                f"请生成结构化的测试输出。"
            )
            context = {
                "_prompt": test_prompt,
                "_system_prompt": f"你是 {skill_name} 专家，按照 Skill 描述执行任务。",
            }
            result = call_llm(context)
            response = result.get("_llm_response", "")

            # 判断是否成功：返回非空且包含有效内容
            if response and len(response.strip()) > 20:
                success_count += 1

        success_rate = success_count / test_runs if test_runs > 0 else 0.0
        status = "active" if success_rate >= 0.8 else "rejected"

        # 更新 skills 表
        db.update(
            "skills",
            "id",
            skill_id,
            {
                "success_rate": success_rate,
                "status": status,
            },
        )

        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "test_runs": test_runs,
            "success_count": success_count,
            "success_rate": success_rate,
            "status": status,
        }

    def validate_all_drafts(self) -> list[dict[str, Any]]:
        """
        验证所有 draft 状态的 Skill。

        Returns:
            每个 Skill 的验证结果列表。
        """
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM skills WHERE status = 'draft'")
        drafts = cursor.fetchall()

        results = []
        for row in drafts:
            result = self.validate_skill(row["id"])
            results.append(result)
        return results

    # ============================================================
    # A-006: 失败复盘机制 — 从失败调用中提取教训
    # ============================================================

    def scan_failed_calls(self, limit: int = 100) -> list[dict[str, Any]]:
        """
        A-006: 扫描 tool_calls 目录，返回所有 success=False 的失败日志。

        按时间倒序排列，最多返回 limit 条。
        """
        if not os.path.exists(self.tool_calls_dir):
            return []

        files = [f for f in os.listdir(self.tool_calls_dir) if f.endswith(".json")]
        calls = []
        for f in sorted(files, reverse=True)[:limit]:
            filepath = os.path.join(self.tool_calls_dir, f)
            try:
                with open(filepath, encoding="utf-8") as fp:
                    data = json.load(fp)
            except (OSError, json.JSONDecodeError):
                continue

            # 只收集失败调用
            if data.get("success") is False:
                calls.append(data)
        return calls

    def _classify_error(self, call: dict[str, Any]) -> str:
        """
        将失败调用归类为已知错误类型。

        Returns:
            错误类型字符串: api_error/timeout_error/validation_error/
                           execution_error/unknown_error
        """
        error_msg = str(call.get("error", "")).lower()
        duration = call.get("duration_ms", 0)

        if any(kw in error_msg for kw in ["timeout", "timed out", "超时"]):
            return "timeout_error"
        if any(kw in error_msg for kw in ["api", "rate limit", "unauthorized", "401", "403"]):
            return "api_error"
        if any(kw in error_msg for kw in ["validation", "invalid", "schema", "parse"]):
            return "validation_error"
        if any(kw in error_msg for kw in ["execution", "runtime", "exception"]):
            return "execution_error"
        if duration > 60000:  # 超过60秒视为超时
            return "timeout_error"
        return "execution_error"

    def extract_lesson_from_failure(self, call: dict[str, Any]) -> dict[str, Any] | None:
        """
        A-006: 从单条失败调用中提取教训（lesson）。

        Returns:
            包含 error_type/tool_name/call_id/summary/suggestion 的字典，
            无法提取时返回 None。
        """
        tool_name = call.get("tool_name", "unknown")
        error_type = self._classify_error(call)
        error_msg = call.get("error", "未知错误")
        call_id = call.get("call_id", "unknown")
        task_id = call.get("task_id", "")
        agent_id = call.get("agent_id", "")

        # 生成教训建议
        suggestions = {
            "timeout_error": f"工具 {tool_name} 调用超时。建议：增加超时时间、拆分大任务、检查网络连接。",
            "api_error": f"工具 {tool_name} API调用失败。建议：检查API密钥和权限、验证请求格式。",
            "validation_error": f"工具 {tool_name} 输入验证失败。建议：检查输入参数格式、确保必填字段完整。",
            "execution_error": f"工具 {tool_name} 执行异常。建议：检查工具代码逻辑、确保依赖可用。",
        }

        suggestion = suggestions.get(
            error_type,
            f"工具 {tool_name} 执行失败，原因未知。建议：检查日志获取更多信息。",
        )

        return {
            "error_type": error_type,
            "tool_name": tool_name,
            "call_id": call_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "summary": f"[{error_type}] {tool_name}: {str(error_msg)[:100]}",
            "suggestion": suggestion,
            "timestamp": call.get("timestamp", datetime.now().isoformat()),
        }

    def scan_and_archive_lessons(self, store=None) -> list[str]:
        """
        A-006: 扫描所有失败调用，提取教训并写入错题本。

        写入格式：lesson:{error_type}:{tool_name}
        如果已存在，则递增 times_encountered。

        Args:
            store: 可选的 Store 实例，用于写入 lesson 数据。
                   如果为 None，则仅返回提取列表，不写入。

        Returns:
            提取的 lesson key 列表。
        """
        failed_calls = self.scan_failed_calls()
        lesson_keys = []

        for call in failed_calls:
            lesson = self.extract_lesson_from_failure(call)
            if not lesson:
                continue

            error_type = lesson["error_type"]
            tool_name = lesson["tool_name"]
            lesson_key = f"lesson:{error_type}:{tool_name}"

            if store is not None:
                try:
                    # 检查是否已存在
                    existing = store.load(lesson_key)
                    if existing and isinstance(existing, dict):
                        # 已存在 → 递增计数 + 追加调用记录
                        existing["times_encountered"] = existing.get("times_encountered", 0) + 1
                        existing["last_seen"] = lesson["timestamp"]
                        call_ids = existing.get("call_ids", [])
                        call_ids.append(lesson["call_id"])
                        existing["call_ids"] = call_ids[-50:]  # 最多保留50条
                    else:
                        # 首次记录
                        existing = {
                            "error_type": error_type,
                            "tool_name": tool_name,
                            "times_encountered": 1,
                            "first_seen": lesson["timestamp"],
                            "last_seen": lesson["timestamp"],
                            "call_ids": [lesson["call_id"]],
                            "summary": lesson["summary"],
                            "suggestion": lesson["suggestion"],
                        }
                    store.save(lesson_key, existing)
                except Exception as e:
                    print(f"⚠️ 写入 lesson 失败 ({lesson_key}): {e}")

            lesson_keys.append(lesson_key)

        return lesson_keys
