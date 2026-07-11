#!/usr/bin/env python3
"""
FROST-SOP V8.0 武器库注册脚本
注册 CODE-001 / TEST-001 / REVIEW-001 三个治理类 Skill 到武器库
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.armory import WeaponMetadata, WeaponType, WeaponCategory, WeaponState, ArmoryRegistry
from core.store import Store
from core.db import get_db


def main():
    print("=" * 60)
    print("FROST-SOP V8.0 武器库注册 - 治理类 Skill 注册")
    print("=" * 60)

    db = get_db()
    store = Store(db=db)
    registry = ArmoryRegistry(store=store)

    print(f"\n[1/4] 武器库已加载，当前武器数量: {len(registry._weapons)}")

    weapons = [
        WeaponMetadata(
            id="skill:code_validator",
            name="编码规范检查",
            type=WeaponType.SKILL,
            category=WeaponCategory.GOVERNANCE,
            version="1.0",
            applicable_scenarios=["编码规范检查", "代码审查", "提交前验证"],
            description="FROST-SOP V8.0 编码硬性要求自动化检查",
            source="manual",
            is_preset=True,
            state=WeaponState.ACTIVE,
            tags=["v8.0", "编码规范", "硬性要求"],
        ),
        WeaponMetadata(
            id="skill:test_validator",
            name="测试规范检查",
            type=WeaponType.SKILL,
            category=WeaponCategory.GOVERNANCE,
            version="1.0",
            applicable_scenarios=["测试规范检查", "代码审查", "提交前验证"],
            description="FROST-SOP V8.0 测试硬性要求自动化检查",
            source="manual",
            is_preset=True,
            state=WeaponState.ACTIVE,
            tags=["v8.0", "测试规范", "硬性要求"],
        ),
        WeaponMetadata(
            id="skill:review_auditor",
            name="代码审查规范检查",
            type=WeaponType.SKILL,
            category=WeaponCategory.GOVERNANCE,
            version="1.0",
            applicable_scenarios=["代码审查", "发布前验证", "合规审计"],
            description="FROST-SOP V8.0 代码审查硬性要求自动化检查",
            source="manual",
            is_preset=True,
            state=WeaponState.ACTIVE,
            tags=["v8.0", "代码审查", "硬性要求"],
        ),
    ]

    for i, weapon in enumerate(weapons, 2):
        result = registry.register(weapon)
        status = "OK" if result else "EXISTS"
        print(f"[{i}/4] 注册 {weapon.id}: {status}")

    # 验证
    print("\n" + "=" * 60)
    print("注册验证")
    print("=" * 60)

    registry2 = ArmoryRegistry(store=store)
    for wid in ["skill:code_validator", "skill:test_validator", "skill:review_auditor"]:
        w = registry2.get(wid)
        if w:
            print(f"  [OK] {wid} - {w.name} (state={w.state.value})")
        else:
            print(f"  [FAIL] {wid} - NOT FOUND")

    print("\n注册完成")
    return 0


if __name__ == "__main__":
    sys.exit(main())
