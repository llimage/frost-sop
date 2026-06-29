"""
FROST V5.0 面板数据提供者——StoreDataProvider 实现

PHILOSOPHY: 面板与后端数据的唯一连接点。
根据 data_source 标识符从 Store 获取实际数据，支持所有 FROST 键前缀规则。

数据格式规范：
- "task.{field}"        → 从当前任务 Store 中获取字段（需要 task_id 上下文）
- "task.stages[{n}]"    → 从当前任务获取第n个阶段
- "intel:{key}"         → 直接从 Store 读取 intel: 前缀键
- "family:{key}"        → 直接从 Store 读取 family: 前缀键
- "immune:{key}"        → 直接从 Store 读取 immune: 前缀键
- "armory:{weapon_id}"  → 从武器库获取武器元数据
- "decision:{id}"       → 从决策记录 Store 获取决策状态
- "panel:{panel_id}"    → 从面板状态 Store 获取面板状态
"""

from typing import Any, Dict, Optional, List

from core.panel_renderer import DataProvider
from core.store import Store


class StoreDataProvider(DataProvider):
    """
    Store 数据提供者——面板渲染引擎与 FROST 后端数据的桥梁。

    使用方式：
        provider = StoreDataProvider(store, task_id="task:xxx")
        data = provider.get("task.status")
        # → store.get("task:xxx")["status"]

    支持的数据源格式：
    1. "task.{field}"        — 从当前任务获取字段
    2. "task.stages[{n}]"   — 从当前任务获取第n阶段（支持切片 stages[:3]）
    3. "{prefix}:{key}"     — 直接从 Store 读取（intel:/family:/immune:/decision:/panel:）
    4. "armory:{weapon_id}" — 从武器库获取武器元数据
    """

    def __init__(self, store: Store, task_id: Optional[str] = None,
                 armory_registry=None, decision_flow=None):
        """
        初始化数据提供者。

        Args:
            store: Store 实例（核心存储）
            task_id: 当前任务ID（可选，用于解析 "task.*" 数据源）
            armory_registry: 武器库注册表（可选，用于解析 "armory:*" 数据源）
            decision_flow: 决策流程（可选，用于解析 "decision:*" 数据源）
        """
        self.store = store
        self.task_id = task_id
        self.armory = armory_registry
        self.decision_flow = decision_flow

    def get(self, data_source: str, data_binding: str = "") -> Any:
        """
        根据 data_source 获取实际数据。

        Args:
            data_source: 数据源标识符（如 "task.status", "intel:strategist_brief"）
            data_binding: 数据绑定路径（如 "stages[0].output"，用于进一步导航）

        Returns:
            实际数据，如果未找到返回 None
        """
        if not data_source:
            return None

        # 1. 解析 data_source 格式
        raw_data = self._resolve_data_source(data_source)
        if raw_data is None:
            return None

        # 2. 如果提供了 data_binding，进一步导航到子字段
        if data_binding:
            return self._navigate_path(raw_data, data_binding)

        return raw_data

    def _resolve_data_source(self, data_source: str) -> Any:
        """解析数据源标识符，获取原始数据"""

        # 格式1: "task.{field}" — 从当前任务获取字段
        if data_source.startswith("task."):
            return self._resolve_task_field(data_source)

        # 格式2: "{prefix}:{key}" — 直接从 Store 读取
        if ":" in data_source:
            prefix, key = data_source.split(":", 1)
            return self._resolve_prefixed_key(prefix, key)

        # 格式3: 未知格式，尝试直接从 Store 读取
        if self.store is not None:
            return self.store.load(data_source)
        return None

    def _resolve_task_field(self, data_source: str) -> Any:
        """
        解析 "task.{field}" 格式。

        示例：
        - "task.status" → task_dict["status"]
        - "task.stages" → task_dict["stages"]
        - "task.stages[0]" → task_dict["stages"][0]
        - "task.stages[0].name" → task_dict["stages"][0]["name"]
        - "task.current_stage" → task_dict["stages"][current_stage_index]
        - "task.quality_score" → task_dict["quality_score"]
        """
        if not self.task_id or self.store is None:
            return None

        # 获取任务数据
        task_data = self.store.load(self.task_id)
        if not isinstance(task_data, dict):
            return None

        # 去掉 "task." 前缀，得到字段路径
        field_path = data_source[5:]  # "task.status" → "status"

        # 处理特殊字段：current_stage
        if field_path == "current_stage":
            stages = task_data.get("stages", [])
            current_idx = task_data.get("current_stage_index", 0)
            if 0 <= current_idx < len(stages):
                return stages[current_idx]
            return None

        # 处理路径导航（如 "stages[0].name"）
        return self._navigate_path(task_data, field_path)

    def _resolve_prefixed_key(self, prefix: str, key: str) -> Any:
        """解析带前缀的键"""

        # 如果 store 为 None，所有需要查 Store 的前缀都返回 None
        if self.store is None:
            return None

        # 2.1: intel: — 情报数据
        if prefix == "intel":
            full_key = f"intel:{key}"
            return self.store.load(full_key)

        # 2.2: family: — 家族数据
        if prefix == "family":
            full_key = f"family:{key}"
            return self.store.load(full_key)

        # 2.3: immune: — 免疫数据
        if prefix == "immune":
            full_key = f"immune:{key}"
            return self.store.load(full_key)

        # 2.4: decision: — 决策记录
        if prefix == "decision":
            if self.decision_flow:
                record = self.decision_flow.records.get(f"decision:{key}")
                if record:
                    return record.to_dict() if hasattr(record, "to_dict") else record.__dict__
            # 回退到 Store
            return self.store.load(f"decision:{key}")

        # 2.5: panel: — 面板状态
        if prefix == "panel":
            return self.store.load(f"panel:{key}")

        # 2.6: armory: — 武器库查询
        if prefix == "armory":
            if self.armory:
                weapon = self.armory.get(key)
                if weapon:
                    return weapon.to_dict()
            return None

        # 2.7: task: — 其他任务（非当前任务）
        if prefix == "task":
            return self.store.load(f"task:{key}")

        # 2.8: 未知前缀，尝试直接读取
        return self.store.load(f"{prefix}:{key}")

    def _navigate_path(self, data: Any, path: str) -> Any:
        """
        在数据结构中导航路径。

        示例：
        - data={"a": {"b": 1}}, path="a.b" → 1
        - data={"stages": [{"name": "x"}]}, path="stages[0].name" → "x"
        - data={"items": [1,2,3]}, path="items[:2]" → [1,2]
        """
        if not path:
            return data

        current = data
        parts = self._split_path(path)

        for part in parts:
            if current is None:
                return None

            # 处理数组索引：stages[0], stages[-1], stages[:3]
            if "[" in part and "]" in part:
                base, idx_str = part.split("[", 1)
                idx_str = idx_str.rstrip("]")

                # 先获取基础字段
                if base:
                    if isinstance(current, dict):
                        current = current.get(base)
                    else:
                        return None

                # 再解析索引
                if idx_str == ":":
                    # 取全部
                    pass
                elif idx_str.startswith(":"):
                    # 切片 [:n]
                    try:
                        n = int(idx_str[1:])
                        if isinstance(current, (list, tuple)):
                            current = current[:n]
                    except ValueError:
                        return None
                elif idx_str.endswith(":"):
                    # 切片 [n:]
                    try:
                        n = int(idx_str[:-1])
                        if isinstance(current, (list, tuple)):
                            current = current[n:]
                    except ValueError:
                        return None
                else:
                    # 单索引 [n]
                    try:
                        n = int(idx_str)
                        if isinstance(current, (list, tuple)):
                            if 0 <= n < len(current):
                                current = current[n]
                            else:
                                return None
                        else:
                            return None
                    except ValueError:
                        return None

            elif isinstance(current, dict):
                current = current.get(part)
            else:
                return None

        return current

    def _split_path(self, path: str) -> List[str]:
        """分割路径字符串，支持点号分隔"""
        # 处理 stages[0].name → ["stages[0]", "name"]
        parts = []
        current = ""
        in_bracket = False

        for char in path:
            if char == "[":
                in_bracket = True
                current += char
            elif char == "]":
                in_bracket = False
                current += char
            elif char == "." and not in_bracket:
                if current:
                    parts.append(current)
                current = ""
            else:
                current += char

        if current:
            parts.append(current)

        return parts


# ────────────────────────────────────────────────────────────────────────────
# 便捷函数
# ────────────────────────────────────────────────────────────────────────────

def create_data_provider(store: Store, task_id: Optional[str] = None,
                         armory_registry=None, decision_flow=None) -> StoreDataProvider:
    """便捷函数：创建 StoreDataProvider"""
    return StoreDataProvider(
        store=store,
        task_id=task_id,
        armory_registry=armory_registry,
        decision_flow=decision_flow,
    )
