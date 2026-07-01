"""
hunt.py 覆盖率补测

目标：将 skills/hunt.py 覆盖率从 30.86% 提升到 80%+

覆盖函数：
- _load_target_list / _save_target_list
- _update_skill_health_in_store
- search_external (所有分支)
- compare_skill (所有分支)
- absorb_skill (所有分支)
- hunt_sop (全流程)
- trigger_continuous_hunt (含 store 数据)
- trigger_predictive_hunt (含缺口)
"""

import contextlib
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestHuntLoadSaveTargetList:
    """测试 _load_target_list 和 _save_target_list"""

    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp(prefix="frost_hunt_test_")

    def teardown_method(self):
        import shutil

        with contextlib.suppress(PermissionError, OSError):
            shutil.rmtree(self.tmpdir)

    def _make_safe_open(self):
        """返回一个绕过路径校验的 safe_open mock"""

        def _safe_open(path, base_dir=None, mode="r", encoding="utf-8", must_exist=False):
            return open(path, mode=mode, encoding=encoding)

        return _safe_open

    def test_load_target_list_file_not_exists(self):
        """文件不存在时返回空列表"""
        from skills import hunt as hunt_mod

        original = hunt_mod.TARGET_LIST_FILE
        hunt_mod.TARGET_LIST_FILE = os.path.join(self.tmpdir, "nonexistent.yaml")
        try:
            result = hunt_mod._load_target_list()
            assert result == []
        finally:
            hunt_mod.TARGET_LIST_FILE = original

    @patch("core.path_safety.safe_open")
    def test_load_target_list_valid(self, mock_safe_open):
        """正常加载目标清单"""
        mock_safe_open.side_effect = self._make_safe_open()
        from skills import hunt as hunt_mod

        target_path = os.path.join(self.tmpdir, "target_list.yaml")
        targets = [
            {"skill_id": "s1", "health_score": 0.5, "days_since_version": 45, "priority": "high"},
            {"skill_id": "s2", "health_score": 0.9, "days_since_version": 10, "priority": "low"},
        ]
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.dump({"targets": targets}, f)

        original = hunt_mod.TARGET_LIST_FILE
        hunt_mod.TARGET_LIST_FILE = target_path
        try:
            result = hunt_mod._load_target_list()
            assert len(result) == 2
            assert result[0]["skill_id"] == "s1"
            assert result[1]["skill_id"] == "s2"
        finally:
            hunt_mod.TARGET_LIST_FILE = original

    @patch("core.path_safety.safe_open")
    def test_load_target_list_bad_yaml(self, mock_safe_open):
        """YAML 损坏时返回空列表"""
        mock_safe_open.side_effect = self._make_safe_open()
        from skills import hunt as hunt_mod

        target_path = os.path.join(self.tmpdir, "bad.yaml")
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            f.write("::: bad yaml :::")

        original = hunt_mod.TARGET_LIST_FILE
        hunt_mod.TARGET_LIST_FILE = target_path
        try:
            result = hunt_mod._load_target_list()
            assert result == []
        finally:
            hunt_mod.TARGET_LIST_FILE = original

    @patch("core.path_safety.safe_open")
    def test_save_target_list(self, mock_safe_open):
        """保存后再加载验证一致性"""
        mock_safe_open.side_effect = self._make_safe_open()
        from skills import hunt as hunt_mod

        target_path = os.path.join(self.tmpdir, "save_test.yaml")
        targets = [
            {"skill_id": "s1", "health_score": 0.3, "days_since_version": 60, "priority": "high"}
        ]

        original = hunt_mod.TARGET_LIST_FILE
        hunt_mod.TARGET_LIST_FILE = target_path
        try:
            hunt_mod._save_target_list(targets)
            loaded = hunt_mod._load_target_list()
            assert len(loaded) == 1
            assert loaded[0]["skill_id"] == "s1"
            assert loaded[0]["health_score"] == 0.3
        finally:
            hunt_mod.TARGET_LIST_FILE = original


class TestUpdateSkillHealthInStore:
    """测试 _update_skill_health_in_store"""

    def test_store_is_none(self):
        """store=None 时直接返回不报错"""
        from skills.hunt import _update_skill_health_in_store

        # 不应抛出异常
        _update_skill_health_in_store(None, "test_skill", 0.5, "hunt_searched")

    def test_update_existing_skill(self):
        """已有 Skill 数据时更新健康评分"""
        from skills.hunt import _update_skill_health_in_store

        store = MagicMock()
        store.load.return_value = {"name": "test_skill", "health_score": 0.3}

        _update_skill_health_in_store(store, "test_skill", 0.8, "hunt_searched")

        # 验证 store.store 被调用，且数据包含更新字段
        store.store.assert_called_once()
        key, data = store.store.call_args[0]
        assert key == "skill_gene:test_skill"
        assert data["health_score"] == 0.8
        assert data["last_hunt_action"] == "hunt_searched"
        assert "last_hunt_time" in data

    def test_update_nonexistent_skill(self):
        """load 返回 None 时不更新"""
        from skills.hunt import _update_skill_health_in_store

        store = MagicMock()
        store.load.return_value = None

        _update_skill_health_in_store(store, "test_skill", 0.8, "hunt_searched")
        store.store.assert_not_called()

    def test_update_non_dict_skill(self):
        """load 返回非 dict 时不更新"""
        from skills.hunt import _update_skill_health_in_store

        store = MagicMock()
        store.load.return_value = "not_a_dict"

        _update_skill_health_in_store(store, "test_skill", 0.8, "hunt_searched")
        store.store.assert_not_called()


class TestSearchExternalAllBranches:
    """测试 search_external 所有分支"""

    def test_missing_target_skill_id(self):
        """缺少 target_skill_id 时返回错误"""
        from skills.hunt import search_external

        context = {"_asset_store": MagicMock()}
        result = search_external(context)

        assert "_hunt_search_result" in result
        assert result["_hunt_search_result"]["error"] == "missing_target_skill_id"

    @patch("skills.llm.call_llm_skill")
    def test_normal_search_with_llm(self, mock_llm):
        """正常搜索：LLM 返回 found=true，含候选者"""
        import json

        from skills.hunt import search_external

        mock_llm.return_value = json.dumps(
            {
                "found": True,
                "candidates": [
                    {
                        "name": "better_skill",
                        "source": "github",
                        "url": "https://github.com/x/y",
                        "health_score": 0.9,
                        "version": "2.0",
                    }
                ],
            }
        )

        store = MagicMock()
        store.load.return_value = None
        context = {
            "_asset_store": store,
            "_hunt_target_skill_id": "old_skill",
            "_hunt_search_query": "better skill python",
            "_current_health_score": 0.5,
        }

        result = search_external(context)

        assert result["_hunt_search_result"]["found"] is True
        assert len(result["_hunt_search_result"]["candidates"]) == 1
        assert result["_hunt_search_result"]["candidates"][0]["name"] == "better_skill"

    @patch("skills.llm.call_llm_skill")
    def test_search_not_found(self, mock_llm):
        """LLM 返回 found=false"""
        import json

        from skills.hunt import search_external

        mock_llm.return_value = json.dumps({"found": False, "candidates": []})

        store = MagicMock()
        store.load.return_value = None
        context = {
            "_asset_store": store,
            "_hunt_target_skill_id": "my_skill",
        }

        result = search_external(context)

        assert result["_hunt_search_result"]["found"] is False
        assert result["_hunt_search_result"]["candidates"] == []

    @patch("skills.llm.call_llm_skill")
    def test_search_llm_exception(self, mock_llm):
        """LLM 调用异常时返回空结果"""
        from skills.hunt import search_external

        mock_llm.side_effect = Exception("LLM unavailable")

        store = MagicMock()
        store.load.return_value = None
        context = {
            "_asset_store": store,
            "_hunt_target_skill_id": "my_skill",
        }

        result = search_external(context)

        assert result["_hunt_search_result"]["found"] is False
        assert result["_hunt_search_result"]["candidates"] == []

    @patch("skills.llm.call_llm_skill")
    def test_search_with_store_none(self, mock_llm):
        """store=None 时正常搜索不报错"""
        import json

        from skills.hunt import search_external

        mock_llm.return_value = json.dumps({"found": False, "candidates": []})

        context = {
            "_asset_store": None,
            "_hunt_target_skill_id": "my_skill",
        }

        result = search_external(context)
        assert result["_hunt_search_result"]["found"] is False


class TestCompareSkillAllBranches:
    """测试 compare_skill 所有分支"""

    def test_not_found_skip(self):
        """search_result.found=False 时跳过"""
        from skills.hunt import compare_skill

        context = {
            "_asset_store": MagicMock(),
            "_hunt_search_result": {"found": False, "candidates": []},
            "_hunt_target_skill_id": "test_skill",
        }

        result = compare_skill(context)
        assert result["_hunt_compare_result"]["action"] == "skip"
        assert result["_hunt_compare_result"]["reason"] == "no_candidates"

    def test_found_but_empty_candidates(self):
        """found=True 但 candidates 为空"""
        from skills.hunt import compare_skill

        context = {
            "_asset_store": MagicMock(),
            "_hunt_search_result": {"found": True, "candidates": []},
            "_hunt_target_skill_id": "test_skill",
        }

        result = compare_skill(context)
        assert result["_hunt_compare_result"]["action"] == "skip"
        assert result["_hunt_compare_result"]["reason"] == "empty_candidates"

    def test_should_replace_health_improved(self):
        """候选者健康评分显著提升 → should_replace=True"""
        from skills.hunt import compare_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.4}

        context = {
            "_asset_store": store,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {
                        "name": "better_skill",
                        "source": "github",
                        "health_score": 0.85,
                        "version": "2.0",
                    }
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        cr = result["_hunt_compare_result"]
        assert cr["should_absorb"] is True
        assert len(cr["compare_results"]) == 1
        assert cr["compare_results"][0]["should_replace"] is True
        assert cr["compare_results"][0]["health_diff"] > 0.1

    def test_should_not_replace_small_improvement(self):
        """候选者健康评分提升很小 → should_replace=False"""
        from skills.hunt import compare_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.8}

        context = {
            "_asset_store": store,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {
                        "name": "slightly_better",
                        "source": "github",
                        "health_score": 0.88,
                        "version": "2.0",
                    }
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        cr = result["_hunt_compare_result"]
        assert cr["should_absorb"] is False
        assert cr["compare_results"][0]["should_replace"] is False

    def test_should_not_replace_worse(self):
        """候选者健康评分更低 → should_replace=False"""
        from skills.hunt import compare_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.9}

        context = {
            "_asset_store": store,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {
                        "name": "worse_skill",
                        "source": "github",
                        "health_score": 0.3,
                        "version": "1.0",
                    }
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        cr = result["_hunt_compare_result"]
        assert cr["should_absorb"] is False
        assert cr["compare_results"][0]["should_replace"] is False

    def test_compare_with_store_none(self):
        """store=None 时也能正常比对"""
        from skills.hunt import compare_skill

        context = {
            "_asset_store": None,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {"name": "better", "source": "github", "health_score": 0.9, "version": "2.0"}
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        cr = result["_hunt_compare_result"]
        # existing_health 默认为 0.0（因为 store=None）
        assert cr["existing_health"] == 0.0
        assert cr["should_absorb"] is True  # 0.9 - 0.0 > 0.1

    def test_compare_store_load_exception(self):
        """store.load 异常时不应中断"""
        from skills.hunt import compare_skill

        store = MagicMock()
        store.load.side_effect = Exception("DB error")

        context = {
            "_asset_store": store,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {"name": "better", "source": "github", "health_score": 0.9, "version": "2.0"}
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        # 不应抛出异常，existing_health 应为 0.0
        assert "_hunt_compare_result" in result

    def test_compare_multiple_candidates(self):
        """多个候选者：只要有一个 should_replace，should_absorb 就是 True"""
        from skills.hunt import compare_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.5}

        context = {
            "_asset_store": store,
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {"name": "worse", "source": "github", "health_score": 0.3, "version": "1.0"},
                    {
                        "name": "better",
                        "source": "huggingface",
                        "health_score": 0.9,
                        "version": "2.0",
                    },
                    {"name": "same", "source": "pypi", "health_score": 0.55, "version": "1.5"},
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = compare_skill(context)
        cr = result["_hunt_compare_result"]
        assert cr["should_absorb"] is True
        assert len(cr["compare_results"]) == 3
        # 只有第二个 should_replace
        assert [r["should_replace"] for r in cr["compare_results"]] == [False, True, False]


class TestAbsorbSkillAllBranches:
    """测试 absorb_skill 所有分支"""

    def test_should_not_absorb(self):
        """should_absorb=False 时拒绝"""
        from skills.hunt import absorb_skill

        context = {
            "_asset_store": MagicMock(),
            "_hunt_compare_result": {"should_absorb": False, "reason": "health_not_improved"},
            "_hunt_search_result": {"found": False},
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        assert result["_hunt_absorb_result"]["action"] == "rejected"
        assert result["_hunt_absorb_result"]["reason"] == "health_not_improved"

    def test_should_absorb_no_candidates(self):
        """should_absorb=True 但搜索无候选者"""
        from skills.hunt import absorb_skill

        context = {
            "_asset_store": MagicMock(),
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {"found": False, "candidates": []},
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        assert result["_hunt_absorb_result"]["action"] == "rejected"
        assert result["_hunt_absorb_result"]["reason"] == "no_candidates"

    def test_absorb_success(self):
        """成功吸收新 Skill"""
        from skills.hunt import absorb_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.5}

        context = {
            "_asset_store": store,
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {
                        "name": "new_skill",
                        "source": "github",
                        "url": "",
                        "health_score": 0.9,
                        "version": "2.0",
                    }
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        ar = result["_hunt_absorb_result"]
        assert ar["action"] == "absorbed"
        assert ar["new_skill_id"] == "new_skill"
        assert ar["replaced_skill_id"] == "old_skill"

        # 验证 store.store 被调用（至少两次：新Skill + 旧Skill更新）
        assert store.store.call_count >= 2

    def test_absorb_store_none(self):
        """store=None 时返回失败"""
        from skills.hunt import absorb_skill

        context = {
            "_asset_store": None,
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {"name": "new_skill", "source": "github", "health_score": 0.9, "version": "2.0"}
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        assert result["_hunt_absorb_result"]["action"] == "failed"
        assert "store_not_available" in result["_hunt_absorb_result"]["error"]

    def test_absorb_store_store_exception(self):
        """store.store 异常时返回失败"""
        from skills.hunt import absorb_skill

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.5}
        store.store.side_effect = Exception("Store write error")

        context = {
            "_asset_store": store,
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {"name": "new_skill", "source": "github", "health_score": 0.9, "version": "2.0"}
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        assert result["_hunt_absorb_result"]["action"] == "failed"

    @patch("urllib.request.urlopen")
    def test_absorb_with_github_download(self, mock_urlopen):
        """GitHub URL 的 Skill 尝试下载内容"""

        from skills.hunt import absorb_skill

        mock_urlopen.return_value.__enter__.return_value.read.return_value = b"# SKILL.md content"
        mock_urlopen.return_value.__enter__.return_value.status = 200

        store = MagicMock()
        store.load.return_value = {"name": "old_skill", "health_score": 0.5}

        context = {
            "_asset_store": store,
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {
                "found": True,
                "candidates": [
                    {
                        "name": "gh_skill",
                        "source": "github",
                        "url": "https://github.com/user/repo/blob/main/SKILL.md",
                        "health_score": 0.95,
                        "version": "2.0",
                    }
                ],
            },
            "_hunt_target_skill_id": "old_skill",
        }

        result = absorb_skill(context)
        ar = result["_hunt_absorb_result"]
        assert ar["action"] == "absorbed"

        # 验证下载了内容
        stored_data = store.store.call_args_list[0][0][1]
        assert "downloaded_content" in stored_data


class TestHuntSOPFullFlow:
    """测试 hunt_sop 全流程"""

    def test_no_targets(self):
        """无目标时退出"""
        from skills.hunt import hunt_sop

        context = {"_asset_store": MagicMock(), "_hunt_targets": []}
        result = hunt_sop(context)
        assert result["_hunt_sop_result"]["status"] == "no_targets"

    @patch("skills.hunt._load_target_list")
    def test_no_targets_from_config(self, mock_load):
        """_hunt_targets 未提供且配置文件无目标"""
        from skills.hunt import hunt_sop

        mock_load.return_value = []
        context = {"_asset_store": MagicMock()}
        result = hunt_sop(context)
        assert result["_hunt_sop_result"]["status"] == "no_targets"

    @patch("skills.hunt.search_external")
    @patch("skills.hunt.compare_skill")
    @patch("skills.hunt.absorb_skill")
    def test_full_flow_with_targets(self, mock_absorb, mock_compare, mock_search):
        """完整狩猎流程：搜索 → 比对 → 吸收"""
        from skills.hunt import hunt_sop

        # Mock search_external 返回 found=true
        mock_search.return_value = {
            "_asset_store": MagicMock(),
            "_hunt_target_skill_id": "s1",
            "_hunt_search_result": {
                "found": True,
                "candidates": [{"name": "new", "health_score": 0.9}],
            },
        }

        # Mock compare_skill 返回 should_absorb=True
        mock_compare.return_value = {
            "_asset_store": MagicMock(),
            "_hunt_search_result": {
                "found": True,
                "candidates": [{"name": "new", "health_score": 0.9}],
            },
            "_hunt_target_skill_id": "s1",
            "_hunt_compare_result": {
                "should_absorb": True,
                "compare_results": [{"should_replace": True}],
            },
        }

        # Mock absorb_skill 返回 absorbed
        mock_absorb.return_value = {
            "_asset_store": MagicMock(),
            "_hunt_compare_result": {"should_absorb": True},
            "_hunt_search_result": {
                "found": True,
                "candidates": [{"name": "new", "health_score": 0.9}],
            },
            "_hunt_target_skill_id": "s1",
            "_hunt_absorb_result": {"action": "absorbed", "new_skill_id": "new_skill"},
        }

        store = MagicMock()
        targets = [
            {"skill_id": "s1", "health_score": 0.5, "days_since_version": 45, "priority": "high"},
            {"skill_id": "s2", "health_score": 0.3, "days_since_version": 60, "priority": "high"},
        ]

        context = {"_asset_store": store, "_hunt_targets": targets, "_hunt_mode": "continuous"}
        result = hunt_sop(context)

        sop_result = result["_hunt_sop_result"]
        assert sop_result["targets_count"] == 2
        assert sop_result["absorbed_count"] == 2
        assert sop_result["rejected_count"] == 0
        assert sop_result["mode"] == "continuous"

    @patch("skills.hunt.search_external")
    @patch("skills.hunt.compare_skill")
    @patch("skills.hunt.absorb_skill")
    def test_full_flow_with_skip_and_reject(self, mock_absorb, mock_compare, mock_search):
        """混合结果：有吸收、有跳过、有拒绝"""
        from skills.hunt import hunt_sop

        # target s1: search → found, compare → absorb, absorb → absorbed
        # target s2: search → found, compare → skip, absorb → rejected

        search_calls = []

        def search_side_effect(ctx):
            sid = ctx.get("_hunt_target_skill_id", "")
            search_calls.append(sid)
            return {
                "_asset_store": MagicMock(),
                "_hunt_target_skill_id": sid,
                "_hunt_search_result": {
                    "found": True,
                    "candidates": [{"name": f"new_{sid}", "health_score": 0.9}],
                },
            }

        mock_search.side_effect = search_side_effect

        def compare_side_effect(ctx):
            sid = ctx.get("_hunt_target_skill_id", "")
            if sid == "s1":
                return {
                    "_hunt_compare_result": {
                        "should_absorb": True,
                        "compare_results": [{"should_replace": True}],
                    }
                }
            else:
                return {
                    "_hunt_compare_result": {
                        "should_absorb": False,
                        "reason": "health_not_improved",
                        "compare_results": [{"should_replace": False}],
                    }
                }

        mock_compare.side_effect = compare_side_effect

        def absorb_side_effect(ctx):
            cr = ctx.get("_hunt_compare_result", {})
            if cr.get("should_absorb"):
                return {"_hunt_absorb_result": {"action": "absorbed"}}
            else:
                return {"_hunt_absorb_result": {"action": "rejected"}}

        mock_absorb.side_effect = absorb_side_effect

        targets = [
            {"skill_id": "s1", "health_score": 0.5},
            {"skill_id": "s2", "health_score": 0.8},
        ]

        context = {
            "_asset_store": MagicMock(),
            "_hunt_targets": targets,
            "_hunt_mode": "predictive",
        }
        result = hunt_sop(context)

        sop_result = result["_hunt_sop_result"]
        assert sop_result["absorbed_count"] == 1
        assert sop_result["rejected_count"] == 1
        assert sop_result["mode"] == "predictive"


class TestTriggerContinuousHunt:
    """测试 trigger_continuous_hunt"""

    def test_trigger_no_skill_genes(self):
        """store 中没有 skill_gene: 前缀的键"""
        from skills.hunt import trigger_continuous_hunt

        store = MagicMock()
        store.list_keys.return_value = ["task:1", "constitution:1", "lesson:1"]

        context = {"_asset_store": store}
        result = trigger_continuous_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "continuous"
        assert tr["targets_found"] == 0

    def test_trigger_store_none(self):
        """store=None 时也能执行"""
        from skills.hunt import trigger_continuous_hunt

        context = {"_asset_store": None}
        result = trigger_continuous_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "continuous"
        assert tr["targets_found"] == 0

    @patch("skills.hunt.hunt_sop")
    def test_trigger_with_low_health_skills(self, mock_hunt_sop):
        """有低健康评分的 Skill → 触发狩猎"""
        from skills.hunt import trigger_continuous_hunt

        mock_hunt_sop.return_value = {
            "_hunt_sop_result": {"absorbed_count": 1, "rejected_count": 0}
        }

        store = MagicMock()
        store.list_keys.return_value = ["skill_gene:s1", "skill_gene:s2", "skill_gene:s3"]
        # s1: low health → should hunt
        # s2: high health, recent → skip
        # s3: non-dict → skip
        store.load.side_effect = lambda key: {
            "skill_gene:s1": {"health_score": 0.3, "name": "s1"},
            "skill_gene:s2": {"health_score": 0.95, "name": "s2"},
            "skill_gene:s3": "not_a_dict",
        }.get(key)

        context = {"_asset_store": store}
        result = trigger_continuous_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "continuous"
        assert tr["targets_found"] == 1  # only s1

    @patch("skills.hunt.hunt_sop")
    def test_trigger_with_old_skills(self, mock_hunt_sop):
        """有超过30天未更新的 Skill → 触发狩猎"""
        from datetime import datetime, timedelta

        from skills.hunt import trigger_continuous_hunt

        mock_hunt_sop.return_value = {
            "_hunt_sop_result": {"absorbed_count": 0, "rejected_count": 1}
        }

        old_date = (datetime.now() - timedelta(days=60)).isoformat()

        store = MagicMock()
        store.list_keys.return_value = ["skill_gene:old"]
        store.load.return_value = {
            "health_score": 0.85,
            "name": "old",
            "last_version_time": old_date,
        }

        context = {"_asset_store": store}
        result = trigger_continuous_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "continuous"
        assert tr["targets_found"] == 1


class TestTriggerPredictiveHunt:
    """测试 trigger_predictive_hunt"""

    def test_no_gaps(self):
        """无能力缺口时跳过"""
        from skills.hunt import trigger_predictive_hunt

        store = MagicMock()
        context = {
            "_asset_store": store,
            "_integrated_briefing": {"briefings": {}},
        }
        result = trigger_predictive_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "predictive"
        assert tr["status"] == "no_gaps"

    @patch("skills.hunt.hunt_sop")
    def test_with_low_success_rate_gap(self, mock_hunt_sop):
        """有低成功率缺口 → 触发预测性搜索"""
        from skills.hunt import trigger_predictive_hunt  # noqa: F811

        mock_hunt_sop.return_value = {
            "_hunt_sop_result": {"absorbed_count": 0, "rejected_count": 1}
        }

        store = MagicMock()
        store.list_keys.return_value = [
            "skill_gene:s1",
            "skill_gene:s2",
            "skill_gene:s3",
        ]
        store.load.side_effect = lambda key: {
            "skill_gene:s1": {"health_score": 0.6, "name": "s1"},  # health < 0.8 → target
            "skill_gene:s2": {"health_score": 0.9, "name": "s2"},  # health >= 0.8 → skip
            "skill_gene:s3": "not_dict",  # skip
        }.get(key)

        context = {
            "_asset_store": store,
            "_integrated_briefing": {"briefings": {}},
            "_analytics_skill": {"success_rate": 0.6},  # < 0.8 → 触发缺口
        }
        result = trigger_predictive_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "predictive"
        assert tr["gaps_found"] == 1
        assert tr["targets_found"] == 1

    @patch("skills.hunt.hunt_sop")
    def test_with_gap_but_no_matching_skills(self, mock_hunt_sop):
        """有缺口但 store 中没有匹配的 Skill → targets=0"""
        from skills.hunt import trigger_predictive_hunt

        mock_hunt_sop.return_value = {
            "_hunt_sop_result": {"absorbed_count": 0, "rejected_count": 0}
        }

        store = MagicMock()
        store.list_keys.return_value = []  # 无 skill_gene

        context = {
            "_asset_store": store,
            "_integrated_briefing": {"briefings": {}},
            "_analytics_skill": {"success_rate": 0.5},
        }
        result = trigger_predictive_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["trigger_type"] == "predictive"
        assert tr["targets_found"] == 0  # 有缺口但没匹配到技能
        assert "status" in tr  # no_targets 状态

    @patch("skills.hunt.hunt_sop")
    def test_with_store_none(self, mock_hunt_sop):
        """store=None 且有缺口 → targets=0（无 Skill 可匹配）"""
        from skills.hunt import trigger_predictive_hunt

        context = {
            "_asset_store": None,
            "_integrated_briefing": {"briefings": {}},
            "_analytics_skill": {"success_rate": 0.5},
        }
        result = trigger_predictive_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["gaps_found"] == 1
        assert tr["targets_found"] == 0

    def test_high_success_rate_no_gap(self):
        """高成功率不触发缺口"""
        from skills.hunt import trigger_predictive_hunt

        context = {
            "_asset_store": MagicMock(),
            "_integrated_briefing": {"briefings": {}},
            "_analytics_skill": {"success_rate": 0.95},  # >= 0.8 → no gap
        }
        result = trigger_predictive_hunt(context)

        tr = result["_hunt_trigger_result"]
        assert tr["status"] == "no_gaps"
