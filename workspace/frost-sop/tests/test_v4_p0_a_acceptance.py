"""
V4.0 P0-a 验收测试

验证：
- AC-2: 数据采集终端（前4个可写入Store，后2个可导入）
- AC-3: 技能图执行引擎（拓扑排序 + 简化执行）
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

import pytest

# 确保项目根目录在路径中
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestAC2DataCollectors:
    """AC-2: 数据采集终端验证"""

    def setup_method(self):
        """每个测试前创建一个Mock Store"""
        self.mock_store = MagicMock()
        self.mock_store.list_keys.return_value = []
        self.mock_store.load.return_value = None

    def test_collectors_import(self):
        """测试：所有采集终端可导入"""
        from skills.collectors import (
            _write_collected_data,
            collect_audit_data,
            collect_cost_data,
            collect_heartbeat_data,
            collect_hunt_data,
            collect_skill_data,
            collect_task_data,
        )

        assert callable(_write_collected_data)
        assert callable(collect_task_data)
        assert callable(collect_cost_data)
        assert callable(collect_skill_data)
        assert callable(collect_audit_data)
        assert callable(collect_heartbeat_data)
        assert callable(collect_hunt_data)

    def test_write_collected_data(self):
        """测试：_write_collected_data 可写入Store"""
        from skills.collectors import _write_collected_data

        result = _write_collected_data(
            self.mock_store, "test_source", "test_metric", 1.0, {"tag1": "value1"}
        )

        assert result == True
        # 验证 store.store 被调用
        assert self.mock_store.store.called

    def test_collect_task_data(self):
        """测试：collect_task_data 可触发写入Store"""
        from skills.collectors import collect_task_data

        context = {
            "_asset_store": self.mock_store,
            "_task_id": "task_001",
            "_task_status": "completed",
            "_task_start_time": datetime.now().isoformat(),
            "_task_end_time": datetime.now().isoformat(),
        }

        result_context = collect_task_data(context)

        assert "_collector_task_result" in result_context
        assert result_context["_collector_task_result"]["written"] == True

    def test_collect_cost_data(self):
        """测试：collect_cost_data 可触发写入Store"""
        from skills.collectors import collect_cost_data

        context = {
            "_asset_store": self.mock_store,
            "_llm_model": "gpt-4",
            "_llm_input_tokens": 100,
            "_llm_output_tokens": 50,
            "_llm_cost": 0.01,
            "_llm_budget_used": 10.0,
            "_llm_budget_total": 100.0,
            "_task_id": "task_001",
        }

        result_context = collect_cost_data(context)

        assert "_collector_cost_result" in result_context
        assert result_context["_collector_cost_result"]["written"] == True

    def test_collect_skill_data(self):
        """测试：collect_skill_data 可触发写入Store"""
        from skills.collectors import collect_skill_data

        context = {
            "_asset_store": self.mock_store,
            "_skill_name": "test_skill",
            "_skill_status": "success",
            "_skill_duration": 1.5,
            "_skill_error": "",
            "_task_id": "task_001",
        }

        result_context = collect_skill_data(context)

        assert "_collector_skill_result" in result_context
        assert result_context["_collector_skill_result"]["written"] == True

    def test_collect_audit_data(self):
        """测试：collect_audit_data 可触发写入Store"""
        from skills.collectors import collect_audit_data

        context = {
            "_asset_store": self.mock_store,
            "_audit_rule_id": "rule_001",
            "_audit_result": "pass",
            "_audit_triggered": True,
            "_audit_message": "Audit passed",
            "_task_id": "task_001",
        }

        result_context = collect_audit_data(context)

        assert "_collector_audit_result" in result_context
        assert result_context["_collector_audit_result"]["written"] == True

    def test_collect_heartbeat_data_import_only(self):
        """测试：collect_heartbeat_data 可导入（不报错）"""
        from skills.collectors import collect_heartbeat_data

        assert callable(collect_heartbeat_data)

    def test_collect_hunt_data_import_only(self):
        """测试：collect_hunt_data 可导入（不报错）"""
        from skills.collectors import collect_hunt_data

        assert callable(collect_hunt_data)

    def test_data_format(self):
        """测试：写入的数据包含timestamp/source/metric_type/value/tags五个字段"""
        from skills.collectors import _write_collected_data

        _write_collected_data(
            self.mock_store, "test_source", "test_metric", 1.0, {"tag1": "value1"}
        )

        # 获取写入的数据
        call_args = self.mock_store.store.call_args
        written_data = call_args[0][1]  # 第二个参数是data

        # 验证五个字段都存在
        assert "timestamp" in written_data
        assert "source" in written_data
        assert "metric_type" in written_data
        assert "value" in written_data
        assert "tags" in written_data


class TestAC3GraphExecutor:
    """AC-3: 技能图执行引擎验证"""

    def test_graph_executor_import(self):
        """测试：GraphExecutor 可导入"""
        from core.graph_executor import BindingLoader, GraphExecutor, create_graph_executor

        assert callable(BindingLoader)
        assert callable(GraphExecutor)
        assert callable(create_graph_executor)

    def test_binding_loader_default(self):
        """测试：BindingLoader 返回默认绑定（当配置不存在时）"""
        from core.graph_executor import BindingLoader

        loader = BindingLoader(platform="nonexistent_platform")
        binding = loader.load("nonexistent_skill")

        assert binding["platform"] == "nonexistent_platform"
        assert binding["binding_type"] == "native"
        assert "note" in binding

    def test_topological_sort(self):
        """测试：GraphExecutor 拓扑排序正确"""
        from core.graph_executor import GraphExecutor

        # 创建一个简单的DAG
        sop_definition = {
            "name": "Test SOP",
            "nodes": [
                {"id": "A", "type": "skill"},
                {"id": "B", "type": "skill"},
                {"id": "C", "type": "skill"},
            ],
            "edges": [
                {"source": "A", "target": "B"},
                {"source": "B", "target": "C"},
            ],
        }

        executor = GraphExecutor(sop_definition, platform="test")
        sorted_nodes = executor._topological_sort(sop_definition["nodes"], sop_definition["edges"])

        sorted_ids = [node["id"] for node in sorted_nodes]

        # 验证拓扑顺序：A -> B -> C
        assert sorted_ids.index("A") < sorted_ids.index("B")
        assert sorted_ids.index("B") < sorted_ids.index("C")

    def test_topological_sort_diamond(self):
        """测试：GraphExecutor 拓扑排序（菱形依赖）"""
        from core.graph_executor import GraphExecutor

        # 创建菱形DAG: A -> B -> D, A -> C -> D
        sop_definition = {
            "name": "Diamond SOP",
            "nodes": [
                {"id": "A", "type": "skill"},
                {"id": "B", "type": "skill"},
                {"id": "C", "type": "skill"},
                {"id": "D", "type": "skill"},
            ],
            "edges": [
                {"source": "A", "target": "B"},
                {"source": "A", "target": "C"},
                {"source": "B", "target": "D"},
                {"source": "C", "target": "D"},
            ],
        }

        executor = GraphExecutor(sop_definition, platform="test")
        sorted_nodes = executor._topological_sort(sop_definition["nodes"], sop_definition["edges"])

        sorted_ids = [node["id"] for node in sorted_nodes]

        # 验证拓扑顺序：A first, D last
        assert sorted_ids[0] == "A"
        assert sorted_ids[-1] == "D"
        # B和C在A之后、D之前
        assert sorted_ids.index("A") < sorted_ids.index("B")
        assert sorted_ids.index("A") < sorted_ids.index("C")
        assert sorted_ids.index("B") < sorted_ids.index("D")
        assert sorted_ids.index("C") < sorted_ids.index("D")

    @pytest.mark.asyncio
    async def test_execute_simplified(self):
        """测试：GraphExecutor.execute 可运行（简化版，不依赖真实Skill）"""
        from core.graph_executor import GraphExecutor

        # 创建最简单的SOP定义（只有1个节点，无依赖）
        sop_definition = {
            "name": "Simplified SOP",
            "nodes": [
                {
                    "id": "node1",
                    "type": "skill",
                    "skill_id": "test_skill",
                    "conditions": [],  # 无条件，直接执行
                }
            ],
            "edges": [],
        }

        executor = GraphExecutor(sop_definition, platform="test")

        # Mock _execute_skill_node 以避免依赖真实Skill
        async def mock_execute_skill_node(node, context):
            context["_executed_nodes"] = context.get("_executed_nodes", []) + [node["id"]]
            return context

        executor._execute_skill_node = mock_execute_skill_node

        context = {}
        result_context = await executor.execute(context)

        assert "_graph_execution_result" in result_context
        assert result_context["_graph_execution_result"]["executed_nodes"] == ["node1"]


class TestRoutePlatform:
    """路由平台Skill验证"""

    def test_route_platform_import(self):
        """测试：route_platform 可导入"""
        from skills.route_platform import route_platform

        assert callable(route_platform)

    def test_route_platform_default_binding(self):
        """测试：route_platform 返回默认绑定（当配置不存在时）"""
        from skills.route_platform import route_platform

        context = {
            "_skill_id": "nonexistent_skill",
            "_target_platform": "nonexistent_platform",
            "_inputs": {},
        }

        result_context = route_platform(context)

        assert "_execution_plan" in result_context
        plan = result_context["_execution_plan"]
        assert plan["skill_id"] == "nonexistent_skill"
        assert plan["platform"] == "nonexistent_platform"
        assert plan["binding_type"] == "native"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
