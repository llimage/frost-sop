"""
FROST-SOP V3.1 测试覆盖率补充: skills/assemble.py
覆盖 _collect_templates, _keyword_fallback, _create_skills_from_genes,
synthesize_skill, create_skill_from_gene 等子函数
"""
import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.store import Store
from core.skill import Skill
from skills.assemble import (
    _collect_templates, _keyword_fallback, _create_skills_from_genes,
    synthesize_skill, create_skill_from_gene, assemble_agent,
)
from stores.asset import create_asset_store


# ============================================================
# _collect_templates 测试
# ============================================================

def test_collect_templates_empty():
    """空Store返回空列表"""
    result = _collect_templates(None)
    assert result == []


def test_collect_templates_with_genes():
    """有skill_gene数据时正确收集"""
    store = Store()
    store.save("skill_gene:test_skill", {"name": "test_skill",
        "description": "测试技能"})
    store.save("task:001", {"id": "001"})  # 非skill_gene应被忽略
    result = _collect_templates(store)
    assert len(result) == 1
    assert result[0]["name"] == "test_skill"


# ============================================================
# _keyword_fallback 测试
# ============================================================

def test_keyword_fallback_match():
    """关键词匹配命中"""
    store = Store()
    store.save("skill_gene:需求分析", {"name": "需求分析",
        "description": "分析需求"})
    store.save("skill_gene:代码生成", {"name": "代码生成",
        "description": "写代码"})
    result = _keyword_fallback(["需求分析", "代码生成"], store)
    assert len(result) == 2
    assert result["需求分析"]["name"] == "需求分析"


def test_keyword_fallback_partial():
    """部分命中"""
    store = Store()
    store.save("skill_gene:需求分析", {"name": "需求分析",
        "description": "分析需求"})
    result = _keyword_fallback(["需求分析", "不存在的技能"], store)
    assert len(result) == 1
    assert "需求分析" in result


def test_keyword_fallback_no_match():
    """全部未命中"""
    store = Store()
    result = _keyword_fallback(["不存在的技能"], store)
    assert len(result) == 0


# ============================================================
# _create_skills_from_genes 测试
# ============================================================

def test_create_skills_from_genes_basic():
    """从基因创建Skill"""
    genes = {
        "test_skill": {"name": "test_skill", "description": "测试技能"},
    }
    skills = _create_skills_from_genes(genes, "document")
    assert len(skills) == 1
    assert "test_skill" in skills
    assert isinstance(skills["test_skill"], Skill)


def test_create_skills_from_genes_empty():
    """空基因返回空"""
    result = _create_skills_from_genes({})
    assert result == {}


# ============================================================
# synthesize_skill 测试
# ============================================================

def test_synthesize_skill_basic():
    """LLM合成Skill（mock模式）"""
    skill = synthesize_skill("测试合成技能", "需要一个测试能力", output_type="document")
    assert isinstance(skill, Skill)
    assert skill.name == "测试合成技能"


def test_synthesize_skill_with_store():
    """合成Skill并归档到Store"""
    store = Store()
    skill = synthesize_skill("归档技能", "归档测试", asset_store=store,
        output_type="code")
    assert isinstance(skill, Skill)
    # 验证归档
    gene = store.load("skill_gene:归档技能")
    assert gene is not None
    assert gene["name"] == "归档技能"


# ============================================================
# create_skill_from_gene 测试
# ============================================================

def test_create_skill_from_gene_document():
    """从基因创建document类型Skill函数"""
    gene = {"name": "doc_skill", "description": "写文档"}
    skill_func = create_skill_from_gene(gene, "document")
    # create_skill_from_gene 返回函数（由 _create_skills_from_genes 包装为 Skill）
    assert callable(skill_func)


def test_create_skill_from_gene_code():
    """从基因创建code类型Skill函数"""
    gene = {"name": "code_skill", "description": "写代码"}
    skill_func = create_skill_from_gene(gene, "code")
    assert callable(skill_func)


# ============================================================
# assemble_agent 边界测试
# ============================================================

def test_assemble_agent_no_requirement():
    """缺少需求描述"""
    ctx = {}
    result = assemble_agent(ctx)
    assert result.get("_assembled_agent") is None
    assert "缺少需求描述" in result.get("_reason", "")


def test_assemble_agent_no_parent():
    """无父辈Agent时独立创建孙辈"""
    asset_store = create_asset_store()
    ctx = {
        "_agent_requirement": "需要一个做代码生成的人",
        "_asset_store": asset_store,
    }
    result = assemble_agent(ctx)
    agent = result.get("_assembled_agent")
    assert agent is not None
    assert agent.generation == 2


if __name__ == "__main__":
    for name, func in list(globals().items()):
        if name.startswith("test_"):
            print(f"Running {name}...")
            func()
            print(f"  ✅ {name} passed")
    print("\n✅ 所有 assemble 覆盖率测试通过")
