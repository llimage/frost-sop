"""
FROST-SOP 能力基因导入 Skill
PHILOSOPHY: 外部标准化角色定义可被家族吸收，转化为能力基因库中的制式装备。
府兵不需要知道这些角色来自哪里——它们只是兵器库中的可选项。
"""

import os
import re
from pathlib import Path
from core.skill import Skill

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def import_agency_agents(context: dict) -> dict:
    """
    扫描 agency-agents-zh 工具包，将专家角色定义导入为 FROST 能力基因。

    输入 context 键：
        _asset_store: Store —— 家族资产Store引用
        _agency_path: str（可选）—— agency-agents-zh 的安装路径，默认自动探测

    输出 context 键：
        _import_result: dict —— 导入统计
        _reason: str
    """

    asset_store = context.get("_asset_store")

    if not asset_store:
        context["_import_result"] = {"success": False, "reason": "缺少资产Store"}
        return context

    # 1. 自动探测 agency-agents-zh 的安装路径
    home = Path.home()
    possible_paths = [
        home / ".workbuddy" / "agency-agents-zh",
        Path("C:/Users/13810/.workbuddy/agency-agents-zh"),
        Path("/c/Users/13810/.workbuddy/agency-agents-zh"),
    ]

    agency_path = context.get("_agency_path")
    if not agency_path:
        for p in possible_paths:
            if p.exists() and p.is_dir():
                agency_path = str(p)
                break

    if not agency_path or not Path(agency_path).exists():
        context["_import_result"] = {
            "success": False,
            "reason": "未找到 agency-agents-zh 目录。请在 _agency_path 中指定路径。",
        }
        return context

    # 2. 扫描角色定义文件
    agency_dir = Path(agency_path)
    imported = 0
    skipped = 0
    errors = []

    # 定义分类目录映射
    category_dirs = {
        "engineering": ["engineering", "game-development", "gis", "security", "testing"],
        "marketing": ["marketing", "paid-media", "sales"],
        "design": ["design"],
        "product": ["product", "project-management"],
        "data": ["data", "ai"],
        "academic": ["academic"],
        "business": ["finance", "hr", "legal", "supply-chain"],
        "specialized": ["specialized", "spatial-computing"],
    }

    # 反向映射：目录名 -> 分类
    dir_to_category = {}
    for cat, dirs in category_dirs.items():
        for d in dirs:
            dir_to_category[d] = cat

    # 扫描所有 .md 文件（排除 README.md 和隐藏文件）
    for md_file in agency_dir.rglob("*.md"):
        # 跳过非角色定义文件
        if md_file.name.startswith(".") or md_file.name.lower() in ["readme.md", "catalog.md", "agency-list.md"]:
            skipped += 1
            continue

        try:
            # 读取 Markdown 文件
            with open(md_file, "r", encoding="utf-8") as f:
                content = f.read()

            # 解析 YAML frontmatter
            role_name = ""
            role_desc = ""
            emoji = ""

            if content.startswith("---"):
                # 有 YAML frontmatter
                end_marker = content.find("---", 3)
                if end_marker > 0:
                    frontmatter = content[3:end_marker].strip()
                    if HAS_YAML:
                        try:
                            fm_data = yaml.safe_load(frontmatter)
                            if isinstance(fm_data, dict):
                                role_name = fm_data.get("name", "")
                                role_desc = fm_data.get("description", "")
                                emoji = fm_data.get("emoji", "")
                        except:
                            pass
                    else:
                        # 简单解析（无yaml模块时）
                        for line in frontmatter.split("\n"):
                            if line.startswith("name:"):
                                role_name = line[5:].strip()
                            elif line.startswith("description:"):
                                role_desc = line[12:].strip()
                            elif line.startswith("emoji:"):
                                emoji = line[7:].strip()

            # 如果没有从frontmatter获取到名称，从文件名推断
            if not role_name:
                role_name = md_file.stem.replace("-", " ").title()

            # 如果没有描述，从内容中提取前200字符
            if not role_desc:
                # 跳过frontmatter，取前几行非空行
                lines = content.split("\n")
                in_fm = False
                desc_parts = []
                for line in lines:
                    if line.strip() == "---":
                        in_fm = not in_fm
                        continue
                    if not in_fm and line.strip() and not line.startswith("#"):
                        desc_parts.append(line.strip())
                        if len(" ".join(desc_parts)) > 200:
                            break
                role_desc = " ".join(desc_parts)[:200]

            if not role_name or role_name.lower() in ["readme", "catalog", "agency-list"]:
                skipped += 1
                continue

            # 从父目录推断分类
            parent_dir = md_file.parent.name.lower()
            category = dir_to_category.get(parent_dir, "imported")

            # 3. 转换为能力基因格式并存入资产Store
            gene_data = {
                "name": role_name,
                "type": "functional",
                "description": role_desc if role_desc else f"{role_name}专家角色",
                "category": category,
                "source": "agency-agents-zh",
                "source_file": str(md_file.relative_to(agency_dir)),
                "emoji": emoji,
                "input_keys": ["task_description"],
                "output_keys": ["generated_content"],
            }

            # 补全缺失字段
            if not gene_data.get("category") or gene_data["category"] == "imported":
                # 根据角色名称推断分类
                name_lower = role_name.lower()
                if any(kw in name_lower for kw in ["开发", "engineer", "dev", "前端", "后端", "全栈"]):
                    gene_data["category"] = "engineering"
                elif any(kw in name_lower for kw in ["营销", "market", "运营", "文案", "小红书", "抖音"]):
                    gene_data["category"] = "marketing"
                elif any(kw in name_lower for kw in ["设计", "design", "ui", "ux"]):
                    gene_data["category"] = "design"
                elif any(kw in name_lower for kw in ["产品", "product", "pm"]):
                    gene_data["category"] = "product"
                elif any(kw in name_lower for kw in ["测试", "test", "qa"]):
                    gene_data["category"] = "testing"
                elif any(kw in name_lower for kw in ["数据", "data", "分析"]):
                    gene_data["category"] = "data"
                else:
                    gene_data["category"] = "general"

            if not gene_data.get("input_keys") or len(gene_data["input_keys"]) == 0:
                gene_data["input_keys"] = ["task_description"]

            if not gene_data.get("output_keys") or len(gene_data["output_keys"]) == 0:
                gene_data["output_keys"] = ["generated_content"]

            gene_key = f"skill_gene:{role_name}"

            # 不覆盖已有的同名基因（除非也是来自agency-agents-zh）
            existing = asset_store.load(gene_key)
            if existing and existing.get("source") != "agency-agents-zh":
                skipped += 1
                continue

            asset_store.save(gene_key, gene_data)
            imported += 1

        except Exception as e:
            errors.append(f"{md_file.name}: {str(e)}")
            skipped += 1

    context["_import_result"] = {
        "success": True,
        "imported": imported,
        "skipped": skipped,
        "errors": errors[:10],
        "total_genes": imported,
    }
    context["_reason"] = f"能力基因导入完成: 新增 {imported} 个角色，跳过 {skipped} 个"

    return context


import_agency_agents_skill = Skill("import_agency_agents", import_agency_agents)
