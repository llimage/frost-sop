#!/usr/bin/env python3
"""
FROST-SOP V3.0 测试覆盖率审计脚本
运行: python audit_coverage.py
"""
import subprocess
import json
from pathlib import Path
import sys

def run_command(cmd, description=""):
    """运行命令并返回结果"""
    print(f"\n[AUDIT] {description}")
    print(f"[AUDIT] 运行: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd='.'
    )
    
    if result.stdout:
        print(result.stdout[-2000:])  # 只显示最后 2000 字符
    
    if result.stderr:
        print("[AUDIT] STDERR:")
        print(result.stderr[-1000:])
    
    return result

def install_tool(package_name):
    """安装工具"""
    print(f"[AUDIT] 安装 {package_name}...")
    result = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', package_name],
        capture_output=True,
        text=True
    )
    if result.returncode == 0:
        print(f"[AUDIT] ✅ {package_name} 安装成功")
        return True
    else:
        print(f"[AUDIT] ❌ {package_name} 安装失败")
        return False

def audit_coverage():
    """测试覆盖率审计"""
    print("\n[AUDIT] === 测试覆盖率审计 ===")
    
    # 检查 pytest-cov 是否已安装
    try:
        import pytest_cov
    except ImportError:
        if not install_tool('pytest-cov'):
            print("[AUDIT] ⚠️  跳过覆盖率审计")
            return False
    
    # 运行测试并生成覆盖率报告
    print("\n[AUDIT] 运行测试并生成覆盖率报告...")
    
    cmd = [
        sys.executable, '-m', 'pytest',
        'tests/',
        '-v',
        '-s',
        '--tb=short',
        f'--cov=core',
        f'--cov=agents',
        f'--cov=skills',
        '--cov-report=term-missing',
        '--cov-report=html:htmlcov',
        '--cov-report=json:audit_results/coverage.json',
        '--asyncio-mode=auto'
    ]
    
    result = run_command(cmd, "运行测试并生成覆盖率")
    
    # 解析覆盖率结果
    try:
        with open('audit_results/coverage.json', 'r', encoding='utf-8') as f:
            coverage_data = json.load(f)
            
            total_coverage = coverage_data.get('totals', {}).get('percent_covered', 0)
            
            print(f"\n[AUDIT] 📊 总体覆盖率: {total_coverage:.2f}%")
            
            # 按模块显示覆盖率
            print("\n[AUDIT] 📊 各模块覆盖率:")
            for file_path, file_data in coverage_data.get('files', {}).items():
                coverage_pct = file_data.get('summary', {}).get('percent_covered', 0)
                print(f"   {file_path}: {coverage_pct:.2f}%")
            
            # 检查是否达到目标
            target_coverage = 80.0
            if total_coverage >= target_coverage:
                print(f"\n[AUDIT] ✅ 覆盖率达标 (≥ {target_coverage}%)")
                return True
            else:
                print(f"\n[AUDIT] ⚠️  覆盖率未达标 (目标: ≥ {target_coverage}%, 当前: {total_coverage:.2f}%)")
                return False
                
    except FileNotFoundError:
        print("[AUDIT] ❌ 覆盖率报告未生成")
        return False
    except Exception as e:
        print(f"[AUDIT] ❌ 解析覆盖率报告失败: {e}")
        return False

def identify_uncovered_lines():
    """识别未覆盖的代码行"""
    print("\n[AUDIT] === 识别未覆盖的代码 ===")
    
    try:
        with open('audit_results/coverage.json', 'r', encoding='utf-8') as f:
            coverage_data = json.load(f)
            
            uncovered_files = []
            
            for file_path, file_data in coverage_data.get('files', {}).items():
                missing_lines = file_data.get('missing_lines', [])
                if missing_lines:
                    uncovered_files.append({
                        'file': file_path,
                        'missing_count': len(missing_lines),
                        'missing_lines': missing_lines[:10]  # 只显示前 10 行
                    })
            
            if uncovered_files:
                print(f"[AUDIT] 发现 {len(uncovered_files)} 个文件有未覆盖代码:")
                for item in uncovered_files[:10]:
                    print(f"   - {item['file']}: {item['missing_count']} 行未覆盖")
                    print(f"     未覆盖行: {item['missing_lines']}")
            else:
                print("[AUDIT] ✅ 所有代码都已覆盖")
            
            # 保存结果
            with open('audit_results/uncovered_lines.json', 'w', encoding='utf-8') as f:
                json.dump(uncovered_files, f, indent=2, ensure_ascii=False)
            
            print("[AUDIT] 详细信息已保存到: audit_results/uncovered_lines.json")
            
    except FileNotFoundError:
        print("[AUDIT] ❌ 覆盖率报告不存在，请先运行覆盖率审计")

def generate_coverage_report():
    """生成覆盖率审计报告"""
    print("\n[AUDIT] === 生成覆盖率审计报告 ===")
    
    report = {
        "audit_time": subprocess.run(['date', '/t'], capture_output=True, text=True).stdout.strip(),
        "overall_coverage": 0.0,
        "module_coverage": {},
        "uncovered_files": [],
        "recommendations": []
    }
    
    # 读取覆盖率数据
    try:
        with open('audit_results/coverage.json', 'r', encoding='utf-8') as f:
            coverage_data = json.load(f)
            
            report["overall_coverage"] = coverage_data.get('totals', {}).get('percent_covered', 0)
            
            # 按模块分组
            module_coverage = {}
            for file_path, file_data in coverage_data.get('files', {}).items():
                # 提取模块名 (core, agents, skills)
                parts = file_path.split('\\')
                if len(parts) >= 2:
                    module = parts[0]
                    if module not in module_coverage:
                        module_coverage[module] = []
                    module_coverage[module].append({
                        'file': file_path,
                        'coverage': file_data.get('summary', {}).get('percent_covered', 0)
                    })
            
            # 计算模块平均覆盖率
            for module, files in module_coverage.items():
                avg_coverage = sum(f['coverage'] for f in files) / len(files)
                report["module_coverage"][module] = round(avg_coverage, 2)
            
    except FileNotFoundError:
        print("[AUDIT] ❌ 覆盖率报告不存在")
        return
    
    # 读取未覆盖代码
    try:
        with open('audit_results/uncovered_lines.json', 'r', encoding='utf-8') as f:
            report["uncovered_files"] = json.load(f)
    except:
        pass
    
    # 生成建议
    if report["overall_coverage"] < 80:
        report["recommendations"].append("补充单元测试，提高覆盖率至 80% 以上")
    
    for module, coverage in report["module_coverage"].items():
        if coverage < 70:
            report["recommendations"].append(f"模块 {module}/ 覆盖率较低 ({coverage}%)，建议重点补充测试")
    
    # 保存报告
    with open('audit_results/coverage_audit_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"[AUDIT] ✅ 覆盖率审计报告已保存: audit_results/coverage_audit_report.json")
    print(f"[AUDIT] 总体覆盖率: {report['overall_coverage']:.2f}%")
    print(f"[AUDIT] 模块覆盖率:")
    for module, coverage in report["module_coverage"].items():
        print(f"   - {module}: {coverage}%")

def main():
    """主函数"""
    print("📊 FROST-SOP V3.0 测试覆盖率审计")
    print("=" * 60)
    
    # 创建结果目录
    Path('audit_results').mkdir(exist_ok=True)
    
    # 运行覆盖率审计
    coverage_ok = audit_coverage()
    
    # 识别未覆盖代码
    identify_uncovered_lines()
    
    # 生成报告
    generate_coverage_report()
    
    print("\n" + "=" * 60)
    if coverage_ok:
        print("✅ 覆盖率审计通过！")
    else:
        print("⚠️  覆盖率未达标，建议补充测试")
    
    print("📂 结果保存在: audit_results/")
    print("\n建议下一步:")
    print("   1. 查看 htmlcov/ 目录中的 HTML 覆盖率报告")
    print("   2. 查看 audit_results/uncovered_lines.json 识别未覆盖代码")
    print("   3. 补充测试用例")
    print("   4. 重新运行此脚本验证覆盖率提升")

if __name__ == '__main__':
    main()
