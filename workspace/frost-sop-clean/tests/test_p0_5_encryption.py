"""
P0-5 自验收测试：API Key 加密存储

测试内容：
1. 加密/解密往返正确性
2. 不同数据产生不同密文
3. 密文不包含明文
4. 修改密文后解密失败（防篡改/GCM认证）
"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.secrets import (
    encrypt_api_key,
    decrypt_api_key,
    _get_machine_key,
    _derive_key,
)


class TestEncryption:
    """测试加密/解密核心功能"""

    def test_encrypt_decrypt_roundtrip(self):
        """测试加密后解密能还原原文"""
        original = "sk-test-api-key-12345-abcdef"
        encrypted = encrypt_api_key(original)

        assert encrypted != original, "密文不应等于原文"
        assert isinstance(encrypted, str), "密文应该是字符串"

        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original, f"解密后应等于原文，实际: {decrypted}"
        print("  ✅ test_encrypt_decrypt_roundtrip 通过")

    def test_different_ciphertexts(self):
        """测试同一原文每次加密产生不同密文（随机 nonce）"""
        original = "my-secret-key"
        enc1 = encrypt_api_key(original)
        enc2 = encrypt_api_key(original)

        assert enc1 != enc2, "两次加密应产生不同密文（GCM nonce 随机）"

        # 但都能解密为相同原文
        assert decrypt_api_key(enc1) == original
        assert decrypt_api_key(enc2) == original
        print("  ✅ test_different_ciphertexts 通过")

    def test_ciphertext_does_not_contain_plaintext(self):
        """测试密文中不包含明文子串"""
        original = "sk-abcdef12345"
        encrypted = encrypt_api_key(original)

        assert original not in encrypted, "密文不应包含明文"
        # 也检查部分匹配
        for i in range(len(original) - 3):
            assert original[i : i + 4] not in encrypted, (
                f"密文包含明文片段 '{original[i : i + 4]}'"
            )
        print("  ✅ test_ciphertext_does_not_contain_plaintext 通过")

    def test_tampered_ciphertext_fails(self):
        """测试篡改密文后解密失败（GCM 认证）"""
        original = "sk-tamper-test-key"
        encrypted = encrypt_api_key(original)

        # 篡改密文（修改最后一个字符）
        tampered = encrypted[:-1] + ("A" if encrypted[-1] != "A" else "B")

        result = decrypt_api_key(tampered)
        assert result is None, "篡改后的密文应解密失败"
        print("  ✅ test_tampered_ciphertext_fails 通过")

    def test_machine_key_consistent(self):
        """测试机器密钥在同一会话中保持稳定"""
        key1 = _get_machine_key()
        key2 = _get_machine_key()
        assert key1 == key2, "机器密钥应在同一会话中保持一致"
        assert len(key1) == 32, f"SHA-256 输出应为 32 字节，实际: {len(key1)}"
        print("  ✅ test_machine_key_consistent 通过")

    def test_derived_key_length(self):
        """测试派生密钥长度为 32 字节（AES-256）"""
        mk = _get_machine_key()
        dk = _derive_key(mk)
        assert len(dk) == 32, f"AES-256 密钥应为 32 字节，实际: {len(dk)}"
        print("  ✅ test_derived_key_length 通过")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
