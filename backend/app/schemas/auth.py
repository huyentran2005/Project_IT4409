import re
from pydantic import BaseModel, Field, field_validator
from app.schemas.user import UserSummary

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(value: str) -> str:
    value = value.strip().lower()
    if len(value) > 320 or not _EMAIL_RE.match(value):
        raise ValueError("Email không hợp lệ")
    return value


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=1, max_length=128)

    _norm_email = field_validator("email")(_normalize_email)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: str
    phone: str = Field(min_length=10, max_length=10, pattern=r"^[0-9]{10}$")#sdt phai nhap 10 so
    password: str = Field(min_length=8, max_length=128)

    _norm_email = field_validator("email")(_normalize_email)

    @field_validator("name")
    @classmethod
    def _strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Họ tên không được để trống")
        return v


class RefreshRequest(BaseModel):
    refreshToken: str


class LogoutRequest(BaseModel):
    refreshToken: str | None = None


class AuthResponse(BaseModel):
    accessToken: str
    refreshToken: str
    user: UserSummary
