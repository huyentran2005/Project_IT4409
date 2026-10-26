import re
from pydantic import BaseModel, Field, field_validator
from app.schemas.user import UserSummary


class CreateProjectRequest(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    key: str
    description: str
    color: str = "#5B5CE2"

    @field_validator("name")
    @classmethod
    def _name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tên dự án không được để trống")
        return v

    @field_validator("description")
    @classmethod
    def _description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mô tả dự án không được để trống")
        return v

    @field_validator("key")
    @classmethod
    def _key(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.fullmatch(r"[A-Z0-9]{1,8}", v):
            raise ValueError("Mã dự án gồm 1-8 ký tự chữ hoặc số, không dấu")
        return v

    @field_validator("color")
    @classmethod
    def _color(cls, v: str) -> str:
        if not re.fullmatch(r"#[0-9A-Fa-f]{6}", v):
            raise ValueError("Màu dự án phải có dạng #RRGGBB")
        return v


class ProjectSummary(BaseModel):
    id: str
    key: str
    name: str
    description: str
    color: str
    progress: int = 0
    members: list[UserSummary] = []
