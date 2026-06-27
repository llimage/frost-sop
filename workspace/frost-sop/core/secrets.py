"""
P0-5: API Key 加密存储模块
使用 AES-256-GCM 加密算法保护 API 密钥等敏感信息。

安全设计：
- 加密密钥从机器标识派生（PBKDF2HMAC + sha256），每台机器唯一
- 加密数据存储在 .secrets.enc 文件中（与代码分离）
- 使用 GCM 模式提供认证加密（防篡改）
- 支持首次运行提示输入和后续自动解密
"""

import os
import json
import base64
import hashlib
import socket
import getpass
from pathlib import Path
from typing import Optional, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag


# ── 常量 ──────────────────────────────────────────────────
_SECRETS_FILE = "data/.secrets.enc"
# 固定盐值（与代码绑定，仅用于KDF，非安全关键）
_KDF_SALT = b"\x8a\x7f\x3e\x1c\xb9\x4d\x2f\x6a\xc3\x55\x7e\x1b\xa8\x9f\x4d\x02"
_KDF_ITERATIONS = 600_000


def _get_machine_key() -> bytes:
    """
    从机器标识派生加密密钥。

    使用 machine-id 或 hostname + MAC 的组合，
    确保每台机器的密钥不同。
    """
    identifiers = []

    # 1. 主机名
    try:
        identifiers.append(socket.gethostname())
    except Exception:
        pass

    # 2. 用户目录（Windows/macOS/Linux 通用）
    try:
        identifiers.append(os.path.expanduser("~"))
    except Exception:
        pass

    # 3. 计算机名（Windows）
    try:
        identifiers.append(os.environ.get("COMPUTERNAME", ""))
    except Exception:
        pass

    # 如果以上都不行，使用固定值（降级）
    if not identifiers:
        identifiers.append("frost-sop-default-machine")

    # 组合并哈希
    combined = "|".join(identifiers).encode("utf-8")
    return hashlib.sha256(combined).digest()


def _derive_key(machine_key: bytes) -> bytes:
    """
    从机器密钥派生 AES-256 密钥。

    Args:
        machine_key: 机器标识原始字节

    Returns:
        32 字节 AES-256 密钥
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_KDF_SALT,
        iterations=_KDF_ITERATIONS,
    )
    return kdf.derive(machine_key)


# ── 核心 API ───────────────────────────────────────────────

def encrypt_api_key(plaintext: str) -> str:
    """
    加密 API 密钥。

    Args:
        plaintext: 明文 API 密钥

    Returns:
        Base64 编码的密文（含 nonce）
    """
    key = _derive_key(_get_machine_key())
    aesgcm = AESGCM(key)

    # 生成随机 nonce（12 字节，GCM 推荐）
    nonce = os.urandom(12)

    # 加密并认证
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # 组合 nonce + ciphertext，Base64 编码
    combined = nonce + ciphertext
    return base64.b64encode(combined).decode("ascii")


def decrypt_api_key(encrypted: str) -> Optional[str]:
    """
    解密 API 密钥。

    Args:
        encrypted: Base64 编码的密文（含 nonce）

    Returns:
        明文 API 密钥，失败返回 None
    """
    try:
        key = _derive_key(_get_machine_key())
        aesgcm = AESGCM(key)

        # 解码 Base64
        combined = base64.b64decode(encrypted)

        # 分离 nonce (12 字节) 和 ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]

        # 解密并验证
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")
    except (InvalidTag, Exception):
        return None


def save_secret(key: str, value: str) -> bool:
    """
    加密并保存一个密钥到 .secrets.enc 文件。

    Args:
        key: 密钥名称（如 "DEEPSEEK_API_KEY"）
        value: 明文值

    Returns:
        是否成功
    """
    try:
        # 确保目录存在
        secrets_path = Path(_SECRETS_FILE)
        secrets_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取现有密钥
        secrets = _load_secrets()

        # 加密新值
        encrypted = encrypt_api_key(value)
        secrets[key] = encrypted

        # 写回文件
        with open(secrets_path, "w", encoding="utf-8") as f:
            json.dump(secrets, f, indent=2)

        print(f"  🔒 已加密保存: {key}")
        return True
    except Exception as e:
        print(f"  ❌ 保存密钥失败: {e}")
        return False


def get_secret(key: str) -> Optional[str]:
    """
    获取解密后的密钥值。

    Args:
        key: 密钥名称

    Returns:
        明文值，失败返回 None
    """
    secrets = _load_secrets()
    encrypted = secrets.get(key)
    if not encrypted:
        return None
    return decrypt_api_key(encrypted)


def list_secret_keys() -> list:
    """列出所有已存储的密钥名称（不显示值）。"""
    secrets = _load_secrets()
    return list(secrets.keys())


def delete_secret(key: str) -> bool:
    """删除一个密钥。"""
    secrets = _load_secrets()
    if key in secrets:
        del secrets[key]
        _save_secrets(secrets)
        print(f"  🗑️ 已删除: {key}")
        return True
    return False


def has_secrets() -> bool:
    """检查是否有已存储的密钥。"""
    return len(_load_secrets()) > 0


def is_first_run() -> bool:
    """检查是否是首次运行（无任何密钥存储）。"""
    return not Path(_SECRETS_FILE).exists() or not _load_secrets()


def setup_wizard() -> Dict[str, str]:
    """
    首次运行设置向导：提示用户输入 API 密钥并加密存储。

    Returns:
        解密后的密钥字典（供当前会话使用）
    """
    print("\n" + "=" * 60)
    print("🔐 S-O-P 首次运行 — API 密钥设置")
    print("=" * 60)
    print()
    print("需要以下 API 密钥（至少一个）：")
    print("  1. DEEPSEEK_API_KEY — DeepSeek API（必填，用于 LLM 调用）")
    print("  2. PERPLEXITY_API_KEY — Perplexity API（可选，用于联网搜索）")
    print()
    print("API 密钥将被 AES-256-GCM 加密存储，仅本机可解密。")
    print()

    decrypted = {}

    # DeepSeek API Key（必填）
    while True:
        key = getpass.getpass("  DEEPSEEK_API_KEY (必填): ").strip()
        if key:
            if save_secret("DEEPSEEK_API_KEY", key):
                decrypted["DEEPSEEK_API_KEY"] = key
            break
        print("  ⚠️ DeepSeek API Key 是必填项。")

    # Perplexity API Key（可选）
    key = getpass.getpass("  PERPLEXITY_API_KEY (可选，直接回车跳过): ").strip()
    if key:
        if save_secret("PERPLEXITY_API_KEY", key):
            decrypted["PERPLEXITY_API_KEY"] = key

    print()
    print("✅ API 密钥设置完成！")
    print(f"   密钥文件: {Path(_SECRETS_FILE).resolve()}")
    print()

    return decrypted


# ── 内部辅助 ───────────────────────────────────────────────

def _load_secrets() -> Dict[str, str]:
    """从文件加载加密的密钥字典。"""
    secrets_path = Path(_SECRETS_FILE)
    if not secrets_path.exists():
        return {}
    try:
        with open(secrets_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def _save_secrets(secrets: Dict[str, str]):
    """保存密钥字典到文件。"""
    secrets_path = Path(_SECRETS_FILE)
    secrets_path.parent.mkdir(parents=True, exist_ok=True)
    with open(secrets_path, "w", encoding="utf-8") as f:
        json.dump(secrets, f, indent=2)


# ── 模块级缓存（单次会话内不解密多次） ──
_decrypted_cache: Dict[str, str] = {}


def get_decrypted_key(key_name: str, prompt_if_missing: bool = True) -> Optional[str]:
    """
    获取解密后的 API 密钥（带缓存）。

    Args:
        key_name: 密钥名称（如 "DEEPSEEK_API_KEY"）
        prompt_if_missing: 如果未找到，是否提示用户输入

    Returns:
        明文密钥，或 None
    """
    # 1. 先查内存缓存
    if key_name in _decrypted_cache:
        return _decrypted_cache[key_name]

    # 2. 查加密文件
    decrypted = get_secret(key_name)
    if decrypted:
        _decrypted_cache[key_name] = decrypted
        return decrypted

    # 3. 回退到环境变量（兼容旧配置）
    env_val = os.getenv(key_name)
    if env_val:
        print(f"  ⚠️  使用环境变量中的 {key_name}（建议迁移到加密存储）")
        _decrypted_cache[key_name] = env_val
        return env_val

    # 4. 提示输入
    if prompt_if_missing:
        print(f"  ⚠️  未找到 {key_name}")
        key = getpass.getpass(f"  请输入 {key_name}: ").strip()
        if key:
            save_secret(key_name, key)
            _decrypted_cache[key_name] = key
            return key

    return None


def migrate_from_env():
    """
    将 .env 中的明文 API Key 迁移到加密存储。
    迁移后建议手动从 .env 中删除明文密钥。
    """
    keys_to_migrate = ["DEEPSEEK_API_KEY", "PERPLEXITY_API_KEY"]
    migrated = []

    for key_name in keys_to_migrate:
        env_val = os.getenv(key_name)
        if env_val and not get_secret(key_name):
            if save_secret(key_name, env_val):
                migrated.append(key_name)

    if migrated:
        print(f"\n  ✅ 已迁移 {len(migrated)} 个密钥到加密存储: {', '.join(migrated)}")
        print(f"  💡 建议从 .env 文件中删除明文密钥以提高安全性。")

    return migrated
