import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.sop import SOP, SOPValidator


def test_sop_load_from_yaml():
    """Test SOP loading from YAML file."""
    sop = SOP.load_from_yaml("sops/templates/DEV-001.yaml")
    assert sop.sop_id == "DEV-001"
    assert len(sop.stages) == 5
    assert "审查交付" in sop.required_stages
    print("[PASS] test_sop_load_from_yaml")


def test_sop_validate_compliant():
    """Test SOP validation with compliant SOP."""
    sop = SOP.load_from_yaml("sops/templates/DEV-001.yaml")
    validator = SOPValidator()
    rules = {
        "required_stages": ["审查交付"],
        "forbidden_skills": ["direct_db_write"],
    }
    result = validator.validate(sop, rules)
    assert result["valid"] is True
    assert len(result["errors"]) == 0
    print("[PASS] test_sop_validate_compliant")


def test_sop_validate_violation():
    """Test SOP validation with policy violation."""
    sop = SOP.load_from_yaml("sops/templates/DEV-001.yaml")
    validator = SOPValidator()
    rules = {
        "required_stages": ["创始人确认"],
        "forbidden_skills": ["audit_code"],
    }
    result = validator.validate(sop, rules)
    assert result["valid"] is False
    assert len(result["errors"]) >= 1
    print("[PASS] test_sop_validate_violation")


if __name__ == "__main__":
    test_sop_load_from_yaml()
    test_sop_validate_compliant()
    test_sop_validate_violation()
    print("\n[ALL PASS] All SOP tests passed!")
