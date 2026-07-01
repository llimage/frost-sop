"""
V0.8.0 集成测试 — 知识库系统全面测试（修订版）
覆盖：模块导入、初始化、文档处理、BM25、向量存储、公开API、CEO注入、代码级验证
"""

import sys
import os
import json
import tempfile
import shutil
import traceback
from pathlib import Path

# Windows 控制台 UTF-8 输出
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# 测试结果收集
results = {"PASS": [], "FAIL": [], "ERROR": [], "SKIP": []}
test_count = {"total": 0, "pass": 0, "fail": 0, "error": 0, "skip": 0}


def record(test_id, status, detail=""):
    """记录测试结果"""
    test_count["total"] += 1
    test_count[status.lower()] += 1
    results[status].append({"id": test_id, "detail": detail})
    icon = {"PASS": "✅", "FAIL": "❌", "ERROR": "💥", "SKIP": "⏭️"}[status]
    print(f"  {icon} [{test_id}] {detail}" if detail else f"  {icon} [{test_id}]")
    sys.stdout.flush()


# ═══════════════════════════════════════════════════════════════
# 第一部分：模块导入测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第一部分：模块导入测试")
print("=" * 70)

# T01: knowledge 包导入
try:
    import knowledge
    record("T01", "PASS", "knowledge 包导入成功")
except Exception as e:
    record("T01", "ERROR", f"knowledge 包导入失败: {e}")

# T02: knowledge 子模块导入
try:
    from knowledge import document_processor
    from knowledge import bm25_index
    from knowledge import vector_store
    record("T02", "PASS", "knowledge 子模块导入成功")
except Exception as e:
    record("T02", "ERROR", f"knowledge 子模块导入失败: {e}")

# T03: agents.ceo 导入
try:
    from agents.ceo import DigitalCEO, set_kb_search_fn
    record("T03", "PASS", "agents.ceo 导入成功，含 set_kb_search_fn")
except Exception as e:
    record("T03", "ERROR", f"agents.ceo 导入失败: {e}")

# T04: data.task_recorder 导入
try:
    from data.task_recorder import save_task, load_all_tasks
    record("T04", "PASS", "data.task_recorder 导入成功")
except Exception as e:
    record("T04", "ERROR", f"data.task_recorder 导入失败: {e}")

# T05: knowledge 公开 API 导入
try:
    from knowledge import (
        init_knowledge_system, list_documents, list_categories,
        add_category, delete_document, get_knowledge_stats,
        rebuild_index, search as kb_search, _detect_backend,
        get_document, delete_category, import_document,
    )
    record("T05", "PASS", "knowledge 公开 API 全部可导入（含 get_document, delete_category, _detect_backend）")
except ImportError as e:
    record("T05", "FAIL", f"knowledge 公开 API 缺失: {e}")

# T06: vector_store 不再有 _detect_backend
try:
    from knowledge.vector_store import _detect_backend as vs_db
    record("T06", "FAIL", "vector_store._detect_backend 仍存在（N-4 未修复）")
except (ImportError, AttributeError):
    record("T06", "PASS", "vector_store._detect_backend 已删除（N-4 修复确认）")


# ═══════════════════════════════════════════════════════════════
# 第二部分：document_processor 测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第二部分：document_processor 测试")
print("=" * 70)

try:
    from knowledge.document_processor import process_document, _smart_chunk, _split_by_sentences

    # T07: 正常文档处理
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# 测试文档\n\n这是第一段内容。包含一些测试文字。\n\n这是第二段内容。更多的测试文字在这里。")
            tmp_path = f.name
        result = process_document(Path(tmp_path), category="test")
        os.unlink(tmp_path)
        if result.get("chunks") and len(result["chunks"]) > 0:
            record("T07", "PASS", f"正常文档处理成功，生成 {len(result['chunks'])} 个 chunks")
        else:
            record("T07", "FAIL", f"正常文档处理返回空 chunks: {result}")
    except Exception as e:
        record("T07", "ERROR", f"正常文档处理异常: {e}")

    # T08: 空 chunk 过滤（S-3 修复验证）
    try:
        empty_text = "   \n\n   \n\n   "
        chunks = _smart_chunk(empty_text, "standard", Path("test.md"))
        if len(chunks) == 0:
            record("T08", "PASS", "S-3 修复验证：全空白文本不产生 chunk")
        else:
            record("T08", "FAIL", f"S-3 未完全修复：全空白文本产生了 {len(chunks)} 个 chunk")
    except Exception as e:
        record("T08", "ERROR", f"空 chunk 测试异常: {e}")

    # T09: 混合空白和有效内容的文本
    try:
        mixed_text = "有效内容。   \n\n   \n\n更多有效内容。"
        chunks = _smart_chunk(mixed_text, "standard", Path("test.md"))
        has_empty = any(not c["content"].strip() for c in chunks)
        if not has_empty and len(chunks) > 0:
            record("T09", "PASS", f"混合文本处理正确，{len(chunks)} 个非空 chunk")
        else:
            record("T09", "FAIL", f"混合文本包含空 chunk 或无有效 chunk")
    except Exception as e:
        record("T09", "ERROR", f"混合文本测试异常: {e}")

    # T10: chunk_id 连续性验证
    try:
        long_text = "这是一个长文本。" * 200
        chunks = _smart_chunk(long_text, "standard", Path("test.txt"))
        ids = [c["chunk_id"] for c in chunks]
        expected = list(range(len(chunks)))
        if ids == expected:
            record("T10", "PASS", f"chunk_id 连续编号正确: {ids[:5]}...")
        else:
            record("T10", "FAIL", f"chunk_id 不连续: {ids}")
    except Exception as e:
        record("T10", "ERROR", f"chunk_id 测试异常: {e}")

    # T11: _split_by_sentences 空字符串过滤
    try:
        result = _split_by_sentences("   ", 100)
        if len(result) == 0:
            record("T11", "PASS", "_split_by_sentences 空白输入返回空列表")
        else:
            record("T11", "FAIL", f"_split_by_sentences 空白输入返回了 {len(result)} 个结果")
    except Exception as e:
        record("T11", "ERROR", f"_split_by_sentences 空白测试异常: {e}")

except Exception as e:
    record("T07-T11", "ERROR", f"document_processor 模块加载失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 第三部分：BM25 索引测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第三部分：BM25 索引测试")
print("=" * 70)

try:
    from knowledge.bm25_index import BM25Index, BM25_DATA_FILE

    # 创建临时目录并重定向 BM25_DATA_FILE
    bm25_test_dir = tempfile.mkdtemp(prefix="bm25_test_")
    original_bm25_data_file = BM25_DATA_FILE

    import knowledge.bm25_index as bm25_mod
    bm25_mod.BM25_DATA_FILE = Path(bm25_test_dir) / "bm25_data.json"

    # T12: BM25Index 初始化
    try:
        bm25 = BM25Index()
        record("T12", "PASS", "BM25Index 初始化成功")
    except Exception as e:
        record("T12", "ERROR", f"BM25Index 初始化失败: {e}")

    # T13: add_document 写入 chunk_ids（S-1 修复验证）
    try:
        bm25 = BM25Index()
        chunks = [
            {"chunk_id": 0, "content": "这是第一个分块的内容，关于产品功能。"},
            {"chunk_id": 1, "content": "这是第二个分块的内容，关于技术架构。"},
            {"chunk_id": 2, "content": "这是第三个分块的内容，关于运营策略。"},
        ]
        bm25.add_document("doc_test_001", chunks, category="test")
        doc_meta = [m for m in bm25.doc_meta if m["doc_id"] == "doc_test_001"]
        if doc_meta and "chunk_ids" in doc_meta[0] and len(doc_meta[0]["chunk_ids"]) == 3:
            record("T13", "PASS", f"S-1 修复验证：add_document 写入 chunk_ids = {doc_meta[0]['chunk_ids']}")
        else:
            record("T13", "FAIL", f"S-1 未修复：doc_meta 缺少 chunk_ids: {doc_meta}")
    except Exception as e:
        record("T13", "ERROR", f"add_document 测试异常: {e}")

    # T14: search 返回 chunk 级内容（S-2 修复验证）
    try:
        results_list = bm25.search("产品功能", top_k=3)
        if results_list:
            first = results_list[0]
            has_chunk_id = "chunk_id" in first
            has_content = "content" in first
            is_chunk_level = len(first.get("content", "")) < 200
            if has_chunk_id and has_content and is_chunk_level:
                record("T14", "PASS", f"S-2 修复验证：search 返回 chunk 级内容 (chunk_id={first.get('chunk_id')})")
            else:
                record("T14", "FAIL", f"S-2 未完全修复：has_chunk_id={has_chunk_id}, content_len={len(first.get('content', ''))}")
        else:
            record("T14", "FAIL", "search 返回空结果")
    except Exception as e:
        record("T14", "ERROR", f"BM25 search 测试异常: {e}")

    # T15: search 去重 key 格式（N-3 修复验证）
    try:
        chunks2 = [
            {"chunk_id": 0, "content": "另一个文档的产品功能描述。"},
            {"chunk_id": 1, "content": "另一个文档的技术架构说明。"},
        ]
        bm25.add_document("doc_test_002", chunks2, category="test")
        results_list = bm25.search("产品功能", top_k=5)
        doc_ids = [r.get("doc_id") for r in results_list]
        if "doc_test_001" in doc_ids and "doc_test_002" in doc_ids:
            record("T15", "PASS", f"N-3 修复验证：跨文档结果未误去重，返回 {len(results_list)} 条")
        else:
            record("T15", "FAIL", f"跨文档搜索结果异常: {doc_ids}")
    except Exception as e:
        record("T15", "ERROR", f"N-3 去重测试异常: {e}")

    # T16: remove_document + _rebuild_chunk_map（S-1 完整验证）
    try:
        bm25.remove_document("doc_test_001")
        remaining_keys = [k for k in bm25.chunk_map.keys() if "doc_test_001" in k]
        if len(remaining_keys) == 0:
            record("T16", "PASS", "remove_document 后 chunk_map 中无残留")
        else:
            record("T16", "FAIL", f"remove_document 后 chunk_map 残留: {remaining_keys}")
    except Exception as e:
        record("T16", "ERROR", f"remove_document 测试异常: {e}")

    # T17: search 删除后结果正确
    try:
        results_list = bm25.search("产品功能", top_k=3)
        doc_ids = [r.get("doc_id") for r in results_list]
        if "doc_test_001" not in doc_ids:
            record("T17", "PASS", "删除文档后搜索结果不再包含该文档")
        else:
            record("T17", "FAIL", "删除文档后搜索仍包含已删文档")
    except Exception as e:
        record("T17", "ERROR", f"删除后搜索测试异常: {e}")

    # 恢复原始路径
    bm25_mod.BM25_DATA_FILE = original_bm25_data_file
    shutil.rmtree(bm25_test_dir, ignore_errors=True)

except Exception as e:
    record("T12-T17", "ERROR", f"BM25Index 模块加载失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 第四部分：向量存储测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第四部分：向量存储测试")
print("=" * 70)

try:
    from knowledge.vector_store import ChromaVectorStore, SQLiteVectorStore, _rrf_fusion, SQLITE_VECTOR_LIMIT

    # T18: _rrf_fusion 公共函数存在（F-2 修复验证）
    try:
        if callable(_rrf_fusion):
            record("T18", "PASS", "F-2 修复验证：_rrf_fusion 公共函数存在且可调用")
        else:
            record("T18", "FAIL", "_rrf_fusion 不可调用")
    except Exception as e:
        record("T18", "ERROR", f"_rrf_fusion 测试异常: {e}")

    # T19: _rrf_fusion 功能验证
    try:
        semantic_results = [
            {"doc_id": "d1", "chunk_id": "c1", "score": 0.9, "content": "语义匹配内容1", "category": "test"},
            {"doc_id": "d2", "chunk_id": "c2", "score": 0.8, "content": "语义匹配内容2", "category": "test"},
        ]
        keyword_results = [
            {"doc_id": "d2", "chunk_id": "c2", "score": 5.0, "content": "关键词匹配内容2", "category": "test"},
            {"doc_id": "d3", "chunk_id": "c3", "score": 4.0, "content": "关键词匹配内容3", "category": "test"},
        ]
        fused = _rrf_fusion(semantic_results, keyword_results, top_k=5, semantic_weight=0.7, keyword_weight=0.3)
        if len(fused) > 0 and ("rrf_score" in fused[0] or "score" in fused[0]):
            record("T19", "PASS", f"RRF 融合返回 {len(fused)} 条结果，top rrf_score={fused[0].get('rrf_score', 0):.6f}")
        else:
            record("T19", "FAIL", f"RRF 融合结果异常: {fused}")
    except Exception as e:
        record("T19", "ERROR", f"_rrf_fusion 功能测试异常: {e}")

    # T20: ChromaVectorStore hybrid_search 方法存在
    try:
        has_method = hasattr(ChromaVectorStore, 'hybrid_search')
        if has_method:
            record("T20", "PASS", "ChromaVectorStore.hybrid_search 方法存在（F-2 修复验证）")
        else:
            record("T20", "FAIL", "ChromaVectorStore 缺少 hybrid_search 方法")
    except Exception as e:
        record("T20", "ERROR", f"ChromaVectorStore 检查异常: {e}")

    # T21: SQLiteVectorStore hybrid_search 方法存在
    try:
        has_method = hasattr(SQLiteVectorStore, 'hybrid_search')
        if has_method:
            record("T21", "PASS", "SQLiteVectorStore.hybrid_search 方法存在（F-2 修复验证）")
        else:
            record("T21", "FAIL", "SQLiteVectorStore 缺少 hybrid_search 方法")
    except Exception as e:
        record("T21", "ERROR", f"SQLiteVectorStore 检查异常: {e}")

    # T22: SQLITE_VECTOR_LIMIT 模块级常量（S-4 修复验证）
    try:
        if SQLITE_VECTOR_LIMIT == 10000:
            record("T22", "PASS", f"S-4 修复验证：SQLITE_VECTOR_LIMIT = {SQLITE_VECTOR_LIMIT}")
        else:
            record("T22", "FAIL", f"SQLITE_VECTOR_LIMIT 值异常: {SQLITE_VECTOR_LIMIT}")
    except Exception as e:
        record("T22", "ERROR", f"SQLITE_VECTOR_LIMIT 检查异常: {e}")

    # T23: SQLiteVectorStore 实例化测试（仅测初始化，跳过 embedding 相关）
    try:
        sqlite_dir = tempfile.mkdtemp(prefix="sqlite_vs_test_")
        sqlite_vs = SQLiteVectorStore(db_path=Path(sqlite_dir))
        # 仅验证初始化成功，不调用 add_chunks（需要 embedding 模型）
        record("T23", "PASS", "SQLiteVectorStore 初始化成功（add_chunks 跳过，需 embedding 模型）")
        shutil.rmtree(sqlite_dir, ignore_errors=True)
    except Exception as e:
        record("T23", "ERROR", f"SQLiteVectorStore 实例化测试异常: {e}")

except Exception as e:
    record("T18-T23", "ERROR", f"vector_store 模块加载失败: {e}")


# ═══════════════════════════════════════════════════════════════
# 第五部分：knowledge 公开 API 集成测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第五部分：knowledge 公开 API 集成测试")
print("=" * 70)

KNOWLEDGE_TEST_ROOT = tempfile.mkdtemp(prefix="kb_integration_test_")

_original_knowledge_dir = None
_original_seed_dir = None
_original_documents_dir = None
_original_bm25_data_file = None
_original_vs_dir = None

try:
    from knowledge import (
        init_knowledge_system, import_document, list_documents,
        list_categories, add_category, delete_category, get_document,
        delete_document, get_knowledge_stats, rebuild_index,
        search as kb_search, _detect_backend,
    )

    # 临时修改 knowledge 模块的路径常量
    import knowledge as kb_mod
    _original_knowledge_dir = kb_mod.KNOWLEDGE_DIR
    _original_seed_dir = kb_mod.SEED_DIR
    _original_documents_dir = kb_mod.DOCUMENTS_DIR

    test_kb_dir = Path(KNOWLEDGE_TEST_ROOT) / "knowledge"
    test_seed_dir = test_kb_dir / "seed"
    test_documents_dir = test_kb_dir / "documents"
    test_vs_dir = test_kb_dir / "vector_store"

    for d in [test_kb_dir, test_seed_dir, test_documents_dir, test_vs_dir]:
        d.mkdir(parents=True, exist_ok=True)

    # 创建种子文档
    (test_seed_dir / "测试种子.md").write_text("# 测试种子文档\n\n这是种子文档的内容，用于测试初始化导入。", encoding="utf-8")

    kb_mod.KNOWLEDGE_DIR = test_kb_dir
    kb_mod.SEED_DIR = test_seed_dir
    kb_mod.DOCUMENTS_DIR = test_documents_dir

    # 同步修改 vector_store 和 bm25_index 的路径常量
    from knowledge import vector_store as vs_mod
    from knowledge import bm25_index as bm25_mod
    _original_vs_dir = vs_mod.VECTOR_STORE_DIR if hasattr(vs_mod, 'VECTOR_STORE_DIR') else None
    _original_bm25_data_file = bm25_mod.BM25_DATA_FILE
    vs_mod.VECTOR_STORE_DIR = test_vs_dir
    bm25_mod.BM25_DATA_FILE = test_kb_dir / "bm25_data.json"

    # T24: _detect_backend 可用
    try:
        backend = _detect_backend()
        if backend in ("chromadb", "sqlite"):
            record("T24", "PASS", f"_detect_backend 返回: {backend}")
        else:
            record("T24", "FAIL", f"_detect_backend 返回异常值: {backend}")
    except Exception as e:
        record("T24", "ERROR", f"_detect_backend 测试异常: {e}")

    # T25: init_knowledge_system 完整初始化
    # 设置离线模式以避免 HuggingFace 网络请求超时
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"

    try:
        result = init_knowledge_system()
        if result:
            record("T25", "PASS", "init_knowledge_system 初始化成功")
        else:
            record("T25", "FAIL", "init_knowledge_system 返回 False")
    except Exception as e:
        record("T25", "ERROR", f"init_knowledge_system 初始化异常: {e}")

    # T26: 初始化后种子文档已导入（时序修复验证）
    try:
        docs = list_documents()
        seed_found = any("种子" in d.get("doc_name", "") or "种子" in d.get("source_path", "") for d in docs)
        if seed_found:
            record("T26", "PASS", "初始化时序验证：种子文档已导入")
        else:
            record("T26", "FAIL", f"种子文档未导入，当前文档列表: {[d.get('doc_name') for d in docs]}")
    except Exception as e:
        record("T26", "ERROR", f"种子文档验证异常: {e}")

    # T27: import_document 完整流程（F-4 修复验证）
    try:
        test_doc_path = Path(KNOWLEDGE_TEST_ROOT) / "测试导入.md"
        test_doc_path.write_text("# 测试导入文档\n\n这是测试导入文档的内容。包含产品功能和运营策略的描述。", encoding="utf-8")
        result = import_document(str(test_doc_path), category="test")
        if result.get("status") == "success" and result.get("chunk_count", 0) > 0:
            record("T27", "PASS", f"F-4 修复验证：import_document 完整流程成功，{result.get('chunk_count')} 个 chunks")
        else:
            record("T27", "FAIL", f"import_document 流程不完整: {result}")
    except Exception as e:
        record("T27", "ERROR", f"import_document 测试异常: {e}")

    # T28: get_document（S-7 修复验证）
    try:
        docs = list_documents()
        if docs:
            doc_id = docs[0].get("doc_id", "")
            doc = get_document(doc_id)
            if doc and doc.get("doc_id") == doc_id:
                record("T28", "PASS", f"get_document 返回正确: doc_id={doc_id}")
            else:
                record("T28", "FAIL", f"get_document 返回异常: {doc}")
        else:
            record("T28", "SKIP", "无文档可测试 get_document")
    except Exception as e:
        record("T28", "ERROR", f"get_document 测试异常: {e}")

    # T29: list_categories 返回 List[Dict]
    try:
        cats = list_categories()
        if isinstance(cats, list) and len(cats) > 0:
            first = cats[0]
            if isinstance(first, dict) and "name" in first:
                record("T29", "PASS", f"list_categories 返回 List[Dict]，{len(cats)} 个分类")
            else:
                record("T29", "FAIL", f"list_categories 元素不是 Dict 或缺少 name: {first}")
        else:
            record("T29", "FAIL", f"list_categories 返回空或格式错误: {cats}")
    except Exception as e:
        record("T29", "ERROR", f"list_categories 测试异常: {e}")

    # T30: add_category
    try:
        add_category("测试分类", description="集成测试用分类")
        cats = list_categories()
        found = any(c.get("name") == "测试分类" for c in cats)
        if found:
            record("T30", "PASS", "add_category 成功")
        else:
            record("T30", "FAIL", f"add_category 后未找到: {[c.get('name') for c in cats]}")
    except Exception as e:
        record("T30", "ERROR", f"add_category 测试异常: {e}")

    # T31: delete_category
    try:
        delete_category("测试分类")
        cats = list_categories()
        found = any(c.get("name") == "测试分类" for c in cats)
        if not found:
            record("T31", "PASS", "delete_category 成功")
        else:
            record("T31", "FAIL", "delete_category 后分类仍存在")
    except Exception as e:
        record("T31", "ERROR", f"delete_category 测试异常: {e}")

    # T32: get_knowledge_stats
    try:
        stats = get_knowledge_stats()
        has_required_keys = all(k in stats for k in ["total_documents", "total_chunks", "backend", "capacity_used_mb"])
        if has_required_keys:
            record("T32", "PASS", f"get_knowledge_stats 完整: docs={stats['total_documents']}, chunks={stats['total_chunks']}, backend={stats['backend']}")
        else:
            record("T32", "FAIL", f"get_knowledge_stats 缺少键: {list(stats.keys())}")
    except Exception as e:
        record("T32", "ERROR", f"get_knowledge_stats 测试异常: {e}")

    # T33: search 功能
    try:
        results_list = kb_search("产品功能", top_k=3)
        if isinstance(results_list, list):
            record("T33", "PASS", f"search 返回 {len(results_list)} 条结果")
        else:
            record("T33", "FAIL", f"search 返回类型错误: {type(results_list)}")
    except Exception as e:
        record("T33", "ERROR", f"search 测试异常: {e}")

    # T34: rebuild_index 返回值（S-5 修复验证）
    try:
        result = rebuild_index()
        if isinstance(result, dict) and "status" in result and "chunk_count" in result:
            record("T34", "PASS", f"S-5 修复验证：rebuild_index 返回 dict: {result}")
        else:
            record("T34", "FAIL", f"rebuild_index 返回值异常: {result}")
    except Exception as e:
        record("T34", "ERROR", f"rebuild_index 测试异常: {e}")

    # T35: delete_document
    try:
        docs = list_documents()
        if docs:
            doc_id = docs[0].get("doc_id", "")
            delete_document(doc_id)
            docs_after = list_documents()
            still_exists = any(d.get("doc_id") == doc_id for d in docs_after)
            if not still_exists:
                record("T35", "PASS", "delete_document 成功")
            else:
                record("T35", "FAIL", "delete_document 后文档仍存在")
        else:
            record("T35", "SKIP", "无文档可测试 delete_document")
    except Exception as e:
        record("T35", "ERROR", f"delete_document 测试异常: {e}")

except Exception as e:
    record("T24-T35", "ERROR", f"knowledge API 测试套件异常: {traceback.format_exc()}")
finally:
    # 恢复原始路径
    import knowledge as kb_mod
    if _original_knowledge_dir:
        kb_mod.KNOWLEDGE_DIR = _original_knowledge_dir
    if _original_seed_dir:
        kb_mod.SEED_DIR = _original_seed_dir
    if _original_documents_dir:
        kb_mod.DOCUMENTS_DIR = _original_documents_dir
    try:
        from knowledge import vector_store as vs_mod
        from knowledge import bm25_index as bm25_mod
        if _original_vs_dir:
            vs_mod.VECTOR_STORE_DIR = _original_vs_dir
        if _original_bm25_data_file:
            bm25_mod.BM25_DATA_FILE = _original_bm25_data_file
    except:
        pass
    shutil.rmtree(KNOWLEDGE_TEST_ROOT, ignore_errors=True)
    # 清理环境变量
    os.environ.pop("HF_HUB_OFFLINE", None)
    os.environ.pop("TRANSFORMERS_OFFLINE", None)


# ═══════════════════════════════════════════════════════════════
# 第六部分：CEO 知识注入测试
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第六部分：CEO 知识注入测试")
print("=" * 70)

# T36: set_kb_search_fn 注入函数
try:
    from agents.ceo import set_kb_search_fn
    import agents.ceo as ceo_mod

    original_fn = ceo_mod._kb_search_fn

    def mock_search(query, top_k=5):
        return [{"doc_id": "mock_1", "content": "模拟结果", "score": 0.9}]

    set_kb_search_fn(mock_search)

    if ceo_mod._kb_search_fn is mock_search:
        record("T36", "PASS", "F-1 修复验证：set_kb_search_fn 注入成功")
    else:
        record("T36", "FAIL", "set_kb_search_fn 注入后 _kb_search_fn 未更新")

    # 恢复原始值
    set_kb_search_fn(original_fn)
except Exception as e:
    record("T36", "ERROR", f"set_kb_search_fn 测试异常: {e}")

# T37: CEO referenced_knowledge 属性（不实例化CEO，仅检查类定义）
try:
    import inspect
    from agents.ceo import DigitalCEO
    # 检查类定义中是否包含 referenced_knowledge
    source = inspect.getsource(DigitalCEO.__init__)
    if "referenced_knowledge" in source:
        record("T37", "PASS", "F-5 修复验证：DigitalCEO.__init__ 包含 referenced_knowledge 初始化")
    else:
        record("T37", "FAIL", "DigitalCEO.__init__ 缺少 referenced_knowledge")
except Exception as e:
    record("T37", "ERROR", f"CEO referenced_knowledge 检查异常: {e}")


# ═══════════════════════════════════════════════════════════════
# 第七部分：task_recorder referenced_knowledge 兼容性
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第七部分：task_recorder referenced_knowledge 兼容性")
print("=" * 70)

# T38: save_task 接受 referenced_knowledge 参数
try:
    from data.task_recorder import save_task
    import inspect
    sig = inspect.signature(save_task)
    has_param = "referenced_knowledge" in sig.parameters
    if has_param:
        record("T38", "PASS", "save_task 包含 referenced_knowledge 参数")
    else:
        record("T38", "FAIL", f"save_task 缺少 referenced_knowledge 参数，签名: {list(sig.parameters.keys())}")
except Exception as e:
    record("T38", "ERROR", f"save_task 签名检查异常: {e}")

# T39: save_task 写入 referenced_knowledge
try:
    from data.task_recorder import save_task
    test_ref = [
        {"doc_id": "doc_001", "doc_name": "测试文档", "chunk_id": "c0", "score": 0.85}
    ]
    task_id = save_task(
        topic="测试referenced_knowledge_V080",
        model="test",
        status="completed",
        execution_time_seconds=1.0,
        final_output="测试输出",
        execution_log="",
        execution_mode="orchestrated",
        referenced_knowledge=test_ref,
    )
    if task_id:
        record("T39", "PASS", f"save_task 含 referenced_knowledge 写入成功，task_id={task_id}")
    else:
        record("T39", "FAIL", "save_task 含 referenced_knowledge 返回空 task_id")
except Exception as e:
    record("T39", "ERROR", f"save_task referenced_knowledge 写入异常: {e}")

# T40: load_all_tasks 读取 referenced_knowledge
try:
    from data.task_recorder import load_all_tasks
    tasks = load_all_tasks()
    # 找到刚写入的测试任务
    test_task = None
    for t in tasks:
        if t.get("topic") == "测试referenced_knowledge_V080":
            test_task = t
            break
    if test_task:
        ref_knowledge = test_task.get("referenced_knowledge", [])
        if ref_knowledge and len(ref_knowledge) > 0:
            record("T40", "PASS", f"load_all_tasks 读取 referenced_knowledge 成功: {ref_knowledge[0].get('doc_id')}")
        else:
            record("T40", "FAIL", f"load_all_tasks 返回的 referenced_knowledge 为空: keys={list(test_task.keys())}")
    else:
        record("T40", "FAIL", "未找到测试任务记录")
except Exception as e:
    record("T40", "ERROR", f"load_all_tasks 读取异常: {e}")


# ═══════════════════════════════════════════════════════════════
# 第八部分：app.py 代码级验证（不启动 Streamlit）
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第八部分：app.py 代码级验证")
print("=" * 70)

# T41: app.py 中 kb_ Session State 初始化（F-3 修复验证）
try:
    app_content = (PROJECT_ROOT / "app.py").read_text(encoding="utf-8")
    kb_state_keys = ["kb_current_category", "kb_show_upload", "kb_show_add_category", "kb_upload_status", "kb_delete_doc_id"]
    missing = [k for k in kb_state_keys if f'st.session_state.{k}' not in app_content]
    if not missing:
        record("T41", "PASS", "F-3 修复验证：app.py 包含全部 5 个 kb_ Session State 初始化")
    else:
        record("T41", "FAIL", f"app.py 缺少 Session State: {missing}")
except Exception as e:
    record("T41", "ERROR", f"app.py Session State 检查异常: {e}")

# T42: _execute_orchestrated 返回 4 元组（F-5 修复验证）
try:
    if "referenced_knowledge = []" in app_content and "return final_output, full_log, error_msg, referenced_knowledge" in app_content:
        record("T42", "PASS", "F-5 修复验证：_execute_orchestrated 返回含 referenced_knowledge 的 4 元组")
    else:
        record("T42", "FAIL", "_execute_orchestrated 未返回 referenced_knowledge")
except Exception as e:
    record("T42", "ERROR", f"_execute_orchestrated 检查异常: {e}")

# T43: save_task 调用包含 referenced_knowledge
try:
    if "referenced_knowledge=referenced_knowledge" in app_content:
        record("T43", "PASS", "app.py save_task 调用包含 referenced_knowledge 参数")
    else:
        record("T43", "FAIL", "app.py save_task 调用缺少 referenced_knowledge 参数")
except Exception as e:
    record("T43", "ERROR", f"save_task 调用检查异常: {e}")

# T44: 不存在 is_seed=False（S-6 修复验证）
try:
    if "is_seed=False" in app_content:
        record("T44", "FAIL", "S-6 未修复：app.py 仍包含 is_seed=False")
    else:
        record("T44", "PASS", "S-6 修复验证：app.py 不再包含 is_seed=False")
except Exception as e:
    record("T44", "ERROR", f"is_seed 检查异常: {e}")

# T45: 重建按钮标签为"重建 BM25 索引"（N-2 修复验证）
try:
    if "重建 BM25 索引" in app_content:
        record("T45", "PASS", "N-2 修复验证：按钮标签改为'重建 BM25 索引'")
    else:
        record("T45", "FAIL", "按钮标签仍为旧名称")
except Exception as e:
    record("T45", "ERROR", f"按钮标签检查异常: {e}")

# T46: app.py 不引用 vector_store._detect_backend（N-4 修复验证）
try:
    if "from knowledge.vector_store import _detect_backend" in app_content:
        record("T46", "FAIL", "N-4 不完整：app.py 仍引用 vector_store._detect_backend")
    else:
        record("T46", "PASS", "N-4 修复验证：app.py 不再引用 vector_store._detect_backend")
except Exception as e:
    record("T46", "ERROR", f"导入检查异常: {e}")

# T47: _handle_file_upload 使用正确签名
try:
    import re
    match = re.search(r'import_document\(tmp_path,\s*category\)', app_content)
    if match:
        record("T47", "PASS", "_handle_file_upload 调用 import_document(tmp_path, category) 签名正确")
    else:
        record("T47", "FAIL", "_handle_file_upload 调用签名可能不正确")
except Exception as e:
    record("T47", "ERROR", f"_handle_file_upload 检查异常: {e}")


# ═══════════════════════════════════════════════════════════════
# 第九部分：需求文档 vs 实现差距验证
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("第九部分：需求文档 vs 实现差距验证")
print("=" * 70)

# T48: 容量限制 1GB
try:
    init_content = (PROJECT_ROOT / "knowledge" / "__init__.py").read_text(encoding="utf-8")
    if "1GB" in init_content or "capacity_limit" in init_content or "1073741824" in init_content:
        record("T48", "PASS", "容量限制 1GB 有实现痕迹")
    else:
        record("T48", "FAIL", "需求缺失：容量限制 1GB 未实现")
except Exception as e:
    record("T48", "ERROR", f"容量限制检查异常: {e}")

# T49: 版本管理
try:
    if ".archive" in init_content and "version" in init_content:
        record("T49", "FAIL", "版本管理有部分实现痕迹，需人工验证完整性")
    else:
        record("T49", "FAIL", "需求缺失：版本管理未实现")
except Exception as e:
    record("T49", "ERROR", f"版本管理检查异常: {e}")

# T50: 敏感信息检测阻塞
try:
    if "sensitivity" in init_content or "sensitive" in init_content:
        record("T50", "FAIL", "敏感信息检测有痕迹但缺少阻塞逻辑")
    else:
        record("T50", "FAIL", "需求缺失：敏感信息检测未实现")
except Exception as e:
    record("T50", "ERROR", f"敏感信息检查异常: {e}")

# T51: 并发文件锁在 import_document
try:
    if "filelock" in init_content.lower() or "FileLock" in init_content:
        record("T51", "PASS", "并发文件锁在 import_document 中有使用")
    else:
        record("T51", "FAIL", "需求缺失：import_document 未加并发文件锁")
except Exception as e:
    record("T51", "ERROR", f"并发锁检查异常: {e}")

# T52: 异常文件 =0.5.0, 存在
try:
    junk_file = PROJECT_ROOT / "=0.5.0,"
    if junk_file.exists():
        record("T52", "FAIL", f"项目根目录存在异常文件: {junk_file.name}（pip参数泄露）")
    else:
        record("T52", "PASS", "项目根目录无异常文件")
except Exception as e:
    record("T52", "ERROR", f"异常文件检查异常: {e}")


# ═══════════════════════════════════════════════════════════════
# 测试结果汇总
# ═══════════════════════════════════════════════════════════════
print("\n" + "=" * 70)
print("测试结果汇总")
print("=" * 70)

total = test_count["total"]
passed = test_count["pass"]
failed = test_count["fail"]
errored = test_count["error"]
skipped = test_count["skip"]
rate = (passed / total * 100) if total > 0 else 0

print(f"\n  总计: {total} 项")
print(f"  ✅ PASS: {passed}")
print(f"  ❌ FAIL: {failed}")
print(f"  💥 ERROR: {errored}")
print(f"  ⏭️  SKIP: {skipped}")
print(f"  通过率: {rate:.1f}%")

if results["FAIL"]:
    print(f"\n  ❌ 失败项 ({len(results['FAIL'])}):")
    for item in results["FAIL"]:
        print(f"    - [{item['id']}] {item['detail']}")

if results["ERROR"]:
    print(f"\n  💥 异常项 ({len(results['ERROR'])}):")
    for item in results["ERROR"]:
        detail = item['detail'][:200]
        print(f"    - [{item['id']}] {detail}")

# 诚实裁决
print(f"\n{'=' * 70}")
if failed == 0 and errored == 0:
    print("🏆 最终裁决：✅ 全部通过")
elif errored == 0 and failed <= 5:
    print(f"🟡 最终裁决：有条件通过（{failed} 项 FAIL，多为需求缺失项）")
else:
    print(f"🔴 最终裁决：不通过（{failed} FAIL + {errored} ERROR），需修复后重新测试")
print(f"{'=' * 70}")

# 输出报告
report_path = PROJECT_ROOT / "tests" / "TEST_REPORT_V080.md"
with open(report_path, "w", encoding="utf-8") as f:
    f.write(f"# V0.8.0 集成测试报告\n\n")
    f.write(f"**测试时间**: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    f.write(f"| 指标 | 数值 |\n|------|------|\n")
    f.write(f"| 总计 | {total} |\n")
    f.write(f"| ✅ PASS | {passed} |\n")
    f.write(f"| ❌ FAIL | {failed} |\n")
    f.write(f"| 💥 ERROR | {errored} |\n")
    f.write(f"| ⏭️ SKIP | {skipped} |\n")
    f.write(f"| 通过率 | {rate:.1f}% |\n\n")

    f.write(f"## 详细结果\n\n")
    for status in ["PASS", "FAIL", "ERROR", "SKIP"]:
        if results[status]:
            f.write(f"### {status}\n\n")
            for item in results[status]:
                f.write(f"- **[{item['id']}]** {item['detail']}\n")
            f.write("\n")

    if failed == 0 and errored == 0:
        f.write("\n**最终裁决**: ✅ 全部通过\n")
    elif errored == 0 and failed <= 5:
        f.write(f"\n**最终裁决**: 🟡 有条件通过（{failed} 项 FAIL）\n")
    else:
        f.write(f"\n**最终裁决**: 🔴 不通过（{failed} FAIL + {errored} ERROR）\n")

print(f"\n报告已保存至: {report_path}")
