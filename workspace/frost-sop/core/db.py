"""
F7 生产加固 - SQLite 持久化
PHILOSOPHY: 内存数据迁移到 SQLite，确保重启后数据完整恢复。

core/db.py - 数据库管理模块
提供 DBManager 单例类，负责连接管理和表初始化。
"""

import contextlib
import re
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Any

# S-001/S-002 修复：表名白名单（与 init_tables 的 CREATE TABLE 一致）
ALLOWED_TABLES = {
    "config",
    "projects",
    "tasks",
    "task_stages",
    "agents",
    "agent_status",
    "sop_templates",
    "sop_executions",
    "audit_log",
    "cost_log",
    "schedule",
    "energy_log",
    "knowledge",
    "knowledge_tags",
    "skills",
    "skill_versions",
    "tool_calls",
    "decision_points",
    "kv_store",
    "event_log",
    "scheduled_jobs",
    "project_skills",
    "config_snapshots",
    "daily_reviews",
}

# S-001 修复：WHERE 子句危险关键字（用于非参数化部分的检测）
_WHERE_DANGEROUS_KEYWORDS = [
    ";",
    "--",
    "/*",
    "*/",
    "UNION",
    "DROP",
    "DELETE",
    "INSERT",
    "UPDATE",
    "ALTER",
    "CREATE",
    "EXEC",
    "EXECUTE",
    "TRUNCATE",
]


class DBManager:
    """
    SQLite 数据库管理器（单例模式）

    负责：
    1. 数据库连接管理
    2. 17张表的创建和迁移
    3. CRUD 操作的封装
    """

    _instance = None
    _connection = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, db_path: str = "data/frost_sop.db"):
        """
        初始化数据库连接

        Args:
            db_path: SQLite 数据库文件路径
        """
        if self._connection is not None:
            return

        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._connection = sqlite3.connect(
            db_path,
            check_same_thread=False,
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA busy_timeout=5000")  # 并发写等待5秒而非立即失败

        self._write_lock = threading.Lock()  # 串行化所有写操作，防止 "database is locked"

        self.init_tables()

    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        if self._connection is None:
            self._connection = sqlite3.connect(self.db_path)
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA journal_mode=WAL")
            self._connection.execute("PRAGMA busy_timeout=5000")
            if not hasattr(self, "_write_lock"):
                self._write_lock = threading.Lock()
        return self._connection  # type: ignore[return-value]

    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def init_tables(self):
        """初始化17张表"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # 1. config - 系统配置表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string',
            description TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 2. tasks - 任务表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            project_id TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            result_summary TEXT,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
        """)

        # 项目表（tasks 的外键依赖）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 3. task_stages - 任务阶段表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS task_stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            stage_name TEXT NOT NULL,
            stage_order INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            output TEXT,
            error TEXT,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """)

        # 4. agents - Agent表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            agent_type TEXT NOT NULL,
            generation INTEGER,
            parent_id TEXT,
            config TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (parent_id) REFERENCES agents(id)
        )
        """)

        # 5. agent_status - Agent状态表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_status (
            agent_id TEXT PRIMARY KEY,
            status TEXT DEFAULT 'idle',
            current_task_id TEXT,
            last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_tokens_used INTEGER DEFAULT 0,
            total_cost REAL DEFAULT 0.0,
            error_count INTEGER DEFAULT 0,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """)

        # 6. sop_templates - SOP模板表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sop_templates (
            id TEXT PRIMARY KEY,
            sop_id TEXT NOT NULL,
            name TEXT NOT NULL,
            version TEXT NOT NULL,
            content TEXT NOT NULL,
            is_preset BOOLEAN DEFAULT 0,
            is_validated BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 7. sop_executions - SOP执行记录表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sop_executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            sop_template_id TEXT NOT NULL,
            started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            completed_at TIMESTAMP,
            status TEXT DEFAULT 'running',
            total_stages INTEGER,
            completed_stages INTEGER DEFAULT 0,
            error TEXT,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (sop_template_id) REFERENCES sop_templates(id)
        )
        """)

        # 8. audit_log - 审计日志表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT,
            action TEXT NOT NULL,
            details TEXT,
            level TEXT DEFAULT 'info'
        )
        """)

        # 9. cost_log - 成本日志表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS cost_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            task_id TEXT,
            agent_id TEXT NOT NULL,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            estimated_cost REAL DEFAULT 0.0,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """)

        # 10. schedule - 调度表（含 F9 migration 列，P0-1 修复）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            title TEXT DEFAULT '',
            description TEXT DEFAULT '',
            cron_expression TEXT,
            task_template TEXT,
            enabled BOOLEAN DEFAULT 1,
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            repeat_type TEXT DEFAULT 'none',
            repeat_end TEXT DEFAULT '',
            notified BOOLEAN DEFAULT 0,
            last_run TIMESTAMP,
            next_run TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 11. energy_log - 能量日志表（Agent 能量/健康度，含 F9 migration 列，P0-1 修复）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS energy_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            energy_level REAL,
            health_score REAL,
            level INTEGER DEFAULT 50,
            emotion TEXT DEFAULT '',
            user_note TEXT DEFAULT '',
            notes TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id)
        )
        """)

        # 12. knowledge - 知识表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            source TEXT,
            knowledge_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 13. knowledge_tags - 知识标签表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS knowledge_tags (
            knowledge_id INTEGER,
            tag TEXT NOT NULL,
            PRIMARY KEY (knowledge_id, tag),
            FOREIGN KEY (knowledge_id) REFERENCES knowledge(id)
        )
        """)

        # 14. skills - 技能表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            skill_type TEXT,
            version TEXT DEFAULT '1.0',
            content TEXT,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 15. skill_versions - 技能版本表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS skill_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id TEXT NOT NULL,
            version TEXT NOT NULL,
            content TEXT NOT NULL,
            changelog TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (skill_id) REFERENCES skills(id)
        )
        """)

        # 16. tool_calls - 工具调用表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT,
            task_id TEXT,
            tool_name TEXT NOT NULL,
            inputs TEXT,
            outputs TEXT,
            duration_ms INTEGER,
            status TEXT DEFAULT 'success',
            error TEXT,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """)

        # 17. decision_points - 决策点表（含 F8 migration 列，P0-1 修复）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            agent_id TEXT,
            task_id TEXT,
            stage_id TEXT DEFAULT '',
            decision_type TEXT,
            question TEXT DEFAULT '',
            options_json TEXT DEFAULT '[]',
            context TEXT,
            decision TEXT NOT NULL,
            reasoning TEXT,
            status TEXT DEFAULT 'pending',
            user_decision TEXT DEFAULT '',
            user_note TEXT DEFAULT '',
            created_at TIMESTAMP,
            responded_at TIMESTAMP,
            FOREIGN KEY (agent_id) REFERENCES agents(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
        """)

        # 18. kv_store - 通用键值存储表（用于 Store 类的持久化）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            value_type TEXT DEFAULT 'string',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # 19. event_log - V2.0 事件日志表（EventBus 持久化）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id TEXT NOT NULL UNIQUE,
            event_type TEXT NOT NULL,
            source TEXT,
            data TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)

        # V2.2: event_log 查询索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log(event_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_log_source ON event_log(source)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_event_log_timestamp ON event_log(timestamp)")

        # 20. scheduled_jobs — V6.0 APScheduler 定时任务持久化
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_jobs (
            id TEXT PRIMARY KEY,
            job_type TEXT NOT NULL,
            target_id TEXT,
            cron_expr TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            last_run TEXT,
            next_run TEXT,
            run_count INTEGER DEFAULT 0,
            fail_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at TEXT DEFAULT (datetime('now', 'localtime'))
        )
        """)
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_type ON scheduled_jobs(job_type)"
        )
        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_enabled ON scheduled_jobs(enabled)"
        )

        # A-007: 性能索引优化（高频查询列）
        self._create_performance_indexes(cursor)

        conn.commit()
        print("✅ 19张表初始化完成")

        # F9: 迁移 energy_log 表（添加创始人需要的列）
        self._migrate_energy_log_table(cursor)

        # F9: 迁移 schedule 表（添加日程管理需要的列）
        self._migrate_schedule_table(cursor)

        # F10: 迁移 skills 表（添加 SkillExtractor 需要的列）
        self._migrate_skills_table(cursor)

        # F10: 迁移 skill_versions 表（添加 file_path 列）
        self._migrate_skill_versions_table(cursor)

        # F8: 迁移 decision_points 表（添加决策管理需要的列）
        self._migrate_decision_points_table(cursor)

        conn.commit()

    def _migrate_table(self, cursor, table_name: str, needed_columns: dict[str, str]):
        """通用表迁移：为指定表添加缺失列（S-003 安全加固）。

        Args:
            cursor: SQLite cursor
            table_name: 表名（必须在 ALLOWED_TABLES 中）
            needed_columns: {列名: 列定义} 字典
        """
        existing = {
            col["name"] for col in cursor.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        for col_name, col_def in needed_columns.items():
            if col_name not in existing:
                # S-003 修复：列名/列定义安全验证
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col_name):
                    continue
                if not re.match(r"^[A-Z]+\s*(DEFAULT\s+[^;\-]*|)$", col_def, re.IGNORECASE):
                    continue
                with contextlib.suppress(Exception):
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")

    def _migrate_energy_log_table(self, cursor):
        """F9: 为 energy_log 表添加创始人需要的列"""
        self._migrate_table(
            cursor,
            "energy_log",
            {
                "level": "INTEGER DEFAULT 50",
                "emotion": "TEXT DEFAULT ''",
                "user_note": "TEXT DEFAULT ''",
            },
        )

    def _migrate_schedule_table(self, cursor):
        """F9: 为 schedule 表添加日程管理需要的列"""
        self._migrate_table(
            cursor,
            "schedule",
            {
                "title": "TEXT DEFAULT ''",
                "description": "TEXT DEFAULT ''",
                "start_time": "TIMESTAMP",
                "end_time": "TIMESTAMP",
                "repeat_type": "TEXT DEFAULT 'none'",
                "repeat_end": "TEXT DEFAULT ''",
                "notified": "BOOLEAN DEFAULT 0",
            },
        )

    def _migrate_skills_table(self, cursor):
        """F10: 为 skills 表添加 SkillExtractor 需要的列"""
        self._migrate_table(
            cursor,
            "skills",
            {
                "trigger_keywords": "TEXT DEFAULT '[]'",
                "success_rate": "REAL DEFAULT 0.0",
                "status": "TEXT DEFAULT 'active'",
                "task_type": "TEXT DEFAULT ''",
            },
        )

    def _migrate_skill_versions_table(self, cursor):
        """F10: 为 skill_versions 表添加 file_path 列"""
        self._migrate_table(cursor, "skill_versions", {"file_path": "TEXT DEFAULT ''"})

    def _migrate_decision_points_table(self, cursor):
        """F8: 为 decision_points 表添加决策管理需要的列"""
        self._migrate_table(
            cursor,
            "decision_points",
            {
                "stage_id": "TEXT DEFAULT ''",
                "question": "TEXT DEFAULT ''",
                "options_json": "TEXT DEFAULT '[]'",
                "status": "TEXT DEFAULT 'pending'",
                "user_decision": "TEXT DEFAULT ''",
                "user_note": "TEXT DEFAULT ''",
                "created_at": "TIMESTAMP",
                "responded_at": "TIMESTAMP",
            },
        )

    # ============================================================
    # 通用 CRUD 操作
    # ============================================================

    @staticmethod
    def _create_performance_indexes(cursor):
        """A-007: 为高频查询列创建性能索引"""
        indexes = [
            # tasks: id 已是 PRIMARY KEY，补充 status 和 project_id
            ("idx_tasks_status", "tasks", "status"),
            ("idx_tasks_project_id", "tasks", "project_id"),
            # task_stages: 按 task_id 和 status 频繁查询
            ("idx_task_stages_task_id", "task_stages", "task_id"),
            ("idx_task_stages_status", "task_stages", "status"),
            # agents: 按 agent_type 和 parent_id 过滤
            ("idx_agents_type", "agents", "agent_type"),
            ("idx_agents_parent_id", "agents", "parent_id"),
            # agent_status: 按状态和当前任务查询
            ("idx_agent_status_status", "agent_status", "status"),
            ("idx_agent_status_task_id", "agent_status", "current_task_id"),
            # sop_executions: 按 task_id 和状态查询
            ("idx_sop_exec_task_id", "sop_executions", "task_id"),
            ("idx_sop_exec_status", "sop_executions", "status"),
            # cost_log: 月度成本统计高频列
            ("idx_cost_log_agent_id", "cost_log", "agent_id"),
            ("idx_cost_log_task_id", "cost_log", "task_id"),
            ("idx_cost_log_timestamp", "cost_log", "timestamp"),
            # audit_log: 按 agent_id 和时间查询
            ("idx_audit_log_agent_id", "audit_log", "agent_id"),
            ("idx_audit_log_timestamp", "audit_log", "timestamp"),
            # energy_log: 按 agent_id 和时间查询
            ("idx_energy_log_agent_id", "energy_log", "agent_id"),
            ("idx_energy_log_timestamp", "energy_log", "timestamp"),
            # tool_calls: 失败复盘查询
            ("idx_tool_calls_agent_id", "tool_calls", "agent_id"),
            ("idx_tool_calls_task_id", "tool_calls", "task_id"),
            ("idx_tool_calls_status", "tool_calls", "status"),
            # decision_points: 决策查询
            ("idx_decisions_agent_id", "decision_points", "agent_id"),
            ("idx_decisions_task_id", "decision_points", "task_id"),
            ("idx_decisions_status", "decision_points", "status"),
            # schedule: 日程提醒查询
            ("idx_schedule_start_time", "schedule", "start_time"),
            ("idx_schedule_enabled", "schedule", "enabled"),
            # skills: 活跃技能查询
            ("idx_skills_active", "skills", "is_active"),
            ("idx_skills_status", "skills", "status"),
        ]

        for idx_name, table, column in indexes:
            with contextlib.suppress(Exception):
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")

    # ============================================================
    # 通用 CRUD 操作
    # ============================================================

    def insert(self, table: str, data: dict[str, Any]) -> Any:
        """
        插入记录

        Args:
            table: 表名
            data: 数据字典

        Returns:
            插入的记录ID（如果是自增ID）
        """
        # S-002 修复：表名白名单验证
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Security: Invalid table name '{table}'")
        # S-002 修复：列名安全验证（只允许字母、数字、下划线）
        for col in data:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                raise ValueError(f"Security: Invalid column name '{col}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?"] * len(data))
        values = list(data.values())

        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        with self._write_lock:
            cursor.execute(sql, values)
            conn.commit()

        return cursor.lastrowid

    def update(self, table: str, id_column: str, id_value: Any, data: dict[str, Any]) -> int:
        """
        更新记录

        Args:
            table: 表名
            id_column: ID列名
            id_value: ID值
            data: 要更新的数据字典

        Returns:
            受影响的行数
        """
        # S-002 修复：表名白名单验证
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Security: Invalid table name '{table}'")
        # S-002 修复：列名安全验证
        for col in list(data.keys()) + [id_column]:
            if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", col):
                raise ValueError(f"Security: Invalid column name '{col}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        set_clause = ", ".join([f"{k} = ?" for k in data])
        values = list(data.values()) + [id_value]

        sql = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?"
        with self._write_lock:
            cursor.execute(sql, values)
            conn.commit()

        return cursor.rowcount

    def delete(self, table: str, id_column: str, id_value: Any) -> int:
        """
        删除记录

        Args:
            table: 表名
            id_column: ID列名
            id_value: ID值

        Returns:
            受影响的行数
        """
        # S-002 修复：表名白名单验证
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Security: Invalid table name '{table}'")
        # S-002 修复：列名安全验证
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", id_column):
            raise ValueError(f"Security: Invalid column name '{id_column}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"DELETE FROM {table} WHERE {id_column} = ?"
        with self._write_lock:
            cursor.execute(sql, [id_value])
            conn.commit()

        return cursor.rowcount

    def select_one(self, table: str, id_column: str, id_value: Any) -> dict[str, Any] | None:
        """
        查询单条记录

        Args:
            table: 表名
            id_column: ID列名
            id_value: ID值

        Returns:
            记录字典，如果不存在则返回None
        """
        # S-002 修复：表名白名单验证
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Security: Invalid table name '{table}'")
        # S-002 修复：列名安全验证
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", id_column):
            raise ValueError(f"Security: Invalid column name '{id_column}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table} WHERE {id_column} = ?"
        cursor.execute(sql, [id_value])
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None

    def select_all(
        self, table: str, where: str | None = None, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        """
        查询多条记录

        Args:
            table: 表名
            where: WHERE 子句（可选，只允许参数化查询）
            params: WHERE 子句的参数（可选）

        Returns:
            记录字典列表
        """
        # S-001 修复：表名白名单验证
        if table not in ALLOWED_TABLES:
            raise ValueError(f"Security: Invalid table name '{table}'")
        # S-001 修复：WHERE 子句安全验证
        if where:
            where_upper = where.upper()
            for keyword in _WHERE_DANGEROUS_KEYWORDS:
                if keyword in where_upper:
                    raise ValueError(f"Security: Dangerous keyword '{keyword}' in WHERE clause")

        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table}"
        if where:
            sql += f" WHERE {where}"

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def execute_sql(self, sql: str, params: list[Any] | None = None) -> Any:
        """
        执行自定义SQL

        警告：此方法接受任意SQL，仅供内部使用，不得将外部输入直接拼入 sql 参数。

        Args:
            sql: SQL语句
            params: 参数列表

        Returns:
            如果是查询，返回结果列表；否则返回受影响的行数
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if params:
            cursor.execute(sql, params)
        else:
            cursor.execute(sql)

        if sql.strip().upper().startswith("SELECT"):
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            conn.commit()
            return cursor.rowcount

    # ============================================================
    # 特定业务操作
    # ============================================================

    def save_task(self, task_data: dict[str, Any]) -> str:
        """
        保存任务（如果已存在则更新）

        Args:
            task_data: 任务数据

        Returns:
            任务ID
        """
        existing = self.select_one("tasks", "id", task_data["id"])

        if existing:
            # 更新
            self.update(
                "tasks", "id", task_data["id"], {k: v for k, v in task_data.items() if k != "id"}
            )
        else:
            # 插入
            self.insert("tasks", task_data)

        return task_data["id"]  # type: ignore[no-any-return]

    def save_agent(self, agent_data: dict[str, Any]) -> str:
        """
        保存Agent（如果已存在则更新）

        Args:
            agent_data: Agent数据

        Returns:
            Agent ID
        """
        existing = self.select_one("agents", "id", agent_data["id"])

        if existing:
            self.update(
                "agents", "id", agent_data["id"], {k: v for k, v in agent_data.items() if k != "id"}
            )
        else:
            self.insert("agents", agent_data)

        return agent_data["id"]  # type: ignore[no-any-return]

    def log_cost(self, cost_data: dict[str, Any]) -> int:
        """
        记录成本日志

        Args:
            cost_data: 成本数据

        Returns:
            插入的日志ID
        """
        return self.insert("cost_log", cost_data)  # type: ignore[no-any-return]

    def log_audit(self, audit_data: dict[str, Any]) -> int:
        """
        记录审计日志

        Args:
            audit_data: 审计数据

        Returns:
            插入的日志ID
        """
        return self.insert("audit_log", audit_data)  # type: ignore[no-any-return]

    def get_monthly_cost(self, year: int, month: int) -> float:
        """
        获取指定月份的总成本

        Args:
            year: 年份
            month: 月份

        Returns:
            总成本（估算）
        """
        sql = """
        SELECT SUM(estimated_cost) as total
        FROM cost_log
        WHERE strftime('%Y', timestamp) = ? AND strftime('%m', timestamp) = ?
        """
        result = self.execute_sql(sql, [str(year), str(month).zfill(2)])
        if result and result[0]["total"]:
            return float(result[0]["total"])
        return 0.0

    def get_table_counts(self) -> dict[str, int]:
        """
        获取所有表的记录数

        Returns:
            表名 -> 记录数的字典
        """
        tables = [
            "config",
            "projects",
            "tasks",
            "task_stages",
            "agents",
            "agent_status",
            "sop_templates",
            "sop_executions",
            "audit_log",
            "cost_log",
            "schedule",
            "energy_log",
            "knowledge",
            "knowledge_tags",
            "skills",
            "skill_versions",
            "tool_calls",
            "decision_points",
        ]

        counts = {}
        for table in tables:
            try:
                result = self.execute_sql(f"SELECT COUNT(*) as cnt FROM {table}")
                counts[table] = result[0]["cnt"] if result else 0
            except Exception:
                counts[table] = -1  # 表不存在

        return counts

    # ============================================================
    # F9 创始人工具 - 能量状态记录
    # ============================================================

    def add_energy_log(self, level: int, emotion: str, note: str = "") -> int:
        """
        写入能量记录

        Args:
            level: 能量等级 (0-100)
            emotion: 情绪标签
            note: 备注

        Returns:
            记录ID
        """
        # 确保 founder agent 存在
        existing = self.select_one("agents", "id", "founder")
        if not existing:
            self.insert(
                "agents",
                {
                    "id": "founder",
                    "name": "创始人",
                    "agent_type": "human",
                    "generation": 0,
                    "created_at": datetime.now().isoformat(),
                },
            )

        result: int = self.insert(  # type: ignore[no-any-return,assignment]
            "energy_log",
            {
                "agent_id": "founder",
                "energy_level": float(level),
                "health_score": float(level),
                "level": level,
                "emotion": emotion,
                "notes": note,
                "user_note": note,
                "timestamp": datetime.now().isoformat(),
            },
        )
        return result  # type: ignore[no-any-return]

    def get_energy_history(self, days: int = 30) -> list:
        """
        获取最近 N 天的能量记录

        Args:
            days: 天数

        Returns:
            记录字典列表
        """
        sql = """
        SELECT id, level, emotion, user_note as note, timestamp as created_at, energy_level
        FROM energy_log
        WHERE timestamp >= datetime('now', '-' || ? || ' days', 'localtime')
        ORDER BY timestamp ASC
        """
        return self.execute_sql(sql, [str(days)])  # type: ignore[no-any-return]

    def get_latest_energy(self) -> dict:
        """
        获取最近一条能量记录

        Returns:
            记录字典，如果没有则返回 None
        """
        sql = """
        SELECT level, emotion, user_note as note, timestamp as created_at
        FROM energy_log
        ORDER BY timestamp DESC LIMIT 1
        """
        result = self.execute_sql(sql)
        return result[0] if result else None  # type: ignore[return-value]

    # ============================================================
    # F9 创始人工具 - 私人日程管理
    # ============================================================

    def add_schedule(
        self,
        title: str,
        start_time: str,
        end_time: str,
        repeat_type: str = "none",
        repeat_end: str = "",
        description: str = "",
    ) -> int:
        """
        添加日程

        Args:
            title: 标题
            start_time: 开始时间
            end_time: 结束时间
            repeat_type: none/daily/weekly/monthly
            repeat_end: 重复结束日期
            description: 描述

        Returns:
            日程ID
        """
        result: int = self.insert(  # type: ignore[no-any-return,assignment]
            "schedule",
            {
                "name": title,
                "title": title,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "repeat_type": repeat_type,
                "repeat_end": repeat_end,
                "notified": 0,
                "enabled": 1,
                "cron_expression": "",
                "task_template": "",
                "created_at": datetime.now().isoformat(),
            },
        )
        return result

    def get_schedules(self, date_from: str = "", date_to: str = "") -> list:
        """
        获取日程列表

        Args:
            date_from: 开始日期（可选）
            date_to: 结束日期（可选）

        Returns:
            日程字典列表
        """
        sql = """
        SELECT id, title, name, description, start_time, end_time,
               repeat_type, repeat_end, notified, created_at
        FROM schedule WHERE 1=1
        """
        params = []
        if date_from:
            sql += " AND start_time >= ?"
            params.append(date_from)
        if date_to:
            sql += " AND start_time <= ?"
            params.append(date_to)
        sql += " ORDER BY start_time ASC"
        return self.execute_sql(sql, params if params else None)  # type: ignore[no-any-return]

    def update_schedule(
        self,
        schedule_id: int,
        title: str,
        start_time: str,
        end_time: str,
        repeat_type: str,
        repeat_end: str,
        description: str,
    ) -> bool:
        """
        更新日程

        Args:
            schedule_id: 日程ID
            title: 新标题
            start_time: 新开始时间
            end_time: 新结束时间
            repeat_type: 新重复类型
            repeat_end: 新重复结束日期
            description: 新描述

        Returns:
            是否成功
        """
        affected = self.update(
            "schedule",
            "id",
            schedule_id,
            {
                "name": title,
                "title": title,
                "description": description,
                "start_time": start_time,
                "end_time": end_time,
                "repeat_type": repeat_type,
                "repeat_end": repeat_end,
            },
        )
        return affected > 0

    def delete_schedule(self, schedule_id: int) -> bool:
        """
        删除日程

        Args:
            schedule_id: 日程ID

        Returns:
            是否成功
        """
        affected = self.delete("schedule", "id", schedule_id)
        return affected > 0

    def get_upcoming_reminders(self, minutes: int = 15) -> list:
        """
        获取接下来 minutes 分钟内需要提醒的日程

        Args:
            minutes: 提前分钟数

        Returns:
            日程字典列表
        """
        sql = """
        SELECT id, title, name, description, start_time
        FROM schedule
        WHERE notified = 0
        AND datetime(start_time) BETWEEN datetime('now', 'localtime')
            AND datetime('now', 'localtime', '+' || ? || ' minutes')
        ORDER BY start_time ASC
        """
        return self.execute_sql(sql, [str(minutes)])  # type: ignore[no-any-return]

    def mark_schedule_notified(self, schedule_id: int) -> None:
        """
        标记日程已通知

        Args:
            schedule_id: 日程ID
        """
        self.update("schedule", "id", schedule_id, {"notified": 1})


# 全局单例实例
_db_manager = None


def get_db() -> DBManager:
    """
    获取数据库管理器单例

    Returns:
        DBManager 实例
    """
    global _db_manager
    if _db_manager is None:
        _db_manager = DBManager()
    return _db_manager


def close_db():
    """关闭数据库连接"""
    global _db_manager
    if _db_manager:
        _db_manager.close()
        _db_manager = None


# F9: 辅助函数，供外部模块使用


def get_db_connection():
    """获取数据库连接（便捷函数）"""
    return get_db().get_connection()
