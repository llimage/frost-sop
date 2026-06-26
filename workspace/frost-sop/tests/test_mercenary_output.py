"""
FROST-SOP 深度质量验证 - 验证三：雇佣兵产出质量

AC-3: 验证3个预置雇佣兵的确定性函数输出
"""
import sys
import os
import re
from typing import Dict, List, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.mercenary import mercenary_md2html, mercenary_keywords, mercenary_date


# ============ 测试用例定义 ============

MD_TEST_CASES = [
    {
        "name": "标题转换（一级）",
        "input": "# 标题",
        "expected_patterns": [r"<h1>标题</h1>"],
        "unexpected_patterns": []
    },
    {
        "name": "标题转换（二级）",
        "input": "## 二级标题",
        "expected_patterns": [r"<h2>二级标题</h2>"],
        "unexpected_patterns": []
    },
    {
        "name": "粗体转换",
        "input": "这是**粗体**文本",
        "expected_patterns": [r"<strong>粗体</strong>"],
        "unexpected_patterns": []
    },
    {
        "name": "斜体转换",
        "input": "这是*斜体*文本",
        "expected_patterns": [r"<em>斜体</em>"],
        "unexpected_patterns": []
    },
    {
        "name": "混合格式",
        "input": "# 标题\n\n这是**粗体**和*斜体*",
        "expected_patterns": [r"<h1>标题</h1>", r"<strong>粗体</strong>", r"<em>斜体</em>"],
        "unexpected_patterns": []
    },
    {
        "name": "空字符串",
        "input": "",
        "expected_patterns": [],  # 空输入应该返回空或基本标签，不崩溃
        "unexpected_patterns": []
    }
]

KEYWORD_TEST_CASES = [
    {
        "name": "技术文本关键词提取",
        "input": "FROST是一个分形智能体框架，支持家族治理和动态组装",
        "min_keywords": 3,  # 至少提取3个关键词
        "expected_keywords": ["FROST", "分形", "智能体", "框架"],
        "unexpected_keywords": []
    },
    {
        "name": "简单文本关键词提取",
        "input": "今天天气很好",
        "min_keywords": 1,  # 至少提取1个关键词
        "expected_keywords": ["今天", "天气", "很好"],
        "unexpected_keywords": []
    },
    {
        "name": "空字符串",
        "input": "",
        "min_keywords": 0,  # 空输入应该返回空列表
        "expected_keywords": [],
        "unexpected_keywords": []
    }
]

DATE_TEST_CASES = [
    {
        "name": "ISO格式日期（常规）",
        "input": "2026-06-21T10:00:00",
        "expected_pattern": r"2026年06月21日.*10:00",
        "unexpected_patterns": []
    },
    {
        "name": "ISO格式日期（边界）",
        "input": "2026-01-01T00:00:00",
        "expected_pattern": r"2026年01月01日.*00:00",
        "unexpected_patterns": []
    },
    {
        "name": "空字符串（应使用当前日期）",
        "input": "",
        "expected_pattern": r"\d{4}年\d{2}月\d{2}日",  # 匹配任何日期格式
        "unexpected_patterns": []
    }
]


# ============ 测试函数 ============

def test_markdown_to_html():
    """测试Markdown→HTML雇佣兵"""
    print("\n" + "=" * 60)
    print("3.1 Markdown→HTML 雇佣兵测试")
    print("=" * 60)
    
    passed_count = 0
    failed_cases = []
    
    for idx, test_case in enumerate(MD_TEST_CASES):
        print(f"\n  测试用例 {idx + 1}: {test_case['name']}")
        print(f"    输入: {repr(test_case['input'])}")
        
        # 准备context
        context = {"_content": test_case["input"]}
        
        # 调用雇佣兵
        try:
            result_ctx = mercenary_md2html.run(["md2html"], context)
            output = result_ctx.get("_result", "")
            
            print(f"    输出: {repr(output[:100])}...")  # 只显示前100个字符
            
            # 验证输出
            passed = True
            failure_reasons = []
            
            # 检查期望的模式
            for pattern in test_case["expected_patterns"]:
                if not re.search(pattern, output):
                    passed = False
                    failure_reasons.append(f"未匹配到期望模式: {pattern}")
            
            # 检查不期望的模式
            for pattern in test_case["unexpected_patterns"]:
                if re.search(pattern, output):
                    passed = False
                    failure_reasons.append(f"匹配到不期望模式: {pattern}")
            
            # 判断结果
            if passed:
                print(f"    ✅ 通过")
                passed_count += 1
            else:
                print(f"    ❌ 失败: {', '.join(failure_reasons)}")
                failed_cases.append({
                    "name": test_case["name"],
                    "input": test_case["input"],
                    "output": output,
                    "reasons": failure_reasons
                })
                
        except Exception as e:
            print(f"    ❌ 执行异常: {type(e).__name__}: {e}")
            failed_cases.append({
                "name": test_case["name"],
                "input": test_case["input"],
                "output": None,
                "reasons": [f"执行异常: {e}"]
            })
    
    # 输出汇总
    print(f"\n  📊 测试结果: {passed_count}/{len(MD_TEST_CASES)} 通过")
    
    return {
        "total": len(MD_TEST_CASES),
        "passed": passed_count,
        "failed": len(MD_TEST_CASES) - passed_count,
        "pass_rate": passed_count / len(MD_TEST_CASES) * 100 if len(MD_TEST_CASES) > 0 else 0.0,
        "failed_cases": failed_cases
    }


def test_keyword_extraction():
    """测试关键词提取雇佣兵"""
    print("\n" + "=" * 60)
    print("3.2 关键词提取 雇佣兵测试")
    print("=" * 60)
    
    passed_count = 0
    failed_cases = []
    
    for idx, test_case in enumerate(KEYWORD_TEST_CASES):
        print(f"\n  测试用例 {idx + 1}: {test_case['name']}")
        print(f"    输入: {repr(test_case['input'])}")
        
        # 准备context
        context = {"_content": test_case["input"]}
        
        # 调用雇佣兵
        try:
            result_ctx = mercenary_keywords.run(["extract_keywords"], context)
            output = result_ctx.get("_result", [])
            
            print(f"    输出: {output}")
            
            # 验证输出
            passed = True
            failure_reasons = []
            
            # 检查输出类型
            if not isinstance(output, list):
                passed = False
                failure_reasons.append(f"输出类型错误: 期望list, 实际{type(output).__name__}")
            else:
                # 检查关键词数量
                if len(output) < test_case["min_keywords"]:
                    passed = False
                    failure_reasons.append(f"关键词数量不足: 期望至少{test_case['min_keywords']}个, 实际{len(output)}个")
                
                # 检查期望的关键词（部分匹配即可）
                if test_case["expected_keywords"]:
                    matched = False
                    for expected in test_case["expected_keywords"]:
                        for actual in output:
                            if expected in actual or actual in expected:
                                matched = True
                                break
                        if matched:
                            break
                    
                    if not matched and test_case["min_keywords"] > 0:
                        # 如果没有匹配到任何期望关键词，且要求至少提取一些关键词，则失败
                        passed = False
                        failure_reasons.append(f"未匹配到任何期望关键词: {test_case['expected_keywords']}")
            
            # 判断结果
            if passed:
                print(f"    ✅ 通过")
                passed_count += 1
            else:
                print(f"    ❌ 失败: {', '.join(failure_reasons)}")
                failed_cases.append({
                    "name": test_case["name"],
                    "input": test_case["input"],
                    "output": output,
                    "reasons": failure_reasons
                })
                
        except Exception as e:
            print(f"    ❌ 执行异常: {type(e).__name__}: {e}")
            failed_cases.append({
                "name": test_case["name"],
                "input": test_case["input"],
                "output": None,
                "reasons": [f"执行异常: {e}"]
            })
    
    # 输出汇总
    print(f"\n  📊 测试结果: {passed_count}/{len(KEYWORD_TEST_CASES)} 通过")
    
    return {
        "total": len(KEYWORD_TEST_CASES),
        "passed": passed_count,
        "failed": len(KEYWORD_TEST_CASES) - passed_count,
        "pass_rate": passed_count / len(KEYWORD_TEST_CASES) * 100 if len(KEYWORD_TEST_CASES) > 0 else 0.0,
        "failed_cases": failed_cases
    }


def test_date_formatting():
    """测试日期格式化雇佣兵"""
    print("\n" + "=" * 60)
    print("3.3 日期格式化 雇佣兵测试")
    print("=" * 60)
    
    passed_count = 0
    failed_cases = []
    
    for idx, test_case in enumerate(DATE_TEST_CASES):
        print(f"\n  测试用例 {idx + 1}: {test_case['name']}")
        print(f"    输入: {repr(test_case['input'])}")
        
        # 准备context
        context = {"_content": test_case["input"]}
        
        # 调用雇佣兵
        try:
            result_ctx = mercenary_date.run(["format_date"], context)
            output = result_ctx.get("_result", "")
            
            print(f"    输出: {repr(output)}")
            
            # 验证输出
            passed = True
            failure_reasons = []
            
            # 检查输出类型
            if not isinstance(output, str):
                passed = False
                failure_reasons.append(f"输出类型错误: 期望str, 实际{type(output).__name__}")
            else:
                # 检查期望的模式
                if hasattr(test_case, "expected_pattern") and test_case.expected_pattern:
                    if not re.search(test_case["expected_pattern"], output):
                        passed = False
                        failure_reasons.append(f"未匹配到期望模式: {test_case['expected_pattern']}")
                
                # 检查不期望的模式
                for pattern in test_case.get("unexpected_patterns", []):
                    if re.search(pattern, output):
                        passed = False
                        failure_reasons.append(f"匹配到不期望模式: {pattern}")
            
            # 判断结果
            if passed:
                print(f"    ✅ 通过")
                passed_count += 1
            else:
                print(f"    ❌ 失败: {', '.join(failure_reasons)}")
                failed_cases.append({
                    "name": test_case["name"],
                    "input": test_case["input"],
                    "output": output,
                    "reasons": failure_reasons
                })
                
        except Exception as e:
            print(f"    ❌ 执行异常: {type(e).__name__}: {e}")
            failed_cases.append({
                "name": test_case["name"],
                "input": test_case["input"],
                "output": None,
                "reasons": [f"执行异常: {e}"]
            })
    
    # 输出汇总
    print(f"\n  📊 测试结果: {passed_count}/{len(DATE_TEST_CASES)} 通过")
    
    return {
        "total": len(DATE_TEST_CASES),
        "passed": passed_count,
        "failed": len(DATE_TEST_CASES) - passed_count,
        "pass_rate": passed_count / len(DATE_TEST_CASES) * 100 if len(DATE_TEST_CASES) > 0 else 0.0,
        "failed_cases": failed_cases
    }


def test_mercenary_output():
    """AC-3: 验证雇佣兵产出质量"""
    print("=" * 60)
    print("验证三：雇佣兵产出质量 (AC-3)")
    print("=" * 60)
    
    # 运行3个雇佣兵测试
    md_result = test_markdown_to_html()
    keyword_result = test_keyword_extraction()
    date_result = test_date_formatting()
    
    # 汇总结果
    print("\n" + "=" * 60)
    print("AC-3 验证结果汇总")
    print("=" * 60)
    
    all_passed = (md_result["failed"] == 0 and 
                   keyword_result["failed"] == 0 and 
                   date_result["failed"] == 0)
    
    print(f"\nMarkdown→HTML: {md_result['passed']}/{md_result['total']} 通过")
    print(f"关键词提取: {keyword_result['passed']}/{keyword_result['total']} 通过")
    print(f"日期格式化: {date_result['passed']}/{date_result['total']} 通过")
    
    if not all_passed:
        print(f"\n⚠️  失败用例详情:")
        for result in [md_result, keyword_result, date_result]:
            for case in result["failed_cases"]:
                print(f"  - {case['name']}: {case['reasons']}")
    
    print(f"\n{'✅' if all_passed else '❌'} AC-3 验证结果: {'通过' if all_passed else '不通过'}")
    print(f"  要求: 所有用例全部通过")
    print(f"  实际: {'全部通过' if all_passed else '有失败用例'}")
    
    return {
        "md_result": md_result,
        "keyword_result": keyword_result,
        "date_result": date_result,
        "passed": all_passed
    }


if __name__ == "__main__":
    result = test_mercenary_output()
    
    print("\n" + "=" * 60)
    print("AC-3 验证完成")
    print("=" * 60)
