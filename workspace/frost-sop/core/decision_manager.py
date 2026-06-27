"""
F8 子任务1：决策管理器
实现后端决策暂停与恢复机制
"""
from datetime import datetime
import json
import logging
from typing import Dict, List, Optional, Any, Union

from core.db import DBManager

logger = logging.getLogger(__name__)


class DecisionManager:
    """
    决策管理器：负责暂停/恢复决策点

    用途：
    - 当SOP执行到需要人工确认的阶段时，暂停执行并记录决策点
    - 用户做出选择后，恢复任务执行

    数据表：decision_points
    字段：id, task_id, stage_id, question, options_json, status,
          user_decision, user_note, created_at, responded_at
    """

    def __init__(self, db: Optional[DBManager] = None):
        """
        初始化决策管理器

        Args:
            db: 数据库管理器实例（可选，默认使用单例）
        """
        self._db = db if db else DBManager()
        self._lock = __import__('threading').Lock()  # P0-2: 线程安全

    def pause_decision(
        self,
        task_id: str,
        stage_id: str,
        question: str,
        options: List[str]
    ) -> int:
        """
        暂停任务并等待用户决策

        Args:
            task_id: 任务ID
            stage_id: 阶段ID
            question: 决策问题描述
            options: 可选选项列表（如 ["confirm", "reject", "modify"]）

        Returns:
            decision_id (int): 决策记录ID（SQLite 自增主键）

        Raises:
            Exception: 数据库写入失败时抛出异常
        """
        # 获取数据库连接
        conn = self._db.get_connection()
        cursor = conn.cursor()

        # 拒绝无效 task_id
        if not task_id or task_id == "unknown":
            logger.warning("跳过无效决策点（task_id='%s'）: %s", task_id, question)
            return -1

        # 确保父记录存在（防止外键约束失败）
        auto_project_id = f"auto_project_{task_id}"
        cursor.execute(
            "INSERT OR IGNORE INTO projects (id, name, description, status) "
            "VALUES (?, ?, ?, 'active')",
            (auto_project_id, f"自动项目-{task_id}", "由决策管理器自动创建")
        )
        cursor.execute(
            "INSERT OR IGNORE INTO tasks (id, title, description, project_id, status) "
            "VALUES (?, ?, ?, ?, 'pending')",
            (task_id, f"自动任务-{task_id}", "由决策管理器自动创建", auto_project_id)
        )
        conn.commit()

        # 插入决策记录（P0-2：显式设置 decision_type 避免 NULL）
        cursor.execute(
            """
            INSERT INTO decision_points
            (task_id, stage_id, decision_type, question, options_json, status, created_at, decision)
            VALUES (?, ?, 'manual_confirm', ?, ?, 'pending', ?, '')
            """,
            (
                task_id,
                stage_id,
                question,
                json.dumps(options, ensure_ascii=False),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
        )

        # 获取自动生成的 integer decision_id
        decision_id = cursor.lastrowid

        conn.commit()

        logger.info("决策点已暂停: %s", decision_id)
        logger.info("  问题: %s", question)
        logger.info("  选项: %s", options)

        return decision_id

    def resume_decision(
        self,
        decision_id: Union[int, str],
        user_choice: str,
        user_note: str = ""
    ) -> bool:
        """
        恢复决策点（用户已做出选择）

        Args:
            decision_id: 决策记录ID（int 来自 lastrowid 或 str 格式）
            user_choice: 用户选择（如 "confirm", "reject", "modify"）
            user_note: 用户备注（可选）

        Returns:
            bool: 是否成功恢复
        """
        with self._lock:  # P0-2: 线程安全
            conn = self._db.get_connection()
            cursor = conn.cursor()

            # 更新决策记录
            cursor.execute(
                """
                UPDATE decision_points
                SET status = 'resolved',
                    user_decision = ?,
                    user_note = ?,
                    responded_at = ?
                WHERE id = ?
                """,
                (
                    user_choice,
                    user_note,
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    decision_id
                )
            )

            if cursor.rowcount == 0:
                logger.error("决策点不存在: %s", decision_id)
                return False

            conn.commit()

        logger.info("决策点已恢复: %s", decision_id)
        logger.info("  用户选择: %s", user_choice)
        if user_note:
            logger.info("  用户备注: %s", user_note)

        return True

    def reject_decision(self, decision_id: Union[int, str], reason: str = "") -> bool:
        """
        拒绝决策点（P0-2 新增：显式拒绝操作）

        Args:
            decision_id: 决策记录ID
            reason: 拒绝原因

        Returns:
            bool: 是否成功
        """
        return self.resume_decision(decision_id, "reject", reason)

    def get_pending_decision(self) -> Optional[Dict[str, Any]]:
        """
        获取当前待处理的决策点

        Returns:
            dict: 决策点信息（包含 id, task_id, stage_id, question, options_json 等）
                 如果没有待处理决策，返回 None
        """
        conn = self._db.get_connection()
        cursor = conn.cursor()

        # 查询最新的待处理决策
        cursor.execute(
            """
            SELECT * FROM decision_points
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )

        row = cursor.fetchone()

        if row is None:
            return None

        # 转换为字典
        columns = [desc[0] for desc in cursor.description]
        decision = dict(zip(columns, row))

        # 解析 JSON 字段
        if decision.get('options_json'):
            decision['options'] = json.loads(decision['options_json'])
        else:
            decision['options'] = []

        return decision

    def has_pending_decision(self) -> bool:
        """
        检查是否存在待处理的决策点

        Returns:
            bool: 是否存在待处理决策
        """
        return self.get_pending_decision() is not None

    def get_decision_by_id(self, decision_id: Union[int, str]) -> Optional[Dict[str, Any]]:
        """
        根据ID获取决策点详情

        Args:
            decision_id: 决策记录ID

        Returns:
            dict: 决策点信息，如果不存在返回 None
        """
        conn = self._db.get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM decision_points WHERE id = ?", (decision_id,))
        row = cursor.fetchone()

        if row is None:
            return None

        columns = [desc[0] for desc in cursor.description]
        decision = dict(zip(columns, row))

        # 解析 JSON 字段
        if decision.get('options_json'):
            decision['options'] = json.loads(decision['options_json'])
        else:
            decision['options'] = []

        return decision

    def get_decisions_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        """
        获取某个任务的所有决策点

        Args:
            task_id: 任务ID

        Returns:
            list: 决策点列表
        """
        conn = self._db.get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM decision_points WHERE task_id = ? ORDER BY created_at ASC",
            (task_id,)
        )

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description]

        decisions = []
        for row in rows:
            decision = dict(zip(columns, row))
            # 解析 JSON 字段
            if decision.get('options_json'):
                decision['options'] = json.loads(decision['options_json'])
            else:
                decision['options'] = []
            decisions.append(decision)

        return decisions


# 全局单例
_default_manager: Optional[DecisionManager] = None


def get_decision_manager(db: Optional[DBManager] = None) -> DecisionManager:
    """
    获取全局决策管理器单例

    Args:
        db: 数据库管理器实例（可选，仅首次创建时使用）

    Returns:
        DecisionManager: 全局单例
    """
    global _default_manager

    if _default_manager is None:
        _default_manager = DecisionManager(db)

    return _default_manager
