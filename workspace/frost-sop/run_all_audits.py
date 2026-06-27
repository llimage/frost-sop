#!/usr/bin/env python3
"""
FROST-SOP V3.0 主审计运行器
依次运行所有审计脚本并生成综合报告
运行: python run_all_audits.py
"""
import subprocess
import json
from pathlib import Path
import sys
import time

def print_header(title):
    """打印标题"""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)

def run_audit_script(script_name, description):
    """运行审计脚本"""
    print_header(f"开始: {description}")
    print(f"[AUDIT] 运行脚本: {script_name}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            cwd='.',
            timeout=600  # 10 分钟超时
        )
        
        # 打印输出
        if result.stdout:
            # 只打印最后 50 行
            lines = result.stdout.split('\n')
            for line in lines[-50:]:
                print(line)
        
        if result.stderr:
            print("\n[WARNING] STDERR 输出:")
            print(result.stderr[-1000:])
        
        elapsed = time.time() - start_time
        
        if result.returncode == 0:
            print(f"\n✅ {description} 完成 (耗时: {elapsed:.1f}s)")
            return True
        else:
            print(f"\n⚠️  {description} 完成 (但有警告，耗时: {elapsed:.1f}s)")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"\n❌ {description} 超时 (>{600}s)")
        return False
    except FileNotFoundError:
        print(f"\n❌ 脚本不存在: {script_name}")
        return False
    except Exception as e:
        print(f"\n❌ {description} 失败: {e}")
        return False

def check_prerequisites():
    """检查审计前置条件"""
    print_header("检查审计前置条件")
    
    prerequisites = {
        "Python": [sys.executable, '--version'],
        "pip": [sys.executable, '-m', 'pip', '--version'],
        "pytest": [sys.executable, '-m', 'pytest', '--version'],
    }
    
    missing = []
    
    for name, cmd in prerequisites.items():
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            print(f"✅ {name}: 已安装")
        except:
            print(f"❌ {name}: 未安装")
            missing.append(name)
    
    if missing:
        print(f"\n⚠️  缺少工具: {', '.join(missing)}")
        print("   部分审计可能跳过，建议先运行: pip install -r requirements.txt")
        return False
    
    return True

def collect_audit_results():
    """收集所有审计结果"""
    print_header("收集审计结果")
    
    results = {
        "code_quality": {},
        "security": {},
        "coverage": {},
        "summary": {
            "total_issues": 0,
            "critical_issues": 0,
            "high_issues": 0,
            "medium_issues": 0,
            "low_issues": 0,
        }
    }
    
    # 1. 代码质量结果
    try:
        with open('audit_results/code_quality_summary.json', 'r', encoding='utf-8') as f:
            results["code_quality"] = json.load(f)
            print("✅ 已加载: 代码质量审计结果")
    except FileNotFoundError:
        print("⚠️  缺少: 代码质量审计结果 (audit_results/code_quality_summary.json)")
    
    # 2. 安全审计结果
    try:
        with open('audit_results/security_audit_report.json', 'r', encoding='utf-8') as f:
            results["security"] = json.load(f)
            print("✅ 已加载: 安全审计报告")
            
            # 统计安全问题
            if results["security"].get("issues_summary"):
                results["summary"]["high_issues"] += results["security"]["issues_summary"].get("bandit_high", 0)
                results["summary"]["medium_issues"] += results["security"]["issues_summary"].get("bandit_medium", 0)
    except FileNotFoundError:
        print("⚠️  缺少: 安全审计报告 (audit_results/security_audit_report.json)")
    
    # 3. 覆盖率审计结果
    try:
        with open('audit_results/coverage_audit_report.json', 'r', encoding='utf-8') as f:
            results["coverage"] = json.load(f)
            print("✅ 已加载: 覆盖率审计报告")
    except FileNotFoundError:
        print("⚠️  缺少: 覆盖率审计报告 (audit_results/coverage_audit_report.json)")
    
    # 4. 计算总问题数
    results["summary"]["total_issues"] = (
        results["summary"]["critical_issues"] +
        results["summary"]["high_issues"] +
        results["summary"]["medium_issues"] +
        results["summary"]["low_issues"]
    )
    
    return results

def generate_final_report(results):
    """生成最终审计报告"""
    print_header("生成最终审计报告")
    
    report = {
        "project": "FROST-SOP",
        "version": "V3.0.0-beta",
        "audit_time": subprocess.run(['date', '/t'], capture_output=True, text=True).stdout.strip(),
        "auditor": "自动化审计工具 (AI Agent)",
        "results": results,
        "conclusions": [],
        "recommendations": []
    }
    
    # 生成结论
    if results["coverage"].get("overall_coverage", 0) < 80:
        report["conclusions"].append("❌ 测试覆盖率未达标 (目标: ≥80%)")
        report["recommendations"].append("补充单元测试，提高测试覆盖率")
    else:
        report["conclusions"].append("✅ 测试覆盖率达标 (≥80%)")
    
    if results["security"].get("risk_level") == "HIGH":
        report["conclusions"].append("❌ 发现高危安全问题")
        report["recommendations"].append("立即修复高危安全问题")
    elif results["security"].get("risk_level") == "MEDIUM":
        report["conclusions"].append("⚠️  发现中危安全问题")
        report["recommendations"].append("计划修复中危安全问题")
    else:
        report["conclusions"].append("✅ 未发现高危安全问题")
    
    if results["summary"]["total_issues"] == 0:
        report["conclusions"].append("✅ 审计通过，可以发布")
    else:
        report["conclusions"].append(f"⚠️  发现 {results['summary']['total_issues']} 个问题，建议修复后重新审计")
    
    # 保存报告
    with open('audit_results/FINAL_AUDIT_REPORT.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print("✅ 最终审计报告已保存: audit_results/FINAL_AUDIT_REPORT.json")
    
    # 生成 Markdown 版本
    md_content = f"""# FROST-SOP V3.0 审计报告

**项目**: FROST-SOP  
**版本**: V3.0.0-beta  
**审计时间**: {report['audit_time']}  
**审计人**: {report['auditor']}  

---

## 📊 审计结果摘要

- **总问题数**: {results['summary']['total_issues']}
- **严重问题**: {results['summary']['critical_issues']}
- **高危问题**: {results['summary']['high_issues']}
- **中危问题**: {results['summary']['medium_issues']}
- **低危问题**: {results['summary']['low_issues']}

---

## 📋 审计结论

"""
    
    for conclusion in report["conclusions"]:
        md_content += f"- {conclusion}\n"
    
    md_content += "\n---\n\n## 💡 建议\n\n"
    
    for rec in report["recommendations"]:
        md_content += f"- {rec}\n"
    
    md_content += "\n---\n\n## 📂 详细报告\n\n"
    md_content += "- 代码质量: `audit_results/code_quality_summary.json`\n"
    md_content += "- 安全审计: `audit_results/security_audit_report.json`\n"
    md_content += "- 覆盖率审计: `audit_results/coverage_audit_report.json`\n"
    md_content += "- HTML 覆盖率报告: `htmlcov/index.html`\n"
    
    with open('audit_results/FINAL_AUDIT_REPORT.md', 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print("✅ 最终审计报告 (Markdown) 已保存: audit_results/FINAL_AUDIT_REPORT.md")
    
    return report

def main():
    """主函数"""
    print("\n" + "=" * 70)
    print("  FROST-SOP V3.0 自动化审计")
    print("=" * 70)
    print("\n此脚本将依次运行:")
    print("  1. 代码质量审计 (audit_code_quality.py)")
    print("  2. 安全审计 (audit_security.py)")
    print("  3. 测试覆盖率审计 (audit_coverage.py)")
    print("  4. 生成最终审计报告")
    print("\n预计耗时: 5-15 分钟")
    print("=" * 70 + "\n")
    
    # 检查前置条件
    prereq_ok = check_prerequisites()
    
    if not prereq_ok:
        print("\n⚠️  部分工具缺失，审计可能不完整")
        response = input("是否继续? (y/n): ")
        if response.lower() != 'y':
            print("审计已取消")
            return
    
    # 创建结果目录
    Path('audit_results').mkdir(exist_ok=True)
    
    # 运行审计脚本
    audit_results = {
        'code_quality': run_audit_script('audit_code_quality.py', '代码质量审计'),
        'security': run_audit_script('audit_security.py', '安全审计'),
        'coverage': run_audit_script('audit_coverage.py', '测试覆盖率审计'),
    }
    
    # 收集结果
    results = collect_audit_results()
    
    # 生成最终报告
    final_report = generate_final_report(results)
    
    # 打印总结
    print_header("审计完成")
    print(f"\n📊 总问题数: {results['summary']['total_issues']}")
    print(f"   严重: {results['summary']['critical_issues']}")
    print(f"   高危: {results['summary']['high_issues']}")
    print(f"   中危: {results['summary']['medium_issues']}")
    print(f"   低危: {results['summary']['low_issues']}")
    
    print(f"\n📂 审计报告保存在: audit_results/")
    print("   - FINAL_AUDIT_REPORT.json (JSON)")
    print("   - FINAL_AUDIT_REPORT.md (Markdown)")
    print("   - htmlcov/ (HTML 覆盖率报告)")
    
    print("\n" + "=" * 70)
    
    if results['summary']['total_issues'] == 0:
        print("✅ 审计通过！可以发布 V3.0.0")
    else:
        print(f"⚠️  发现 {results['summary']['total_issues']} 个问题，建议修复后重新审计")
    
    print("=" * 70 + "\n")

if __name__ == '__main__':
    main()
