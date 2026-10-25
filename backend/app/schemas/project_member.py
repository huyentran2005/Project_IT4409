import re
from datetime import datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ProjectRoleCode = Literal["owner", "manager", "member", "viewer"]


class RoleSummary(BaseModel):
    id: str
    code: str
    name: str


class ProjectMemberResponse(BaseModel):
    id: str
    name: str
    email: str
    avatarUrl: str | None = None
    initials: str
    color: str
    role: RoleSummary
    joinedAt: datetime


class InviteMemberRequest(BaseModel):
    email: str
    roleCode: ProjectRoleCode = "member"

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Mục đích:
            Chuẩn hóa và kiểm tra email dùng để gửi lời mời.

        Đầu vào:
            value: Chuỗi email nhận từ request.
        Đầu ra:
            Email đã bỏ khoảng trắng và chuyển thành chữ thường; phát sinh lỗi
            validation nếu email không đúng định dạng.
        """
        value = value.strip().lower()
        if len(value) > 320 or not _EMAIL_RE.match(value):
            raise ValueError("Email không hợp lệ")
        return value


class InvitationResponse(BaseModel):
    id: str
    email: str
    roleCode: str
    status: Literal["pending", "accepted", "expired"]
    expiresAt: datetime
    createdAt: datetime
    inviteUrl: str | None = None


class InvitationDetailResponse(BaseModel):
    projectId: str
    projectName: str
    projectKey: str
    projectColor: str
    roleCode: str
    roleName: str
    inviterName: str
    email: str
    status: Literal["pending", "accepted", "expired"]
    expiresAt: datetime


class AcceptInvitationResponse(BaseModel):
    message: str
    projectId: str


class RejectInvitationResponse(BaseModel):
    message: str


class UpdateMemberRoleRequest(BaseModel):
    roleCode: ProjectRoleCode = Field(
        validation_alias=AliasChoices("roleCode", "role")
    )


class RolePermissionResponse(BaseModel):
    key: str
    label: str
    description: str
    roles: list[str]


class RolePermissionUpdate(BaseModel):
    key: str = Field(min_length=1, max_length=80)
    roles: list[ProjectRoleCode]


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[RolePermissionUpdate]

