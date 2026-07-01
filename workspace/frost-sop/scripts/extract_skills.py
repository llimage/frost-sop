"""
F10 - Skill 提取 CLI 入口
用法：python scripts/extract_skills.py
"""

import os
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.skill_extractor import SkillExtractor


def main():
    extractor = SkillExtractor()
    files = extractor.scan_and_extract_all()
    print(f"✅ 提取了 {len(files)} 个 Skill 草案")
    for f in files:
        print(f"   - {f}")

    # 自动验证
    if files:
        print("\n🔍 开始自动验证...")
        results = extractor.validate_all_drafts()
        for r in results:
            status_emoji = "✅" if r.get("status") == "active" else "❌"
            print(
                f"   {status_emoji} {r.get('skill_name', r.get('skill_id'))}: "
                f"{r.get('success_count')}/{r.get('test_runs')} "
                f"({r.get('success_rate', 0):.0%}) → {r.get('status')}"
            )


if __name__ == "__main__":
    main()
