"""
PHILOSOPHY:
SOP is the constitution text. A structured sequence of stages.
SOPValidator provides governance check before execution.
"""

import yaml


class SOP:
    """
    PHILOSOPHY: The constitution text. A structured sequence of stages.
    """

    def __init__(
        self,
        sop_id: str,
        name: str,
        version: str,
        stages: list,
        required_stages: list | None = None,
        forbidden_skills: list | None = None,
    ):
        """
        Initialize an SOP.

        Args:
            sop_id: The unique identifier of the SOP
            name: The name of the SOP
            version: The version of the SOP
            stages: List of stage dictionaries
            required_stages: List of required stage names
            forbidden_skills: List of forbidden skill names
        """
        self.sop_id = sop_id
        self.name = name
        self.version = version
        self.stages = stages
        self.required_stages = required_stages if required_stages is not None else []
        self.forbidden_skills = forbidden_skills if forbidden_skills is not None else []

    @classmethod
    def load_from_yaml(cls, filepath: str) -> "SOP":
        """
        Load SOP from YAML file.

        Args:
            filepath: Path to the YAML file

        Returns:
            SOP instance
        """
        with open(filepath, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(
            sop_id=data["sop_id"],
            name=data["name"],
            version=data.get("version", "1.0"),
            stages=data.get("stages", []),
            required_stages=data.get("required_stages", []),
            forbidden_skills=data.get("forbidden_skills", []),
        )


class SOPValidator:
    """
    PHILOSOPHY: Governance check. Validates SOP against compliance rules.

    V2.0: 增加结构完整性检查、字段必填检查、阶段唯一性检查
    """

    # 每个 stage 至少需要的字段（或等价字段）
    REQUIRED_STAGE_FIELDS = ["name"]
    # 阶段执行描述字段（至少一个）
    STAGE_INSTRUCTION_FIELDS = ["requirement", "prompt"]
    # 阶段执行能力字段（至少一个）
    STAGE_EXECUTOR_FIELDS = ["skill", "agent", "skills"]
    # 可选但推荐的字段
    RECOMMENDED_STAGE_FIELDS = ["output_type", "output_format", "constraint"]

    def validate(self, sop: SOP, rules: dict) -> dict:
        """
        全面验证 SOP。

        检查项：
        1. 基础字段完整性（sop_id, name, stages）
        2. 每个 stage 的结构完整性（必填字段）
        3. 阶段名称唯一性
        4. required_stages 合规性
        5. forbidden_skills 合规性
        6. 预算限制
        """
        errors = []
        warnings = []

        # 1. 基础字段检查
        if not sop.sop_id:
            errors.append({"rule": "sop_id", "message": "SOP ID 不能为空"})
        if not sop.name:
            errors.append({"rule": "name", "message": "SOP 名称不能为空"})
        if not sop.stages:
            errors.append({"rule": "stages", "message": "SOP 至少需要一个阶段"})

        # 2. 每个 stage 的结构检查
        stage_names = set()
        for i, stage in enumerate(sop.stages):
            stage_name = stage.get("name", f"阶段{i + 1}")

            # 检查必填字段（name 必须存在）
            for field in self.REQUIRED_STAGE_FIELDS:
                if field not in stage or not stage[field]:
                    errors.append(
                        {
                            "rule": "stage_field_required",
                            "message": f"Stage '{stage_name}' 缺少必需字段: {field}",
                            "stage": stage_name,
                            "field": field,
                        }
                    )

            # 检查阶段执行描述（requirement 或 prompt 至少一个）
            has_instruction = any(
                field in stage and stage[field] for field in self.STAGE_INSTRUCTION_FIELDS
            )
            if not has_instruction:
                errors.append(
                    {
                        "rule": "stage_instruction_missing",
                        "message": f"Stage '{stage_name}' 缺少执行描述（requirement 或 prompt）",
                        "stage": stage_name,
                    }
                )

            # 检查阶段执行能力（skill/agent/skills 至少一个）
            has_executor = any(
                field in stage and stage[field] for field in self.STAGE_EXECUTOR_FIELDS
            )
            if not has_executor:
                errors.append(
                    {
                        "rule": "stage_executor_missing",
                        "message": f"Stage '{stage_name}' 缺少执行能力（skill/agent/skills）",
                        "stage": stage_name,
                    }
                )

            # 检查阶段名唯一性
            if stage_name in stage_names:
                errors.append(
                    {
                        "rule": "duplicate_stage_name",
                        "message": f"Stage 名称重复: '{stage_name}'",
                        "stage": stage_name,
                    }
                )
            stage_names.add(stage_name)

            # 检查推荐字段（warning 级别）
            for field in self.RECOMMENDED_STAGE_FIELDS:
                if field not in stage:
                    warnings.append(
                        {
                            "rule": "stage_field_recommended",
                            "message": f"Stage '{stage_name}' 缺少推荐字段: {field}",
                            "stage": stage_name,
                            "field": field,
                        }
                    )

        # 3. required_stages 检查
        required = rules.get("required_stages", [])
        for stage_name in required:
            if not any(s.get("name") == stage_name for s in sop.stages):
                errors.append(
                    {
                        "rule": "required_stages",
                        "message": f"Missing required stage: {stage_name}",
                    }
                )

        # 4. forbidden_skills 检查
        forbidden = rules.get("forbidden_skills", [])
        for skill_name in forbidden:
            for stage in sop.stages:
                stage_skills = stage.get("skills", [])
                if skill_name in stage_skills:
                    errors.append(
                        {
                            "rule": "forbidden_skills",
                            "message": f"Stage '{stage.get('name')}' contains forbidden skill: {skill_name}",
                        }
                    )

        # 5. 预算检查
        max_budget = rules.get("max_budget")
        if max_budget is not None and hasattr(sop, "budget") and sop.budget > max_budget:
            errors.append(
                {
                    "rule": "max_budget",
                    "message": f"Budget exceeded: {sop.budget} > {max_budget}",
                }
            )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "stage_count": len(sop.stages),
            "checked_at": __import__("datetime").datetime.now().isoformat(),
        }

    def validate_yaml(self, yaml_path: str) -> dict:
        """
        直接从 YAML 文件验证 SOP。

        Args:
            yaml_path: YAML 文件路径

        Returns:
            验证结果字典
        """
        try:
            sop = SOP.load_from_yaml(yaml_path)
            return self.validate(sop, {})
        except Exception as e:
            return {
                "valid": False,
                "errors": [{"rule": "yaml_load", "message": str(e)}],
                "warnings": [],
            }
