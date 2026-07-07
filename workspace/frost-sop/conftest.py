"""
FROST-SOP 全局 pytest 配置（根目录）

测试分级：
- unit: 单元测试（mock 模式，快速）
- smoke: 冒烟测试（真实 LLM，3 分钟）
- integration: 集成测试（真实 LLM，手动触发）

环境变量 FROST_TESTING 根据测试标记自动设置。
"""

import os

import pytest


def pytest_configure(config):
    """注册自定义标记和根据测试标记自动设置测试模式。"""
    # 注册自定义标记
    config.addinivalue_line("markers", "unit: 单元测试（mock 模式，快速）")
    config.addinivalue_line("markers", "smoke: 冒烟测试（真实 LLM，3 分钟）")
    config.addinivalue_line("markers", "integration: 集成测试（真实 LLM，手动触发）")

    # 根据测试标记设置测试模式
    marker_expr = config.getoption("-m", default="")
    markers_str = marker_expr if isinstance(marker_expr, str) else ""

    # 如果没有指定标记，或指定了 unit 标记，使用 mock 模式
    if not markers_str or "unit" in markers_str:
        os.environ["FROST_TESTING"] = "1"
    elif "smoke" in markers_str or "integration" in markers_str:
        # 冒烟/集成测试使用真实 LLM
        os.environ.pop("FROST_TESTING", None)


def pytest_collection_modifyitems(config, items):
    """自动给没有标记的测试添加 unit 标记。"""
    for item in items:
        if not any(
            marker.name in ("unit", "smoke", "integration") for marker in item.iter_markers()
        ):
            item.add_marker(pytest.mark.unit)
