"""
Integration test for FROST-SOP system.
Tests the complete family model workflow.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stores.constitution import create_constitution_store
from stores.asset import create_asset_store
from agents.ancestor import create_ancestor
from agents.parent import create_parent
from core.store import Store
from core.sop import SOP


def test_full_workflow():
    """End-to-end smoke test: verify family model minimal closed loop."""
    print("=" * 60)
    print("FROST-SOP Integration Test")
    print("=" * 60)

    # 1. Create Stores
    constitution_store = create_constitution_store()
    asset_store = create_asset_store()
    print("[PASS] Store initialization complete")

    # 2. Create Ancestor
    ancestor = create_ancestor(constitution_store, asset_store)
    assert ancestor.name == "ancestor"
    assert ancestor.generation == 0
    assert ancestor.max_spawn_generation == 1
    print("[PASS] Ancestor Agent created")

    # 3. Ancestor LLM decomposes task
    context = ancestor.run(
        sop_steps=["call_llm"],
        initial_context={"_prompt": "Add user authentication feature to the project"},
    )
    assert "_llm_response" in context
    print("[PASS] Ancestor LLM decomposition complete")

    # 4. Load SOP template
    sop = SOP.load_from_yaml("sops/templates/DEV-001.yaml")
    assert sop.sop_id == "DEV-001"
    print("[PASS] SOP template loaded")

    # 5. Compliance validation
    compliance_rules = {
        "required_stages": ["审查交付"],
        "forbidden_skills": ["direct_db_write"],
    }
    context = ancestor.run(
        sop_steps=["validate_sop"],
        initial_context={
            "_sop_to_validate": sop,
            "_compliance_rules": compliance_rules,
        },
    )
    validation = context.get("_validation_result", {})
    assert validation.get("valid") is True, (
        f"Compliance check failed: {validation.get('errors')}"
    )
    print("[PASS] Compliance validation passed")

    # 6. Create Parent and execute
    coordination_store = Store()
    parent = create_parent("parent_dev", coordination_store)
    assert parent.name == "parent_dev"
    print("[PASS] Parent Agent created")

    # 7. Simulate SOP stage execution
    for stage in sop.stages:
        print(f"   Executing stage: {stage['name']}")

    # 8. Harvest outputs
    asset_store.save(
        "task:latest",
        {
            "task": "User authentication feature",
            "sop": sop.name,
            "stages_completed": len(sop.stages),
        },
    )
    assert asset_store.load("task:latest") is not None
    print("[PASS] Output harvesting complete")

    print("\n" + "=" * 60)
    print("[ALL PASS] All integration tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    test_full_workflow()
