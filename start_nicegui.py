"""
启动 Solo-Ops-Platform 驾驶舱（NiceGUI版本）
使用方法：
    python start_nicegui.py
    
然后打开浏览器访问 http://localhost:8080
"""

import os
import sys

# 检查NiceGUI是否已安装
try:
    import nicegui
    print(f"✅ NiceGUI version: {nicegui.__version__}")
except ImportError:
    print("❌ NiceGUI not found. Installing...")
    os.system(f"{sys.executable} -m pip install nicegui")
    import nicegui

print("🚀 Starting Solo-Ops-Platform Cockpit (NiceGUI)...")
print("📍 URL: http://localhost:8080")
print("🛑 Press Ctrl+C to stop")
print()

# 启动应用
from app import create_ui
create_ui()
