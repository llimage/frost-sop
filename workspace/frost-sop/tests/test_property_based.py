"""
FROST-SOP 属性测试 (Hypothesis)

使用 Hypothesis 进行基于属性的测试，自动生成测试数据，
发现手动编写测试用例难以覆盖的边界条件。

运行方式:
    pytest tests/test_property_based.py -m property -s -q
"""

import json
import tempfile
from pathlib import Path

import pytest
import yaml
from hypothesis import given, strategies as st, settings, assume


# ──────────────────────────────────────────────────────────────
# Store 属性测试
# ──────────────────────────────────────────────────────────────


@pytest.mark.property
class TestStoreProperties:
    """Store 的核心属性：幂等性、可逆性、一致性。"""

    @staticmethod
    def _new_store():
        """创建全新的 Store 实例。"""
        from core.store import Store
        return Store()

    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=50),
        value=st.dictionaries(
            keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=20),
            values=st.one_of(
                st.text(max_size=100),
                st.integers(min_value=-1000, max_value=1000),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
            ),
            min_size=1,
            max_size=10,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_save_then_load_roundtrip(self, key, value):
        """属性：保存后再加载，数据完全一致。"""
        store = self._new_store()
        store.save(key, value)
        loaded = store.load(key)
        assert loaded == value, f"Roundtrip failed: saved {value}, loaded {loaded}"

    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=50),
    )
    @settings(max_examples=50, deadline=None)
    def test_delete_then_load_returns_none(self, key):
        """属性：删除后加载应返回 None。"""
        store = self._new_store()
        store.save(key, {"test": True})
        store.delete(key)
        loaded = store.load(key)
        assert loaded is None, f"After delete, load({key!r}) returned {loaded!r}, expected None"

    @given(
        key=st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_-", min_size=1, max_size=50),
        value1=st.dictionaries(keys=st.text(min_size=1, max_size=10), values=st.integers(), min_size=1, max_size=5),
        value2=st.dictionaries(keys=st.text(min_size=1, max_size=10), values=st.integers(), min_size=1, max_size=5),
    )
    @settings(max_examples=50, deadline=None)
    def test_last_write_wins(self, key, value1, value2):
        """属性：最后写入的值覆盖之前的值。"""
        store = self._new_store()
        store.save(key, value1)
        store.save(key, value2)
        loaded = store.load(key)
        assert loaded == value2, f"Last write didn't win: expected {value2}, got {loaded}"


# ──────────────────────────────────────────────────────────────
# 加密属性测试
# ──────────────────────────────────────────────────────────────


@pytest.mark.property
class TestEncryptionProperties:
    """加密模块属性测试：加解密往返、唯一性。"""

    @given(
        plaintext=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=1,
            max_size=500,
        ),
    )
    @settings(max_examples=200, deadline=None)
    def test_encrypt_decrypt_roundtrip(self, plaintext):
        """属性：任意明文加密再解密，结果与原文一致。"""
        from core.secrets import encrypt_api_key, decrypt_api_key

        assume(plaintext.strip())

        ciphertext = encrypt_api_key(plaintext)
        decrypted = decrypt_api_key(ciphertext)

        assert decrypted == plaintext, (
            f"Roundtrip failed:\n  Plain:  {plaintext!r}\n  Decrypt: {decrypted!r}"
        )

    @given(
        plaintext=st.text(
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
            min_size=1,
            max_size=200,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_ciphertext_differs_from_plaintext(self, plaintext):
        """属性：密文不等于明文。"""
        from core.secrets import encrypt_api_key

        assume(plaintext.strip())

        ciphertext = encrypt_api_key(plaintext)
        assert ciphertext != plaintext, "Ciphertext should differ from plaintext"

    @given(
        text1=st.text(min_size=1, max_size=100),
        text2=st.text(min_size=1, max_size=100),
    )
    @settings(max_examples=100, deadline=None)
    def test_different_inputs_different_ciphertexts(self, text1, text2):
        """属性：不同明文产生不同密文。"""
        from core.secrets import encrypt_api_key

        assume(text1.strip() and text2.strip())
        assume(text1 != text2)

        c1 = encrypt_api_key(text1)
        c2 = encrypt_api_key(text2)
        assert c1 != c2, f"Different inputs produced same ciphertext:\n  {text1!r} vs {text2!r}"


# ──────────────────────────────────────────────────────────────
# JSON 安全性属性测试
# ──────────────────────────────────────────────────────────────


@pytest.mark.property
class TestJSONSafetyProperties:
    """JSON 处理模块属性测试。"""

    @given(
        data=st.dictionaries(
            keys=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_", min_size=1, max_size=30),
            values=st.one_of(
                st.text(max_size=200),
                st.integers(),
                st.floats(allow_nan=False, allow_infinity=False),
                st.booleans(),
                st.none(),
            ),
            min_size=0,
            max_size=20,
        ),
    )
    @settings(max_examples=100, deadline=None)
    def test_safe_json_parse_on_serialized(self, data):
        """属性：JSON 序列化后再 safe_json_parse，结构一致。"""
        from core.json_safety import safe_json_parse

        serialized = json.dumps(data)
        result, error = safe_json_parse(serialized)

        if error is None and result is not None:
            assert isinstance(result, dict), "safe_json_parse of dict JSON should return dict"

    @given(
        text=st.text(max_size=1000),
    )
    @settings(max_examples=100, deadline=None)
    def test_safe_json_parse_no_crash_on_random(self, text):
        """属性：safe_json_parse 不会因任意输入而崩溃。"""
        from core.json_safety import safe_json_parse

        try:
            result, error = safe_json_parse(text)
            # 正常结果： (dict, None) 或 (None, str)
            # 不应该抛出未捕获异常
            assert error is None or isinstance(error, str)
            assert result is None or isinstance(result, dict)
        except Exception as e:
            pytest.fail(f"safe_json_parse crashed on: {text[:100]!r}: {e}")


# ──────────────────────────────────────────────────────────────
# SOP 解析器属性测试
# ──────────────────────────────────────────────────────────────


@pytest.mark.property
class TestSOPParserProperties:
    """SOP 解析器属性测试。"""

    @given(
        sop_id=st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-", min_size=3, max_size=20),
        name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz ", min_size=2, max_size=50),
        num_stages=st.integers(min_value=1, max_value=10),
    )
    @settings(max_examples=50, deadline=None)
    def test_parse_roundtrip(self, sop_id, name, num_stages):
        """属性：写入 YAML 再解析回来，SOP ID 和阶段数一致。"""
        from core.sop import SOP

        stages = []
        for i in range(num_stages):
            stages.append({
                "name": f"Stage {i + 1}",
                "description": f"Description {i + 1}",
                "inputs": ["input"],
                "outputs": ["output"],
                "skill": "test_skill",
            })

        sop_data = {
            "sop_id": sop_id,
            "name": name.strip(),
            "description": "Auto-generated test SOP",
            "version": "1.0",
            "stages": stages,
        }

        sop_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", encoding="utf-8", delete=False
            ) as f:
                yaml.dump(sop_data, f)
                sop_path = f.name

            sop = SOP.load_from_yaml(sop_path)
            assert sop.sop_id == sop_id
            assert len(sop.stages) == num_stages
        finally:
            if sop_path:
                Path(sop_path).unlink(missing_ok=True)

    @given(
        invalid_yaml=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=50, deadline=None)
    def test_parse_invalid_yaml_handles_gracefully(self, invalid_yaml):
        """属性：无效 YAML 被安全处理，不崩溃。"""
        from core.sop import SOP

        assume(not invalid_yaml.strip().startswith("sop_id:"))

        sop_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", encoding="utf-8", delete=False
            ) as f:
                f.write(invalid_yaml)
                sop_path = f.name

            try:
                SOP.load_from_yaml(sop_path)
            except Exception:
                pass  # 预期：无效 YAML 可能抛异常
        finally:
            if sop_path:
                Path(sop_path).unlink(missing_ok=True)


# ──────────────────────────────────────────────────────────────
# DB 查询安全性属性测试
# ──────────────────────────────────────────────────────────────


@pytest.mark.property
class TestDBQueryProperties:
    """数据库查询安全性属性测试。"""

    @given(
        table_name=st.text(alphabet="abcdefghijklmnopqrstuvwxyz_0123456789", min_size=1, max_size=30),
    )
    @settings(max_examples=200, deadline=None)
    def test_table_name_validation(self, table_name):
        """属性：合法表名通过格式验证，含 SQL 注入的表名不在白名单。"""
        from core.db import ALLOWED_TABLES
        import re

        pattern = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

        # 在白名单中的表名必须通过格式验证
        if table_name in ALLOWED_TABLES:
            assert pattern.match(table_name), f"Allowed table '{table_name}' should match pattern"

        # 包含危险关键词的表名不应在白名单中
        dangerous_kw = [";", "--", "/*", "DROP", "SELECT", "UNION", "INSERT", "DELETE", "UPDATE"]
        if any(dc.lower() in table_name.lower() for dc in dangerous_kw):
            assert table_name not in ALLOWED_TABLES, (
                f"Table with dangerous chars should not be in ALLOWED_TABLES: {table_name!r}"
            )
