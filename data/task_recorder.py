"""
data/task_recorder.py - 任务记录读写模块
项目：Solo-Ops-Platform V0.2.0
---
负责 /data/task_history.json 的增删查操作。
零外部依赖，仅使用标准库。
"""

import json
import os
import random
import string
from datetime import datetime

# JSON 存储文件路径（相对于项目根目录）
_HISTORY_FILE = os.path.join(os.path.dirname(__file__), "task_history.json")


def _generate_task_id() -> str:
    """
    生成唯一任务ID。
    格式：年月日-时分秒-随机4位，如 20260603-143025-a1b2
    """
    now = datetime.now()
    rand = "".join(random.choices(string.ascii_lowercase + string.digits, k=4))
    return now.strftime("%Y%m%d-%H%M%S") + "-" + rand


def _read_file() -> list:
    """
    内部函数：读取 JSON 文件，返回任务列表。
    文件不存在或为空时返回空列表。
    """
    if not os.path.exists(_HISTORY_FILE):
        return []
    try:
        with open(_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def _write_file(records: list) -> None:
    """
    内部函数：将任务列表写入 JSON 文件。
    使用 atomic write（先写临时文件再重命名），防止写入中断导致数据损坏。
    """
    tmp_path = _HISTORY_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, _HISTORY_FILE)


def save_task(
    topic: str,
    model: str,
    status: str,
    execution_time_seconds: float,
    final_output: str,
    execution_log: str,
    execution_mode: str = "sequential",
    product_line_id: str = "default",
    task_type: str = "normal",
    referenced_knowledge: list = None,
) -> dict:
    """
    追加一条任务记录到 history 文件。

    参数：
        topic: 用户输入的任务主题
        model: 使用的模型名称
        status: 任务状态，"completed" 或 "failed"
        execution_time_seconds: 执行耗时（秒）
        final_output: 最终简报内容
        execution_log: Agent 执行日志
        execution_mode: 执行模式，"orchestrated"（CEO智能调度）或 "sequential"（固定流水线）
        product_line_id: 产品线ID，默认为 "default"
        task_type: 任务类型，"normal"（普通任务）或 "company"（公司级任务）

    返回：新创建的完整任务记录字典
    """
    now = datetime.now()
    record = {
        "task_id": _generate_task_id(),
        "created_at": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "topic": topic,
        "model": model,
        "status": status,
        "execution_time_seconds": round(execution_time_seconds, 1),
        "execution_mode": execution_mode,
        "product_line_id": product_line_id,
        "task_type": task_type,
        "final_output": final_output,
        "execution_log": execution_log,
        "referenced_knowledge": referenced_knowledge or [],
    }

    records = _read_file()
    records.append(record)
    _write_file(records)

    return record


def load_all_tasks() -> list:
    """
    读取全部任务记录，按时间倒序返回（最新的在最前面）。

    返回：任务记录列表（倒序），确保每个记录包含 referenced_knowledge 字段。
    """
    records = _read_file()
    # 确保每个记录都有 referenced_knowledge 字段（兼容旧数据）
    for record in records:
        if "referenced_knowledge" not in record:
            record["referenced_knowledge"] = []
    return sorted(records, key=lambda r: r.get("created_at", ""), reverse=True)


def get_task(task_id: str) -> dict:
    """
    根据任务ID获取单条任务详情。

    返回：任务记录字典（确保包含 referenced_knowledge 字段），未找到则返回 None
    """
    records = _read_file()
    for record in records:
        if record.get("task_id") == task_id:
            # 确保 referenced_knowledge 字段存在（兼容旧数据）
            if "referenced_knowledge" not in record:
                record["referenced_knowledge"] = []
            return record
    return None


def delete_task(task_id: str) -> bool:
    """
    删除指定ID的任务记录。

    参数：
        task_id: 任务唯一标识

    返回：是否成功删除（True/False）
    """
    records = _read_file()
    new_records = [r for r in records if r.get("task_id") != task_id]

    if len(new_records) == len(records):
        return False  # 未找到该记录

    _write_file(new_records)
    return True


def migrate_old_data():
    """
    数据迁移：为旧任务记录添加缺失的字段。
    启动时调用一次。
    添加字段：product_line_id（默认 "default"）、task_type（默认 "normal"）
    """
    records = _read_file()
    migrated_count = 0

    for record in records:
        modified = False

        if "product_line_id" not in record:
            record["product_line_id"] = "default"
            modified = True

        if "task_type" not in record:
            record["task_type"] = "normal"
            modified = True

        if "referenced_knowledge" not in record:
            record["referenced_knowledge"] = []
            modified = True

        if modified:
            migrated_count += 1

    if migrated_count > 0:
        _write_file(records)

    return migrated_count
