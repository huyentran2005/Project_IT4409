import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any
import jwt
from pwdlib import PasswordHash
from app.core.config import settings

# Argon2id - khớp yêu cầu SRS: băm mật khẩu bcrypt/argon2
_password_hash = PasswordHash.recommended()
# Hash giả để verify khi email không tồn tại -> thời gian phản hồi không lộ email có tồn tại hay không
_DUMMY_HASH = _password_hash.hash("dummy-password-for-timing")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Trả về True nếu mật khẩu khớp. password_hash=None (tài khoản chỉ SSO) luôn trả False."""
    if not password_hash:
        _password_hash.verify(password, _DUMMY_HASH)
        return False
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        return False


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
    }
    encoded_jwt = jwt.encode(
        to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
    )
    return encoded_jwt


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except jwt.PyJWTError:
        return None


def generate_refresh_token() -> tuple[str, str]:
    """Tạo refresh token ngẫu nhiên và mã hash SHA-256 để lưu trữ an toàn trong DB."""
    raw_token = secrets.token_urlsafe(64)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

