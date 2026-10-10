"""
安全工具模块：密码哈希、JWT 令牌、API Key 生成。

密码哈希采用标准库 hashlib.pbkdf2_hmac，避免引入需要本地编译的依赖。
"""
import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.core.config import settings

# PBKDF2 迭代次数（兼顾安全与性能）
_PBKDF2_ROUNDS = 200_000
_PBKDF2_ALGO = "sha256"


def hash_password(password: str) -> str:
    """对明文密码进行加盐哈希，返回 `算法$迭代$盐$哈希` 格式字符串。"""
    salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac(
        _PBKDF2_ALGO, password.encode("utf-8"), salt, _PBKDF2_ROUNDS
    )
    return f"pbkdf2_{_PBKDF2_ALGO}${_PBKDF2_ROUNDS}${salt.hex()}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码与存储的哈希是否匹配。"""
    try:
        algo_tag, rounds_s, salt_hex, hash_hex = stored.split("$")
        rounds = int(rounds_s)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
        algo = algo_tag.replace("pbkdf2_", "")
        dk = hashlib.pbkdf2_hmac(algo, password.encode("utf-8"), salt, rounds)
        # 使用恒定时间比较，防止时序攻击
        return hmac.compare_digest(dk, expected)
    except (ValueError, AttributeError):
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    """生成 JWT 访问令牌，subject 通常为用户名。"""
    minutes = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    expire = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    """解码 JWT 令牌，成功返回 subject（用户名），失败返回 None。"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def generate_api_key() -> str:
    """生成一个高强度的 API Key。"""
    return "gk_" + secrets.token_urlsafe(32)
