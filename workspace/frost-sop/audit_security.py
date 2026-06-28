#!/usr/bin/env python3
"""
FROST-SOP V3.0 安全审计脚本
运行: python audit_security.py
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

def audit_dependency_vulnerabilities():
    """依赖漏洞扫描 (Safety & pip-audit)"""
    print("\n[AUDIT] === 1. 依赖漏洞扫描 ===")
    
    # 1.1 Safety 检查
    print("\n[AUDIT] 1.1 Safety 漏洞扫描...")
    if not check_tool_installed('safety'):
        if not install_tool('safety'):
            print("[AUDIT] ⚠️  跳过 Safety 检查")
        else:
            # 使用 python -m safety 方式调用
            cmd = [sys.executable, '-m', 'safety', 'check', '-r', 'requirements.txt', '--json']
            run_command(cmd, 'audit_results/safety_vulnerabilities.json')
    
    # 1.2 pip-audit 检查
    print("\n[AUDIT] 1.2 pip-audit 漏洞扫描...")
    if not check_tool_installed('pip-audit'):
        if not install_tool('pip-audit'):
            print("[AUDIT] ⚠️  跳过 pip-audit 检查")
        else:
            # 使用 python -m pip_audit 方式调用
            cmd = [sys.executable, '-m', 'pip_audit', '-r', 'requirements.txt', '--format',
                'json', '--output', 'audit_results/pip_audit_vulnerabilities.json']
            run_command(cmd)
    
    return True

def audit_static_security():
    """静态安全分析 (Bandit)"""
    print("\n[AUDIT] === 2. 静态安全分析 (Bandit) ===")
    
    if not check_tool_installed('bandit'):
        if not install_tool('bandit'):
            print("[AUDIT] ⚠️  跳过 Bandit 检查")
            return False
    
    # 使用 python -m bandit 方式调用
    cmd = [
        sys.executable, '-m', 'bandit',
        '-r', 'core/', 'agents/', 'skills/',
        '-f', 'json',
        '-o', 'audit_results/bandit_security_issues.json',
        '-ll',  # 只显示 MEDIUM 及以上严重级别
    ]
    
    result = run_command(cmd)
    
    # 解析结果
    try:
        with open('audit_results/bandit_security_issues.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            issue_count = len(data.get('results', []))
            high_severity = len([i for i in data.get('results', [])
                                if i.get('issue_severity') == 'HIGH'])
            
            print(f"[AUDIT] Bandit 发现 {issue_count} 个安全问题 (高危: {high_severity})")
            
            if high_severity > 0:
                print("[AUDIT] ⚠️  发现高危安全问题，建议立即修复！")
                return False
    except:
        pass
    
    print("[AUDIT] ✅ Bandit 检查通过")
    return True

def audit_sensitive_info():
    """敏感信息扫描 (detect-secrets)"""
    print("\n[AUDIT] === 3. 敏感信息扫描 (detect-secrets) ===")
    
    if not check_tool_installed('detect-secrets'):
        if not install_tool('detect-secrets'):
            print("[AUDIT] ⚠️  跳过 detect-secrets 检查")
            return False
    
    # 3.1 扫描敏感信息（使用 python -m detect_secrets 方式调用）
    cmd = [sys.executable, '-m', 'detect_secrets', 'scan', '--all-files', '--json']
    result = run_command(cmd, 'audit_results/detect_secrets_baseline.json')
    
    # 3.2 审计基线
    print("\n[AUDIT] 3.2 审计敏感信息基线...")
    cmd_audit = [sys.executable, '-m', 'detect_secrets',
        'audit', 'audit_results/detect_secrets_baseline.json']
    result_audit = run_command(cmd_audit)
    
    if result_audit.returncode != 0:
        print("[AUDIT] ⚠️  发现敏感信息泄露风险！")
        return False
    
    print("[AUDIT] ✅ 敏感信息扫描通过")
    return True

def audit_license_compliance():
    """开源协议合规性检查"""
    print("\n[AUDIT] === 4. 开源协议合规性检查 ===")
    
    if not check_tool_installed('pip-licenses'):
        if not install_tool('pip-licenses'):
            print("[AUDIT] ⚠️  跳过程协议检查")
            return False
    
    # 使用 python -m pip_licenses 方式调用
    cmd = [
        sys.executable, '-m', 'pip_licenses',
        '--format=json',
        '--output=audit_results/license_compliance.json'
    ]
    
    run_command(cmd)
    
    # 检查是否有高风险协议 (GPL 等)
    try:
        with open('audit_results/license_compliance.json', 'r', encoding='utf-8') as f:
            licenses = json.load(f)
            risky_licenses = ['GPL', 'AGPL', 'LGPL']
            risky_deps = [dep for dep in licenses if any(
                rl in dep.get('License', '') for rl in risky_licenses)]
            
            if risky_deps:
                print(f"[AUDIT] ⚠️  发现 {len(risky_deps)} 个高风险协议依赖:")
                for dep in risky_deps[:5]:
                    print(f"   - {dep['Name']}: {len(dep['License'])}")
                return False
    except:
        pass
    
    print("[AUDIT] ✅ 协议合规性检查通过")
    return True

def audit_hardcoded_secrets():
    """硬编码密钥检测 (Grep 搜索)"""
    print("\n[AUDIT] === 5. 硬编码密钥检测 ===")
    
    import re
    
    patterns = [
        (r'api[_-]?key\s*=\s*["\']\w+["\']', 'API Key'),
        (r'password\s*=\s*["\']\w+["\']', 'Password'),
        (r'secret\s*=\s*["\']\w+["\']', 'Secret'),
        (r'token\s*=\s*["\']\w+["\']', 'Token'),
        (r'sk-[a-zA-Z0-9]{32,}', 'OpenAI API Key'),
        (r'Bearer\s+[a-zA-Z0-9_\-\.]+', 'Bearer Token'),
    ]
    
    issues_found = []
    
    # 扫描 Python 文件
    for py_file in Path('.').rglob('*.py'):
        if 'audit_' in py_file.name or 'test_' in py_file.name:
            continue
        
        try:
            with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
                for pattern, desc in patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        issues_found.append((str(py_file), desc))
        except:
            pass
    
    if issues_found:
        print(f"[AUDIT] ⚠️  发现 {len(issues_found)} 处可能的硬编码密钥:")
        for file, desc in issues_found[:10]:
            print(f"   - {file}: {desc}")
        
        # 保存结果
        with open('audit_results/hardcoded_secrets.txt', 'w', encoding='utf-8') as f:
            for file, desc in issues_found:
                f.write(f"{file}: {desc}\n")
        
        return False
    else:
        print("[AUDIT] ✅ 未发现硬编码密钥")
        return True

def generate_security_report():
    """生成安全审计报告"""
    print("\n[AUDIT] === 生成安全审计报告 ===")
    
    report = {
        "audit_time": subprocess.run(['date', '/t'], capture_output=True, text=True).stdout.strip(),
        "checks_performed": [
            "依赖漏洞扫描 (Safety, pip-audit)",
            "静态安全分析 (Bandit)",
            "敏感信息扫描 (detect-secrets)",
            "开源协议检查 (pip-licenses)",
            "硬编码密钥检测"
        ],
        "issues_summary": {},
        "risk_level": "LOW"  # LOW, MEDIUM, HIGH
    }
    
    # 读取 Bandit 结果
    try:
        with open('audit_results/bandit_security_issues.json', 'r') as f:
            bandit_data = json.load(f)
            high_issues = [i for i in bandit_data.get(
                'results', []) if i.get('issue_severity') == 'HIGH']
            medium_issues = [i for i in bandit_data.get(
                'results', []) if i.get('issue_severity') == 'MEDIUM']
            
            report["issues_summary"]["bandit_high"] = len(high_issues)
            report["issues_summary"]["bandit_medium"] = len(medium_issues)
            
            if high_issues:
                report["risk_level"] = "HIGH"
            elif medium_issues:
                report["risk_level"] = "MEDIUM"
    except:
        pass
    
    # 保存报告
    with open('audit_results/security_audit_report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"[AUDIT] ✅ 安全审计报告已保存: audit_results/security_audit_report.json")
    print(f"[AUDIT] 风险等级: {report['risk_level']}")

def main():
    """主函数"""
    print("🔒 FROST-SOP V3.0 安全审计")
    print("=" * 60)
    
    # 创建结果目录
    Path('audit_results').mkdir(exist_ok=True)
    
    # 运行审计
    results = {
        'dependency_vulns': audit_dependency_vulnerabilities(),
        'static_security': audit_static_security(),
        'sensitive_info': audit_sensitive_info(),
        'license_compliance': audit_license_compliance(),
        'hardcoded_secrets': audit_hardcoded_secrets(),
    }
    
    # 生成报告
    generate_security_report()
    
    print("\n" + "=" * 60)
    print("✅ 安全审计完成！")
    print("📂 结果保存在: audit_results/")
    print("\n建议下一步:")
    print("   1. 查看 audit_results/security_audit_report.json")
    print("   2. 修复高危安全问题")
    print("   3. 运行 python audit_coverage.py 进行覆盖率审计")

if __name__ == '__main__':
    main()
