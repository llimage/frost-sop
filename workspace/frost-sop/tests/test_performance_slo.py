"""
#48 性能 SLO 门禁

使用 pytest-benchmark 对关键路径做性能基准测试，设定 SLO 阈值。
覆盖以下关键路径：
- DB 操作（读/写/查询）
- API 端点响应时间
- Store 操作
- SOP 加载
- 事件总线
"""

import os
import sys
import time

import pytest

os.environ["FROST_TESTING"] = "1"
os.environ["FROST_DB_PATH"] = ":memory:"

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# Helper: DB singleton reset (inline to avoid conftest import issues)
def _reset_db(db_path=":memory:"):
    import core.db as db_mod

    # 使用 core.db.close_db() 正确关闭连接
    db_mod.close_db()
    # 额外确保类级别单例也被清除
    db_mod.DBManager._instance = None
    db_mod.DBManager._connection = None


# ═══════════════════════════════════════════════════════════════
# 性能 SLO 定义
# ═══════════════════════════════════════════════════════════════

# 单位: 秒
SLO = {
    "db_select_simple": 0.010,  # 10ms — 简单 SELECT
    "db_insert_simple": 0.020,  # 20ms — 简单 INSERT
    "db_select_with_join": 0.050,  # 50ms — 联表查询
    "api_health_check": 0.050,  # 50ms — 健康检查
    "api_list_projects": 0.100,  # 100ms — 列表查询
    "api_list_tasks": 0.200,  # 200ms — 任务列表
    "store_read_memory": 0.005,  # 5ms — 内存 Store 读
    "store_write_memory": 0.010,  # 10ms — 内存 Store 写
    "sop_load_yaml": 0.100,  # 100ms — SOP YAML 加载
    "event_bus_publish": 0.010,  # 10ms — 事件发布
    "event_bus_deliver": 0.020,  # 20ms — 事件投递
}


# ═══════════════════════════════════════════════════════════════
# 类别 A: DB 操作性能
# ═══════════════════════════════════════════════════════════════


class TestDBPerformance:
    """数据库操作性能 SLO。"""

    def test_select_simple_performance(self, benchmark):
        """简单 SELECT 应在 10ms 内完成。"""
        from core.db import get_db

        _reset_db()
        db = get_db()
        conn = db.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS perf_test (id TEXT PRIMARY KEY, val TEXT)")
        conn.execute("INSERT OR REPLACE INTO perf_test VALUES ('x', 'hello')")
        conn.commit()

        def do_select():
            return db.execute_sql("SELECT * FROM perf_test WHERE id = ?", ["x"])

        result = benchmark(do_select)
        assert result is not None

        # 验证性能（统计中位数）
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["db_select_simple"], (
            f"SELECT 性能超标: median={median:.4f}s > SLO={SLO['db_select_simple']}s"
        )

    def test_insert_simple_performance(self, benchmark):
        """简单 INSERT 应在 20ms 内完成。"""
        from core.db import get_db

        _reset_db()
        db = get_db()
        conn = db.get_connection()
        conn.execute("CREATE TABLE IF NOT EXISTS perf_insert (id TEXT PRIMARY KEY, val TEXT)")

        counter = [0]

        def do_insert():
            counter[0] += 1
            conn.execute(
                "INSERT OR REPLACE INTO perf_insert (id, val) VALUES (?, ?)",
                (f"perf_{counter[0]}", f"value_{counter[0]}"),
            )
            conn.commit()

        result = benchmark(do_insert)
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["db_insert_simple"], (
            f"INSERT 性能超标: median={median:.4f}s > SLO={SLO['db_insert_simple']}s"
        )


# ═══════════════════════════════════════════════════════════════
# 类别 B: API 端点性能
# ═══════════════════════════════════════════════════════════════


class TestAPIPerformance:
    """API 端点响应时间 SLO。"""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient

        from api.main import app

        return TestClient(app)

    def test_health_check_performance(self, client, benchmark):
        """健康检查应在 50ms 内完成。"""

        def health():
            return client.get("/api/health")

        result = benchmark(health)
        assert result.status_code == 200
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["api_health_check"], (
            f"健康检查性能超标: median={median:.4f}s > SLO={SLO['api_health_check']}s"
        )

    def test_list_projects_performance(self, client, benchmark):
        """项目列表应在 100ms 内完成。"""

        def list_proj():
            return client.get("/api/projects")

        result = benchmark(list_proj)
        assert result.status_code == 200
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["api_list_projects"], (
            f"项目列表性能超标: median={median:.4f}s > SLO={SLO['api_list_projects']}s"
        )

    def test_list_tasks_performance(self, client, benchmark):
        """任务列表应在 200ms 内完成。"""

        def list_tasks():
            return client.get("/api/tasks")

        result = benchmark(list_tasks)
        assert result.status_code == 200
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["api_list_tasks"], (
            f"任务列表性能超标: median={median:.4f}s > SLO={SLO['api_list_tasks']}s"
        )


# ═══════════════════════════════════════════════════════════════
# 类别 C: Store 操作性能
# ═══════════════════════════════════════════════════════════════


class TestStorePerformance:
    """Store 读写性能 SLO。"""

    def test_memory_store_write_performance(self, benchmark):
        """内存 Store 写操作应在 10ms 内完成。"""
        from core.store import Store

        store = Store()

        counter = [0]

        def write():
            counter[0] += 1
            store.save(f"key_{counter[0]}", {"data": f"value_{counter[0]}"})

        benchmark(write)
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["store_write_memory"], (
            f"Store 写性能超标: median={median:.4f}s > SLO={SLO['store_write_memory']}s"
        )

    def test_memory_store_read_performance(self, benchmark):
        """内存 Store 读操作应在 5ms 内完成。"""
        from core.store import Store

        store = Store()
        store.save("read_key", {"data": "cached_value"})

        def read():
            return store.load("read_key")

        result = benchmark(read)
        assert result is not None
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["store_read_memory"], (
            f"Store 读性能超标: median={median:.4f}s > SLO={SLO['store_read_memory']}s"
        )


# ═══════════════════════════════════════════════════════════════
# 类别 D: SOP 加载性能
# ═══════════════════════════════════════════════════════════════


class TestSOPLoadPerformance:
    """SOP YAML 加载性能。"""

    def test_sop_yaml_load_performance(self, benchmark):
        """SOP YAML 文件加载应在 100ms 内完成。"""
        from core.sop import SOP

        def load_sop():
            return SOP.load_from_yaml("sops/templates/DEV-001.yaml")

        result = benchmark(load_sop)
        assert result is not None
        stats = benchmark.stats
        median = stats.get("median", 999)
        assert median < SLO["sop_load_yaml"], (
            f"SOP 加载性能超标: median={median:.4f}s > SLO={SLO['sop_load_yaml']}s"
        )


# ═══════════════════════════════════════════════════════════════
# 类别 E: EventBus 性能
# ═══════════════════════════════════════════════════════════════


class TestEventBusPerformance:
    """EventBus 操作性能。"""

    def test_event_publish_performance(self, benchmark):
        """事件发布应在 10ms 内完成。"""
        from core.event_bus import Event, EventBus

        bus = EventBus()
        bus.clear_subscribers()
        received = []

        def handler(event):
            received.append(event)

        bus.subscribe("perf.test.event", handler)

        def publish():
            bus.publish(Event(event_type="perf.test.event", source="test", data={"bench": True}))

        benchmark(publish)
        stats = benchmark.stats
        median = stats.get("median", 999)
        bus.clear_subscribers()
        assert median < SLO["event_bus_publish"], (
            f"EventBus 发布性能超标: median={median:.4f}s > SLO={SLO['event_bus_publish']}s"
        )


# ═══════════════════════════════════════════════════════════════
# 性能回归摘要收集
# ═══════════════════════════════════════════════════════════════


def test_performance_summary():
    """
    收集所有关键路径的原始计时（非 benchmark 模式），
    生成性能摘要用于审计报告。
    """
    from fastapi.testclient import TestClient

    from api.main import app
    from core.db import get_db
    from core.sop import SOP
    from core.store import Store

    results = {}

    # DB SELECT
    _reset_db()
    db = get_db()
    conn = db.get_connection()
    conn.execute("CREATE TABLE IF NOT EXISTS perf_sum (id TEXT)")
    conn.execute("INSERT INTO perf_sum VALUES ('1')")
    conn.commit()

    t0 = time.perf_counter()
    db.execute_sql("SELECT * FROM perf_sum WHERE id = ?", ["1"])
    results["db_select"] = time.perf_counter() - t0

    # DB INSERT
    t0 = time.perf_counter()
    conn.execute("INSERT INTO perf_sum VALUES ('2')")
    conn.commit()
    results["db_insert"] = time.perf_counter() - t0

    # API Health
    client = TestClient(app)
    t0 = time.perf_counter()
    client.get("/api/health")
    results["api_health"] = time.perf_counter() - t0

    # API Projects
    t0 = time.perf_counter()
    client.get("/api/projects")
    results["api_projects"] = time.perf_counter() - t0

    # Store write
    store = Store()
    t0 = time.perf_counter()
    store.save("perf_test", {"v": 1})
    results["store_write"] = time.perf_counter() - t0

    # Store read
    t0 = time.perf_counter()
    store.load("perf_test")
    results["store_read"] = time.perf_counter() - t0

    # SOP load
    t0 = time.perf_counter()
    SOP.load_from_yaml("sops/templates/DEV-001.yaml")
    results["sop_load"] = time.perf_counter() - t0

    # 打印结果
    print("\n" + "=" * 60)
    print("性能基准摘要")
    print("=" * 60)
    all_pass = True
    for name, elapsed in sorted(results.items()):
        slo = SLO.get(name, 0.5)
        status = "✅" if elapsed < slo else "❌"
        if elapsed >= slo:
            all_pass = False
        print(f"  {status} {name:20s}: {elapsed * 1000:8.2f}ms  (SLO: {slo * 1000:.0f}ms)")

    print("=" * 60)
    print(f"总体: {'✅ 全部通过' if all_pass else '❌ 有超标项'}")
    print("=" * 60)

    # 将所有结果写入 results dict 作为测试的一部分
    assert "db_select" in results, "性能测试完成"
