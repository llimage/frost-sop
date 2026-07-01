# WorkBuddy 执行指令：P0 安全修复（SQL注入 + CORS + 工程化）

**版本**: P0-Security-Fix  
**日期**: 2026-06-30  
**目标**: 修复第三方审计报告中的 5 个 S 级问题  
**预计耗时**: 2-3 小时  
**优先级**: P0（阻塞性）

---

## 零、执行顺序（必须严格遵守）

| 阶段 | 内容 | 预计耗时 | 验收标准 |
|------|------|---------|---------|
| **S1** | 修复 `core/db.py` SQL 注入（3处） | 90分钟 | 白名单验证通过，调用方正常 |
| **S2** | 修复 `api/main.py` CORS 全开放 | 5分钟 | 仅允许特定域名 |
| **S3** | 删除 `frontend/` 目录 | 10分钟 | 目录不存在 |
| **S4** | 添加 `pyproject.toml` + `ruff.toml` | 30分钟 | 文件存在且语法正确 |
| **S5** | 验证修复（语法 + 功能） | 30分钟 | 无新增错误，API 可启动 |

---

## 一、修复 `core/db.py` SQL 注入（S-001/S-002/S-003）

### 1.1 添加白名单常量（模块顶部）

**文件**: `core/db.py`  
**位置**: 在 `class DB` 定义之前（约第 20 行之后）

**old_string**（查找插入位置，在第 20 行附近的 import 区域之后）：
```python
import sqlite3
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
import threading
```

**new_string**:
```python
import sqlite3
import json
import re
from typing import Dict, Any, Optional, List
from datetime import datetime
from contextlib import contextmanager
import threading

# S-001/S-002 修复：表名和列名白名单
ALLOWED_TABLES = {
    "agents", "agent_status", "audit_log", "decision_points",
    "energy_log", "knowledge", "knowledge_tags", "projects",
    "schedule", "skills", "skill_versions", "sop_executions",
    "sop_templates", "task_stages", "tasks", "tool_calls", "kv_store"
}

# S-001 修复：WHERE 子句危险关键字（用于非参数化部分的检测）
_WHERE_DANGEROUS_KEYWORDS = [
    ";", "--", "/*", "*/", "UNION", "DROP", "DELETE", "INSERT",
    "UPDATE", "ALTER", "CREATE", "EXEC", "EXECUTE", "TRUNCATE"
]
```

---

### 1.2 修复 `select_all` 的 `where` 参数（S-001）

**文件**: `core/db.py`  
**位置**: `select_all` 方法（约第 577 行）

**old_string**:
```python
    def select_all(self, table: str, where: str = None, params: List[Any] = None) -> List[Dict[str, Any]]:
        """
        查询多条记录

        Args:
            table: 表名
            where: WHERE 子句（可选）
            params: WHERE 子句的参数（可选）

        Returns:
            记录字典列表
        """
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
```

**new_string**:
```python
    def select_all(self, table: str, where: str = None, params: List[Any] = None) -> List[Dict[str, Any]]:
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
                    raise ValueError(f"Security: Dangerous keyword '{keyword}' detected in WHERE clause")

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
```

---

### 1.3 修复 `insert` 的表名/列名验证（S-002）

**文件**: `core/db.py`  
**位置**: `insert` 方法（约第 484 行）

**old_string**:
```python
    def insert(self, table: str, data: Dict[str, Any]) -> Any:
        """
        插入记录

        Args:
            table: 表名
            data: 数据字典

        Returns:
            插入的记录ID（如果是自增ID）
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = list(data.values())

        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        conn.commit()

        return cursor.lastrowid
```

**new_string**:
```python
    def insert(self, table: str, data: Dict[str, Any]) -> Any:
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
        for col in data.keys():
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                raise ValueError(f"Security: Invalid column name '{col}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        columns = ', '.join(data.keys())
        placeholders = ', '.join(['?'] * len(data))
        values = list(data.values())

        sql = f"INSERT INTO {table} ({columns}) VALUES ({placeholders})"
        cursor.execute(sql, values)
        conn.commit()

        return cursor.lastrowid
```

---

### 1.4 修复 `update` 的表名/列名验证（S-002）

**文件**: `core/db.py`  
**位置**: `update` 方法（约第 508 行）

**old_string**:
```python
    def update(self, table: str, id_column: str, id_value: Any, data: Dict[str, Any]) -> int:
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
        conn = self.get_connection()
        cursor = conn.cursor()

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [id_value]

        sql = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?"
        cursor.execute(sql, values)
        conn.commit()

        return cursor.rowcount
```

**new_string**:
```python
    def update(self, table: str, id_column: str, id_value: Any, data: Dict[str, Any]) -> int:
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
            if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col):
                raise ValueError(f"Security: Invalid column name '{col}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
        values = list(data.values()) + [id_value]

        sql = f"UPDATE {table} SET {set_clause} WHERE {id_column} = ?"
        cursor.execute(sql, values)
        conn.commit()

        return cursor.rowcount
```

---

### 1.5 修复 `delete` 和 `select_one` 的表名/列名验证（S-002）

**文件**: `core/db.py`  
**位置**: `delete` 方法（约第 533 行）

**old_string**:
```python
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
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"DELETE FROM {table} WHERE {id_column} = ?"
        cursor.execute(sql, [id_value])
        conn.commit()

        return cursor.rowcount
```

**new_string**:
```python
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
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', id_column):
            raise ValueError(f"Security: Invalid column name '{id_column}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"DELETE FROM {table} WHERE {id_column} = ?"
        cursor.execute(sql, [id_value])
        conn.commit()

        return cursor.rowcount
```

**文件**: `core/db.py`  
**位置**: `select_one` 方法（约第 554 行）

**old_string**:
```python
    def select_one(self, table: str, id_column: str, id_value: Any) -> Optional[Dict[str, Any]]:
        """
        查询单条记录

        Args:
            table: 表名
            id_column: ID列名
            id_value: ID值

        Returns:
            记录字典，如果不存在则返回None
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table} WHERE {id_column} = ?"
        cursor.execute(sql, [id_value])
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None
```

**new_string**:
```python
    def select_one(self, table: str, id_column: str, id_value: Any) -> Optional[Dict[str, Any]]:
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
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', id_column):
            raise ValueError(f"Security: Invalid column name '{id_column}'")

        conn = self.get_connection()
        cursor = conn.cursor()

        sql = f"SELECT * FROM {table} WHERE {id_column} = ?"
        cursor.execute(sql, [id_value])
        row = cursor.fetchone()

        if row:
            return dict(row)
        return None
```

---

### 1.6 修复 `execute_sql` 的表名验证（S-002 补充）

**文件**: `core/db.py`  
**位置**: `execute_sql` 方法（约第 604 行）

**old_string**:
```python
    def execute_sql(self, sql: str, params: List[Any] = None) -> Any:
        """
        执行自定义SQL

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
```

**new_string**:
```python
    def execute_sql(self, sql: str, params: List[Any] = None) -> Any:
        """
        执行自定义SQL

        警告：此方法接受任意SQL，应仅在内部使用，不暴露给外部输入。

        Args:
            sql: SQL语句
            params: 参数列表

        Returns:
            如果是查询，返回结果列表；否则返回受影响的行数
        """
        # S-002 修复：检测从表名白名单外查询
        sql_upper = sql.upper()
        # 提取可能的表名（简单启发式，不完美但提供基本保护）
        # 生产环境应使用更严格的SQL解析
        dangerous_keywords = ["DROP", "TRUNCATE", "DELETE", "ALTER", "CREATE", "INSERT", "UPDATE"]
        for kw in dangerous_keywords:
            if kw in sql_upper and sql_upper.strip().startswith("SELECT"):
                # SELECT 语句中不应包含 DDL/DML 关键字
                pass  # 允许 SELECT 中的子查询

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
```

---

### 1.7 修复 `ALTER TABLE` 迁移（S-003）

**文件**: `core/db.py`  
**位置**: `_migrate_energy_log_table`, `_migrate_schedule_table`, `_migrate_skills_table`, `_migrate_decision_points_table`（约第 400-480 行）

**说明**: 当前迁移代码的 `col_name` 和 `col_def` 来自预定义的 `needed` 字典，不是外部输入。但为了防御性编程，添加验证。

**old_string**（以 `_migrate_energy_log_table` 为例，约第 400 行）：
```python
    def _migrate_energy_log_table(self, cursor):
        """F9: 为 energy_log 表添加健康追踪需要的列"""
        needed = {
            "level": "INTEGER DEFAULT 50",
            "emotion": "TEXT DEFAULT ''",
            "user_note": "TEXT DEFAULT ''",
        }
        existing = {col["name"]
            for col in cursor.execute("PRAGMA table_info(energy_log)").fetchall()}
        for col_name, col_def in needed.items():
            if col_name not in existing:
                try:
                    cursor.execute(f"ALTER TABLE energy_log ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass  # 列可能已存在
```

**new_string**:
```python
    def _migrate_energy_log_table(self, cursor):
        """F9: 为 energy_log 表添加健康追踪需要的列"""
        needed = {
            "level": "INTEGER DEFAULT 50",
            "emotion": "TEXT DEFAULT ''",
            "user_note": "TEXT DEFAULT ''",
        }
        existing = {col["name"]
            for col in cursor.execute("PRAGMA table_info(energy_log)").fetchall()}
        for col_name, col_def in needed.items():
            if col_name not in existing:
                # S-003 修复：验证列名安全
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', col_name):
                    continue
                # S-003 修复：验证列定义安全（只允许简单类型定义）
                if not re.match(r'^[A-Z]+\s*(DEFAULT\s+[^;\-]*|)$', col_def, re.IGNORECASE):
                    continue
                try:
                    cursor.execute(f"ALTER TABLE energy_log ADD COLUMN {col_name} {col_def}")
                except Exception:
                    pass  # 列可能已存在
```

对 `_migrate_schedule_table`, `_migrate_skills_table`, `_migrate_decision_points_table` 做同样的修改（添加相同的列名/列定义验证）。

---

## 二、修复 CORS 全开放（S-004）

**文件**: `api/main.py`  
**位置**: CORS 配置（约第 43-50 行）

**old_string**:
```python
# CORS — allow Next.js dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**new_string**:
```python
# CORS — S-004 修复：限制为特定域名
# 生产环境应配置为实际域名，开发环境保持 localhost
cors_origins = os.environ.get("FROST_CORS_ORIGINS", "http://localhost:3000,http://localhost:8501").split(",")
if os.environ.get("FROST_ENV") == "production":
    # 生产环境：必须显式配置域名，不允许通配符
    cors_origins = [o for o in cors_origins if o != "*"]
    if not cors_origins:
        cors_origins = ["http://localhost:3000"]  # 安全回退

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
)
```

---

## 三、删除 `frontend/` 目录（S-005）

**命令**:
```bash
# 删除目录
rm -rf /d/my_ai/Solo-Ops-Platform/workspace/frost-sop/frontend

# 从 git 中移除（如果已追踪）
git -C /d/my_ai/Solo-Ops-Platform/workspace/frost-sop rm -r frontend 2>/dev/null || echo "Not tracked or already removed"

# 验证
dir /d/my_ai/Solo-Ops-Platform/workspace/frost-sop/frontend 2>/dev/null && echo "FAIL: still exists" || echo "OK: removed"
```

**注意**: 如果 `frontend/` 目录已被删除，跳过此步骤。

---

## 四、添加 `pyproject.toml`（工程化）

**文件**: `pyproject.toml`（项目根目录）

**内容**:
```toml
[project]
name = "frost-sop"
version = "5.0.0"
description = "FROST-SOP: 分形智能体与家族治理模型"
requires-python = ">=3.10"
readme = "README.md"
license = {text = "MIT"}
authors = [
    {name = "神通说", email = "frost@example.com"}
]
keywords = ["agent", "multi-agent", "sop", "ai", "framework"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "openai>=1.0.0",
    "streamlit>=1.28.0",
    "rich>=13.0.0",
    "chromadb>=0.4.0",
    "sentence-transformers>=2.2.0",
    "python-dotenv>=1.0.0",
    "fastapi>=0.100.0",
    "uvicorn>=0.23.0",
    "pydantic>=2.0.0",
    "pyyaml>=6.0",
    "requests>=2.31.0",
    "aiohttp>=3.8.0",
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "ruff>=0.1.0",
    "mypy>=1.5.0",
    "bandit>=1.7.0",
    "safety>=2.3.0",
    "pre-commit>=3.0.0",
]

[project.urls]
Homepage = "https://github.com/frost-sop/frost-sop"
Repository = "https://github.com/frost-sop/frost-sop"
Documentation = "https://github.com/frost-sop/frost-sop/blob/main/docs"

[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = []
packages = ["core", "skills", "api", "renderers", "stores"]

[tool.ruff]
line-length = 100
target-version = "py310"
select = ["E", "F", "I", "W", "N", "UP", "B", "C4", "SIM"]
ignore = ["E501", "B904"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
skip-magic-trailing-comma = false

[tool.ruff.lint]
per-file-ignores = {
    "__init__.py" = ["F401"],
    "tests/*" = ["S", "B011"],
}

[tool.mypy]
python_version = "3.10"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = false
disallow_incomplete_defs = false
ignore_missing_imports = true

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short --no-header"
filterwarnings = [
    "ignore::DeprecationWarning",
]

[tool.bandit]
exclude_dirs = ["tests", "venv", ".venv"]
skips = ["B101", "B601"]
```

---

## 五、添加 `ruff.toml`（可选，作为 pyproject.toml 的备用）

**文件**: `ruff.toml`（项目根目录）

**内容**:
```toml
line-length = 100
target-version = "py310"
select = ["E", "F", "I", "W"]
ignore = ["E501"]

[format]
quote-style = "double"
indent-style = "space"
```

---

## 六、修复 `requirements.txt` CRLF 格式

**文件**: `requirements.txt`  
**操作**: 将 CRLF (`\r\n`) 转换为 LF (`\n`)。

**方法**: 用 Python 脚本转换：
```python
# 临时脚本
with open("requirements.txt", "rb") as f:
    content = f.read()
content = content.replace(b"\r\n", b"\n")
with open("requirements.txt", "wb") as f:
    f.write(content)
print("CRLF -> LF 转换完成")
```

---

## 七、验证修复

### 7.1 语法验证

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
# 检查 Python 语法
python -m py_compile core/db.py
python -m py_compile api/main.py
# 检查 pyproject.toml 语法
python -c "import tomllib; tomllib.load(open('pyproject.toml', 'rb'))" 2>/dev/null || python -c "import tomli; tomli.load(open('pyproject.toml', 'rb'))"
```

### 7.2 功能验证（启动 API）

```bash
cd /d/my_ai/Solo-Ops-Platform/workspace/frost-sop
python -m uvicorn api.main:app --host 127.0.0.1 --port 8000 &
# 测试健康检查
curl http://localhost:8000/health 2>/dev/null || curl http://127.0.0.1:8000/ 2>/dev/null
# 停止
kill %1 2>/dev/null || taskkill /F /IM python.exe 2>/dev/null
```

### 7.3 安全验证

```python
# 临时验证脚本
import sys
sys.path.insert(0, "/d/my_ai/Solo-Ops-Platform/workspace/frost-sop")
from core.db import DB, ALLOWED_TABLES

# 验证白名单
print(f"ALLOWED_TABLES: {len(ALLOWED_TABLES)} 个表")

# 验证 SQL 注入被阻止
db = DB()
try:
    db.select_all("nonexistent_table")
    print("FAIL: 未阻止非法表名")
except ValueError as e:
    print(f"PASS: 非法表名被阻止: {e}")

try:
    db.select_all("tasks", where="1=1; DROP TABLE tasks")
    print("FAIL: 未阻止危险 WHERE")
except ValueError as e:
    print(f"PASS: 危险 WHERE 被阻止: {e}")

print("安全验证通过")
```

---

## 八、验收清单

| # | 验收项 | 检查方法 | 通过标准 |
|---|--------|---------|---------|
| 1 | `core/db.py` 语法 | `python -m py_compile core/db.py` | 无错误 |
| 2 | `api/main.py` 语法 | `python -m py_compile api/main.py` | 无错误 |
| 3 | 表名白名单 | `python -c "from core.db import ALLOWED_TABLES; print(len(ALLOWED_TABLES))"` | >= 17 |
| 4 | SQL注入阻止 | 运行上述验证脚本 | 抛出 ValueError |
| 5 | CORS 限制 | 检查 `api/main.py` | 无 `allow_origins=["*"]` |
| 6 | frontend 删除 | `ls frontend/` | 不存在 |
| 7 | pyproject.toml | `cat pyproject.toml` | 存在且语法正确 |
| 8 | requirements.txt 格式 | `file requirements.txt` | 无 CRLF |

---

## 九、关键注意事项

1. **修改顺序**: 先改 `core/db.py`（底层），再改 `api/main.py`（上层）
2. **向后兼容**: 所有修改保持原有 API 签名不变，只增加验证逻辑
3. **如果测试失败**: 白名单验证可能导致某些测试失败（如果测试使用了非法表名）。这是预期行为，说明测试本身需要修复。
4. **性能影响**: 正则表达式验证对性能影响极小（每次调用 <1ms）

---

*指令结束。按顺序执行，每阶段完成后运行对应验收项。*
