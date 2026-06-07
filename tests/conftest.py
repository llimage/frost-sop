"""
tests/conftest.py - 测试共享 fixtures
Solo-Ops-Platform V0.9.0
"""
import os
import json
import tempfile
from pathlib import Path
import pytest


@pytest.fixture
def sample_markdown():
    """示例 Markdown 文档内容。"""
    return """# 产品规划文档

## 第一部分：市场分析

AI 编程工具市场在2025年持续增长，主要玩家包括 Cursor、Windsurf、Codeium 等。
关键数据：市场规模约 50 亿美元，年增长率 35%。

## 第二部分：竞品对比

| 工具 | 特点 | 定价 |
|------|------|------|
| Cursor | VS Code 分支，深度 AI 集成 | $20/月 |
| Windsurf | 独立 IDE，AI-first | $15/月 |
| Codeium | 免费为主，VS Code 插件 | 免费 |

## 第三部分：技术路线

1. 阶段一：核心功能开发
2. 阶段二：AI 集成
3. 阶段三：市场推广

## 总结

市场前景广阔，但竞争激烈。需要差异化定位。
"""


@pytest.fixture
def sample_text_with_sensitivity():
    """包含各类敏感信息的文本。"""
    return """员工信息汇总

张三的身份证号是 110101199001011234，手机号是 13800138000。
银行卡号：6222021234567890123。
邮箱：zhangsan@example.com
密码：password=MySecret123

以上信息请保密。"""


@pytest.fixture
def temp_dir():
    """临时目录，测试结束后自动清理。"""
    with tempfile.TemporaryDirectory(prefix="solo_ops_test_") as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def temp_markdown_file(temp_dir, sample_markdown):
    """临时 Markdown 文件。"""
    f = temp_dir / "test_doc.md"
    f.write_text(sample_markdown, encoding="utf-8")
    return f


@pytest.fixture
def temp_text_file(temp_dir):
    """临时纯文本文件。"""
    content = "这是一个测试文档。\n\n包含两个段落。"
    f = temp_dir / "test_doc.txt"
    f.write_text(content, encoding="utf-8")
    return f


@pytest.fixture
def temp_sensitive_file(temp_dir, sample_text_with_sensitivity):
    """临时包含敏感信息的文件。"""
    f = temp_dir / "sensitive_doc.txt"
    f.write_text(sample_text_with_sensitivity, encoding="utf-8")
    return f
