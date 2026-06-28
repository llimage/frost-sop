"""
F10 高级能力 - Skill 版本管理器
支持版本创建、回滚、历史查询和旧版本自动清理。

PHILOSOPHY: 每个 Skill 都有演进的生命周期。保留完整的版本审计链，
让系统可以在任何时刻回退到经过验证的版本。
"""

import os
from typing import Optional, List, Dict, Any

from core.db import get_db


class SkillVersionManager:
    """
    Skill 版本管理器

    职责：
    1. 为 Skill 创建新版本（写入文件和数据库）
    2. 版本回滚（复制旧内容作为新版本）
    3. 查询版本历史
    4. 自动清理超过保留数量的旧版本文件

    用法：
        manager = SkillVersionManager()
        manager.create_new_version(skill_id, new_content, "修复了 XX 问题")
        manager.rollback(skill_id, 2)
        history = manager.get_versions(skill_id)
    """

    def __init__(self, skills_dir: str = "skills"):
        self.skills_dir = skills_dir
        self.max_versions = 5  # 最多保留的历史版本数

    def _get_skill_dir(self, skill_name: str) -> str:
        """获取 Skill 的版本文件目录"""
        safe_name = skill_name.replace(" ", "_").replace("/", "_")
        return os.path.join(self.skills_dir, safe_name)

    def create_new_version(
        self,
        skill_id: str,
        content: str,
        changelog: str = ""
    ) -> int:
        """
        为 Skill 创建新版本。

        Args:
            skill_id: skills 表中的 ID
            content: 新版本的 SKILL.md 内容
            changelog: 变更说明

        Returns:
            新版本号（从1自增的整数）

        Raises:
            ValueError: Skill 不存在时抛出
        """
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()

        # 获取当前版本号和名称
        cursor.execute(
            "SELECT name, version FROM skills WHERE id = ?",
            (skill_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Skill {skill_id} not found")

        skill_name = row["name"]
        current_version = row["version"]

        # 计算新版本号
        try:
            major_version = int(current_version.split(".")[0])
        except (ValueError, AttributeError):
            major_version = 1
        new_version_str = f"{major_version + 1}.0"

        # 保存文件到 skills/{skill_name}/v{N}/SKILL.md
        skill_dir = self._get_skill_dir(skill_name)
        version_dir = os.path.join(skill_dir, f"v{major_version + 1}")
        os.makedirs(version_dir, exist_ok=True)
        filepath = os.path.join(version_dir, "SKILL.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        # 插入 skill_versions 表
        db.insert("skill_versions", {
            "skill_id": skill_id,
            "version": new_version_str,
            "content": content,
            "file_path": filepath,
            "changelog": changelog,
        })

        # 更新 skills 表的 version 和 content
        db.update("skills", "id", skill_id, {
            "version": new_version_str,
            "content": content,
        })

        # 清理旧版本（保留最多 max_versions 个）
        self._cleanup_old_versions(skill_id)
        return major_version + 1

    def _cleanup_old_versions(self, skill_id: str):
        """
        清理超出保留数量的旧版本文件和数据库记录。

        注意：只删除文件和版本历史记录，不删除 skills 表记录。
        保留最近 max_versions 个版本。
        """
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, version, file_path FROM skill_versions
               WHERE skill_id = ? ORDER BY CAST(
                   SUBSTR(version, 1, INSTR(version || '.', '.') - 1) AS INTEGER
               ) DESC""",
            (skill_id,)
        )
        versions = cursor.fetchall()

        if len(versions) <= self.max_versions:
            return

        # 删除多余的旧版本
        for v in versions[self.max_versions:]:
            # 删除文件
            file_path = v["file_path"]
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except OSError:
                    pass

            # 删除空目录
            parent_dir = os.path.dirname(file_path) if file_path else ""
            if parent_dir and os.path.exists(parent_dir):
                try:
                    remaining = os.listdir(parent_dir)
                    if not remaining:
                        os.rmdir(parent_dir)
                except OSError:
                    pass

    def rollback(self, skill_id: str, target_version: int) -> bool:
        """
        回滚到指定版本。

        实现方式：读取目标版本内容，创建一个新版本（内容为旧版本内容），
        完整保留审计链。

        Args:
            skill_id: skills 表中的 ID
            target_version: 目标版本号（整数，如 2）

        Returns:
            True 表示成功，False 表示目标版本不存在
        """
        target_version_str = f"{target_version}.0"

        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT content, file_path FROM skill_versions
               WHERE skill_id = ? AND version = ?""",
            (skill_id, target_version_str)
        )
        row = cursor.fetchone()

        if not row:
            return False

        # 读取目标版本内容（如果文件存在则读取文件，否则用数据库内容）
        content = row["content"]
        if row["file_path"] and os.path.exists(row["file_path"]):
            try:
                with open(row["file_path"], "r", encoding="utf-8") as f:
                    content = f.read()
            except (IOError, UnicodeDecodeError):
                pass  # 回退到数据库内容

        # 创建新版本（内容为目标版本内容）
        self.create_new_version(
            skill_id, content,
            f"回滚到版本 {target_version_str}"
        )
        return True

    def get_versions(self, skill_id: str) -> List[Dict[str, Any]]:
        """
        获取 Skill 的所有版本历史。

        Returns:
            版本列表，按版本号降序排列。
        """
        db = get_db()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT version, file_path, changelog, created_at
               FROM skill_versions
               WHERE skill_id = ?
               ORDER BY CAST(
                   SUBSTR(version, 1, INSTR(version || '.', '.') - 1) AS INTEGER
               ) DESC""",
            (skill_id,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def get_latest_version(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 Skill 的最新版本。

        Returns:
            最新版本信息字典，或 None（如果不存在）。
        """
        versions = self.get_versions(skill_id)
        return versions[0] if versions else None
