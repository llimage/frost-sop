"""
elder.py 覆盖率补测

目标：将 agents/elder.py 覆盖率从 58.36% 提升到 85%+

重点覆盖未测试：
- check_ancestor_alive (所有分支)
- audit_health (drift/rule_effect 模式)
- _detect_direction_drift
- track_rule_effects (持久化)
- generate_revision_suggestions + _generate_high/medium_failure_suggestion
- apply_revision (新旧接口)
- _generate_report (budget/高任务数分支)
- _compute_statistics (非dict任务)
- _make_elder_event_handler (异常分支)
"""

import os
import sys
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ================================================================
# _scan_store / _compute_statistics / _generate_report / _log_audit_result
# ================================================================


class TestElderSubFunctions:
    """测试 audit_family 的四个子函数"""

    def test_scan_store_no_list_keys(self):
        """asset_store 无 list_keys 属性"""
        from agents.elder import _scan_store

        store = MagicMock(spec=[])  # no list_keys
        result = _scan_store(store)
        assert result["all_keys"] == []
        assert result["tasks"] == []
        assert result["lessons"] == []

    def test_scan_store_with_tasks_and_lessons(self):
        """扫描含 task 和 lesson 的 Store"""
        from agents.elder import _scan_store

        store = MagicMock()
        store.list_keys.return_value = ["task:1", "task:2", "lesson:1", "other:1"]
        store.load.side_effect = lambda k: {
            "task:1": {"status": "completed"},
            "task:2": None,  # None → 跳过
            "lesson:1": {"title": "lesson1"},
            "other:1": {"data": "other"},
        }.get(k)

        result = _scan_store(store)
        assert len(result["tasks"]) == 1
        assert len(result["lessons"]) == 1

    def test_compute_statistics_non_dict_task(self):
        """任务不是 dict → 计入失败"""
        from agents.elder import _compute_statistics

        raw = {
            "tasks": ["not_a_dict", {"status": "completed"}, {"status": "failed"}],
            "lessons": [],
        }
        stats = _compute_statistics(raw)
        assert stats["total_tasks"] == 3
        assert stats["failed_tasks"] >= 1  # at least the non-dict one

    def test_compute_statistics_with_stage_results(self):
        """stage_results 中所有阶段都 completed → 视为成功"""
        from agents.elder import _compute_statistics

        raw = {
            "tasks": [
                {
                    "status": "running",
                    "stage_results": [{"status": "completed"}, {"status": "completed"}],
                },
            ],
            "lessons": [],
        }
        stats = _compute_statistics(raw)
        assert stats["successful_tasks"] == 1

    def test_generate_report_with_budget(self):
        """有 budget 参数"""
        from agents.elder import _generate_report

        report = _generate_report(
            {"total_tasks": 5, "successful_tasks": 3, "failed_tasks": 2, "total_lessons": 1},
            [],
            [],
            budget=5000,
        )
        assert report["statistics"]["monthly_budget"] == 5000

    def test_generate_report_high_task_count(self):
        """任务数 > 20 → 建议增加父辈"""
        from agents.elder import _generate_report

        report = _generate_report(
            {"total_tasks": 25, "successful_tasks": 20, "failed_tasks": 5, "total_lessons": 0},
            [],
            [],
        )
        assert any("增加父辈Agent" in r for r in report["recommendations"])

    def test_generate_report_high_failure_rate(self):
        """失败率 > 30% 且 >= 5 个任务"""
        from agents.elder import _generate_report

        report = _generate_report(
            {"total_tasks": 5, "successful_tasks": 2, "failed_tasks": 3, "total_lessons": 0}, [], []
        )
        assert any("失败率较高" in r for r in report["recommendations"])

    def test_generate_report_low_failure_skips(self):
        """失败率高但总任务数 < 5 → 不建议"""
        from agents.elder import _generate_report

        report = _generate_report(
            {"total_tasks": 3, "successful_tasks": 1, "failed_tasks": 2, "total_lessons": 0}, [], []
        )
        assert len(report["recommendations"]) == 0

    def test_generate_report_with_lessons(self):
        """有错题本 → findings 包含教训"""
        from agents.elder import _generate_report

        report = _generate_report(
            {"total_tasks": 0, "successful_tasks": 0, "failed_tasks": 0, "total_lessons": 5}, [], []
        )
        assert any("错题本" in f for f in report["findings"])

    def test_log_audit_result(self):
        """验证审计日志写入"""
        from agents.elder import _log_audit_result

        context = {}
        report = {"status": "healthy"}
        stats = {"total_tasks": 10, "successful_tasks": 8, "failed_tasks": 2, "total_lessons": 3}

        result = _log_audit_result(context, report, stats)
        assert result["_audit_report"] is report
        assert "10" in result["_reason"]


# ================================================================
# check_ancestor_alive
# ================================================================


class TestCheckAncestorAlive:
    """测试 Dead Man's Watch — 祖辈存活检查"""

    def test_store_none(self):
        """store=None 时返回 WARNING"""
        from agents.elder import check_ancestor_alive

        context = {"_store": None, "_heartbeat_timeout_minutes": 15}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "WARNING"
        assert "无法读取 Store" in report["report"]

    def test_store_load_exception(self):
        """store.load 异常"""
        from agents.elder import check_ancestor_alive

        store = MagicMock()
        store.load.side_effect = Exception("DB error")

        context = {"_store": store}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "WARNING"

    def test_both_none(self):
        """两个活动记录都为 None"""
        from agents.elder import check_ancestor_alive

        store = MagicMock()
        store.load.return_value = None

        context = {"_store": store}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "WARNING"
        assert "故障" in report["report"]

    def test_healthy_within_timeout(self):
        """心跳在超时内 → HEALTHY"""
        from agents.elder import check_ancestor_alive

        now = datetime.now()

        store = MagicMock()
        store.load.side_effect = lambda k: {
            "ancestor:last_heartbeat": now - timedelta(minutes=5),
            "ancestor:last_task_design_time": now - timedelta(minutes=10),
        }.get(k)

        context = {"_store": store, "_heartbeat_timeout_minutes": 15}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "HEALTHY"

    def test_timeout_exceeded(self):
        """心跳超时 → WARNING"""
        from agents.elder import check_ancestor_alive

        now = datetime.now()

        store = MagicMock()
        store.load.side_effect = lambda k: {
            "ancestor:last_heartbeat": now - timedelta(minutes=30),
            "ancestor:last_task_design_time": None,
        }.get(k)

        context = {"_store": store, "_heartbeat_timeout_minutes": 15}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "WARNING"

    def test_uses_asset_store_fallback(self):
        """使用 _asset_store 而非 _store"""
        from agents.elder import check_ancestor_alive

        now = datetime.now()
        store = MagicMock()
        store.load.return_value = now - timedelta(minutes=5)

        context = {"_asset_store": store, "_heartbeat_timeout_minutes": 15}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        assert report["status"] == "HEALTHY"

    def test_non_datetime_heartbeat(self):
        """心跳值不是 datetime → 跳过计算"""
        from agents.elder import check_ancestor_alive

        store = MagicMock()
        store.load.side_effect = lambda k: {
            "ancestor:last_heartbeat": "2024-01-01T00:00:00",  # str, not datetime
            "ancestor:last_task_design_time": None,
        }.get(k)

        context = {"_store": store, "_heartbeat_timeout_minutes": 15}
        result = check_ancestor_alive(context)
        report = result["_dead_mans_watch_report"]
        # Non-datetime value: heartbeat_idle remains None, design_idle = None
        # max_idle = 0, which is NOT > timeout → HEALTHY
        assert report["status"] == "HEALTHY"


# ================================================================
# audit_family 边缘分支
# ================================================================


class TestAuditFamilyEdgeCases:
    """测试 audit_family 的边缘分支"""

    def test_no_asset_store(self):
        """无 asset_store 时返回错误"""
        from agents.elder import audit_family

        context = {}
        result = audit_family(context)
        assert result["_audit_report"]["status"] == "error"

    def test_with_constitution_store(self):
        """有 constitution_store 时加载预算"""
        from agents.elder import audit_family

        asset_store = MagicMock()
        asset_store.list_keys.return_value = []
        asset_store.load.return_value = None

        constitution_store = MagicMock()
        constitution_store.load.return_value = None  # 无 budget

        context = {
            "_asset_store": asset_store,
            "_constitution_store": constitution_store,
        }
        result = audit_family(context)
        assert "_audit_report" in result
        # constitution_store was accessed
        constitution_store.load.assert_called()


# ================================================================
# audit_health
# ================================================================


class TestAuditHealth:
    """测试 audit_health 健康检查"""

    def test_routine_check(self):
        """常规检查（无任务）"""
        from agents.elder import audit_health

        store = MagicMock()
        store.list_keys.return_value = []

        context = {
            "_asset_store": store,
            "_health_check_type": "routine",
        }
        result = audit_health(context)
        report = result["_health_report"]
        assert report["check_type"] == "routine"
        assert report["status"] == "healthy"

    def test_routine_with_low_success_rate(self):
        """常规检查：低成功率 → WARNING"""
        from agents.elder import audit_health

        store = MagicMock()
        tasks = [{"status": "failed"} for _ in range(10)]  # all failed
        store.list_keys.return_value = [f"task:{i}" for i in range(10)]
        store.load.return_value = tasks[0]  # all same

        context = {
            "_asset_store": store,
            "_health_check_type": "routine",
        }
        result = audit_health(context)
        report = result["_health_report"]
        assert report["status"] == "warning"
        assert report["success_rate"] == 0.0

    def test_drift_check_no_data(self):
        """方向漂移检测：数据不足"""
        from agents.elder import audit_health

        store = MagicMock()
        store.list_keys.return_value = ["task:1"]

        context = {
            "_asset_store": store,
            "_health_check_type": "drift",
        }
        result = audit_health(context)
        assert "_drift_detected" in result

    @patch("agents.elder.track_rule_effects")
    def test_rule_effect_check(self, mock_track):
        """规则效果追踪检查"""
        from agents.elder import audit_health

        mock_track.return_value = {
            "_rule_effects": {},
            "_rules_need_revision": [],
        }

        store = MagicMock()
        store.list_keys.return_value = []
        constitution_store = MagicMock()

        context = {
            "_asset_store": store,
            "_constitution_store": constitution_store,
            "_health_check_type": "rule_effect",
        }
        result = audit_health(context)
        report = result["_health_report"]
        assert "rule_effects" in report

    @patch("agents.elder.track_rule_effects")
    def test_full_check(self, mock_track):
        """全量检查（drift + rule_effect）"""
        from agents.elder import audit_health

        mock_track.return_value = {
            "_rule_effects": {},
            "_rules_need_revision": [],
        }

        store = MagicMock()
        store.list_keys.return_value = []
        constitution_store = MagicMock()

        context = {
            "_asset_store": store,
            "_constitution_store": constitution_store,
            "_health_check_type": "full",
        }
        result = audit_health(context)
        report = result["_health_report"]
        assert "drift_detected" in report
        assert "rule_effects" in report

    def test_rule_effect_with_high_failure(self):
        """规则效果检查：高失败率 → WARNING"""
        from agents.elder import audit_health

        store = MagicMock()
        store.list_keys.return_value = []
        constitution_store = MagicMock()

        context = {
            "_asset_store": store,
            "_constitution_store": constitution_store,
            "_health_check_type": "rule_effect",
        }

        with patch("agents.elder.track_rule_effects") as mock_track:
            mock_track.return_value = {
                "_rule_effects": {
                    "rule1": {"trigger_count": 15, "failure_rate": 0.5},
                    "rule2": {"trigger_count": 5, "failure_rate": 0.2},
                },
                "_rules_need_revision": ["rule1"],
            }
            result = audit_health(context)

        report = result["_health_report"]
        assert report["status"] == "warning"


# ================================================================
# _detect_direction_drift
# ================================================================


class TestDetectDirectionDrift:
    """测试方向漂移检测"""

    def test_no_store(self):
        """无 store → False"""
        from agents.elder import _detect_direction_drift

        context = {}
        assert _detect_direction_drift(context) is False

    def test_insufficient_data(self):
        """数据不足（< 3 条简报）"""
        from agents.elder import _detect_direction_drift

        store = MagicMock()
        store.list_keys.return_value = ["briefing:1", "briefing:2"]
        store.load.side_effect = lambda k: {"main_topic": f"topic_{k}"}

        context = {"_asset_store": store}
        assert _detect_direction_drift(context) is False

    def test_no_drift_same_topic(self):
        """主题一致 → 无漂移"""
        from agents.elder import _detect_direction_drift

        store = MagicMock()
        store.list_keys.return_value = ["briefing:1", "briefing:2", "briefing:3"]
        store.load.side_effect = lambda k: {"main_topic": "same_topic"}

        context = {"_asset_store": store}
        assert _detect_direction_drift(context) is False

    def test_drift_detected(self):
        """三个不同主题 → 漂移"""
        from agents.elder import _detect_direction_drift

        store = MagicMock()
        store.list_keys.return_value = ["briefing:1", "briefing:2", "briefing:3"]
        topics = ["A", "B", "C"]
        store.load.side_effect = lambda k: {"main_topic": topics[int(k.split(":")[1]) - 1]}

        context = {"_asset_store": store}
        assert _detect_direction_drift(context) is True

    def test_none_briefing_skipped(self):
        """None 简报跳过"""
        from agents.elder import _detect_direction_drift

        store = MagicMock()
        store.list_keys.return_value = ["briefing:1", "briefing:2", "briefing:3", "briefing:4"]
        call_count = [0]

        def load_side_effect(k):
            call_count[0] += 1
            idx = int(k.split(":")[1])
            if idx == 2:
                return None  # skip
            return {"main_topic": "same"}

        store.load.side_effect = load_side_effect
        context = {"_asset_store": store}
        assert _detect_direction_drift(context) is False


# ================================================================
# track_rule_effects — 持久化分支
# ================================================================


class TestTrackRuleEffects:
    """测试 track_rule_effects"""

    def test_no_stores(self):
        """无 constitution_store 或 asset_store → 空结果"""
        from agents.elder import track_rule_effects

        context = {}
        result = track_rule_effects(context)
        assert result["_rule_effects"] == {}
        assert result["_rules_need_revision"] == []

    def test_basic_effect_tracking(self):
        """基本规则效果追踪"""
        from agents.elder import track_rule_effects

        constitution = MagicMock()
        constitution.load.return_value = [
            {
                "id": "rule1",
                "text": "预算规则",
                "type": "budget",
                "trigger_count": 3,
                "success_count": 2,
                "failure_count": 1,
                "complaint_count": 0,
            },
        ]

        asset = MagicMock()
        asset.list_keys.return_value = ["task:1", "lesson:1"]
        asset.load.side_effect = lambda k: {
            "task:1": {"status": "completed", "triggered_rules": ["rule1"]},
            "lesson:1": {"title": "lesson", "related_rule": "rule1"},
        }.get(k)

        context = {
            "_constitution_store": constitution,
            "_asset_store": asset,
        }
        result = track_rule_effects(context)
        effects = result["_rule_effects"]
        assert "rule1" in effects
        # complaint from lesson
        assert effects["rule1"]["complaint_count"] >= 1

    def test_need_revision(self):
        """规则需要修订（高失败率）"""
        from agents.elder import track_rule_effects

        constitution = MagicMock()
        constitution.load.return_value = [
            {
                "id": "bad_rule",
                "text": "问题规则",
                "type": "compliance",
                "trigger_count": 0,
                "success_count": 0,
                "failure_count": 0,
                "complaint_count": 0,
            },
        ]
        constitution.save.return_value = True

        asset = MagicMock()
        # 创建 10 个失败任务触发 bad_rule → 失败率 = 1.0, trigger_count = 10
        asset.list_keys.return_value = [f"task:{i}" for i in range(10)]
        asset.load.return_value = {"status": "failed", "triggered_rules": ["bad_rule"]}

        context = {
            "_constitution_store": constitution,
            "_asset_store": asset,
        }
        result = track_rule_effects(context)
        effects = result["_rule_effects"]
        assert effects["bad_rule"]["failure_rate"] > 0.3
        assert "bad_rule" in result["_rules_need_revision"]


# ================================================================
# _track_constitution_rule_effects (旧接口兼容)
# ================================================================


class TestTrackConstitutionRuleEffects:
    """测试旧接口 _track_constitution_rule_effects 兼容性"""

    @patch("agents.elder.track_rule_effects")
    def test_old_format_conversion(self, mock_track):
        """旧接口转换为 dict 格式"""
        from agents.elder import _track_constitution_rule_effects

        mock_track.return_value = {
            "_rule_effects": {
                "rule1": {"rule_id": "rule1", "failure_rate": 0.5},
            },
            "_rules_need_revision": ["rule1"],
        }

        context = {"_store": MagicMock()}
        result = _track_constitution_rule_effects(context)
        assert isinstance(result, dict)
        assert "rule1" in result
        assert result["rule1"]["rule_id"] == "rule1"


# ================================================================
# generate_revision_suggestions
# ================================================================


class TestGenerateRevisionSuggestions:
    """测试 generate_revision_suggestions"""

    def test_empty_effects(self):
        """空效果列表"""
        from agents.elder import generate_revision_suggestions

        context = {"_rule_effects": []}
        result = generate_revision_suggestions(context)
        assert result["_revision_suggestions"] == []

    def test_dict_input(self):
        """输入是 dict 而非 list"""
        from agents.elder import generate_revision_suggestions

        store = MagicMock()
        store.load.return_value = {"id": "rule1", "type": "budget", "params": {"alert_ratio": 0.8}}

        context = {
            "_rule_effects": {
                "rule1": {"rule_id": "rule1", "failure_rate": 0.6, "rule_text": "预算规则"},
            },
            "_store": store,
        }
        result = generate_revision_suggestions(context)
        suggestions = result["_revision_suggestions"]
        assert len(suggestions) > 0

    def test_tuple_input(self):
        """输入是 tuple 列表"""
        from agents.elder import generate_revision_suggestions

        store = MagicMock()
        store.load.return_value = {"id": "rule1", "type": "budget", "params": {"alert_ratio": 0.8}}

        context = {
            "_rule_effects": [
                ("rule1", {"rule_id": "rule1", "failure_rate": 0.6, "rule_text": "预算规则"}),
            ],
            "_store": store,
        }
        result = generate_revision_suggestions(context)
        assert len(result["_revision_suggestions"]) > 0

    def test_low_failure_skipped(self):
        """失败率 < 30% → 不生成建议"""
        from agents.elder import generate_revision_suggestions

        effects = [{"rule_id": "rule1", "failure_rate": 0.2, "rule_text": ""}]
        store = MagicMock()
        store.load.return_value = None

        context = {"_rule_effects": effects, "_store": store}
        result = generate_revision_suggestions(context)
        assert result["_revision_suggestions"] == []

    def test_rule_not_found_in_store(self):
        """store 中找不到规则 → 跳过"""
        from agents.elder import generate_revision_suggestions

        effects = [{"rule_id": "missing_rule", "failure_rate": 0.6, "rule_text": ""}]
        store = MagicMock()
        store.load.return_value = None  # 找不到

        context = {"_rule_effects": effects, "_store": store}
        result = generate_revision_suggestions(context)
        assert result["_revision_suggestions"] == []

    def test_rule_found_in_constitution_rules_list(self):
        """从 constitution:rules 列表中找到规则"""
        from agents.elder import generate_revision_suggestions

        store = MagicMock()
        store.load.side_effect = lambda k: {
            "rule:rule1": None,
            "constitution:rules": [{"id": "rule1", "type": "timing", "params": {"timeout": 120}}],
        }.get(k)

        effects = [{"rule_id": "rule1", "failure_rate": 0.6, "rule_text": "超时规则"}]
        context = {"_rule_effects": effects, "_store": store}
        result = generate_revision_suggestions(context)
        assert len(result["_revision_suggestions"]) > 0


# ================================================================
# _generate_high_failure_suggestion
# ================================================================


class TestHighFailureSuggestion:
    """测试 _generate_high_failure_suggestion 所有规则类型"""

    def test_budget_type(self):
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "budget", "params": {"alert_ratio": 0.8}}
        effect = {"rule_id": "r1", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["params_to_update"]["alert_ratio"] == 0.9  # 0.8 + 0.1

    def test_compliance_type(self):
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "compliance", "params": {"required_stages": ["s1", "s2", "s3"]}}
        effect = {"rule_id": "r2", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert len(suggestion["params_to_update"]["required_stages"]) == 2

    def test_compliance_cannot_relax(self):
        """合规规则只有一个阶段 → 返回 None"""
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "compliance", "params": {"required_stages": ["s1"]}}
        effect = {"rule_id": "r2", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is None  # 无法进一步放宽

    def test_permission_type(self):
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "permission", "params": {"max_spawn_generation": 3}}
        effect = {"rule_id": "r3", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["params_to_update"]["max_spawn_generation"] == 4

    def test_timing_type(self):
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "timing", "params": {"timeout": 120}}
        effect = {"rule_id": "r4", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["params_to_update"]["timeout"] == 180  # 120 * 1.5

    def test_unknown_type(self):
        from agents.elder import _generate_high_failure_suggestion

        rule = {"type": "unknown_xyz", "params": {}}
        effect = {"rule_id": "r5", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert "审查" in suggestion["description"]

    def test_rule_is_list(self):
        """rule 是列表（兼容处理）"""
        from agents.elder import _generate_high_failure_suggestion

        rule = [{"type": "budget", "params": {"alert_ratio": 0.8}}]
        effect = {"rule_id": "r6", "failure_rate": 0.6}
        suggestion = _generate_high_failure_suggestion(rule, effect)

        assert suggestion is not None


# ================================================================
# _generate_medium_failure_suggestion
# ================================================================


class TestMediumFailureSuggestion:
    """测试 _generate_medium_failure_suggestion"""

    def test_budget_medium(self):
        from agents.elder import _generate_medium_failure_suggestion

        rule = {"type": "budget", "params": {"alert_ratio": 0.8}}
        effect = {"rule_id": "r1", "failure_rate": 0.4, "rule_text": "预算规则"}
        suggestion = _generate_medium_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["auto_apply"] is True
        assert suggestion["params_to_update"]["alert_ratio"] == pytest.approx(0.85)

    def test_timing_medium(self):
        from agents.elder import _generate_medium_failure_suggestion

        rule = {"type": "timing", "params": {"timeout": 120}}
        effect = {"rule_id": "r2", "failure_rate": 0.4, "rule_text": "超时规则"}
        suggestion = _generate_medium_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["params_to_update"]["timeout"] == 144

    def test_unknown_type_from_text(self):
        """从 rule_text 推断类型"""
        from agents.elder import _generate_medium_failure_suggestion

        rule = {}
        effect = {"rule_id": "r3", "failure_rate": 0.4, "rule_text": "这是一个合规相关规则"}
        suggestion = _generate_medium_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert "优化" in suggestion["description"]

    def test_empty_type_unknown_text(self):
        """无法推断类型 → 通用建议"""
        from agents.elder import _generate_medium_failure_suggestion

        rule = {}
        effect = {"rule_id": "r4", "failure_rate": 0.4, "rule_text": "xxxxx"}
        suggestion = _generate_medium_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert "歧义" in suggestion["description"]

    def test_rule_is_list(self):
        """rule 是列表"""
        from agents.elder import _generate_medium_failure_suggestion

        rule = [{"type": "budget", "params": {"alert_ratio": 0.8}}]
        effect = {"rule_id": "r5", "failure_rate": 0.4, "rule_text": "预算"}
        suggestion = _generate_medium_failure_suggestion(rule, effect)

        assert suggestion is not None
        assert suggestion["auto_apply"] is True


# ================================================================
# apply_revision — 旧接口 + 新接口
# ================================================================


class TestApplyRevision:
    """测试 apply_revision 新旧接口"""

    def test_old_interface_auto_apply(self):
        """旧接口：auto_apply → 自动应用"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = []
        constitution.save.return_value = True

        context = {
            "_store": constitution,
            "_revision_suggestions": [
                {
                    "rule_id": "r1",
                    "description": "测试建议",
                    "risk_level": "low",
                    "auto_apply": True,
                }
            ],
            "_monarch_approved": [],
        }
        result = apply_revision(context)
        assert len(result["_applied_revisions"]) == 1
        assert result["_applied_revisions"][0]["applied_by"] == "auto"

    def test_old_interface_monarch_approved(self):
        """旧接口：君主批准"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "alert_ratio": 0.8}]
        constitution.save.return_value = True

        context = {
            "_store": constitution,
            "_revision_suggestions": [
                {
                    "rule_id": "r1",
                    "description": "测试建议",
                    "risk_level": "medium",
                    "auto_apply": False,
                    "params_to_update": {"alert_ratio": 0.9},
                }
            ],
            "_monarch_approved": ["r1"],
        }
        result = apply_revision(context)
        assert len(result["_applied_revisions"]) == 1
        assert result["_applied_revisions"][0]["applied_by"] == "monarch"

    def test_old_interface_pending(self):
        """旧接口：等待审批"""
        from agents.elder import apply_revision

        constitution = MagicMock()

        context = {
            "_store": constitution,
            "_revision_suggestions": [
                {
                    "rule_id": "r1",
                    "description": "高风险建议",
                    "risk_level": "high",
                    "auto_apply": False,
                }
            ],
            "_monarch_approved": [],
        }
        result = apply_revision(context)
        assert len(result["_pending_approvals"]) == 1
        assert len(result["_applied_revisions"]) == 0

    def test_old_interface_update_rules(self):
        """旧接口：更新宪法规则持久化"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "alert_ratio": 0.8}]
        constitution.save.return_value = True

        context = {
            "_store": constitution,
            "_revision_suggestions": [
                {
                    "rule_id": "r1",
                    "description": "调整预算",
                    "risk_level": "low",
                    "auto_apply": True,
                    "params_to_update": {"alert_ratio": 0.9},
                }
            ],
            "_monarch_approved": [],
        }
        apply_revision(context)
        # constitution.save 被调用
        assert constitution.save.called

    def test_new_interface_no_store(self):
        """新接口：无 constitution_store → 失败"""
        from agents.elder import apply_revision

        context = {
            "_rule_id": "r1",
            "_suggestion": {"params_to_update": {"x": 1}},
            "_approval_level": "auto",
        }
        result = apply_revision(context)
        assert result["_revision_result"]["success"] is False

    def test_new_interface_rule_not_found(self):
        """新接口：规则不存在"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = []

        context = {
            "_store": constitution,
            "_rule_id": "r1",
            "_suggestion": {"params_to_update": {"x": 1}},
            "_approval_level": "auto",
        }
        result = apply_revision(context)
        assert result["_revision_result"]["success"] is False
        assert "不存在" in result["_revision_result"]["reason"]

    def test_new_interface_pending_monarch(self):
        """新接口：需要君主审批"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "type": "budget"}]
        constitution.save.return_value = True

        context = {
            "_store": constitution,
            "_rule_id": "r1",
            "_suggestion": {"params_to_update": {"alert_ratio": 0.9}},
            "_approval_level": "pending",
        }
        result = apply_revision(context)
        assert result["_revision_result"]["success"] is True
        assert result["_revision_result"]["action"] == "pending_monarch"

    def test_new_interface_no_params_to_update(self):
        """新接口：suggestion 缺少 params_to_update"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "alert_ratio": 0.8}]

        context = {
            "_store": constitution,
            "_rule_id": "r1",
            "_suggestion": {},  # 无 params_to_update
            "_approval_level": "auto",
        }
        result = apply_revision(context)
        assert result["_revision_result"]["success"] is False

    def test_new_interface_apply_success(self):
        """新接口：自动修订成功"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "alert_ratio": 0.8}]
        constitution.save.return_value = True

        context = {
            "_store": constitution,
            "_rule_id": "r1",
            "_suggestion": {
                "params_to_update": {"alert_ratio": 0.9},
                "reason": "失败率过高",
            },
            "_approval_level": "auto",
        }
        result = apply_revision(context)
        assert result["_revision_result"]["success"] is True
        assert result["_revision_result"]["action"] == "applied"
        assert "alert_ratio" in result["_revision_result"]["updated_params"]

    def test_old_interface_save_exception(self):
        """旧接口：save 异常时不中断"""
        from agents.elder import apply_revision

        constitution = MagicMock()
        constitution.load.return_value = [{"id": "r1", "alert_ratio": 0.8}]
        constitution.save.side_effect = Exception("DB error")

        context = {
            "_store": constitution,
            "_revision_suggestions": [
                {
                    "rule_id": "r1",
                    "description": "测试",
                    "risk_level": "low",
                    "auto_apply": True,
                    "params_to_update": {"alert_ratio": 0.9},
                }
            ],
            "_monarch_approved": [],
        }
        # 不应抛出异常
        result = apply_revision(context)
        assert len(result["_applied_revisions"]) == 1


# ================================================================
# _make_elder_event_handler / subscribe_elder_to_events
# ================================================================


class TestElderEventHandlers:
    """测试事件处理器"""

    def test_event_handler_exception(self):
        """事件处理器异常时不中断"""
        from agents.elder import _make_elder_event_handler

        # 创建一个会触发异常的 elder_agent
        elder_agent = MagicMock()
        elder_agent.store.list_keys.side_effect = Exception("Store corrupted")

        handler = _make_elder_event_handler(elder_agent)

        # 创建一个 mock 事件
        event = MagicMock()
        event.data = {"task_id": "test_task"}

        # 不应抛出异常（内部被 catch）
        handler(event)

    def test_subscribe_error(self):
        """subscribe_elder_to_events 异常时返回 False"""
        from agents.elder import subscribe_elder_to_events

        elder_agent = MagicMock()

        with patch("core.event_bus.get_event_bus", side_effect=Exception("EventBus not available")):
            result = subscribe_elder_to_events(elder_agent)

        assert result is False


# ================================================================
# create_elder
# ================================================================


class TestCreateElder:
    """测试 create_elder 工厂"""

    def test_create_with_stores(self):
        from agents.elder import create_elder

        asset = MagicMock()
        constitution = MagicMock()
        elder = create_elder(name="test_elder", asset_store=asset, constitution_store=constitution)

        assert elder.name == "test_elder"
        assert "audit_family" in elder.skills
        assert "audit_health" in elder.skills
        assert "track_rule_effects" in elder.skills
        assert "generate_revision_suggestions" in elder.skills
        assert "apply_revision" in elder.skills

    def test_create_default_name(self):
        from agents.elder import create_elder

        elder = create_elder()
        assert elder.name == "elder"
