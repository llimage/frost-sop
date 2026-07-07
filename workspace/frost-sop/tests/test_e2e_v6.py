"""
V6.0 端到端测试: 狩猎→分析→进化完整闭环
"""

import os
import time

import pytest

os.environ["FROST_TESTING"] = "1"


@pytest.fixture(autouse=True)
def _join_background_threads():
    """每个测试结束后等待后台守护线程退出，防止 Python 3.13 segfault。"""
    yield
    # 给守护线程 0.5 秒优雅退出时间
    time.sleep(0.5)


class TestE2EHuntEvolution:
    """端到端: 狩猎→分析→进化"""

    def test_full_pipeline(self):
        """验证完整5阶段流水线"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [{"skill_id": "e2e_test_skill"}],
            "_hunt_mode": "continuous",
            "_auto_execute": False,
        }
        result = hunt_and_evolve(ctx)

        evo_result = result["_hunt_evolution_result"]

        # 验证所有阶段都执行了
        assert evo_result["status"] == "completed"
        assert evo_result["duration_seconds"] >= 0

        # 验证狩猎结果
        assert "hunt" in evo_result

        # 验证分析结果
        assert "briefing" in evo_result

        # 验证整合结果
        assert "integration" in evo_result
        assert isinstance(evo_result["integration"], list)

        # 验证进化结果
        assert "evolution" in evo_result
        assert "suggestions" in evo_result["evolution"]

        # 验证调度结果
        assert "schedule" in evo_result

    def test_with_multiple_targets(self):
        """验证多目标狩猎"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [
                {"skill_id": "skill_a"},
                {"skill_id": "skill_b"},
                {"skill_id": "skill_c"},
            ],
            "_hunt_mode": "continuous",
            "_auto_execute": False,
        }
        result = hunt_and_evolve(ctx)

        assert result["_hunt_evolution_result"]["status"] == "completed"

    def test_predictive_with_auto_execute(self):
        """验证预测模式+自动执行"""
        from skills.hunt_orchestration import hunt_and_evolve

        ctx = {
            "_hunt_targets": [{"skill_id": "pred_skill"}],
            "_hunt_mode": "predictive",
            "_auto_execute": True,
        }
        result = hunt_and_evolve(ctx)

        assert result["_hunt_evolution_result"]["status"] == "completed"


class TestE2EContentPipeline:
    """端到端: 选题→撰写→标题优化"""

    def test_redbook_pipeline(self):
        """验证小红书完整内容流水线"""
        from skills.content.writer import optimize_title, select_topic, write_redbook_note

        # Step 1: 选题
        ctx = {"_platform": "redbook"}
        ctx = select_topic(ctx)
        assert "_selected_topic" in ctx

        # Step 2: 撰写
        ctx["_topic"] = ctx["_selected_topic"]
        ctx = write_redbook_note(ctx)
        assert "_generated_content" in ctx

        # Step 3: 标题优化
        ctx["_content"] = ctx["_generated_content"]
        ctx["_platform"] = "redbook"
        ctx = optimize_title(ctx)
        assert "_optimized_titles" in ctx

    def test_juejin_pipeline(self):
        """验证掘金完整内容流水线"""
        from skills.content.writer import select_topic, write_tech_article

        # Step 1: 选题
        ctx = {"_platform": "juejin"}
        ctx = select_topic(ctx)
        assert "_selected_topic" in ctx

        # Step 2: 撰写
        ctx["_topic"] = ctx["_selected_topic"]
        ctx = write_tech_article(ctx)
        assert "_generated_content" in ctx
        assert "_article_title" in ctx

    def test_email_pipeline(self):
        """验证邮件完整内容流水线"""
        from skills.content.writer import select_topic, write_newsletter

        # Step 1: 选题
        ctx = {"_platform": "email"}
        ctx = select_topic(ctx)
        assert "_selected_topic" in ctx

        # Step 2: 撰写
        ctx["_topic"] = ctx["_selected_topic"]
        ctx = write_newsletter(ctx)
        assert "_generated_content" in ctx
        assert "_email_subject" in ctx

    def test_publish_mock_pipeline(self):
        """验证发布 mock 流水线（不实际调用外部 API）"""
        from skills.content.writer import write_tech_article
        from skills.publish.juejin import publish_juejin

        # 撰写
        ctx = {"_topic": "测试文章"}
        ctx = write_tech_article(ctx)

        # 发布（mock）
        ctx["_article_title"] = ctx["_article_title"]
        ctx["_article_content"] = ctx["_generated_content"]
        ctx = publish_juejin(ctx)

        assert ctx["_publish_result"]["success"] is True


class TestE2EFinalizeLoop:
    """端到端: finalize_task → 审计 + 分析 + 进化"""

    def test_finalize_task_triggers_all(self):
        """验证 finalize_task 触发所有三个后台线程标志位"""
        import time

        from skills.orchestration import finalize_task

        ctx = {
            "_task_id": f"e2e_test_{int(time.time()) * 1000}",
            "_asset_store": None,
            "_constitution_store": None,
        }
        result = finalize_task(ctx)

        # 验证所有三个标志
        assert result["_elder_audit_triggered"] is True
        assert result["_analytics_triggered"] is True
        assert result["_evolution_triggered"] is True

        # 验证推理痕迹包含三个模块
        assert "长老审计" in result["_reason"]
        assert "军师分析" in result["_reason"]
        assert "自进化" in result["_reason"]

    def test_finalize_task_no_task_id(self):
        """验证无 task_id 时跳过"""
        from skills.orchestration import finalize_task

        ctx = {"_task_id": "unknown"}
        result = finalize_task(ctx)

        assert result["_elder_audit_triggered"] is False
        assert result["_analytics_triggered"] is False
        assert result["_evolution_triggered"] is False


class TestE2EScheduledExecution:
    """端到端: 定时触发→执行"""

    def test_scheduled_sop_job(self):
        """验证定时 SOP 执行"""
        from core.scheduler import _execute_sop_job

        # 不应抛异常
        _execute_sop_job("DEV-001", store=None)

    def test_scheduled_hunt_job(self):
        """验证定时狩猎"""
        from core.scheduler import _execute_hunt_job

        _execute_hunt_job("test_skill", store=None)

    def test_scheduled_snapshot_job(self):
        """验证定时快照"""
        from core.scheduler import _execute_snapshot_job

        _execute_snapshot_job(store=None)

    def test_scheduled_retrospective_job(self):
        """验证定时复盘"""
        from core.scheduler import _execute_retrospective_job

        _execute_retrospective_job(store=None)
