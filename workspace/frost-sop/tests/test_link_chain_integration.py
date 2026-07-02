"""
FROST-SOP 运行链路集成测试

覆盖 A-004/A-005/A-006 闭环：
  _merge_child_store_to_parent → _record_weapon_usage → _scan_failed_calls_for_lessons

以及 LLM 失败日志的写入→扫描往返验证。
"""

import json
import tempfile
from unittest.mock import patch

# ═══════════════════════════════════════════════════════════════
# 测试 1: 失败日志写入 → 扫描往返
# ═══════════════════════════════════════════════════════════════


class TestFailureLogRoundTrip:
    """验证 skills/llm.py 写入的失败日志可被 SkillExtractor 正确扫描。"""

    def test_write_failure_log_creates_valid_json(self, tmp_path):
        """_write_failure_log 写入的 JSON 符合 scan_failed_calls 期望格式。"""
        import skills.llm as llm_mod
        from skills.llm import _write_failure_log

        original_dir = llm_mod._TOOL_CALLS_DIR
        try:
            llm_mod._TOOL_CALLS_DIR = tmp_path
            ctx = {"_agent_id": "agent_test", "_task_id": "task_001"}
            _write_failure_log("call_llm", "API timeout", ctx, duration_ms=65000)

            files = list(tmp_path.glob("*.json"))
            assert len(files) == 1, f"期望 1 个文件, 实际 {len(files)}"

            data = json.loads(files[0].read_text(encoding="utf-8"))
            assert data["success"] is False
            assert data["tool_name"] == "call_llm"
            assert "timeout" in data["error"].lower()
            assert data["call_id"].startswith("llm_")
            assert data["agent_id"] == "agent_test"
            assert data["task_id"] == "task_001"
            assert data["duration_ms"] == 65000
        finally:
            llm_mod._TOOL_CALLS_DIR = original_dir

    def test_scan_failed_calls_sees_written_logs(self, tmp_path):
        """扫描器能正确读取 _write_failure_log 写入的日志。"""
        import skills.llm as llm_mod
        from core.skill_extractor import SkillExtractor
        from skills.llm import _write_failure_log

        original_dir = llm_mod._TOOL_CALLS_DIR
        try:
            llm_mod._TOOL_CALLS_DIR = tmp_path
            # 写入 3 条失败 + 1 条成功
            _write_failure_log("tool_a", "timeout", {"_agent_id": "a1"})
            _write_failure_log("tool_b", "api 401 error", {"_agent_id": "a2"})
            _write_failure_log("tool_c", "validation error", {"_agent_id": "a3"})
            # 手动写一条 success: true（不应被扫到）
            (tmp_path / "success_001.json").write_text(
                json.dumps({"call_id": "s001", "tool_name": "ok", "success": True}),
                encoding="utf-8",
            )

            extractor = SkillExtractor(tool_calls_dir=str(tmp_path))
            failed = extractor.scan_failed_calls()
            assert len(failed) == 3, f"期望 3 条失败, 实际 {len(failed)}"
            tool_names = [c["tool_name"] for c in failed]
            assert "tool_a" in tool_names
            assert "tool_b" in tool_names
            assert "tool_c" in tool_names
        finally:
            llm_mod._TOOL_CALLS_DIR = original_dir

    def test_failure_logs_classified_correctly(self, tmp_path):
        """错误分类器正确归类各类失败。"""
        import skills.llm as llm_mod
        from core.skill_extractor import SkillExtractor
        from skills.llm import _write_failure_log

        original_dir = llm_mod._TOOL_CALLS_DIR
        try:
            llm_mod._TOOL_CALLS_DIR = tmp_path
            _write_failure_log("t_timeout", "Connection timed out")
            _write_failure_log("t_api", "API rate limit exceeded (401)")
            _write_failure_log("t_validation", "Invalid schema: missing field")
            _write_failure_log("t_exec", "Runtime exception: null pointer")

            extractor = SkillExtractor(tool_calls_dir=str(tmp_path))
            failed = extractor.scan_failed_calls()

            categories = {c["tool_name"]: extractor._classify_error(c) for c in failed}
            assert categories.get("t_timeout") == "timeout_error"
            assert categories.get("t_api") == "api_error"
            assert categories.get("t_validation") == "validation_error"
            assert categories.get("t_exec") == "execution_error"
        finally:
            llm_mod._TOOL_CALLS_DIR = original_dir

    def test_lesson_extraction_from_failure(self, tmp_path):
        """从失败日志中提取的教训包含期望字段。"""
        import skills.llm as llm_mod
        from core.skill_extractor import SkillExtractor
        from skills.llm import _write_failure_log

        original_dir = llm_mod._TOOL_CALLS_DIR
        try:
            llm_mod._TOOL_CALLS_DIR = tmp_path
            _write_failure_log(
                "api_gateway",
                "API rate limit exceeded",
                {"_agent_id": "agent_x", "_task_id": "task_42"},
            )

            extractor = SkillExtractor(tool_calls_dir=str(tmp_path))
            failed = extractor.scan_failed_calls()
            assert len(failed) == 1

            lesson = extractor.extract_lesson_from_failure(failed[0])
            assert lesson is not None
            assert lesson["error_type"] == "api_error"
            assert lesson["tool_name"] == "api_gateway"
            assert lesson["agent_id"] == "agent_x"
            assert lesson["task_id"] == "task_42"
            assert "API rate limit" in lesson["summary"]
            assert "建议" in lesson["suggestion"]
        finally:
            llm_mod._TOOL_CALLS_DIR = original_dir


# ═══════════════════════════════════════════════════════════════
# 测试 2: merge_from 集成
# ═══════════════════════════════════════════════════════════════


class TestMergeChildStoreIntegration:
    """验证 _merge_child_store_to_parent 在实际场景中正确工作。"""

    def test_merge_business_keys_only(self):
        """只合并业务键，跳过 _ 开头的内部键。"""
        from core.agent import Agent
        from core.store import Store
        from skills.orchestration import _merge_child_store_to_parent

        child_store = Store()
        child_store.save("output", "result_123")
        child_store.save("status", "completed")
        child_store.save("_internal_debug", "secret")

        child = Agent(name="child_agent", store=child_store)
        parent_store = Store()
        context = {"_store": parent_store}

        _merge_child_store_to_parent(child, context)

        assert parent_store.load("output") == "result_123"
        assert parent_store.load("status") == "completed"
        # 内部键应被跳过
        assert parent_store.load("_internal_debug") is None

    def test_merge_empty_child_skipped(self):
        """子辈无数据时合并不报错。"""
        from core.agent import Agent
        from core.store import Store
        from skills.orchestration import _merge_child_store_to_parent

        child = Agent(name="empty_child", store=Store())
        parent_store = Store()
        context = {"_store": parent_store}

        # 不应抛出异常
        _merge_child_store_to_parent(child, context)
        assert list(parent_store.list_keys()) == []

    def test_merge_without_store_context_skipped(self):
        """context 无 _store 时安全跳过。"""
        from core.agent import Agent
        from core.store import Store
        from skills.orchestration import _merge_child_store_to_parent

        child = Agent(name="child", store=Store())
        context = {}

        _merge_child_store_to_parent(child, context)
        # 不应抛出异常

    def test_merge_none_child_skipped(self):
        """child 为 None 时安全跳过。"""
        from skills.orchestration import _merge_child_store_to_parent

        context = {"_store": None}
        _merge_child_store_to_parent(None, context)
        # 不应抛出异常

    def test_merge_overwrite_existing_key(self):
        """合并时覆盖父辈已有键。"""
        from core.agent import Agent
        from core.store import Store
        from skills.orchestration import _merge_child_store_to_parent

        parent_store = Store()
        parent_store.save("output", "old_value")

        child_store = Store()
        child_store.save("output", "new_value")

        child = Agent(name="child", store=child_store)
        _merge_child_store_to_parent(child, {"_store": parent_store})

        assert parent_store.load("output") == "new_value"


# ═══════════════════════════════════════════════════════════════
# 测试 3: record_usage 集成
# ═══════════════════════════════════════════════════════════════


def _make_weapon(id_str, name, health_score=50.0, success_count=5, failure_count=5, usage_count=10):
    """辅助函数：快速创建 WeaponMetadata（success_rate 由 success_count/failure_count 计算）。"""
    from core.armory import WeaponMetadata, WeaponType

    w = WeaponMetadata(
        id=id_str,
        name=name,
        type=WeaponType.SKILL,
        health_score=health_score,
        success_count=success_count,
        failure_count=failure_count,
        usage_count=usage_count,
    )
    return w


class TestRecordWeaponUsageIntegration:
    """验证 _record_weapon_usage 最终更新武器健康评分。"""

    def test_record_usage_updates_health_score(self):
        """记录成功后健康评分应该变化。"""
        from core.armory import ArmoryRegistry
        from core.store import Store
        from skills.orchestration import _record_weapon_usage

        store = Store()
        armory = ArmoryRegistry(store=store)
        weapon = _make_weapon(
            "skill:test_weapon",
            "test_weapon",
            health_score=50.0,
            success_count=5,
            failure_count=5,
            usage_count=10,
        )
        armory.register(weapon)
        initial_health = weapon.health_score

        with patch("core.armory.get_armory_registry", return_value=armory):
            agent_config = {"skills": ["test_weapon"]}
            _record_weapon_usage(agent_config, {"_store": store}, success=True)

            updated = armory.get("skill:test_weapon")
            assert updated is not None
            assert updated.usage_count == 11
            assert updated.success_rate > 0.5  # 5/10=0.5 → 6/11>0.5
            assert updated.health_score != initial_health

    def test_record_usage_failure_decreases_success_rate(self):
        """失败的使用记录降低成功率。"""
        from core.armory import ArmoryRegistry
        from core.store import Store
        from skills.orchestration import _record_weapon_usage

        store = Store()
        armory = ArmoryRegistry(store=store)
        weapon = _make_weapon(
            "skill:fail_weapon",
            "fail_weapon",
            health_score=80.0,
            success_count=8,
            failure_count=2,
            usage_count=10,
        )
        armory.register(weapon)
        initial_sr = weapon.success_rate  # 8/10 = 0.8

        with patch("core.armory.get_armory_registry", return_value=armory):
            _record_weapon_usage({"skills": ["fail_weapon"]}, {"_store": store}, success=False)

            updated = armory.get("skill:fail_weapon")
            assert updated.usage_count == 11
            assert updated.success_rate < initial_sr  # 8/11 < 8/10

    def test_record_usage_no_skills_present_skipped(self):
        """agent_config 无 skills 时跳过。"""
        from skills.orchestration import _record_weapon_usage

        _record_weapon_usage({}, {}, success=True)
        # 不应抛出异常

    def test_record_usage_persists_to_store(self):
        """更新后武器数据持久化到 Store。"""
        from core.armory import ArmoryRegistry
        from core.store import Store
        from skills.orchestration import _record_weapon_usage

        store = Store()
        armory = ArmoryRegistry(store=store)
        weapon = _make_weapon(
            "skill:persisted",
            "persisted",
            health_score=60.0,
            success_count=6,
            failure_count=4,
            usage_count=10,
        )
        armory.register(weapon)

        with patch("core.armory.get_armory_registry", return_value=armory):
            _record_weapon_usage({"skills": ["persisted"]}, {"_store": store}, success=True)

            # 从 Store 创建新 Armory，验证持久化（__init__ 自动调用 _load_from_store）
            armory2 = ArmoryRegistry(store=store)
            restored = armory2.get("skill:persisted")
            assert restored is not None
            assert restored.usage_count == 11, f"期望 11, 实际 {restored.usage_count}"
            assert restored.success_rate > 0.6


# ═══════════════════════════════════════════════════════════════
# 测试 4: scan_failed_calls_for_lessons 集成
# ═══════════════════════════════════════════════════════════════


class TestScanFailedCallsIntegration:
    """验证 _scan_failed_calls_for_lessons 完整链路。"""

    def test_scan_writes_lessons_to_asset_store(self):
        """扫描到的失败教训写入 asset_store（lesson: 前缀）。"""
        import skills.llm as llm_mod
        from core.skill_extractor import SkillExtractor
        from core.store import Store
        from skills.llm import _write_failure_log
        from skills.orchestration import _scan_failed_calls_for_lessons

        original_dir = llm_mod._TOOL_CALLS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            try:
                llm_mod._TOOL_CALLS_DIR = llm_mod._TOOL_CALLS_DIR.__class__(tmp)
                _write_failure_log(
                    "broken_tool",
                    "timeout after 120s",
                    {"_agent_id": "test_agent", "_task_id": "task_scan"},
                )

                asset_store = Store()
                context = {"_asset_store": asset_store}

                # Patch SkillExtractor 使用临时目录
                mock_extractor = SkillExtractor(tool_calls_dir=str(tmp))
                with patch("core.skill_extractor.SkillExtractor", return_value=mock_extractor):
                    result = _scan_failed_calls_for_lessons(context)

                assert result["_lessons_archived"] >= 1
                assert len(result["_lesson_keys"]) >= 1
                for key in result["_lesson_keys"]:
                    assert key.startswith("lesson:"), f"键名应为 lesson: 开头: {key}"
                lesson_data = asset_store.load(result["_lesson_keys"][0])
                assert lesson_data is not None
                assert "error_type" in lesson_data
                assert lesson_data["tool_name"] == "broken_tool"
            finally:
                llm_mod._TOOL_CALLS_DIR = original_dir

    def test_scan_no_failures_returns_zero(self):
        """无失败日志时返回 0。"""
        from core.skill_extractor import SkillExtractor
        from skills.orchestration import _scan_failed_calls_for_lessons

        with tempfile.TemporaryDirectory() as tmp:
            # 空目录，无任何 JSON 文件
            mock_extractor = SkillExtractor(tool_calls_dir=tmp)
            with patch("core.skill_extractor.SkillExtractor", return_value=mock_extractor):
                context = {}
                result = _scan_failed_calls_for_lessons(context)
                assert result["_lessons_archived"] == 0

    def test_duplicate_errors_increment_counter(self):
        """同一工具重复失败递增 times_encountered。"""
        import skills.llm as llm_mod
        from core.skill_extractor import SkillExtractor
        from core.store import Store
        from skills.llm import _write_failure_log
        from skills.orchestration import _scan_failed_calls_for_lessons

        original_dir = llm_mod._TOOL_CALLS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            try:
                llm_mod._TOOL_CALLS_DIR = llm_mod._TOOL_CALLS_DIR.__class__(tmp)
                for i in range(3):
                    _write_failure_log("repeat_tool", f"timeout attempt {i}")

                asset_store = Store()
                context = {"_asset_store": asset_store}

                mock_extractor = SkillExtractor(tool_calls_dir=str(tmp))
                with patch("core.skill_extractor.SkillExtractor", return_value=mock_extractor):
                    result = _scan_failed_calls_for_lessons(context)

                assert result["_lessons_archived"] >= 1
                found = False
                for key in result["_lesson_keys"]:
                    lesson = asset_store.load(key)
                    if lesson and lesson.get("tool_name") == "repeat_tool":
                        assert lesson.get("times_encountered", 0) >= 1
                        found = True
                        break
                assert found, "未找到 repeat_tool 的 lesson"
            finally:
                llm_mod._TOOL_CALLS_DIR = original_dir


# ═══════════════════════════════════════════════════════════════
# 测试 5: 全链路端到端
# ═══════════════════════════════════════════════════════════════


class TestFullChainEndToEnd:
    """验证 merge → record → scan 完整链路。"""

    def test_full_chain_merge_record_scan(self):
        """模拟一次完整的孙辈执行：合并Store → 记录武器 → 扫描失败。"""
        import skills.llm as llm_mod
        from core.agent import Agent
        from core.armory import ArmoryRegistry, WeaponType
        from core.skill_extractor import SkillExtractor
        from core.store import Store
        from skills.llm import _write_failure_log
        from skills.orchestration import (
            _merge_child_store_to_parent,
            _record_weapon_usage,
            _scan_failed_calls_for_lessons,
        )

        original_dir = llm_mod._TOOL_CALLS_DIR

        with tempfile.TemporaryDirectory() as tmp:
            try:
                llm_mod._TOOL_CALLS_DIR = llm_mod._TOOL_CALLS_DIR.__class__(tmp)

                # ── 准备环境 ──
                parent_store = Store()
                asset_store = Store()

                # 武器库
                armory = ArmoryRegistry(store=parent_store)
                for name in ["skill_a", "skill_b", "skill_c"]:
                    from core.armory import WeaponMetadata

                    w = WeaponMetadata(
                        id=f"skill:{name}",
                        name=name,
                        type=WeaponType.SKILL,
                        health_score=70.0,
                        success_count=7,
                        failure_count=3,
                        usage_count=10,
                    )
                    armory.register(w)

                # 孙辈 Agent
                child_store = Store()
                child_store.save("task:output", "result_12345")
                child_store.save("lesson:learned", "不要超时")
                child_store.save("_debug_trace", "internal")
                child = Agent(name="grandchild_1", store=child_store, generation=3)

                # 失败日志
                _write_failure_log("skill_c", "timeout after 80s", {"_agent_id": "grandchild_1"})

                context = {"_store": parent_store, "_asset_store": asset_store}

                # ── Step 1: merge_from ──
                _merge_child_store_to_parent(child, context)
                assert parent_store.load("task:output") == "result_12345"
                assert parent_store.load("lesson:learned") == "不要超时"
                assert parent_store.load("_debug_trace") is None

                # ── Step 2: record_usage ──
                agent_config = {"skills": ["skill_a", "skill_b", "skill_c"]}
                with patch("core.armory.get_armory_registry", return_value=armory):
                    _record_weapon_usage(agent_config, context, success=True)

                assert armory.get("skill:skill_a").usage_count == 11
                assert armory.get("skill:skill_b").usage_count == 11
                assert armory.get("skill:skill_c").usage_count == 11

                # ── Step 3: scan_failed_calls_for_lessons ──
                mock_extractor = SkillExtractor(tool_calls_dir=str(tmp))
                with patch("core.skill_extractor.SkillExtractor", return_value=mock_extractor):
                    result = _scan_failed_calls_for_lessons(context)
                    assert result["_lessons_archived"] >= 1
            finally:
                llm_mod._TOOL_CALLS_DIR = original_dir
