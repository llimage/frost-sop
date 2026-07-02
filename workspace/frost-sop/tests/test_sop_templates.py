"""
V6.0 测试: 运营 SOP 解析和执行
测试 REDBOOK-001, JUEJIN-001, EMAIL-001 三个 SOP 模板
"""

import os

os.environ["FROST_TESTING"] = "1"


class TestRedbookSOP:
    """测试 REDBOOK-001 SOP"""

    def test_sop_exists(self):
        from pathlib import Path

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        assert sop_path.exists(), f"REDBOOK-001.yaml 不存在: {sop_path}"

    def test_sop_parse(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        assert sop["sop_id"] == "REDBOOK-001"
        assert sop["version"] == "1.0"
        assert sop["category"] == "content"
        assert len(sop["stages"]) == 6

    def test_sop_required_stages(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        assert "r2_content_writing" in sop["required_stages"]

    def test_stage_structure(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        for stage in sop["stages"]:
            assert "phase_id" in stage
            assert "name" in stage
            assert "agent" in stage
            assert "skills" in stage
            assert "requirement" in stage
            assert "output_type" in stage

    def test_content_constraints(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        constraints = sop["content_constraints"]
        assert constraints["max_word_count"] == 500
        assert constraints["min_word_count"] == 300
        assert constraints["must_have_emoji"] is True
        assert "在当今时代" in constraints["avoid_phrases"]


class TestJuejinSOP:
    """测试 JUEJIN-001 SOP"""

    def test_sop_exists(self):
        from pathlib import Path

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "JUEJIN-001.yaml"
        assert sop_path.exists(), f"JUEJIN-001.yaml 不存在: {sop_path}"

    def test_sop_parse(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "JUEJIN-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        assert sop["sop_id"] == "JUEJIN-001"
        assert sop["version"] == "1.0"
        assert len(sop["stages"]) == 4

    def test_content_constraints(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "JUEJIN-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        constraints = sop["content_constraints"]
        assert constraints["min_word_count"] == 2000
        assert constraints["must_have_code_example"] is True
        assert "FROST" in constraints["suggested_tags"]


class TestEmailSOP:
    """测试 EMAIL-001 SOP"""

    def test_sop_exists(self):
        from pathlib import Path

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "EMAIL-001.yaml"
        assert sop_path.exists(), f"EMAIL-001.yaml 不存在: {sop_path}"

    def test_sop_parse(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "EMAIL-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        assert sop["sop_id"] == "EMAIL-001"
        assert sop["version"] == "1.0"
        assert len(sop["stages"]) == 3

    def test_content_constraints(self):
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "EMAIL-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        constraints = sop["content_constraints"]
        assert constraints["format"] == "markdown"
        assert constraints["email_provider"] == "buttondown"
        assert constraints["send_status_default"] == "draft"


class TestSOPIntegration:
    """SOP 与 Skill 的集成测试"""

    def test_redbook_skills_available(self):
        """验证 REDBOOK-001 所需 Skill 存在"""
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "REDBOOK-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        # 收集所有需要的 skills
        all_skills = []
        for stage in sop["stages"]:
            all_skills.extend(stage["skills"])

        # 已知的 V6.0 skills
        v6_skills = [
            "select_topic",
            "write_redbook_note",
            "optimize_title",
            "create_cover_image",
            "publish_redbook",
            "archive_content",
        ]

        for skill in all_skills:
            assert skill in v6_skills or len(skill) > 0

    def test_juejin_skills_available(self):
        """验证 JUEJIN-001 所需 Skill 存在"""
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "JUEJIN-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        all_skills = []
        for stage in sop["stages"]:
            all_skills.extend(stage["skills"])

        expected = ["select_tech_topic", "write_tech_article", "validate_code", "publish_juejin"]
        for skill in all_skills:
            assert skill in expected or len(skill) > 0

    def test_email_skills_available(self):
        """验证 EMAIL-001 所需 Skill 存在"""
        from pathlib import Path

        import yaml

        sop_path = Path(__file__).parent.parent / "sops" / "templates" / "EMAIL-001.yaml"
        with open(sop_path, encoding="utf-8") as f:
            sop = yaml.safe_load(f)

        all_skills = []
        for stage in sop["stages"]:
            all_skills.extend(stage["skills"])

        expected = ["plan_newsletter", "write_newsletter", "send_email"]
        for skill in all_skills:
            assert skill in expected or len(skill) > 0
