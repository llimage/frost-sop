"""
tests/test_degrader.py - 降级管理器测试
Solo-Ops-Platform V0.9.0

覆盖：状态流转、权重调整、手动降级/恢复、回调通知、容器集成
"""
import pytest
import time
from unittest.mock import patch, MagicMock


class TestBackendDegrader:
    """降级管理器核心逻辑测试。"""

    def test_initial_state(self):
        """初始状态：NORMAL。"""
        from resilience.degrader import BackendDegrader, BackendState
        d = BackendDegrader()
        assert d.state == BackendState.NORMAL
        assert d.current_backend == "chromadb"

    def test_normal_weights(self):
        """正常权重：语义0.7 / 关键词0.3。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        weights = d.get_weights()
        assert weights["semantic"] == 0.7
        assert weights["keyword"] == 0.3

    def test_degrade_changes_state(self):
        """降级改变状态。"""
        from resilience.degrader import BackendDegrader, BackendState
        d = BackendDegrader()
        d.degrade("测试降级")
        assert d.state == BackendState.DEGRADED
        assert d.current_backend == "sqlite"

    def test_degraded_weights(self):
        """降级权重：语义0.4 / 关键词0.6。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        d.degrade("测试")
        weights = d.get_weights()
        assert weights["semantic"] == 0.4
        assert weights["keyword"] == 0.6

    def test_recover_changes_state(self):
        """恢复改变状态。"""
        from resilience.degrader import BackendDegrader, BackendState
        d = BackendDegrader()
        d.degrade("测试降级")
        d.recover()
        assert d.state == BackendState.NORMAL
        assert d.current_backend == "chromadb"

    def test_recover_weights_back_to_normal(self):
        """恢复后权重回到正常。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        d.degrade("测试")
        d.recover()
        weights = d.get_weights()
        assert weights["semantic"] == 0.7
        assert weights["keyword"] == 0.3

    def test_double_degrade_noop(self):
        """重复降级无效果。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        d.degrade("第一次")
        d.degrade("第二次")  # 不应该报错
        assert d.state.value == "degraded"

    def test_double_recover_noop(self):
        """重复恢复无效果。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        d.recover()  # 已是 NORMAL，不应该报错
        assert d.state.value == "normal"

    def test_get_status(self):
        """状态查询。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        status = d.get_status()
        assert "state" in status
        assert "backend" in status
        assert "weights" in status


class TestDegraderCallbacks:
    """降级回调测试。"""

    def test_degrade_callback(self):
        """降级触发回调。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        events = []
        d.on_state_change(lambda e: events.append(e))
        d.degrade("测试")
        assert len(events) == 1
        assert events[0]["event"] == "degraded"
        assert events[0]["backend"] == "sqlite"

    def test_recover_callback(self):
        """恢复触发回调。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        events = []
        d.on_state_change(lambda e: events.append(e))
        d.degrade("测试")
        d.recover()
        assert len(events) == 2
        assert events[1]["event"] == "recovered"
        assert events[1]["backend"] == "chromadb"

    def test_callback_exception_doesnt_crash(self):
        """回调异常不影响主流程。"""
        from resilience.degrader import BackendDegrader
        d = BackendDegrader()
        d.on_state_change(lambda e: 1/0)  # 会抛异常
        d.degrade("测试")  # 不应该崩溃
        assert d.state.value == "degraded"


class TestGetDegrader:
    """全局单例测试。"""

    def test_singleton(self):
        """get_degrader 返回单例。"""
        from resilience.degrader import get_degrader
        # 注意：这个测试在单例模式下，可能拿到已有实例
        d1 = get_degrader()
        d2 = get_degrader()
        assert d1 is d2


class TestAppContainer:
    """依赖注入容器测试。"""

    def test_container_singleton(self):
        """容器单例。"""
        from config.container import get_container
        c1 = get_container()
        c2 = get_container()
        assert c1 is c2

    def test_initial_phase(self):
        """初始阶段。"""
        from config.container import AppContainer, InitPhase
        c = AppContainer()
        c.reset()
        assert c.phase == InitPhase.NONE
        assert not c.is_ready

    def test_phase_progression(self):
        """阶段正向流转。"""
        from config.container import AppContainer, InitPhase
        c = AppContainer()
        c.reset()
        c.set_phase(InitPhase.KNOWLEDGE)
        assert c.phase == InitPhase.KNOWLEDGE
        c.set_phase(InitPhase.RESILIENCE)
        assert c.phase == InitPhase.RESILIENCE
        c.set_phase(InitPhase.READY)
        assert c.is_ready

    def test_phase_backwards_raises(self):
        """阶段不可回退。"""
        from config.container import AppContainer, InitPhase
        c = AppContainer()
        c.reset()
        c.set_phase(InitPhase.KNOWLEDGE)
        with pytest.raises(ValueError, match="非法阶段回退"):
            c.set_phase(InitPhase.NONE)

    def test_mark_component(self):
        """组件标记。"""
        from config.container import AppContainer
        c = AppContainer()
        c.reset()
        c.mark_component("knowledge", True)
        status = c.get_status()
        assert status["components"]["knowledge"] is True

    def test_get_status(self):
        """状态查询。"""
        from config.container import AppContainer, InitPhase
        c = AppContainer()
        c.reset()
        c.set_phase(InitPhase.KNOWLEDGE)
        status = c.get_status()
        assert status["phase"] == "knowledge"
        assert not status["is_ready"]


class TestSearchWeightsIntegration:
    """搜索权重集成测试。"""

    def test_get_search_weights_normal(self):
        """正常状态权重。"""
        from knowledge.vector_store import _get_search_weights
        s, k = _get_search_weights(0.7, 0.3)
        # 如果降级器未初始化或状态正常，返回默认权重
        assert 0.0 <= s <= 1.0
        assert 0.0 <= k <= 1.0

    def test_get_search_weights_with_degrader(self):
        """降级状态下权重调整。"""
        from knowledge.vector_store import _get_search_weights
        from resilience.degrader import get_degrader
        d = get_degrader()
        original_state = d.state

        try:
            d.degrade("测试降级")
            s, k = _get_search_weights(0.7, 0.3)
            assert s == 0.4
            assert k == 0.6
        finally:
            # 恢复原状态
            if original_state.value == "normal":
                try:
                    d.recover()
                except Exception:
                    pass
