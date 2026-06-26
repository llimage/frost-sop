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
from typing import Dict, Any, List, Optional

from core.db import get_db, get_db_connection


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

    def scan_successful_calls(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        扫描 tool_calls 目录，返回所有 success=True 且有提取提示的日志。

        按时间倒序排列，最多返回 limit 条。
        """
        if not os.path.exists(self.tool_calls_dir):
            return []

        files = [
            f for f in os.listdir(self.tool_calls_dir)
            if f.endswith(".json")
        ]
        calls = []
        for f in sorted(files, reverse=True)[:limit]:
            filepath = os.path.join(self.tool_calls_dir, f)
            try:
                with open(filepath, "r", encoding="utf-8") as fp:
                    data = json.load(fp)
            except (json.JSONDecodeError, IOError):
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
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', skill_name.lower())
        safe_name = safe_name[:40]  # 限制长度
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"skill_ext_{safe_name}_{timestamp}"

    def extract_skill_from_call(self, call: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        steps_text = "\n".join(
            [f"{i+1}. {step}" for i, step in enumerate(steps)]
        ) if steps else "1. 执行任务\n2. 输出结果"

        skill_md = f"""# {skill_name}

## 描述
{hints.get('description', '从历史工具调用中提取的 Skill')}

## 触发条件
- 任务类型：{hints.get('task_type', 'unknown')}
- 关键词：{', '.join(hints.get('trigger_keywords', []))}

## 输入格式
```json
{json.dumps(extracted.get('input_types', []), ensure_ascii=False)}
```

## 执行步骤
{steps_text}

## 输出格式
{extracted.get('output_structure', '结构化报告')}

## 来源
- 原始调用 ID：{call.get('call_id')}
- 工具名称：{call.get('tool_name')}
- 提取时间：{datetime.now().isoformat()}
- 成功率参考：{hints.get('success_rate', '待验证')}
"""
        return {
            "name": skill_name,
            "description": hints.get("description", f"从 {call.get('tool_name')} 提取"),
            "task_type": hints.get("task_type", "unknown"),
            "trigger_keywords": hints.get("trigger_keywords", []),
            "content": skill_md,
            "source_call_id": call.get("call_id"),
        }

    def generate_skill_draft(self, call: Dict[str, Any]) -> Optional[str]:
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
        safe_name = re.sub(r'[^a-zA-Z0-9_\-]', '_', draft["name"].lower())
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
            db.insert("skills", {
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
            })

            # 插入 skill_versions 表
            db.insert("skill_versions", {
                "skill_id": skill_id,
                "version": "1.0",
                "content": draft["content"],
                "file_path": filepath,
                "changelog": f"初始提取自 {draft['source_call_id']}",
            })
        except Exception as e:
            print(f"⚠️ 写入数据库失败: {e}")

        return filepath

    def scan_and_extract_all(self) -> List[str]:
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
            cursor.execute(
                "SELECT id FROM skills WHERE name = ?",
                (skill_name,)
            )
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

    def validate_skill(self, skill_id: str, test_runs: int = 3) -> Dict[str, Any]:
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
            (skill_id,)
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
        db.update("skills", "id", skill_id, {
            "success_rate": success_rate,
            "status": status,
        })

        return {
            "skill_id": skill_id,
            "skill_name": skill_name,
            "test_runs": test_runs,
            "success_count": success_count,
            "success_rate": success_rate,
            "status": status,
        }

    def validate_all_drafts(self) -> List[Dict[str, Any]]:
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
