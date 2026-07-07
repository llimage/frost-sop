"""
FROST-SOP 统一测试 Fixtures

提供所有测试文件共用的 fixtures：
- temp_db: 临时数据库
- clean_db: 清理后的数据库连接
- mock_store: 模拟 Store
- mock_llm: 模拟 LLM 客户端
- mock_openai: 模拟 OpenAI API
- memory_store: 内存 Store
- sample_sop_yaml: 示例 SOP YAML
- sample_task_config: 示例任务配置
"""

import asyncio
import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Ensure project root is in path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ──────────────────────────────────────────────────────────────
# DB Singleton Reset Helper
# ──────────────────────────────────────────────────────────────


def reset_db_singleton(db_path: str | None = None):
    """
    Reset all DBManager singleton state for test isolation.

    Resets both DBManager._instance (class-level) and
    core.db._db_manager (module-level used by get_db()).
    Call this in setup_class for tests that create their own DB.

    Args:
        db_path: Optional new DB path. If None, uses default.
    """
    import core.db as db_mod

    # Close existing connection if any
    if db_mod._db_manager is not None:
        with contextlib.suppress(Exception):
            db_mod._db_manager.close()

    db_mod.DBManager._instance = None
    db_mod.DBManager._connection = None
    db_mod._db_manager = None
    if db_path:
        db_mod._DB_PATH = db_path


def reset_all_singletons():
    """
    Reset ALL module-level singletons for complete test isolation.

    Call this as an autouse fixture to guarantee no state leaks between tests.
    Resets: DBManager, ArmoryRegistry, EventBus, AsyncEventBus, DecisionFlow.
    """
    # 1. DBManager singleton
    import core.db as db_mod

    if db_mod._db_manager is not None:
        with contextlib.suppress(Exception):
            db_mod._db_manager.close()
    db_mod.DBManager._instance = None
    db_mod.DBManager._connection = None
    db_mod._db_manager = None

    # 2. ArmoryRegistry singleton
    import core.armory as armory_mod

    armory_mod._armory_registry = None

    # 3. EventBus singleton
    try:
        from core.event_bus import AsyncEventBus, EventBus

        EventBus._instance = None
        AsyncEventBus._instance = None
    except ImportError:
        pass

    # 4. DecisionFlow singleton
    try:
        import core.panel_decision as pd_mod

        pd_mod._decision_flow_instance = None
    except (ImportError, AttributeError):
        pass


# ──────────────────────────────────────────────────────────────
# pytest Configuration
# ──────────────────────────────────────────────────────────────


def pytest_configure(config):
    """Register custom markers and configure test environment."""
    markers = [
        ("unit", "Unit tests (fast, no external dependencies)"),
        ("integration", "Integration tests (may use DB/memory backends)"),
        ("e2e", "End-to-end tests (full pipeline)"),
        ("slow", "Slow tests (>5s, may use real LLM)"),
        ("benchmark", "Performance benchmark tests"),
        ("property", "Property-based tests (Hypothesis)"),
        ("load", "Load/stress tests (Locust)"),
        ("security", "Security-related tests"),
        ("asyncio", "Async test (handled by pytest-asyncio auto mode)"),
    ]
    for name, desc in markers:
        config.addinivalue_line("markers", f"{name}: {desc}")


def pytest_collection_modifyitems(config, items):
    """Auto-mark tests based on path/module names."""
    for item in items:
        # Auto-mark based on path
        path_str = str(item.fspath)

        if any(k in path_str for k in ["benchmark", "test_bench"]):
            item.add_marker(pytest.mark.benchmark)
        elif any(k in path_str for k in ["property", "hypothesis"]):
            item.add_marker(pytest.mark.property)
        elif any(k in path_str for k in ["load", "locust"]):
            item.add_marker(pytest.mark.load)
        elif any(k in path_str for k in ["e2e", "acceptance"]):
            item.add_marker(pytest.mark.e2e)
        elif any(k in path_str for k in ["integration", "test_f6_all", "test_f6_sop_e2e"]):
            item.add_marker(pytest.mark.integration)
        else:
            item.add_marker(pytest.mark.unit)

        # Auto-mark slow tests
        if "e2e" in item.name or "integration" in item.name:
            item.add_marker(pytest.mark.slow)


# ──────────────────────────────────────────────────────────────
# Autouse: Singleton Isolation
# ──────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_singletons():
    """Reset all module-level singletons before AND after each test.

    This is the critical test isolation mechanism:
    - DBManager singleton locks to a DB path; if a temp dir is cleaned up,
      the next test gets a stale connection → sqlite3.OperationalError.
    - ArmoryRegistry singleton holds a Store reference that may be stale.
    - EventBus singleton accumulates subscribers across tests.

    By resetting before each test, every test starts with a clean slate.
    By resetting after each test, we clean up any connections opened during
    the test, preventing file-locking on Windows.
    """
    reset_all_singletons()
    yield
    reset_all_singletons()


# ──────────────────────────────────────────────────────────────
# Database Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def temp_dir():
    """Create a temporary directory for file-based tests. Auto-cleanup."""
    d = tempfile.mkdtemp(prefix="frost_test_")
    yield Path(d)
    with contextlib.suppress(PermissionError, OSError):
        shutil.rmtree(d)  # Windows file locking


@pytest.fixture(scope="function")
def temp_db(temp_dir):
    """Create a temporary SQLite database file path."""
    db_path = temp_dir / "test_frost.db"
    yield str(db_path)


@pytest.fixture(scope="function")
def clean_db(temp_db):
    """Create and return a clean DBManager connection for testing.

    Sets FROST_DB_PATH to temp_db, initializes DBManager, yields connection.
    Auto-closes on teardown.
    """
    from core.db import DBManager

    old_path = os.environ.get("FROST_DB_PATH")
    os.environ["FROST_DB_PATH"] = temp_db

    db = DBManager()
    db.initialize()

    yield db

    # Cleanup
    with contextlib.suppress(Exception):
        db.close()

    if old_path:
        os.environ["FROST_DB_PATH"] = old_path
    else:
        os.environ.pop("FROST_DB_PATH", None)


# ──────────────────────────────────────────────────────────────
# Store Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def memory_store():
    """Create an in-memory Store for fast unit tests."""
    from core.store import Store

    return Store(backend="memory")


@pytest.fixture(scope="function")
def mock_store():
    """Create a MagicMock Store with common defaults.

    Override specific methods in your test as needed:
        mock_store.load.return_value = {"key": "value"}
    """
    store = MagicMock()
    store.load.return_value = None
    store.save.return_value = True
    store.delete.return_value = True
    store.list_keys.return_value = []
    store.search.return_value = []
    store.exists.return_value = False
    store.get_all.return_value = {}
    store.prefix = "test:"
    return store


# ──────────────────────────────────────────────────────────────
# LLM Mock Fixtures
# ──────────────────────────────────────────────────────────────

_MOCK_LLM_CONTENT_MAP = {
    "分析以下Agent需求": {
        "agent_type": "test_agent",
        "skills": ["skill_a", "skill_b"],
        "config": {"max_retries": 3},
    },
    "Skill设计助手": {
        "skill_name": "test_skill",
        "gene_data": {"version": "1.0", "inputs": [], "outputs": []},
    },
    "技能匹配专家": {
        "matched_skills": ["skill_a"],
        "confidence": 0.9,
    },
    "请生成": "Generated content for testing purposes.",
    "需求": '{"task_type": "feature", "priority": "high"}',
    "设计": '{"architecture": "modular", "components": ["core", "api"]}',
    "代码": 'def test_func():\n    return "ok"\n',
    "测试": '{"test_cases": [{"name": "test_1", "expected": "pass"}]}',
}


def _generate_mock_content(prompt: str) -> str:
    """Generate mock LLM response based on prompt keywords."""
    for keyword, content in _MOCK_LLM_CONTENT_MAP.items():
        if keyword in prompt:
            if isinstance(content, dict):
                import json

                return json.dumps(content, ensure_ascii=False)
            return content
    return '{"status": "ok", "message": "mock response"}'


def _create_mock_choice(content: str):
    """Create a mock OpenAI ChatCompletionMessage with the given content."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


def _mock_create_side_effect(*args, **kwargs):
    """Side effect for mock OpenAI client.chat.completions.create."""
    messages = kwargs.get("messages", [])
    last_msg = messages[-1]["content"] if messages else ""
    content = _generate_mock_content(last_msg)
    return _create_mock_choice(content)


@pytest.fixture(scope="function")
def mock_llm_client():
    """Create a mock OpenAI-compatible LLM client.

    Returns a MagicMock that responds based on prompt keywords.
    """
    mock_client = MagicMock()
    mock_completions = MagicMock()
    mock_completions.create.side_effect = _mock_create_side_effect
    mock_client.chat.completions = mock_completions
    return mock_client


@pytest.fixture(scope="function")
def patch_openai_fixture(mock_llm_client):
    """Context manager fixture: patches skills.llm.OpenAI with mock client.

    Usage in test:
        def test_something(patch_openai_fixture):
            with patch_openai_fixture:
                result = call_something_using_llm()
                assert result is not None
    """
    return patch("skills.llm.OpenAI", return_value=mock_llm_client, create=True)


@pytest.fixture(scope="function")
def mock_openai(monkeypatch, mock_llm_client):
    """Auto-applied mock: patches skills.llm.OpenAI (function scope).

    Automatically patches OpenAI in skills.llm for the test.
    No manual 'with' block needed.
    """
    monkeypatch.setattr(
        "skills.llm.OpenAI",
        lambda *a, **kw: mock_llm_client,
    )
    return mock_llm_client


# ──────────────────────────────────────────────────────────────
# SOP & Task Fixtures
# ──────────────────────────────────────────────────────────────

_SAMPLE_SOP_YAML = """
sop_id: DEV-001
name: 新功能开发
description: 标准新功能开发流程
version: "1.0"
phases:
  - phase_id: phase_1
    name: 需求分析
    description: 分析并确认需求
    inputs: [task_description]
    outputs: [requirement_doc]
    skill: analyze_requirements
  - phase_id: phase_2
    name: 设计
    description: 系统设计与架构
    inputs: [requirement_doc]
    outputs: [design_doc]
    skill: system_design
  - phase_id: phase_3
    name: 实现
    description: 代码实现
    inputs: [design_doc]
    outputs: [code_artifacts]
    skill: implement_code
"""


@pytest.fixture(scope="session")
def sample_sop_yaml() -> str:
    """Sample SOP YAML content for testing."""
    return _SAMPLE_SOP_YAML


@pytest.fixture(scope="function")
def sample_sop_file(temp_dir):
    """Create a temporary SOP YAML file on disk."""
    sop_path = temp_dir / "DEV-001.yaml"
    sop_path.write_text(_SAMPLE_SOP_YAML, encoding="utf-8")
    return str(sop_path)


@pytest.fixture(scope="function")
def sample_task_config():
    """Sample task configuration dict for testing."""
    return {
        "task_id": "task_test_001",
        "task_type": "feature_development",
        "sop_id": "DEV-001",
        "description": "实现用户登录功能",
        "priority": "high",
        "tags": ["auth", "security"],
    }


# ──────────────────────────────────────────────────────────────
# Event Bus Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="function")
def clean_event_bus():
    """Create a fresh EventBus instance (v2.0)."""
    from core.event_bus import EventBus

    EventBus.reset()
    return EventBus()


@pytest.fixture(scope="function")
def clean_async_event_bus():
    """Create a fresh AsyncEventBus instance (v3.0)."""
    from core.event_bus import AsyncEventBus

    AsyncEventBus.reset()
    return AsyncEventBus()


# ──────────────────────────────────────────────────────────────
# Async Helpers
# ──────────────────────────────────────────────────────────────


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_setup():
    """Async setup fixture for tests needing an initialized async context."""
    yield
