"""
FROST-SOP 深度质量验证 - 验证一：能力基因库内容质量

AC-1: 验证498个模板的字段完整性
"""
import sys
import os
from typing import Dict, Any

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stores.asset import create_asset_store


def load_asset_store(filepath: str = "data/assets.json") -> "HierarchicalStore":
    """加载资产Store"""
    return create_asset_store(backend='file', path=filepath)


def check_template_fields(template: Dict[str, Any], template_name: str) -> Dict[str, Any]:
    """
    检查单个模板的字段完整性
    
    Returns:
        {"valid": bool, "missing_fields": list, "errors": list}
    """
    required_fields = {
        "name": str,
        "type": str,
        "description": str,
        "category": str,
        "input_keys": list,
        "output_keys": list
    }
    
    missing_fields = []
    errors = []
    
    # 检查字段是否存在
    for field, expected_type in required_fields.items():
        if field not in template:
            missing_fields.append(field)
        elif not isinstance(template[field], expected_type):
            errors.append(
                f"{field}类型错误: 期望{expected_type.__name__}, 实际{type(template[field]).__name__}")
        elif expected_type == str and not template[field].strip():
            errors.append(f"{field}为空字符串")
        elif expected_type == list and len(template[field]) == 0:
            errors.append(f"{field}为空列表")
    
    # 检查type字段的值
    if "type" in template and template["type"] != "functional":
        errors.append(f"type字段值应为'functional', 实际为'{template['type']}'")
    
    valid = (len(missing_fields) == 0 and len(errors) == 0)
    
    return {
        "valid": valid,
        "missing_fields": missing_fields,
        "errors": errors
    }


def test_gene_quality():
    """AC-1: 验证能力基因库内容质量"""
    print("=" * 60)
    print("验证一：能力基因库内容质量 (AC-1)")
    print("=" * 60)
    
    # 加载资产Store
    asset_store = load_asset_store()
    
    # 获取所有能力基因模板
    all_keys = asset_store.list_keys()
    gene_keys = [k for k in all_keys if k.startswith("skill_gene:")]
    
    print(f"\n📊 统计信息:")
    print(f"  资产Store总键数: {len(all_keys)}")
    print(f"  能力基因模板数: {len(gene_keys)}")
    
    if len(gene_keys) == 0:
        print("\n❌ 错误: 未找到任何skill_gene:前缀的键")
        return {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "pass_rate": 0.0,
            "invalid_templates": []
        }
    
    # 检查每个模板
    valid_count = 0
    invalid_templates = []
    
    print(f"\n🔍 检查模板字段完整性...")
    
    for idx, key in enumerate(gene_keys):
        template = asset_store.load(key)
        
        # 检查template是否为字典
        if not isinstance(template, dict):
            invalid_templates.append({
                "key": key,
                "missing_fields": [],
                "errors": [f"模板值类型错误: 期望dict, 实际{type(template).__name__}"]
            })
            continue
        
        # 检查字段
        check_result = check_template_fields(template, key)
        
        if check_result["valid"]:
            valid_count += 1
        else:
            invalid_templates.append({
                "key": key,
                "template_name": template.get("name", "未知"),
                "missing_fields": check_result["missing_fields"],
                "errors": check_result["errors"]
            })
        
        # 每100个显示一次进度
        if (idx + 1) % 100 == 0:
            print(f"  进度: {idx + 1}/{len(gene_keys)}")
    
    # 计算合格率
    total = len(gene_keys)
    invalid_count = total - valid_count
    pass_rate = (valid_count / total * 100) if total > 0 else 0.0
    
    print(f"\n📈 验证结果:")
    print(f"  总模板数: {total}")
    print(f"  合格模板数: {valid_count}")
    print(f"  不合格模板数: {invalid_count}")
    print(f"  合格率: {pass_rate:.1f}%")
    
    # 显示不合格模板
    if invalid_templates:
        print(f"\n⚠️  不合格模板详情:")
        for item in invalid_templates[:10]:  # 只显示前10个
            print(f"  - {item['key']}")
            if item['missing_fields']:
                print(f"    缺失字段: {', '.join(item['missing_fields'])}")
            if item['errors']:
                print(f"    错误: {', '.join(item['errors'])}")
        
        if len(invalid_templates) > 10:
            print(f"  ... (还有{len(invalid_templates) - 10}个不合格模板未显示)")
    
    # 判断是否通过
    passed = pass_rate >= 95.0
    
    print(f"\n{'✅' if passed else '❌'} AC-1 验证结果: {'通过' if passed else '不通过'}")
    print(f"  要求: 合格率 ≥ 95%")
    print(f"  实际: 合格率 = {pass_rate:.1f}%")
    
    return {
        "total": total,
        "valid": valid_count,
        "invalid": invalid_count,
        "pass_rate": pass_rate,
        "passed": passed,
        "invalid_templates": invalid_templates
    }


if __name__ == "__main__":
    result = test_gene_quality()
    
    print("\n" + "=" * 60)
    print("AC-1 验证完成")
    print("=" * 60)
