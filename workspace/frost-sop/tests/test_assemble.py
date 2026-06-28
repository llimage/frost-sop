"""
FROST-SOP 动态组装测试
PHILOSOPHY: 验证孙辈Agent能被动态组装，能力基因库能正常工作。
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from stores.asset import create_asset_store
from agents.parent import create_parent
from core.store import Store
from skills.assemble import assemble_agent


def test_skill_gene_library_initialized():
    """验证能力基因库已初始化九种基础能力"""
    asset_store = create_asset_store()
    genes = [
        "需求分析", "技术设计", "代码生成", "测试验证", "审查交付",
        "内容创作", "营销策划", "财务分析", "运营优化",
    ]
    for gene_name in genes:
        gene = asset_store.load(f"skill_gene:{gene_name}")
        assert gene is not None, f"能力基因 {gene_name} 未初始化"
        assert gene.get("name") == gene_name
    print(f"✅ 能力基因库已初始化 {len(genes)} 种基础能力")


def test_assemble_agent_from_gene_library():
    """验证从基因库组装Agent（不调用LLM合成）"""
    asset_store = create_asset_store()
    parent = create_parent("test_parent", Store())
    
    context = {
        "_agent_requirement": "需要一个做需求分析的人",
        "_asset_store": asset_store,
        "_parent_agent": parent,
    }
    result = assemble_agent(context)
    
    agent = result.get("_assembled_agent")
    config = result.get("_agent_config", {})
    
    assert agent is not None, "组装失败：未返回Agent"
    assert agent.generation == 2, f"孙辈代际应为2，实际为{agent.generation}"
    assert len(config.get("skills", [])) > 0, "Agent应有至少一个Skill"
    
    # 验证基因库命中
    sources = config.get("skill_sources", {})
    gene_hits = [s for s in sources.values() if s == "gene_library"]
    print(
        f"✅ 组装成功: {agent.name}，{len(config['skills'])}个Skill（基因库命中:{len(gene_hits)} 合成:{len(config['skills'])-len(gene_hits)}）")



if __name__ == "__main__":
    test_skill_gene_library_initialized()
    test_assemble_agent_from_gene_library()
    print("\n✅ 所有动态组装测试通过")
