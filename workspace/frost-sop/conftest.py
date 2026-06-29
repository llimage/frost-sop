"""
FROST-SOP 全局 pytest 配置

- 配置 pytest-asyncio 模式：auto（自动识别 async def 函数）
- 提供测试模式的全局环境变量
"""
import os
import sys

# 测试模式环境变量（避免真实 LLM 调用）
os.environ.setdefault("FROST_TESTING", "1")

# pytest-asyncio 配置
# mode=auto: 自动将 async def 识别为 asyncio 测试
import pytest

# 注册 asyncio marker
def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as async (handled by pytest-asyncio in auto mode)",
    )
