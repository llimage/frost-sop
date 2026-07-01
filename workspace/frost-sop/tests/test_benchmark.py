"""
FROST-SOP 性能基准测试 (pytest-benchmark)

对核心路径建立性能基准，后续代码变更可检测性能回归。

运行方式:
    # 运行所有基准测试
    pytest tests/test_benchmark.py -m benchmark --benchmark-only -s -q

    # 与历史基准对比
    pytest tests/test_benchmark.py --benchmark-only --benchmark-compare --benchmark-autosave
"""

import pytest
import yaml

# ──────────────────────────────────────────────────────────────
# Store 性能基准
# ──────────────────────────────────────────────────────────────


@pytest.mark.benchmark
class TestStoreBenchmark:
    """Store 读写性能基准。"""

    @pytest.fixture
    def store(self):
        from core.store import Store

        return Store()

    def test_store_save_small(self, benchmark, store):
        """基准：保存小型数据（10键 dict）。"""
        data = {f"key_{i}": f"value_{i}" for i in range(10)}

        def save():
            store.save("bench_save_small", data)

        benchmark(save)

    def test_store_save_medium(self, benchmark, store):
        """基准：保存中型数据（100键 dict）。"""
        data = {f"key_{i}": f"value_{i}_" * 10 for i in range(100)}

        def save():
            store.save("bench_save_medium", data)

        benchmark(save)

    def test_store_load_small(self, benchmark, store):
        """基准：加载小型数据。"""
        data = {f"key_{i}": f"value_{i}" for i in range(10)}
        store.save("bench_load_small", data)

        def load():
            return store.load("bench_load_small")

        result = benchmark(load)
        assert result == data

    def test_store_save_then_load(self, benchmark, store):
        """基准：保存+加载往返（小型数据）。"""
        data = {f"k{i}": i for i in range(50)}

        def roundtrip():
            store.save("bench_rt", data)
            return store.load("bench_rt")

        result = benchmark(roundtrip)
        assert result == data


# ──────────────────────────────────────────────────────────────
# SOP 解析性能基准
# ──────────────────────────────────────────────────────────────


@pytest.mark.benchmark
class TestSOPBenchmark:
    """SOP 解析器性能基准。"""

    @pytest.fixture
    def sop_file(self, tmp_path):
        """创建包含10个阶段的 SOP 文件。"""
        stages = []
        for i in range(10):
            stages.append(
                {
                    "name": f"Phase {i + 1}",
                    "description": f"This is a detailed description for phase {i + 1}.",
                    "inputs": [f"input_{i}_a", f"input_{i}_b"],
                    "outputs": [f"output_{i}_a", f"output_{i}_b"],
                    "skill": f"skill_{i + 1}",
                }
            )

        sop_data = {
            "sop_id": "BENCH-001",
            "name": "Benchmark SOP",
            "description": "SOP for performance benchmarking",
            "version": "1.0",
            "stages": stages,
        }

        sop_path = tmp_path / "BENCH-001.yaml"
        with open(sop_path, "w", encoding="utf-8") as f:
            yaml.dump(sop_data, f)

        return str(sop_path)

    def test_sop_parse_10_phases(self, benchmark, sop_file):
        """基准：解析10阶段 SOP。"""
        from core.sop import SOP

        def parse():
            sop = SOP.load_from_yaml(sop_file)
            return sop.stages

        result = benchmark(parse)
        assert len(result) == 10

    def test_sop_parse_and_validate(self, benchmark, sop_file):
        """基准：解析+验证 SOP。"""
        from core.sop import SOP, SOPValidator

        def parse_and_validate():
            sop = SOP.load_from_yaml(sop_file)
            validator = SOPValidator()
            rules = {"required_stages": [], "forbidden_skills": [], "max_budget": None}
            result = validator.validate(sop, rules)
            assert sop.sop_id == "BENCH-001"
            assert result["valid"] is True
            return sop

        benchmark(parse_and_validate)


# ──────────────────────────────────────────────────────────────
# 加密性能基准
# ──────────────────────────────────────────────────────────────


@pytest.mark.benchmark
class TestEncryptionBenchmark:
    """加密模块性能基准。"""

    def test_encrypt_short_text(self, benchmark):
        """基准：加密短文本（API key 长度）。"""
        from core.secrets import encrypt_api_key

        text = "sk-test-api-key-abcdefghijklmnop"
        result = benchmark(encrypt_api_key, text)
        assert result != text

    def test_encrypt_decrypt_roundtrip(self, benchmark):
        """基准：加密+解密往返。"""
        from core.secrets import decrypt_api_key, encrypt_api_key

        text = "sk-test-api-key-1234567890-abcdef"

        def roundtrip():
            cipher = encrypt_api_key(text)
            return decrypt_api_key(cipher)

        result = benchmark(roundtrip)
        assert result == text

    def test_encrypt_long_text(self, benchmark):
        """基准：加密长文本（500字符）。"""
        from core.secrets import encrypt_api_key

        text = "A" * 500
        result = benchmark(encrypt_api_key, text)
        assert result != text


# ──────────────────────────────────────────────────────────────
# EventBus 性能基准
# ──────────────────────────────────────────────────────────────


@pytest.mark.benchmark
class TestEventBusBenchmark:
    """EventBus 性能基准。"""

    @pytest.fixture(autouse=True)
    def _reset_bus(self):
        from core.event_bus import EventBus

        EventBus.reset()

    def test_publish_no_subscribers(self, benchmark):
        """基准：发布事件（无订阅者）。"""
        from core.event_bus import Event, EventBus

        bus = EventBus()
        event = Event("test.event", source="benchmark")

        def publish():
            bus.publish(event)

        benchmark(publish)

    def test_publish_with_subscribers(self, benchmark):
        """基准：发布事件（10个订阅者）。"""
        from core.event_bus import Event, EventBus

        bus = EventBus()
        call_count = [0]

        def handler(event):
            call_count[0] += 1

        for i in range(10):
            bus.subscribe(f"bench.event.{i}", handler)

        event = Event("bench.event.5", source="benchmark")

        def publish():
            bus.publish(event)

        benchmark(publish)

    def test_publish_100_events(self, benchmark):
        """基准：连续发布100个事件。"""
        from core.event_bus import Event, EventBus

        bus = EventBus()

        counter = [0]

        def handler(event):
            counter[0] += 1

        bus.subscribe("bench.*", handler)

        events = [Event(f"bench.event.{i}", source="benchmark") for i in range(100)]

        def publish_all():
            for e in events:
                bus.publish(e)

        benchmark(publish_all)


# ──────────────────────────────────────────────────────────────
# 导入性能基准
# ──────────────────────────────────────────────────────────────


@pytest.mark.benchmark
class TestImportBenchmark:
    """模块导入性能基准。"""

    def test_import_core_modules(self, benchmark):
        """基准：导入所有核心模块的耗时。"""

        def import_all():
            import importlib

            modules = [
                "core.store",
                "core.sop",
                "core.db",
                "core.secrets",
                "core.event_bus",
                "core.json_safety",
            ]
            for mod in modules:
                importlib.import_module(mod)

        benchmark(import_all)
