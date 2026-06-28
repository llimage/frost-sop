"""
F7 生产加固 - 验收测试
测试 F7 的4个子任务：
1. SQLite持久化
2. ChromaDB集成
3. 成本熔断
4. 常驻Agent
"""
import os
import sys
import pytest
import tempfile
import shutil
from datetime import datetime

# 设置测试环境
os.environ['FROST_TESTING'] = '1'

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def temp_db():
    """创建临时数据库"""
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, 'test_f7.db')
    yield db_path
    try:
        shutil.rmtree(temp_dir)
    except PermissionError:
        pass  # Windows 文件锁定

@pytest.fixture
def temp_chromadb():
    """创建临时ChromaDB目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    try:
        shutil.rmtree(temp_dir)
    except PermissionError:
        pass  # Windows 下 ChromaDB 尚未释放文件句柄

# ==================== 子任务1：SQLite持久化测试 ====================

def test_sqlite_persistence_task(temp_db):
    """测试任务数据持久化到SQLite"""
    try:
        from core.db import DBManager
        from core.store import Store
        
        # 创建数据库和Store
        db = DBManager(db_path=temp_db)
        store = Store(db=db)
        
        # 保存任务
        store.save("task:test_001", {
            "task_id": "test_001",
            "title": "F7测试任务",
            "status": "completed",
            "created_at": datetime.now().isoformat()
        })
        
        # 验证数据已保存
        loaded = store.load("task:test_001")
        assert loaded is not None, "任务数据应该被保存"
        assert loaded["task_id"] == "test_001", "任务ID应该匹配"
        assert loaded["title"] == "F7测试任务", "任务标题应该匹配"
        
        print("[PASS] test_sqlite_persistence_task")
        return True
    except Exception as e:
        print(f"[FAIl] test_sqlite_persistence_task: {e}")
        return False

def test_sqlite_persistence_skill_gene(temp_db):
    """测试技能基因持久化"""
    try:
        from core.db import DBManager
        from core.store import Store
        
        # 创建数据库和Store
        db = DBManager(db_path=temp_db)
        store = Store(db=db)
        
        # 保存技能基因
        gene_data = {
            "name": "Python开发",
            "description": "Python编程能力",
            "category": "开发",
            "tags": ["python", "开发", "后端"]
        }
        store.save("skill_gene:python_dev", gene_data)
        
        # 验证数据已保存
        loaded = store.load("skill_gene:python_dev")
        assert loaded is not None, "技能基因应该被保存"
        assert loaded["name"] == "Python开发", "技能名称应该匹配"
        
        print("[PASS] test_sqlite_persistence_skill_gene")
        return True
    except Exception as e:
        print(f"[FAIl] test_sqlite_persistence_skill_gene: {e}")
        return False

# ==================== 子任务2：ChromaDB集成测试 ====================

def test_chromadb_initialization(temp_chromadb):
    """测试ChromaDB初始化"""
    try:
        from core.memory import MemoryStore
        
        # 创建MemoryStore
        memory = MemoryStore(agent_id="test_agent", persist_directory=temp_chromadb)
        
        # 验证初始化成功
        assert memory is not None, "MemoryStore应该被创建"
        assert memory.agent_id == "test_agent", "agent_id应该匹配"
        
        print("[PASS] test_chromadb_initialization")
        return True
    except Exception as e:
        print(f"[FAIl] test_chromadb_initialization: {e}")
        return False

def test_chromadb_add_and_search(temp_chromadb):
    """测试ChromaDB添加和搜索"""
    try:
        from core.memory import MemoryStore
        
        # 创建MemoryStore
        memory = MemoryStore(agent_id="test_agent", persist_directory=temp_chromadb)
        
        # 添加记忆
        memory.add(
            memory_id="mem_001",
            content="FROST是一个分形智能体框架",
            metadata={"type": "knowledge", "source": "test"}
        )
        
        # 搜索记忆
        results = memory.search(query="分形智能体", top_k=3)
        
        # 验证搜索结果
        assert len(results) > 0, "应该找到至少1条记忆"
        
        print("[PASS] test_chromadb_add_and_search")
        return True
    except Exception as e:
        print(f"[FAIl] test_chromadb_add_and_search: {e}")
        return False

# ==================== 子任务3：成本熔断测试 ====================

def test_cost_tracker_initialization():
    """测试成本跟踪器初始化"""
    try:
        from core.cost import get_cost_tracker
        
        # 获取成本跟踪器
        tracker = get_cost_tracker()
        
        # 验证初始化
        assert tracker is not None, "CostTracker应该被创建"
        assert tracker.monthly_budget > 0, "月度预算应该大于0"
        
        print("[PASS] test_cost_tracker_initialization")
        return True
    except Exception as e:
        print(f"[FAIl] test_cost_tracker_initialization: {e}")
        return False

def test_cost_tracker_budget_check():
    """测试预算检查"""
    try:
        from core.cost import CostTracker
        
        # 创建测试用的跟踪器
        tracker = CostTracker(monthly_budget=100.0)  # 100元预算
        
        # 检查预算（应该通过）
        budget_info = tracker.check_budget()
        assert budget_info["status"] in ["healthy", "warning"], "预算状态应该是healthy或warning"
        
        print("[PASS] test_cost_tracker_budget_check")
        return True
    except Exception as e:
        print(f"[FAIl] test_cost_tracker_budget_check: {e}")
        return False

def test_cost_tracker_exceeded():
    """测试预算超限"""
    try:
        from core.cost import CostTracker, BudgetExceededError
        
        # 创建测试用的跟踪器（预算0.01元，几乎为0）
        tracker = CostTracker(monthly_budget=0.01)
        
        # 模拟已使用预算
        tracker.month_cost = 0.02  # 超过预算
        
        # 检查预算（应该失败）
        try:
            tracker.check_and_throw(agent_id="test", tokens=1000, model="test")
            print("[FAIl] test_cost_tracker_exceeded: 应该抛出BudgetExceededError")
            return False
        except BudgetExceededError:
            # 预期异常
            pass
        
        print("[PASS] test_cost_tracker_exceeded")
        return True
    except Exception as e:
        print(f"[FAIl] test_cost_tracker_exceeded: {e}")
        return False

# ==================== 子任务4：常驻Agent测试 ====================

def test_preloaded_agent_creation():
    """测试预加载Agent创建"""
    try:
        from agents.parent import create_parent
        from agents.elder import create_elder
        from core.store import Store
        
        # 创建Store
        store = Store()
        
        # 预加载父辈Agent
        parent = create_parent("test_parent", store)
        assert parent is not None, "父辈Agent应该被创建"
        
        # 预加载长老Agent
        elder = create_elder("test_elder", asset_store=store)
        assert elder is not None, "长老Agent应该被创建"
        
        print("[PASS] test_preloaded_agent_creation")
        return True
    except Exception as e:
        print(f"[FAIl] test_preloaded_agent_creation: {e}")
        return False

# ==================== 集成测试 ====================

def test_f7_integration():
    """测试F7集成的端到端场景"""
    try:
        from core.db import DBManager
        from core.store import Store
        from core.cost import get_cost_tracker
        
        # 1. 测试SQLite持久化
        db = DBManager()
        store = Store(db=db)
        store.save("task:f7_test", {"test": "F7集成测试"})
        loaded = store.load("task:f7_test")
        assert loaded is not None, "集成测试：SQLite持久化应该工作"
        
        # 2. 测试成本跟踪
        tracker = get_cost_tracker()
        assert tracker is not None, "集成测试：成本跟踪器应该可用"
        
        print("[PASS] test_f7_integration")
        return True
    except Exception as e:
        print(f"[FAIl] test_f7_integration: {e}")
        return False

if __name__ == "__main__":
    """直接运行测试"""
    print("=" * 60)
    print("F7 生产加固 - 验收测试")
    print("=" * 60)
    
    results = []
    
    # 子任务1：SQLite持久化
    print("\n子任务1：SQLite持久化")
    results.append(test_sqlite_persistence_task(temp_db=tempfile.mkdtemp() + "/test.db"))
    results.append(test_sqlite_persistence_skill_gene(temp_db=tempfile.mkdtemp() + "/test.db"))
    
    # 子任务2：ChromaDB集成
    print("\n子任务2：ChromaDB集成")
    results.append(test_chromadb_initialization(temp_chromadb=tempfile.mkdtemp()))
    results.append(test_chromadb_add_and_search(temp_chromadb=tempfile.mkdtemp()))
    
    # 子任务3：成本熔断
    print("\n子任务3：成本熔断")
    results.append(test_cost_tracker_initialization())
    results.append(test_cost_tracker_budget_check())
    results.append(test_cost_tracker_exceeded())
    
    # 子任务4：常驻Agent
    print("\n子任务4：常驻Agent")
    results.append(test_preloaded_agent_creation())
    
    # 集成测试
    print("\n集成测试")
    results.append(test_f7_integration())
    
    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for r in results if r)
    failed = sum(1 for r in results if not r)
    print(f"总测试数: {len(results)}")
    print(f"通过: {passed}")
    print(f"失败: {failed}")
    print(f"通过率: {passed/len(results)*100:.1f}%")
    
    if failed > 0:
        print("\n❌ 部分测试失败")
        sys.exit(1)
    else:
        print("\n✅ 所有测试通过")
        sys.exit(0)
