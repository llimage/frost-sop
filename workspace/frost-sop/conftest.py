"""
FROST-SOP 全局 pytest 配置（根目录）

仅设置测试模式环境变量。
所有 fixtures 和 marker 注册在 tests/conftest.py 中统一管理。
"""

import os

# 测试模式环境变量（避免真实 LLM 调用）
os.environ.setdefault("FROST_TESTING", "1")
