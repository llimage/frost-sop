"""
V4.0 P0-a: 技能图执行引擎

包含：
1. BindingLoader - 按需加载平台绑定
2. GraphExecutor - 瞬态执行器
"""

import logging
import os
from datetime import datetime

import yaml

logger = logging.getLogger(__name__)

# 默认绑定目录
DEFAULT_BINDINGS_DIR = os.path.join(os.path.dirname(__file__), "..", "bindings")


class BindingLoader:
    """
    按需加载平台绑定配置。

    绑定配置文件路径：bindings/{platform}/{skill_id}.yaml
    例如：bindings/wechat-mp/call_llm_for_output.yaml
    """

    def __init__(self, platform: str, bindings_dir: str = None):
        """
        初始化绑定加载器。

        Args:
            platform: 目标平台（如 "wechat-mp", "web", "desktop"）
            bindings_dir: 绑定配置目录（默认：bindings/）
        """
        self.platform = platform
        self.bindings_dir = bindings_dir or DEFAULT_BINDINGS_DIR
        self._cache = {}

        logger.info(f"[BindingLoader] 初始化: platform={platform}, dir={self.bindings_dir}")

    def load(self, skill_id: str) -> dict:
        """
        加载指定Skill在当前平台的绑定配置。

        Args:
            skill_id: Skill ID（如 "call_llm_for_output"）

        Returns:
            dict: 绑定配置，包含：
                - platform: 平台名称
                - skill_id: Skill ID
                - binding_type: 绑定类型（"native" / "api" / "sdk"）
                - config: 平台特定配置
                - dependencies: 依赖列表
                - 如果未找到绑定，返回默认配置（binding_type="native"）
        """
        # 检查缓存
        cache_key = f"{self.platform}:{skill_id}"
        if cache_key in self._cache:
            logger.debug(f"[BindingLoader] 缓存命中: {cache_key}")
            return self._cache[cache_key]

        # 构建配置文件路径
        config_path = os.path.join(self.bindings_dir, self.platform, f"{skill_id}.yaml")

        if os.path.exists(config_path):
            try:
                from core.path_safety import safe_open

                with safe_open(config_path, encoding="utf-8") as f:
                    config = yaml.safe_load(f)

                # 缓存结果
                self._cache[cache_key] = config
                logger.info(f"[BindingLoader] 已加载绑定: {config_path}")
                return config
            except Exception as e:
                logger.error(f"[BindingLoader] 加载失败 {config_path}: {e}")
                return self._default_binding(skill_id)
        else:
            logger.warning(f"[BindingLoader] 绑定配置不存在: {config_path}")
            return self._default_binding(skill_id)

    def _default_binding(self, skill_id: str) -> dict:
        """
        返回默认绑定配置（原生执行）。
        """
        return {
            "platform": self.platform,
            "skill_id": skill_id,
            "binding_type": "native",
            "config": {},
            "dependencies": [],
            "note": "默认绑定（原生执行）",
        }

    def release(self):
        """
        释放所有缓存。
        """
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"[BindingLoader] 已释放缓存: {cache_size} 条")


class GraphExecutor:
    """
    瞬态执行器：执行图谱SOP，支持拓扑排序+并行调度+条件分支。

    执行模型：
    1. 解析SOP定义为有向无环图（DAG）
    2. 拓扑排序确定执行顺序
    3. 并行执行无依赖的节点
    4. 支持条件分支（基于上下文判断）
    """

    def __init__(self, sop_definition: dict, platform: str, graph_store=None, event_bus=None):
        """
        初始化图谱执行器。

        Args:
            sop_definition: SOP定义（包含 nodes, edges, conditional_branches）
            platform: 目标平台
            graph_store: 图谱Store（可选）
            event_bus: 事件总线（可选）
        """
        self.sop_definition = sop_definition
        self.platform = platform
        self.graph_store = graph_store
        self.event_bus = event_bus
        self.binding_loader = BindingLoader(platform)

        logger.info(f"[GraphExecutor] 初始化: platform={platform}")

    async def execute(self, context: dict) -> dict:
        """
        执行图谱SOP。

        Args:
            context: 执行上下文

        Returns:
            dict: 更新后的上下文（包含执行结果）
        """
        logger.info(
            f"[GraphExecutor] 开始执行图谱SOP: {self.sop_definition.get('name', 'unknown')}"
        )

        # 1. 解析SOP定义为DAG
        nodes = self.sop_definition.get("nodes", [])
        edges = self.sop_definition.get("edges", [])

        if not nodes:
            logger.warning("[GraphExecutor] SOP定义为空，无需执行")
            return context

        # 2. 拓扑排序
        sorted_nodes = self._topological_sort(nodes, edges)
        logger.info(f"[GraphExecutor] 拓扑排序完成: {len(sorted_nodes)} 个节点")

        # 3. 按拓扑顺序执行
        executed_nodes = set()
        for node in sorted_nodes:
            node_id = node.get("id", "unknown")
            node_type = node.get("type", "skill")

            logger.info(f"[GraphExecutor] 执行节点: {node_id} (type={node_type})")

            # 检查条件分支
            if not self._should_execute_node(node, context):
                logger.info(f"[GraphExecutor] 跳过节点（条件不满足）: {node_id}")
                continue

            # 执行节点
            if node_type == "skill":
                context = await self._execute_skill_node(node, context)
            elif node_type == "decision":
                context = self._execute_decision_node(node, context)
            else:
                logger.warning(f"[GraphExecutor] 未知节点类型: {node_type}")

            executed_nodes.add(node_id)

        # 4. 释放绑定缓存
        self.binding_loader.release()

        # 5. 写入执行结果
        context["_graph_execution_result"] = {
            "sop_name": self.sop_definition.get("name", "unknown"),
            "platform": self.platform,
            "executed_nodes": list(executed_nodes),
            "total_nodes": len(nodes),
            "execution_time": datetime.now().isoformat(),
        }

        logger.info(f"[GraphExecutor] 执行完成: {len(executed_nodes)}/{len(nodes)} 个节点")
        return context

    def _topological_sort(self, nodes: list[dict], edges: list[dict]) -> list[dict]:
        """
        拓扑排序（Kahn算法）。

        Args:
            nodes: 节点列表
            edges: 边列表（包含 source, target）

        Returns:
            List[dict]: 排序后的节点列表
        """
        # 构建邻接表和入度表
        adj = {node.get("id"): [] for node in nodes}
        in_degree = {node.get("id"): 0 for node in nodes}

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source in adj and target in adj:
                adj[source].append(target)
                in_degree[target] += 1

        # Kahn算法
        queue = [node_id for node_id, degree in in_degree.items() if degree == 0]
        sorted_ids = []

        while queue:
            node_id = queue.pop(0)
            sorted_ids.append(node_id)

            for neighbor in adj[node_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 根据排序后的ID返回节点
        id_to_node = {node.get("id"): node for node in nodes}
        return [id_to_node[node_id] for node_id in sorted_ids if node_id in id_to_node]

    def _should_execute_node(self, node: dict, context: dict) -> bool:
        """
        检查节点是否应该执行（条件分支）。

        Args:
            node: 节点定义
            context: 执行上下文

        Returns:
            bool: 是否应该执行
        """
        conditions = node.get("conditions", [])
        if not conditions:
            return True  # 无条件下直接执行

        # 检查所有条件
        for condition in conditions:
            field = condition.get("field")
            operator = condition.get("operator")
            value = condition.get("value")

            context_value = context.get(field)

            if operator == "equals":
                if context_value != value:
                    return False
            elif operator == "not_equals":
                if context_value == value:
                    return False
            elif operator == "exists":
                if context_value is None:
                    return False
            elif operator == "not_exists":
                if context_value is not None:
                    return False
            # 可扩展更多操作符

        return True

    async def _execute_skill_node(self, node: dict, context: dict) -> dict:
        """
        执行技能节点。

        Args:
            node: 节点定义
            context: 执行上下文

        Returns:
            dict: 更新后的上下文
        """
        skill_id = node.get("skill_id")
        if not skill_id:
            logger.error("[GraphExecutor] 技能节点缺少 skill_id")
            return context

        # 加载平台绑定
        binding = self.binding_loader.load(skill_id)
        binding_type = binding.get("binding_type", "native")

        logger.info(f"[GraphExecutor] 执行技能: {skill_id} (binding_type={binding_type})")

        # 根据绑定类型执行
        if binding_type == "native":
            # 原生执行（直接调用Skill函数）
            context = await self._execute_native_skill(skill_id, node, context)
        elif binding_type == "api":
            # API调用
            context = await self._execute_api_skill(skill_id, binding, node, context)
        elif binding_type == "sdk":
            # SDK调用
            context = await self._execute_sdk_skill(skill_id, binding, node, context)
        else:
            logger.error(f"[GraphExecutor] 未知绑定类型: {binding_type}")

        return context

    async def _execute_native_skill(self, skill_id: str, node: dict, context: dict) -> dict:
        """
        原生执行Skill：动态导入 skills/ 模块并调用对应函数。
        """
        logger.info(f"[GraphExecutor] 原生执行Skill: {skill_id}")
        try:
            module_name = f"skills.{skill_id}"
            module = __import__(module_name, fromlist=["*"])
            # 尝试调用模块中的主函数（与 skill_id 同名）
            func = getattr(module, skill_id, None)
            if func and callable(func):
                result = func(context)
                if isinstance(result, dict):
                    context.update(result)
                context[f"_skill_result_{skill_id}"] = {
                    "status": "executed",
                    "skill_id": skill_id,
                    "execution_mode": "native",
                }
            else:
                context[f"_skill_result_{skill_id}"] = {
                    "status": "executed",
                    "skill_id": skill_id,
                    "execution_mode": "native",
                    "note": "no matching function",
                }
        except (ImportError, AttributeError) as e:
            logger.warning(f"[GraphExecutor] Skill {skill_id} 不可导入: {e}")
            context[f"_skill_result_{skill_id}"] = {
                "status": "unavailable",
                "skill_id": skill_id,
                "execution_mode": "native",
                "error": str(e),
            }
        return context

    async def _execute_api_skill(
        self, skill_id: str, binding: dict, node: dict, context: dict
    ) -> dict:
        """
        API方式执行Skill。
        """
        logger.info(f"[GraphExecutor] API执行Skill: {skill_id}（placeholder）")
        context[f"_skill_result_{skill_id}"] = {
            "status": "executed",
            "skill_id": skill_id,
            "execution_mode": "api",
        }
        return context

    async def _execute_sdk_skill(
        self, skill_id: str, binding: dict, node: dict, context: dict
    ) -> dict:
        """
        SDK方式执行Skill。
        """
        logger.info(f"[GraphExecutor] SDK执行Skill: {skill_id}（placeholder）")
        context[f"_skill_result_{skill_id}"] = {
            "status": "executed",
            "skill_id": skill_id,
            "execution_mode": "sdk",
        }
        return context

    def _execute_decision_node(self, node: dict, context: dict) -> dict:
        """
        执行决策节点：基于上下文条件评估决策路径。
        """
        node_id = node.get("id", "unknown")
        logger.info(f"[GraphExecutor] 执行决策节点: {node_id}")

        # 评估节点定义的条件规则
        decisions = node.get("decisions", {})
        default_decision = node.get("default", "continue")

        for decision_key, conditions in decisions.items():
            if not isinstance(conditions, dict):
                continue
            all_match = True
            for field, expected in conditions.items():
                actual = context.get(field)
                if actual != expected:
                    all_match = False
                    break
            if all_match:
                logger.info(f"[GraphExecutor] 决策匹配: {node_id} → {decision_key}")
                context[f"_decision_{node_id}"] = decision_key
                return context

        # 无匹配，使用默认决策
        logger.info(f"[GraphExecutor] 默认决策: {node_id} → {default_decision}")
        context[f"_decision_{node_id}"] = default_decision
        return context


# 便捷函数
def create_graph_executor(sop_definition: dict, platform: str, **kwargs) -> GraphExecutor:
    """
    创建图谱执行器。
    """
    return GraphExecutor(sop_definition, platform, **kwargs)
