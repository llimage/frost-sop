"""
PHILOSOPHY:
Asset Store is the root node of the asset hierarchy (parent=None).
It persists project assets (SOPs, Skills, task records).
"""

import json
import os
from core.store import Store, HierarchicalStore


class FileStore(Store):
    """
    Store backed by JSON file.
    """

    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                self._memory = json.load(f)
        else:
            self._memory = {}

    def save(self, key: str, value):
        """Save to memory and persist to file."""
        super().save(key, value)
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(self._memory, f, ensure_ascii=False, indent=2)


def create_asset_store(backend: str = "file", path: str = "data/assets.json") -> HierarchicalStore:
    """
    Create asset store with specified backend.

    Args:
        backend: "file" or "memory"
        path: File path for file backend

    Returns:
        HierarchicalStore instance
    """
    if backend == "file":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        own = FileStore(path)
    else:
        own = Store()

    store = HierarchicalStore(own_store=own, parent=None)
    _init_skill_genes(store)
    return store


def _init_skill_genes(asset_store):
    """初始化九种基础能力基因种子"""
    base_genes = {
        "需求分析": {
            "name": "需求分析",
            "type": "functional",
            "description": "分析用户需求，输出结构化的需求文档",
            "input_keys": ["task_description"],
            "output_keys": ["requirement_doc"],
        },
        "技术设计": {
            "name": "技术设计",
            "type": "functional",
            "description": "根据需求设计技术方案，包括架构、模块划分",
            "input_keys": ["requirement_doc"],
            "output_keys": ["design_doc"],
        },
        "代码生成": {
            "name": "代码生成",
            "type": "functional",
            "description": "根据设计文档生成可运行的代码",
            "input_keys": ["design_doc"],
            "output_keys": ["code_files"],
        },
        "测试验证": {
            "name": "测试验证",
            "type": "functional",
            "description": "编写测试用例，验证代码功能",
            "input_keys": ["code_files"],
            "output_keys": ["test_results"],
        },
        "审查交付": {
            "name": "审查交付",
            "type": "functional",
            "description": "审查代码和文档质量，确保交付标准",
            "input_keys": ["code_files", "docs"],
            "output_keys": ["review_report"],
        },
        "内容创作": {
            "name": "内容创作",
            "type": "functional",
            "description": "创作文字内容，包括文案、文章、脚本",
            "input_keys": ["topic", "style"],
            "output_keys": ["content"],
        },
        "营销策划": {
            "name": "营销策划",
            "type": "functional",
            "description": "制定营销策略和推广方案",
            "input_keys": ["product_info", "target_audience"],
            "output_keys": ["marketing_plan"],
        },
        "财务分析": {
            "name": "财务分析",
            "type": "functional",
            "description": "分析财务数据，生成报表和建议",
            "input_keys": ["financial_data"],
            "output_keys": ["report"],
        },
        "运营优化": {
            "name": "运营优化",
            "type": "functional",
            "description": "分析运营数据，提出流程优化建议",
            "input_keys": ["ops_data"],
            "output_keys": ["optimization_plan"],
        },
    }

    for name, gene in base_genes.items():
        if asset_store.load(f"skill_gene:{name}") is None:
            asset_store.save(f"skill_gene:{name}", gene)
