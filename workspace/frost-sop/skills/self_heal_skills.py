"""
SELF-HEAL-001 Skill注册脚本
运行此脚本将3个Skill注册到FROST-SOP系统。
"""

from skills.code_diagnoser import diagnose as code_diagnoser_func
from skills.patch_applier import apply_patch as patch_applier_func
from skills.patch_generator import generate_patch as patch_generator_func
from skills.skill import Skill

# 注册Skill（如果系统支持运行时注册）
# 否则在初始化时手动添加
SELF_HEAL_SKILLS = {
    "code-diagnoser": Skill("code-diagnoser", code_diagnoser_func),
    "patch-generator": Skill("patch-generator", patch_generator_func),
    "patch-applier": Skill("patch-applier", patch_applier_func),
}

if __name__ == "__main__":
    print("SELF-HEAL-001 Skills registered:")
    for name, skill in SELF_HEAL_SKILLS.items():
        print(f"  - {name}: {skill.name}")
