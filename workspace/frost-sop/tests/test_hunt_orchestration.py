"""
V6.0 测试: 狩猎进化闭环 (hunt_orchestration)
测试 hunt_and_evolve 的 5 阶段流水线
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestHuntAndEvolve:
    """测试主入口 hunt_and_evolve()"""

    def test_basic_call(self):
        """验证基本调用不抛异常"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {"_hunt_mode": "continuous", "_auto_execute": False}
        result = hunt_and_evolve(ctx)

        assert "_hunt_evolution_result" in result
        assert result["_hunt_evolution_result"]["status"] == "completed"

    def test_with_hunt_targets(self):
        """验证指定狩猎目标"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [{"skill_id": "test_skill_1"}],
            "_hunt_mode": "continuous",
            "_auto_execute": False,
        }
        result = hunt_and_evolve(ctx)

        assert result["_hunt_evolution_result"]["status"] == "completed"

    def test_auto_execute_enabled(self):
        """验证自动执行模式"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [{"skill_id": "test_skill_2"}],
            "_hunt_mode": "continuous",
            "_auto_execute": True,
        }
        result = hunt_and_evolve(ctx)

        assert result["_hunt_evolution_result"]["status"] == "completed"
        # 自动执行模式下应尝试调度
        assert "_scheduled_actions" in result

    def test_predictive_mode(self):
        """验证预测性狩猎模式"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [{"skill_id": "test_skill_3"}],
            "_hunt_mode": "predictive",
            "_auto_execute": False,
        }
        result = hunt_and_evolve(ctx)

        assert result["_hunt_evolution_result"]["status"] == "completed"

    def test_result_structure(self):
        """验证结果结构完整性"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {"_hunt_mode": "continuous"}
        result = hunt_and_evolve(ctx)

        evo_result = result["_hunt_evolution_result"]
        assert "hunt" in evo_result
        assert "briefing" in evo_result
        assert "integration" in evo_result
        assert "evolution" in evo_result
        assert "schedule" in evo_result
        assert "duration_seconds" in evo_result
        assert evo_result["duration_seconds"] >= 0

    def test_reason_set(self):
        """验证推理痕迹"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {"_hunt_mode": "continuous"}
        result = hunt_and_evolve(ctx)

        assert "_reason" in result
        assert "狩猎进化闭环完成" in result["_reason"]


class TestHuntPhase:
    """测试狩猎阶段"""

    def test_run_hunt_phase(self):
        from skills.hunt_orchestration import _run_hunt_phase

        ctx = {"_hunt_mode": "continuous"}
        result = _run_hunt_phase(ctx)

        assert "_hunt_sop_result" in result

    def test_run_hunt_phase_with_targets(self):
        from skills.hunt_orchestration import _run_hunt_phase

        ctx = {
            "_hunt_targets": [{"skill_id": "t1"}, {"skill_id": "t2"}],
            "_hunt_mode": "continuous",
        }
        result = _run_hunt_phase(ctx)

        assert "_hunt_sop_result" in result


class TestAnalysisPhase:
    """测试分析阶段"""

    def test_run_analysis_phase(self):
        from skills.hunt_orchestration import _run_analysis_phase

        ctx = {"_hunt_mode": "continuous"}
        # 模拟狩猎后的 context
        ctx["_hunt_sop_result"] = {"absorbed_count": 0, "rejected_count": 0}
        result = _run_analysis_phase(ctx)

        assert "_integrated_briefing" in result

    def test_merge_analytics_results(self):
        from skills.hunt_orchestration import _merge_analytics_results

        context = {}
        ctx = {"_analytics_finance": {"budget": 100}, "_analytics_skill": {}}
        _merge_analytics_results(context, ctx)

        assert "_analytics_finance" in context
        assert context["_analytics_finance"]["budget"] == 100
        assert "_analytics_skill" in context


class TestIntegrationPhase:
    """测试整合阶段"""

    def test_run_integration_phase(self):
        from skills.hunt_orchestration import _run_integration_phase

        ctx = {
            "_hunt_sop_result": {"absorbed_count": 0, "rejected_count": 0},
            "_integrated_briefing": {"correlations": []},
        }
        result = _run_integration_phase(ctx)

        assert "_integration_actions" in result

    def test_with_absorbed_skills(self):
        from skills.hunt_orchestration import _run_integration_phase

        ctx = {
            "_hunt_sop_result": {
                "absorbed_count": 1,
                "absorb_results": [{"action": "absorbed", "new_skill_id": "skill_123"}],
            },
            "_integrated_briefing": {"correlations": []},
        }
        result = _run_integration_phase(ctx)

        assert "_integration_actions" in result


class TestEvolutionPhase:
    """测试进化阶段"""

    def test_run_evolution_phase(self):
        from skills.hunt_orchestration import _run_evolution_phase

        ctx = {"_asset_store": None}
        result = _run_evolution_phase(ctx)

        assert "_evolution_suggestions" in result
        assert "_evolution_actions" in result

    def test_process_sop_optimizations(self):
        from skills.hunt_orchestration import _process_sop_optimizations

        ctx = {
            "_asset_store": None,
        }
        suggestions = [
            {"type": "sop_optimization", "target": "DEV-001"},
            {"type": "other"},
        ]
        actions = []
        _process_sop_optimizations(ctx, suggestions, actions)

        # 应尝试优化第一项
        assert isinstance(actions, list)


class TestExecutionSchedule:
    """测试执行安排阶段"""

    def test_run_execution_schedule_off(self):
        from skills.hunt_orchestration import _run_execution_schedule

        ctx = {"_auto_execute": False}
        result = _run_execution_schedule(ctx)

        assert result["_scheduled_actions"] == ["自动执行关闭"]

    def test_run_execution_schedule_on(self):
        from skills.hunt_orchestration import _run_execution_schedule

        ctx = {
            "_auto_execute": True,
            "_evolution_actions": [],
        }
        result = _run_execution_schedule(ctx)

        assert isinstance(result["_scheduled_actions"], list)


class TestSkillInstance:
    """测试 Skill 实例"""

    def test_skill_instance(self):
        from core.skill import Skill
        from skills.hunt_orchestration import hunt_and_evolve_skill

        assert isinstance(hunt_and_evolve_skill, Skill)
        assert hunt_and_evolve_skill.name == "hunt_and_evolve"

    def test_skill_execute(self):
        from skills.hunt_orchestration import hunt_and_evolve_skill

        ctx = {"_hunt_mode": "continuous"}
        result = hunt_and_evolve_skill.execute(ctx)

        assert "_hunt_evolution_result" in result
