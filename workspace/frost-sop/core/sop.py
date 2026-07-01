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
    """

    def validate(self, sop: SOP, rules: dict) -> dict:
        """
        Validate SOP against compliance rules.

        Args:
            sop: The SOP to validate
            rules: Dictionary of compliance rules

        Returns:
            Dictionary with 'valid' (bool) and 'errors' (list)
        """
        errors = []

        # Check required stages
        required = rules.get("required_stages", [])
        for stage_name in required:
            if not any(s.get("name") == stage_name for s in sop.stages):
                errors.append(
                    {"rule": "required_stages", "message": f"Missing required stage: {stage_name}"}
                )

        # Check forbidden skills
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

        # Check budget limit
        max_budget = rules.get("max_budget")
        if max_budget is not None and hasattr(sop, "budget") and sop.budget > max_budget:
            errors.append(
                {"rule": "max_budget", "message": f"Budget exceeded: {sop.budget} > {max_budget}"}
            )

        return {"valid": len(errors) == 0, "errors": errors}
