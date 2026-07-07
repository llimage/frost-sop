"""
V6.0.1 测试: stores/asset.py 运营基因初始化
验证 P0-002 修复：基因库包含12个基因（9旧+3新）
"""

import os

import pytest

os.environ["FROST_TESTING"] = "1"


@pytest.fixture
def fresh_store():
    """创建全新的 memory-store（隔离每次测试）"""
    from stores.asset import create_asset_store

    return create_asset_store(backend="memory")


class TestAssetV601:
    """运营基因初始化测试"""

    def test_gene_count(self, fresh_store):
        """TC-001: 创建asset_store -> 检查12个基因（9旧+3新）"""
        store = fresh_store
        genes = [k for k in store.list_keys() if k.startswith("skill_gene:")]
        gene_names = [k.replace("skill_gene:", "") for k in genes]
        assert len(genes) == 12, f"期望12个基因，实际{len(genes)}: {gene_names}"

    def test_no_duplicate_init(self, fresh_store):
        """TC-002: 重复创建 -> 不重复初始化（已存在的不覆盖）"""
        from stores.asset import _init_skill_genes

        store = fresh_store
        genes_before = len([k for k in store.list_keys() if k.startswith("skill_gene:")])

        # 再次初始化
        _init_skill_genes(store)
        genes_after = len([k for k in store.list_keys() if k.startswith("skill_gene:")])

        assert genes_before == genes_after == 12

    def test_redbook_gene_exists(self, fresh_store):
        """TC-003: 小红书运营基因 -> skill_gene:小红书运营 存在"""
        store = fresh_store
        gene = store.load("skill_gene:小红书运营")
        assert gene is not None
        assert gene["name"] == "小红书运营"
        assert "小红书" in gene["description"]

    def test_juejin_gene_exists(self, fresh_store):
        """TC-004: 掘金发布基因 -> skill_gene:掘金发布 存在"""
        store = fresh_store
        gene = store.load("skill_gene:掘金发布")
        assert gene is not None
        assert gene["name"] == "掘金发布"
        assert "掘金" in gene["description"]

    def test_email_gene_exists(self, fresh_store):
        """TC-005: 邮件Newsletter基因 -> skill_gene:邮件Newsletter 存在"""
        store = fresh_store
        gene = store.load("skill_gene:邮件Newsletter")
        assert gene is not None
        assert gene["name"] == "邮件Newsletter"
        assert "Newsletter" in gene["description"]

    def test_gene_structure_correct(self, fresh_store):
        """TC-006: 基因结构正确 -> 包含name/type/description/input_keys/output_keys"""
        store = fresh_store
        for key in store.list_keys():
            if key.startswith("skill_gene:"):
                gene = store.load(key)
                assert "name" in gene, f"{key} 缺少 name"
                assert "type" in gene, f"{key} 缺少 type"
                assert gene["type"] == "functional", f"{key} type 不是 functional"
                assert "description" in gene, f"{key} 缺少 description"
                assert "input_keys" in gene, f"{key} 缺少 input_keys"
                assert "output_keys" in gene, f"{key} 缺少 output_keys"
                assert isinstance(gene["input_keys"], list)
                assert isinstance(gene["output_keys"], list)
