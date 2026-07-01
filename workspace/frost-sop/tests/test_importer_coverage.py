"""
importer.py 全面补测 — 从 3.80% 提升到 90%+。

覆盖：
  - 无 asset_store 返回错误
  - 路径自动探测 + 显式指定 + 未找到
  - YAML frontmatter 解析（有/无 yaml 模块）
  - 文件名回退名称、内容回退描述
  - README/catalog 文件跳过
  - 分类推断（目录名、关键词）
  - 已有基因不覆盖
  - 异常处理
  - 结果构建
"""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from skills.importer import import_agency_agents

# ────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ────────────────────────────────────────────────────────────────────────────


def _make_md_file(root: Path, rel_path: str, content: str):
    """在 root 下创建 .md 文件"""
    full = root / rel_path
    full.parent.mkdir(parents=True, exist_ok=True)
    full.write_text(content, encoding="utf-8")
    return full


def _make_store(**kwargs):
    """创建配置好的 Store mock（load 默认返回 None 避免误判为已有基因）"""
    store = MagicMock(**kwargs)
    # 默认 load 返回 None（而不是 truthy MagicMock）
    store.load.return_value = None
    return store


# =============================================================================
# Part 1: 错误路径
# =============================================================================


class TestErrorPaths:
    """无 store / 路径未找到"""

    def test_no_asset_store(self):
        context = {}
        result = import_agency_agents(context)
        assert result["_import_result"]["success"] is False
        assert "缺少资产Store" in result["_import_result"]["reason"]

    def test_path_not_found(self):
        mock_store = _make_store()
        context = {
            "_asset_store": mock_store,
            "_agency_path": "/nonexistent/path/to/agency",
        }
        result = import_agency_agents(context)
        assert result["_import_result"]["success"] is False
        assert "未找到" in result["_import_result"]["reason"]

    def test_no_path_and_no_default(self):
        """自动探测也找不到目录 — mock Path.exists 确保所有路径都不存在"""
        with (
            patch("skills.importer.Path.exists", return_value=False),
            patch("skills.importer.Path.is_dir", return_value=False),
        ):
            context = {"_asset_store": _make_store()}
            result = import_agency_agents(context)
            assert result["_import_result"]["success"] is False


# =============================================================================
# Part 2: 路径发现
# =============================================================================


class TestPathDiscovery:
    """路径自动探测、显式指定"""

    def test_explicit_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 创建空的 agency 目录（至少需要存在）
            agency_dir = root / "test-agency"
            agency_dir.mkdir()

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(agency_dir),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["success"] is True
            assert result["_import_result"]["imported"] == 0

    def test_auto_detect_from_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            agency_dir = root / ".workbuddy" / "agency-agents-zh"
            agency_dir.mkdir(parents=True)

            mock_store = _make_store()
            with patch("skills.importer.Path.home") as mock_home:
                mock_home.return_value = root
                context = {"_asset_store": mock_store}
                result = import_agency_agents(context)
                assert result["_import_result"]["success"] is True


# =============================================================================
# Part 3: 文件扫描与跳过
# =============================================================================


class TestFileScanning:
    """文件扫描、README跳过、隐藏文件跳过"""

    def test_skip_readme(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "README.md", "# README")
            _make_md_file(root, "engineering/test_agent.md", "---\nname: Test Agent\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            # README 被跳过，只有 test_agent 被导入
            assert result["_import_result"]["imported"] == 1
            assert result["_import_result"]["skipped"] >= 1

    def test_skip_catalog(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "catalog.md", "# Catalog")
            _make_md_file(root, "engineering/engineer.md", "---\nname: Engineer\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1

    def test_skip_hidden_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, ".hidden.md", "# Hidden")
            _make_md_file(root, "engineering/engineer.md", "---\nname: Engineer\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1

    def test_skip_agency_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "agency-list.md", "# Agency List")
            _make_md_file(root, "engineering/engineer.md", "---\nname: Engineer\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1


# =============================================================================
# Part 4: YAML Frontmatter 解析
# =============================================================================


class TestYamlParsing:
    """YAML frontmatter 解析（有 yaml 模块时）"""

    def test_parse_full_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/backend_architect.md",
                "---\nname: 后端架构师\ndescription: 精通后端架构设计\nemoji: \U0001f3d7\ufe0f\n---\n\n# 内容\n这是正文内容",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1
            # 验证保存的数据
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["name"] == "后端架构师"
            assert "后端架构设计" in saved_gene["description"]
            assert saved_gene["emoji"] == "🏗️"

    def test_parse_name_only_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/simple_agent.md",
                "---\nname: Simple Agent\n---\n\nJust some content about this agent role.",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["name"] == "Simple Agent"

    def test_parse_no_frontmatter(self):
        """无 frontmatter — 从文件名推断名称，从内容提取描述"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/code-reviewer.md",
                "# Code Reviewer\n\nThis is a code review expert role.",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["name"] == "Code Reviewer"

    def test_parse_no_frontmatter_no_desc(self):
        """无 frontmatter 且无描述内容 — 使用回退名称"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/test-specialist.md",
                "---\n---\n",  # 空 frontmatter
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            # 文件名推断名称: "test-specialist" -> "Test Specialist"
            assert result["_import_result"]["imported"] == 1

    def test_corrupted_frontmatter(self):
        """损坏的 YAML 不崩溃"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/broken.md",
                "---\n: invalid: yaml: :\n---\n\nContent here for description extraction.",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1


# =============================================================================
# Part 5: 无 yaml 模块时的回退解析
# =============================================================================


class TestNoYamlFallback:
    """HAS_YAML=False 时的简单解析"""

    def test_simple_parse_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/agent.md",
                "---\nname: Fallback Agent\ndescription: A fallback agent\nemoji: \U0001f916\n---\n\nContent",
            )

            mock_store = _make_store()
            with patch("skills.importer.HAS_YAML", False):
                context = {
                    "_asset_store": mock_store,
                    "_agency_path": str(root),
                }
                result = import_agency_agents(context)
                assert result["_import_result"]["imported"] == 1

    def test_simple_parse_no_name_line(self):
        """无 name: 行 → 从文件名推断"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/my-skill.md",
                "---\ndescription: Just a skill\n---\n\nSome content.",
            )

            mock_store = _make_store()
            with patch("skills.importer.HAS_YAML", False):
                context = {
                    "_asset_store": mock_store,
                    "_agency_path": str(root),
                }
                result = import_agency_agents(context)
                assert result["_import_result"]["imported"] == 1


# =============================================================================
# Part 6: 分类推断
# =============================================================================


class TestCategoryInference:
    """从目录名和关键词推断分类"""

    def test_category_from_directory(self):
        """从父目录名推断分类"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root, "marketing/seo_specialist.md", "---\nname: SEO Specialist\n---\nContent"
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "marketing"

    def test_category_from_keyword(self):
        """目录名不在映射中 → 从关键词推断"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "unknown-dir/前端开发.md",
                "---\nname: 前端开发\n---\nContent",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "engineering"

    def test_category_fallback_general(self):
        """无匹配的目录名也无关键词 → general"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "misc/unknown_role.md",
                "---\nname: Unknown Role\n---\nContent",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "general"

    def test_category_design_from_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "design/ui_designer.md", "---\nname: UI Designer\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "design"

    def test_category_product_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "random/product_manager.md",
                "---\nname: Product Manager\n---\nContent",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "product"

    def test_category_data_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "random/data_analyst.md", "---\nname: Data Analyst\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "data"

    def test_category_marketing_keyword_chinese(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "random/小红书运营.md", "---\nname: 小红书运营\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "marketing"

    def test_category_testing_keyword(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "random/qa_tester.md", "---\nname: QA Tester\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert saved_gene["category"] == "testing"


# =============================================================================
# Part 7: 已有基因处理
# =============================================================================


class TestExistingGenes:
    """不覆盖非 agency 来源的已有基因"""

    def test_dont_overwrite_non_agency_gene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root, "engineering/backend_architect.md", "---\nname: 后端架构师\n---\nContent"
            )

            # 已存在一个非 agency 来源的同名基因
            mock_store = _make_store()
            mock_store.load.return_value = {"source": "manual", "name": "后端架构师"}
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            # 应该被跳过
            assert result["_import_result"]["imported"] == 0
            assert result["_import_result"]["skipped"] >= 1

    def test_overwrite_agency_gene(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root, "engineering/backend_architect.md", "---\nname: 后端架构师\n---\nContent"
            )

            mock_store = _make_store()
            # 已存在一个 agency 来源的同名基因 → 可以覆盖
            mock_store.load.return_value = {"source": "agency-agents-zh", "name": "后端架构师"}
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1

    def test_no_existing_gene(self):
        """无已有基因 → 正常导入"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "engineering/new_agent.md", "---\nname: New Agent\n---\nContent")

            mock_store = _make_store()
            mock_store.load.return_value = None  # 不存在
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 1


# =============================================================================
# Part 8: 异常处理与结果
# =============================================================================


class TestExceptionHandling:
    """异常处理不崩溃，记录错误"""

    def test_read_error_skipped(self):
        """读取文件出错 → 跳过并记录错误"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "engineering/test.md", "---\nname: Test\n---\nContent")

            # Mock open 在读取此文件时抛出异常
            original_open = open

            def _mock_open(file, *args, **kwargs):
                fpath = str(file)
                if "test.md" in fpath:
                    raise OSError("模拟读取失败")
                return original_open(file, *args, **kwargs)

            mock_store = _make_store()
            with patch("builtins.open", _mock_open):
                context = {
                    "_asset_store": mock_store,
                    "_agency_path": str(root),
                }
                result = import_agency_agents(context)
            assert result["_import_result"]["success"] is True
            assert len(result["_import_result"]["errors"]) >= 1

    def test_import_result_structure(self):
        """验证导入结果的完整结构"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "engineering/agent1.md", "---\nname: Agent1\n---\nContent1")
            _make_md_file(root, "marketing/agent2.md", "---\nname: Agent2\n---\nContent2")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            ir = result["_import_result"]
            assert ir["success"] is True
            assert ir["imported"] == 2
            assert ir["skipped"] >= 0
            assert isinstance(ir["errors"], list)
            assert ir["total_genes"] == 2
            assert "_reason" in result

    def test_name_readme_skip(self):
        """role_name 为 readme/catalog/agency-list → 跳过"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 虽然文件名不是 README.md 但 frontmatter name 是 readme
            _make_md_file(root, "engineering/guide.md", "---\nname: README\n---\nContent")
            _make_md_file(root, "engineering/agent.md", "---\nname: Real Agent\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            # guide.md 因为 name=README 被跳过
            assert result["_import_result"]["imported"] == 1

    def test_description_from_content_fallback(self):
        """无 frontmatter description → 从正文提取"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(
                root,
                "engineering/agent.md",
                "---\nname: Agent Name\n---\n\nThis is the first paragraph of description.\nThis is the second line.\n\n# Heading",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert "This is the first paragraph" in saved_gene["description"]

    def test_long_description_truncated(self):
        """描述超过200字符被截断"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            long_desc = "A" * 300
            _make_md_file(
                root,
                "engineering/agent.md",
                f"---\nname: Agent\n---\n\n{long_desc}",
            )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            saved_gene = mock_store.save.call_args[0][1]
            assert len(saved_gene["description"]) <= 200

    def test_multiple_files_batch(self):
        """批量导入多个文件"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(5):
                _make_md_file(
                    root,
                    f"engineering/agent_{i}.md",
                    f"---\nname: Agent{i}\n---\nContent {i}",
                )

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            result = import_agency_agents(context)
            assert result["_import_result"]["imported"] == 5
            assert mock_store.save.call_count == 5

    def test_gene_key_format(self):
        """验证基因 key 格式: skill_gene:{name}"""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_md_file(root, "engineering/test_agent.md", "---\nname: TestAgent\n---\nContent")

            mock_store = _make_store()
            context = {
                "_asset_store": mock_store,
                "_agency_path": str(root),
            }
            import_agency_agents(context)
            gene_key = mock_store.save.call_args[0][0]
            assert gene_key == "skill_gene:TestAgent"
