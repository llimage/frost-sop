"""
tests/test_capacity.py - 容量限制测试
Solo-Ops-Platform V0.9.0

覆盖：容量常量、缓存机制、超限拒绝、80%预警
"""
import pytest
import time
from unittest.mock import patch


class TestCapacityConstants:
    """容量限制常量测试。"""

    def test_capacity_limit_value(self):
        from knowledge import CAPACITY_LIMIT_MB
        assert CAPACITY_LIMIT_MB == 1024

    def test_warning_ratio_value(self):
        from knowledge import CAPACITY_WARNING_RATIO
        assert CAPACITY_WARNING_RATIO == 0.8

    def test_cache_ttl_value(self):
        from knowledge import CAPACITY_CACHE_TTL
        assert CAPACITY_CACHE_TTL == 60


class TestCapacityCheck:
    """容量检查逻辑测试。"""

    def test_under_limit(self):
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=500.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is False
            assert cap["used_mb"] == 500.0
            assert cap["limit_mb"] == 1024

    def test_exactly_at_limit(self):
        """恰好在限制边界。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=1024.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is False

    def test_over_limit(self):
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=2048.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is False
            assert cap["warning_80"] is True

    def test_warning_threshold(self):
        """80% 预警阈值。"""
        from knowledge import _check_capacity_limit
        # 1024 * 0.8 = 819.2
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=820.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is True

    def test_just_below_warning(self):
        """略低于80%预警。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=819.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is False

    def test_zero_usage(self):
        """零使用量。"""
        from knowledge import _check_capacity_limit
        with patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=0.0):
            cap = _check_capacity_limit()
            assert cap["allowed"] is True
            assert cap["warning_80"] is False
            assert cap["used_mb"] == 0.0


class TestCapacityCache:
    """容量缓存机制测试。"""

    def test_cache_hit(self):
        """缓存命中：60秒内返回缓存值。"""
        from knowledge import _get_knowledge_dir_size_mb_cached
        with patch.dict("knowledge._capacity_cache", {
            "value": 42.0,
            "timestamp": time.time(),
        }):
            assert _get_knowledge_dir_size_mb_cached() == 42.0

    def test_cache_miss(self):
        """缓存未命中：超过60秒重新计算。"""
        from knowledge import _get_knowledge_dir_size_mb_cached
        with patch.dict("knowledge._capacity_cache", {
            "value": 42.0,
            "timestamp": time.time() - 120,  # 2分钟前
        }):
            with patch("knowledge._get_knowledge_dir_size_mb", return_value=55.0):
                assert _get_knowledge_dir_size_mb_cached() == 55.0

    def test_cache_none_value(self):
        """缓存值为None时重新计算。"""
        from knowledge import _get_knowledge_dir_size_mb_cached
        with patch.dict("knowledge._capacity_cache", {
            "value": None,
            "timestamp": time.time(),
        }):
            with patch("knowledge._get_knowledge_dir_size_mb", return_value=33.0):
                assert _get_knowledge_dir_size_mb_cached() == 33.0


class TestCapacityInStats:
    """容量信息在统计API中的测试。"""

    def test_stats_includes_capacity_limit(self):
        from knowledge import get_knowledge_stats
        with patch("knowledge._detect_backend", return_value="sqlite"), \
             patch("knowledge._load_index", return_value={"documents": {}}), \
             patch("knowledge._get_knowledge_dir_size_mb_cached", return_value=50.0):
            stats = get_knowledge_stats()
            assert "capacity_used_mb" in stats
            assert "capacity_limit_mb" in stats
            assert stats["capacity_limit_mb"] == 1024
