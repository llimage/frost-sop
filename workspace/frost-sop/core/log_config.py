"""
FROST-SOP 日志配置模块。

提供统一的日志初始化，支持：
- 按天轮转（TimedRotatingFileHandler，保留 30 天）
- 控制台输出（开发模式）
- 敏感信息自动过滤
- 级别配置（环境变量 FROST_LOG_LEVEL）

Usage:
    from core.log_config import setup_logging
    setup_logging()
"""

from __future__ import annotations

import logging
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path


# 日志目录
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

# 敏感信息过滤模式
_SENSITIVE_PATTERNS = [
    (re.compile(r"(api_key|apikey|secret|token|password|authorization)[=:]\s*\S+", re.I), r"\1=***"),
    (re.compile(r"sk-[a-zA-Z0-9]{20,}"), "sk-***"),
    (re.compile(r"Bearer\s+\S+"), "Bearer ***"),
]


class SensitiveFilter(logging.Filter):
    """自动过滤日志中的敏感信息。"""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            for pattern, replacement in _SENSITIVE_PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


def setup_logging(
    level: str | None = None,
    console: bool = True,
    file_rotation: bool = True,
) -> logging.Logger:
    """
    初始化全局日志配置。

    Args:
        level: 日志级别（默认从 FROST_LOG_LEVEL 环境变量读取，回退到 INFO）
        console: 是否输出到控制台
        file_rotation: 是否启用按天轮转文件日志

    Returns:
        根 logger
    """
    if level is None:
        level = os.environ.get("FROST_LOG_LEVEL", "INFO")

    root_logger = logging.getLogger("frost")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # 避免重复添加 handler
    if root_logger.handlers:
        return root_logger

    # 格式
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)-5s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 敏感信息过滤器
    sensitive_filter = SensitiveFilter()

    # 控制台输出
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG if level.upper() == "DEBUG" else logging.INFO)
        console_handler.setFormatter(formatter)
        console_handler.addFilter(sensitive_filter)
        root_logger.addHandler(console_handler)

    # 文件日志（按天轮转，保留 30 天）
    if file_rotation:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename=str(LOG_DIR / "frost.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        file_handler.suffix = "%Y%m%d"
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        file_handler.addFilter(sensitive_filter)
        root_logger.addHandler(file_handler)

    # 错误日志单独文件
    if file_rotation:
        error_handler = TimedRotatingFileHandler(
            filename=str(LOG_DIR / "error.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        error_handler.suffix = "%Y%m%d"
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(formatter)
        error_handler.addFilter(sensitive_filter)
        root_logger.addHandler(error_handler)

    root_logger.info("FROST-SOP logging initialized (level=%s)", level)
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """获取子 logger（命名空间: frost.<name>）。"""
    return logging.getLogger(f"frost.{name}")
