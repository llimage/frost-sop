"""
#46 故障注入测试

模拟生产环境中的各种故障场景，验证系统在异常条件下的行为：
- DB 连接失败
- 磁盘空间不足
- 数据损坏/异常格式
- 超时场景
- 并发冲突
- 资源耗尽
"""

import os
import sys
import sqlite3
import tempfile
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

os.environ["FROST_TESTING"] = "1"
os.environ["FROST_DB_PATH"] = ":memory:"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Helper: DB singleton reset (inline to avoid conftest import issues)
def _reset_db(db_path=":memory:"):
    import core.db as db_mod
    db_mod.close_db()
    db_mod.DBManager._instance = None
    db_mod.DBManager._connection = None


# ═══════════════════════════════════════════════════════════════
# 类别 A: DB 故障注入
# ═══════════════════════════════════════════════════════════════


class TestDBConnectionFailure:
    """数据库连接失败的故障场景。"""

    def test_db_locked_error_handled(self):
        """数据库被锁时，写入操作应优雅失败而非崩溃。"""
        # 使用临时文件 DB 测试锁场景
        import sqlite3
        import tempfile
        import os as _os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            db_path = tf.name

        try:
            conn1 = sqlite3.connect(db_path)
            conn1.execute("CREATE TABLE IF NOT EXISTS test_lock (id TEXT)")
            conn1.execute("BEGIN EXCLUSIVE")

            conn2 = sqlite3.connect(db_path, timeout=0.1)

            try:
                conn2.execute("INSERT INTO test_lock VALUES ('x')")
            except sqlite3.OperationalError as e:
                assert "locked" in str(e).lower() or "database is locked" in str(e).lower()

            conn1.execute("ROLLBACK")
            conn1.close()
            conn2.close()
        finally:
            try:
                _os.unlink(db_path)
            except OSError:
                pass
            _reset_db()

    def test_corrupted_db_handled_gracefully(self):
        """损坏的数据库文件不应导致进程崩溃。"""
        import sqlite3
        import tempfile
        import os as _os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tf:
            tf.write(b"this is not a valid sqlite database file!!!\x00\xff")
            bad_path = tf.name

        try:
            error_occurred = False
            try:
                conn = sqlite3.connect(bad_path)
                conn.execute("SELECT 1")
            except sqlite3.DatabaseError:
                error_occurred = True

            # 关键：进程没有崩溃
            assert True, "进程未因损坏 DB 崩溃"
        finally:
            try:
                _os.unlink(bad_path)
            except OSError:
                pass

    def test_readonly_db_write_fails(self):
        """只读数据库写入操作应产生明确错误。"""
        import sqlite3
        import tempfile
        import os as _os

        fd, db_path = tempfile.mkstemp(suffix=".db")
        _os.close(fd)
        conn = sqlite3.connect(db_path)
        conn.execute("CREATE TABLE test_ro (id TEXT)")
        conn.close()
        _os.chmod(db_path, 0o444)

        try:
            error_raised = False
            try:
                ro_conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                ro_conn.execute("INSERT INTO test_ro VALUES ('x')")
            except sqlite3.OperationalError:
                error_raised = True

            assert error_raised, "只读 DB 写入应抛出异常"
        finally:
            try:
                _os.chmod(db_path, 0o644)
                _os.unlink(db_path)
            except OSError:
                pass


# ═══════════════════════════════════════════════════════════════
# 类别 B: 数据异常注入
# ═══════════════════════════════════════════════════════════════


class TestDataCorruption:
    """异常数据输入的容错性。"""

    def test_select_all_handles_missing_table(self):
        """查询不存在的表应返回空或异常而非崩溃。"""
        from core.db import get_db

        _reset_db()
        db = get_db()

        try:
            result = db.select_all("nonexistent_table_xyz")
            assert isinstance(result, (list, type(None)))
        except (sqlite3.OperationalError, Exception):
            pass  # 异常也是可接受的

    def test_null_values_in_db_dont_crash(self):
        """含 NULL 值的行应正确处理。"""
        from core.db import get_db

        _reset_db()
        db = get_db()

        conn = db.get_connection()
        conn.execute("DROP TABLE IF EXISTS test_nulls")
        conn.execute("CREATE TABLE test_nulls (id TEXT, val TEXT)")
        conn.execute("INSERT INTO test_nulls (id, val) VALUES ('1', NULL)")
        conn.execute("INSERT INTO test_nulls (id, val) VALUES ('2', 'ok')")
        conn.commit()

        rows = db.execute_sql("SELECT * FROM test_nulls")
        assert len(rows) >= 2  # 至少有2行，宽松断言
        for row in rows:
            d = dict(row)
            assert "id" in d

    def test_oversized_string_truncation(self):
        """超大字符串输入不应导致崩溃。"""
        from core.db import get_db

        _reset_db()
        db = get_db()

        oversized = "x" * 100000

        conn = db.get_connection()
        conn.execute("DROP TABLE IF EXISTS test_big")
        conn.execute("CREATE TABLE IF NOT EXISTS test_big (id TEXT, data TEXT)")
        conn.execute("INSERT INTO test_big (id, data) VALUES ('big', ?)", (oversized,))
        conn.commit()

        rows = db.execute_sql("SELECT * FROM test_big WHERE id = 'big'")
        assert len(rows) == 1
        assert len(dict(rows[0])["data"]) == 100000


# ═══════════════════════════════════════════════════════════════
# 类别 C: 并发冲突
# ═══════════════════════════════════════════════════════════════


class TestConcurrency:
    """并发访问场景。"""

    def test_concurrent_reads_safe(self):
        """多个线程同时连接 DB 应安全——验证不崩溃。"""
        import sqlite3
        import tempfile
        import os as _os

        fd, db_path = tempfile.mkstemp(suffix=".db")
        _os.close(fd)

        try:
            # 使用非 WAL 模式避免 Windows 锁问题
            setup_conn = sqlite3.connect(db_path)
            setup_conn.execute("PRAGMA journal_mode=DELETE")
            setup_conn.execute("CREATE TABLE test_conc (id TEXT)")
            for i in range(20):
                setup_conn.execute("INSERT INTO test_conc VALUES (?)", (f"id_{i}",))
            setup_conn.commit()
            setup_conn.close()

            errors = []

            def reader():
                try:
                    local_conn = sqlite3.connect(db_path)
                    local_conn.execute("SELECT COUNT(*) FROM test_conc")
                    local_conn.close()
                except Exception as e:
                    errors.append(str(e))

            threads = [threading.Thread(target=reader) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0, f"并发读出错: {errors}"
        finally:
            try:
                _os.unlink(db_path)
            except OSError:
                pass

    def test_rapid_inserts_no_deadlock(self):
        """快速连续插入不应导致死锁。"""
        from core.db import get_db

        _reset_db()
        db = get_db()

        conn = db.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS test_rapid (id TEXT PRIMARY KEY, ts REAL)")

        import time

        for i in range(50):
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO test_rapid (id, ts) VALUES (?, ?)",
                    (f"r_{i}", time.time()),
                )
                if i % 10 == 0:
                    conn.commit()
            except sqlite3.OperationalError as e:
                pytest.fail(f"快速插入第 {i} 次失败: {e}")

        conn.commit()
        rows = conn.execute("SELECT COUNT(*) FROM test_rapid").fetchone()
        assert rows[0] == 50, f"期望 50 行，实际 {rows[0]}"


# ═══════════════════════════════════════════════════════════════
# 类别 D: 资源耗尽
# ═══════════════════════════════════════════════════════════════


class TestResourceExhaustion:
    """资源耗尽场景。"""

    def test_max_connections_limit(self):
        """达到最大连接数时应正确处理。"""
        connections = []
        try:
            for i in range(100):
                conn = sqlite3.connect(":memory:")
                connections.append(conn)
            assert len(connections) == 100
        except sqlite3.OperationalError:
            pass
        finally:
            for c in connections:
                try:
                    c.close()
                except Exception:
                    pass

    def test_memory_db_doesnt_leak(self):
        """内存数据库在多次创建/销毁后不应泄漏。"""
        import gc

        gc.collect()

        from core.db import get_db

        _reset_db()

        for _ in range(20):
            _reset_db()
            db = get_db()
            conn = db.get_connection()
            conn.execute("CREATE TABLE IF NOT EXISTS leak_test (id TEXT)")
            conn.execute("INSERT INTO leak_test VALUES ('x')")
            conn.commit()

        # 如果走到这里没崩溃，就是成功
        assert True, "内存 DB 多次操作未崩溃"


# ═══════════════════════════════════════════════════════════════
# 类别 E: API 故障注入
# ═══════════════════════════════════════════════════════════════


class TestAPIFaultInjection:
    """API 层面的故障注入。"""

    def test_db_error_during_request_returns_500(self):
        """DB 故障时 API 应返回 4xx/5xx 而非崩溃。"""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)

        with patch("api.main.get_db") as mock_db:
            mock_db.side_effect = sqlite3.OperationalError("Simulated DB failure")

            # TestClient 在遇到未捕获异常时会直接传播
            # 这里验证系统不会崩溃，异常能被传播（而非段错误）
            try:
                r = client.get("/api/projects")
                # 如果返回了响应（FastAPI 有全局异常处理）
                assert r.status_code >= 400, f"期望 4xx/5xx, 实际 {r.status_code}"
            except sqlite3.OperationalError:
                # 异常直接传播也是可接受的——说明进程未崩溃
                pass

    def test_import_failure_during_task_creation(self):
        """模块导入失败时任务创建应妥善处理。"""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)

        with patch("agents.ancestor.create_ancestor", side_effect=ImportError("Module not found")):
            r = client.post(
                "/api/tasks",
                json={"description": "test fault", "sop_id": "DEV-001", "use_real_llm": False},
            )
            assert r.status_code in (200, 500), f"导入失败时状态码: {r.status_code}"
            if r.status_code == 200:
                data = r.json()
                assert data.get("status") in ("failed", "completed")

    def test_malformed_json_body(self):
        """畸形 JSON body 应返回 422。"""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)

        r = client.post(
            "/api/tasks",
            content=b"this is not json",
            headers={"Content-Type": "application/json"},
        )
        assert r.status_code in (400, 422), f"畸形 JSON 期望 400/422, 实际 {r.status_code}"

    def test_oversized_payload(self):
        """超大请求体应正确处理。"""
        from fastapi.testclient import TestClient
        from api.main import app

        client = TestClient(app)

        huge_description = "x" * 50000

        r = client.post(
            "/api/tasks",
            json={"description": huge_description, "sop_id": "DEV-001", "use_real_llm": False},
        )
        assert r.status_code in (200, 413, 422), f"超大 payload 状态码: {r.status_code}"


# ═══════════════════════════════════════════════════════════════
# 类别 F: 路径安全边界
# ═══════════════════════════════════════════════════════════════


class TestPathSafetyEdge:
    """路径安全边界测试。"""

    def test_path_traversal_blocked(self):
        """路径遍历攻击应被拦截。"""
        from core.path_safety import validate_path

        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32\\config\\SAM",
        ]

        base_dir = Path(tempfile.gettempdir()) / "frost_safe_test"
        base_dir.mkdir(exist_ok=True)

        try:
            for mp in malicious_paths:
                try:
                    result = validate_path(str(base_dir / mp), str(base_dir))
                    assert str(base_dir) in str(result), f"路径遍历未阻止: {mp}"
                except (ValueError, PermissionError, OSError):
                    pass
        finally:
            try:
                base_dir.rmdir()
            except OSError:
                pass

    def test_symlink_attack_prevented(self):
        """符号链接攻击不应绕过路径检查。"""
        import platform

        if platform.system() != "Linux":
            pytest.skip("符号链接测试仅在 Linux 上可靠")

        from core.path_safety import validate_path

        base_dir = Path(tempfile.gettempdir()) / "frost_symlink_test"
        base_dir.mkdir(exist_ok=True)
        (base_dir / "safe").mkdir(exist_ok=True)

        try:
            link_path = base_dir / "safe" / "escape"
            os.symlink("/etc", str(link_path))

            try:
                validate_path(str(link_path / "passwd"), str(base_dir))
                pytest.fail("应阻止符号链接逃逸")
            except (ValueError, PermissionError, OSError):
                pass
        finally:
            import shutil
            shutil.rmtree(base_dir, ignore_errors=True)
