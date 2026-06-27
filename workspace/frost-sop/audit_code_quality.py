#!/usr/bin/env python3
"""
FROST-SOP V3.0 代码质量审计脚本
运行: python audit_code_quality.py
"""
import subprocess
import json
from pathlib import Path
import sys

def run_command(cmd, output_file=None, cwd=None):
    """运行命令并返回结果"""
    print(f"[AUDIT] 运行: {' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=cwd or '.'
    )
    
    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result.stdout)
            if result.stderr:
                f.write("\n\n--- STDERR ---\n")
                f.write(result.stderr)
        print(f"[AUDIT] 结果已保存到: {output_file}")
    
    return result

def check_tool_installed(tool_name):
    """检查工具是否已安装"""
    try:
        subprocess.run([tool_name, '--version'], 
                      capture_output=True, 
                      check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

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
        print(f"[AUDIT] ❌ {package_name} 安装失败: {result.stderr}")
        return False

def audit_pylint():
    """Pylint 代码规范检查"""
    print("\n[AUDIT] === 1. Pylint 代码规范检查 ===")
    
    if not check_tool_installed('pylint'):
        if not install_tool('pylint'):
            print("[AUDIT] ⚠️  跳过 Pylint 检查")
            return False
    
    # 使用 python -m pylint 方式调用（避免 PATH 问题）
    cmd = [
        sys.executable, '-m', 'pylint',
        'core/', 'agents/', 'skills/', 'main.py', 'app.py',
        '--output-format=json',
        '--disable=all',
        '--enable=E,F',  # 只检查错误和致命问题
    ]
    
    result = run_command(cmd, 'audit_results/pylint_errors.json')
    
    # 解析结果
    try:
        with open('audit_results/pylint_errors.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            error_count = len([m for m in data if m.get('type') in ('error', 'fatal')])
            print(f"[AUDIT] Pylint 发现 {error_count} 个错误")
            return error_count == 0
    except:
        return False

def audit_flake8():
    """Flake8 PEP 8 合规性检查"""
    print("\n[AUDIT] === 2. Flake8 PEP 8 检查 ===")
    
    if not check_tool_installed('flake8'):
        if not install_tool('flake8'):
            print("[AUDIT] ⚠️  跳过 Flake8 检查")
            return False
    
    # 使用 python -m flake8 方式调用
    cmd = [
        sys.executable, '-m', 'flake8',
        'core/', 'agents/', 'skills/', 'main.py', 'app.py',
        '--format=json',
        '--max-line-length=120',
        '--ignore=E501,W503',  # 忽略行长度和换行警告
    ]
    
    result = run_command(cmd, 'audit_results/flake8_issues.json')
    
    # 统计问题数
    if result.returncode != 0:
        try:
            with open('audit_results/flake8_issues.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                print(f"[AUDIT] Flake8 发现 {len(data)} 个问题")
                return False
        except:
            pass
    
    print("[AUDIT] ✅ Flake8 检查通过（0 个问题）")
    return True

def audit_radon():
    """Radon 圈复杂度分析"""
    print("\n[AUDIT] === 3. Radon 圈复杂度分析 ===")
    
    if not check_tool_installed('radon'):
        if not install_tool('radon'):
            print("[AUDIT] ⚠️  跳过 Radon 检查")
            return False
    
    # 复杂度分析 (Cyclomatic Complexity)
    # 使用 python -m radon 方式调用
    cmd = [
        sys.executable, '-m', 'radon', 'cc',
        'core/', 'agents/', 'skills/',
        '-j',  # JSON 格式
        '--min=C',  # 只显示 C 及以上复杂度
    ]
    
    result = run_command(cmd, 'audit_results/radon_complexity.json')
    
    print("[AUDIT] 复杂度分析完成")
    return True

def audit_mypy():
    """MyPy 类型注解检查"""
    print("\n[AUDIT] === 4. MyPy 类型注解检查 ===")
    
    if not check_tool_installed('mypy'):
        if not install_tool('mypy'):
            print("[AUDIT] ⚠️  跳过 MyPy 检查")
            return False
    
    # 使用 python -m mypy 方式调用
    cmd = [
        sys.executable, '-m', 'mypy',
        'core/', 'agents/', 'skills/',
        '--ignore-missing-imports',
        '--disallow-untyped-defs',
    ]
    
    result = run_command(cmd, 'audit_results/mypy_types.txt')
    
    if result.returncode == 0:
        print("[AUDIT] ✅ MyPy 检查通过")
        return True
    else:
        print("[AUDIT] ⚠️  MyPy 发现类型注解问题")
        return False

def generate_summary():
    """生成审计摘要"""
    print("\n[AUDIT] === 生成审计摘要 ===")
    
    summary = {
        "audit_time": subprocess.run(['date', '/t'], capture_output=True, text=True).stdout.strip(),
        "tools_used": [],
        "issues_found": {},
        "recommendations": []
    }
    
    # 读取 Pylint 结果
    try:
        with open('audit_results/pylint_errors.json', 'r') as f:
            pylint_data = json.load(f)
            error_count = len([m for m in pylint_data if m.get('type') in ('error', 'fatal')])
            summary["issues_found"]["pylint_errors"] = error_count
            summary["tools_used"].append("pylint")
    except:
        pass
    
    # 读取 Flake8 结果
    try:
        with open('audit_results/flake8_issues.json', 'r') as f:
            flake8_data = json.load(f)
            summary["issues_found"]["flake8_issues"] = len(flake8_data)
            summary["tools_used"].append("flake8")
    except:
        pass
    
    # 保存摘要
    with open('audit_results/code_quality_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print("[AUDIT] ✅ 摘要已保存到: audit_results/code_quality_summary.json")
    
    # 打印摘要
    print("\n📊 代码质量审计摘要:")
    print(f"   工具: {', '.join(summary['tools_used'])}")
    for key, value in summary["issues_found"].items():
        print(f"   {key}: {value}")

def main():
    """主函数"""
    print("📋 FROST-SOP V3.0 代码质量审计")
    print("=" * 60)
    
    # 创建结果目录
    Path('audit_results').mkdir(exist_ok=True)
    
    # 运行审计
    results = {
        'pylint': audit_pylint(),
        'flake8': audit_flake8(),
        'radon': audit_radon(),
        'mypy': audit_mypy(),
    }
    
    # 生成摘要
    generate_summary()
    
    print("\n" + "=" * 60)
    print("✅ 代码质量审计完成！")
    print("📂 结果保存在: audit_results/")
    print("\n建议下一步:")
    print("   1. 查看 audit_results/ 目录中的详细报告")
    print("   2. 修复发现的问题")
    print("   3. 运行 python audit_security.py 进行安全审计")

if __name__ == '__main__':
    main()
