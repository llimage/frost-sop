"""
PHILOSOPHY:
Store provides basic key-value storage.
HierarchicalStore implements hierarchical model with parent-child relationships,
read-only key protection, and on-demand inheritance.
This is the data foundation of the FROST family model.

F7 更新：增加 SQLite 持久化支持
"""

import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# F7 新增：导入 DBManager
from core.db import get_db, DBManager


class Store:
    """
    PHILOSOPHY: The cell nucleus. Holds memory, does not process.

    F7 更新：增加可选的 SQLite 持久化支持。
    如果提供了 db 参数，则在 save/delete 时同时写入 SQLite。
    """

    def __init__(self, db: DBManager = None):
        """
        初始化存储

        Args:
            db: DBManager 实例（可选）。如果提供，则启用 SQLite 持久化。
        """
        self._memory = {}
        self._db = db

    def save(self, key: str, value):
        """Save a key-value pair to the store and optionally persist to SQLite."""
        self._memory[key] = value

        # F7 新增：如果启用了 SQLite，则持久化
        if self._db is not None:
            self._persist_to_sqlite(key, value)

    def load(self, key: str):
        """Load a value from the store. Returns None if key doesn't exist."""
        return self._memory.get(key, None)

    def delete(self, key: str):
        """Delete a key-value pair from the store."""
        if key in self._memory:
            del self._memory[key]

        # F7 新增：如果启用了 SQLite，则从 SQLite 删除
        if self._db is not None:
            self._delete_from_sqlite(key)

    def list_keys(self) -> list:
        """List all keys in the store."""
        return list(self._memory.keys())

    def _persist_to_sqlite(self, key: str, value):
        """
        将键值对持久化到 SQLite

        策略：
        - 以 "task:" 开头的键 → tasks 表
        - 以 "skill_gene:" 开头的键 → skills 表
        - 以 "sop:" 开头的键 → sop_templates 表
        - 其他 → kv_store 表（通用键值存储）
        """
        try:
            if key.startswith("task:"):
                # 任务数据 → tasks 表
                if isinstance(value, dict):
                    task_id = value.get("id", key.replace("task:", ""))
                    task_data = {
                        "id": task_id,
                        "title": value.get("title", ""),
                        "description": value.get("description", ""),
                        "status": value.get("status", "pending"),
                        "result_summary": json.dumps(value, ensure_ascii=False)
                        if value
                        else None,
                    }
                    self._db.save_task(task_data)
            elif key.startswith("skill_gene:"):
                # 技能数据 → skills 表
                if isinstance(value, dict):
                    skill_id = f"skill_{key}"
                    existing = self._db.select_one("skills", "id", skill_id)
                    if existing:
                        self._db.update(
                            "skills",
                            "id",
                            skill_id,
                            {
                                "name": value.get("name", key),
                                "description": value.get("description", ""),
                                "skill_type": value.get("type", "functional"),
                                "content": json.dumps(value, ensure_ascii=False),
                            },
                        )
                    else:
                        self._db.insert(
                            "skills",
                            {
                                "id": skill_id,
                                "name": value.get("name", key),
                                "description": value.get("description", ""),
                                "skill_type": value.get("type", "functional"),
                                "content": json.dumps(value, ensure_ascii=False),
                            },
                        )
            else:
                # 其他数据 → kv_store 表
                existing = self._db.select_one("kv_store", "key", key)
                if existing:
                    self._db.update(
                        "kv_store",
                        "key",
                        key,
                        {
                            "value": json.dumps(value, ensure_ascii=False),
                            "value_type": type(value).__name__,
                        },
                    )
                else:
                    self._db.insert(
                        "kv_store",
                        {
                            "key": key,
                            "value": json.dumps(value, ensure_ascii=False),
                            "value_type": type(value).__name__,
                        },
                    )
        except Exception as e:
            print(f"⚠️ SQLite 持久化失败: {key} - {e}")

    def _delete_from_sqlite(self, key: str):
        """从 SQLite 删除键值对"""
        try:
            if key.startswith("task:"):
                task_id = key.replace("task:", "")
                self._db.delete("tasks", "id", task_id)
            elif key.startswith("skill_gene:"):
                skill_id = f"skill_{key}"
                self._db.delete("skills", "id", skill_id)
            else:
                self._db.delete("kv_store", "key", key)
        except Exception as e:
            print(f"⚠️ SQLite 删除失败: {key} - {e}")


class HierarchicalStore(Store):
    """
    PHILOSOPHY: Inherited memory. Read-only keys from ancestors protect the constitution.
    """

    def __init__(
        self,
        own_store: Store = None,
        parent: "HierarchicalStore" = None,
        readonly_keys: set = None,
        overrideable_keys: set = None,
    ):
        super().__init__()
        self.own = own_store if own_store is not None else Store()
        self.parent = parent
        self._readonly = readonly_keys if readonly_keys is not None else set()
        self._overrideable = (
            overrideable_keys if overrideable_keys is not None else set()
        )

    def save(self, key: str, value):
        """
        Save a key-value pair.

        Raises:
            PermissionError: If key is in readonly_keys and parent is not None
        """
        if self.parent is not None and key in self._readonly:
            raise PermissionError(f"Key '{key}' is read-only from ancestor")
        self.own.save(key, value)

    def load(self, key: str):
        """
        Load a value. Check local store first, then traverse parent chain.

        Returns:
            The stored value, or None if not found in any level
        """
        val = self.own.load(key)
        if val is not None:
            return val
        if self.parent is not None:
            return self.parent.load(key)
        return None

    def delete(self, key: str):
        """
        Delete a key-value pair.

        Raises:
            PermissionError: If key is in readonly_keys and parent is not None
        """
        if self.parent is not None and key in self._readonly:
            raise PermissionError(f"Key '{key}' is read-only from ancestor")
        self.own.delete(key)

    def list_keys(self) -> list:
        """
        List all keys accessible from this store (including parent chain).

        Returns:
            List of all accessible keys
        """
        keys = set(self.own.list_keys())
        if self.parent is not None:
            keys.update(self.parent.list_keys())
        return list(keys)

    def list_own_keys(self) -> list:
        """
        List only the keys stored in this store (not including parent).

        Returns:
            List of keys in local store
        """
        return self.own.list_keys()

    def merge_from(self, other_store: Store, filter_func=None):
        """
        Copy key-value pairs from another store to local store.

        Args:
            other_store: Another Store or HierarchicalStore to copy from
            filter_func: Optional function that receives key and returns bool.
                        If None, copies nothing (safe default).

        Note:
            Respects readonly_keys constraints during write.
        """
        if filter_func is None:
            return
        for key in other_store.list_keys():
            if filter_func(key):
                value = other_store.load(key)
                self.save(key, value)


class AssetStore:
    """
    F6.5 撒豆成兵 - 配置存储与加载

    负责将系统配置（包括项目结构、SOP选择、任务参数等）保存为JSON文件，
    下次启动驾驶舱时，点击"唤醒"按钮，系统自动加载上次的配置状态。

    F7 更新：改用 SQLite 持久化（config 表）
    """

    def __init__(self, assets_dir="assets/"):
        """
        初始化配置存储

        F7 更新：使用 SQLite 而不是 JSON 文件
        """
        self.assets_dir = assets_dir
        os.makedirs(self.assets_dir, exist_ok=True)
        self._db = get_db()

    def save(self, config: Dict[str, Any], filename: Optional[str] = None) -> str:
        """
        保存配置到 SQLite (config 表)

        Args:
            config: 配置字典
            filename: 文件名（可选，为了兼容性保留，但实际使用 timestamp 作为 key）

        Returns:
            保存的配置 key (config:YYYYMMDD_HHMMSS)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        key = f"config:{timestamp}"

        self._db.insert(
            "config",
            {
                "key": key,
                "value": json.dumps(config, ensure_ascii=False),
                "value_type": "json",
                "description": f"F6.5 撒豆成兵配置 - {config.get('version', 'unknown')}",
            },
        )

        return key

    def load(self, key: str) -> Dict[str, Any]:
        """
        从 SQLite 加载指定的配置

        Args:
            key: 配置 key (config:YYYYMMDD_HHMMSS)

        Returns:
            配置字典
        """
        row = self._db.select_one("config", "key", key)
        if row:
            return json.loads(row["value"])
        else:
            raise ValueError(f"配置不存在: {key}")

    def list(self) -> list:
        """
        列出所有可唤醒的配置

        Returns:
            配置 key 列表（最新的在最前）
        """
        rows = self._db.select_all("config", where="key LIKE ?", params=["config:%"])
        # 按 key 降序排列（最新的在前）
        rows.sort(key=lambda x: x["key"], reverse=True)
        return [row["key"] for row in rows]

    def load_latest(self) -> Optional[Dict[str, Any]]:
        """
        加载最新的配置（用于自动唤醒）

        Returns:
            配置字典，如果没有配置则返回None
        """
        keys = self.list()
        if not keys:
            return None
        return self.load(keys[0])
