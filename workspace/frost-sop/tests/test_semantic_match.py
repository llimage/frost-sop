"""
FROST-SOP 深度质量验证 - 验证二：语义匹配准确性

AC-2: 验证语义匹配准确性（3个测试用例）
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stores.asset import create_asset_store
from agents.parent import create_parent
from skills.assemble import assemble_agent_skill


# 测试用例
TEST_CASES = [
    {
        "id": 1,
        "requirement": "需要一个开发登录页面的人",
        "expected_categories": ["前端", "开发", "Web", "全栈"],
        "unexpected_categories": ["营销", "财务", "设计"]
    },
    {
        "id": 2,
        "requirement": "需要一个写小红书文案的人",
        "expected_categories": ["内容", "营销", "文案", "社交媒体"],
        "unexpected_categories": ["后端", "测试", "运维"]
    },
    {
        "id": 3,
        "requirement": "需要一个分析公司财务数据的人",
        "expected_categories": ["财务", "数据", "分析", "商业"],
        "unexpected_categories": ["设计", "运维", "测试"]
    }
]


def test_semantic_match():
    """AC-2: 验证语义匹配准确性"""
    print("=" * 60)
    print("验证二：语义匹配准确性 (AC-2)")
    print("=" * 60)
    
    # 加载资产Store
    print("\n📂 加载资产Store...")
    asset_store = create_asset_store(backend='file', path='data/assets.json')
    
    # 创建父辈Agent（用于spawn）
    print("🤖 创建父辈Agent...")
    parent = create_parent("test_parent", asset_store)
    
    # 统计结果
    passed_count = 0
    results = []
    
    # 遍历测试用例
    for test_case in TEST_CASES:
        print(f"\n{'-' * 60}")
        print(f"测试用例 {test_case['id']}: \"{test_case['requirement']}\"")
        print(f"{'-' * 60}")
        
        # 准备context
        context = {
            "_agent_requirement": test_case["requirement"],
            "_asset_store": asset_store,
            "_parent_agent": parent
        }
        
        # 调用assemble_agent
        print(f"  🔄 调用assemble_agent...")
        try:
            result_ctx = assemble_agent_skill.execute(context)
            
            # 获取匹配结果
            assembled_agent = result_ctx.get("_assembled_agent")
            agent_config = result_ctx.get("_agent_config", {})
            reason = result_ctx.get("_reason", "")
            
            # 检查是否匹配成功
            if assembled_agent is None:
                print(f"  ❌ 匹配失败: {reason}")
                results.append({
                    "id": test_case["id"],
                    "passed": False,
                    "reason": f"匹配失败: {reason}"
                })
                continue
            
            # 获取匹配的技能列表
            skills = agent_config.get("skills", [])
            skill_sources = agent_config.get("skill_sources", {})
            
            print(f"  ✅ 匹配成功")
            print(f"  Agent名称: {agent_config.get('name', '未知')}")
            print(f"  匹配的技能数: {len(skills)}")
            print(f"  技能列表: {skills[:5]}...")  # 只显示前5个
            
            # 判断匹配是否相关
            # 策略：检查技能名称或来源是否包含期望的关键词
            matched_keywords = []
            for skill in skills:
                for keyword in test_case["expected_categories"]:
                    if keyword in skill:
                        matched_keywords.append(keyword)
                        break
            
            # 去重
            matched_keywords = list(set(matched_keywords))
            
            # 判断是否通过
            passed = len(matched_keywords) > 0
            
            if passed:
                print(f"  ✅ 匹配相关: 包含关键词 {matched_keywords}")
                passed_count += 1
                results.append({
                    "id": test_case["id"],
                    "passed": True,
                    "matched_keywords": matched_keywords,
                    "skills": skills[:5]
                })
            else:
                print(f"  ❌ 匹配不相关: 未包含任何期望关键词")
                print(f"     期望关键词: {test_case['expected_categories']}")
                results.append({
                    "id": test_case["id"],
                    "passed": False,
                    "reason": "匹配结果不包含期望关键词",
                    "skills": skills[:5]
                })
                
        except Exception as e:
            print(f"  ❌ 执行异常: {type(e).__name__}: {e}")
            results.append({
                "id": test_case["id"],
                "passed": False,
                "reason": f"执行异常: {e}"
            })
    
    # 输出汇总
    print(f"\n{'=' * 60}")
    print(f"AC-2 验证结果汇总")
    print(f"{'=' * 60}")
    print(f"总测试用例: {len(TEST_CASES)}")
    print(f"通过: {passed_count}")
    print(f"失败: {len(TEST_CASES) - passed_count}")
    print(f"通过率: {passed_count / len(TEST_CASES) * 100:.1f}%")
    
    # 判断是否通过
    passed = passed_count >= 2  # 要求：3个用例中至少2个匹配相关
    
    print(f"\n{'✅' if passed else '❌'} AC-2 验证结果: {'通过' if passed else '不通过'}")
    print(f"  要求: 3个用例中至少2个匹配相关")
    print(f"  实际: {passed_count}个用例匹配相关")
    
    return {
        "total": len(TEST_CASES),
        "passed": passed_count,
        "pass_rate": passed_count / len(TEST_CASES) * 100,
        "passed": passed,
        "results": results
    }


if __name__ == "__main__":
    result = test_semantic_match()
    
    print("\n" + "=" * 60)
    print("AC-2 验证完成")
    print("=" * 60)
