import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_project_permission
from app.core.config import settings
from app.db.session import get_db
from app.models.project_invitation import ProjectInvitation
from app.models.project_member import ProjectMember
from app.models.project import Project
from app.models.project_role import ProjectRole
from app.models.user import User
from app.schemas.project_member import (
    AcceptInvitationResponse,
    InvitationDetailResponse,
    InvitationResponse,
    InviteMemberRequest,
    RejectInvitationResponse,
)
from app.services.email_service import (
    EmailDeliveryError,
    send_project_invitation_email,
    smtp_is_configured,
)


router = APIRouter(prefix="/projects", tags=["project-invitations"])
invitation_router = APIRouter(prefix="/invitations", tags=["invitations"])


def _invitation_status(
    invitation: ProjectInvitation, now: datetime | None = None
) -> str:
    """Mục đích:
        Xác định trạng thái hiện tại của một lời mời.

    Đầu vào:
        invitation: Bản ghi lời mời cần kiểm tra.
        now: Thời điểm so sánh; mặc định sử dụng thời gian UTC hiện tại.
    Đầu ra:
        Chuỗi trạng thái ``accepted``, ``expired`` hoặc ``pending``.
    """
    now = now or datetime.now(timezone.utc)
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.expires_at <= now:
        return "expired"
    return "pending"


@router.post(
    "/{project_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    project_id: uuid.UUID,
    body: InviteMemberRequest,
    actor: Annotated[
        ProjectMember, Depends(require_project_permission("member.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Tạo lời mời tham gia dự án và gửi email cho người nhận.

    Đầu vào:
        project_id: ID dự án cần mời thành viên.
        body: Email người nhận và mã vai trò sẽ được cấp.
        actor: Thành viên gửi lời mời, đã có quyền ``member.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        InvitationResponse của lời mời vừa tạo hoặc được cấp lại token.
    """
    if not smtp_is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="SMTP chưa được cấu hình; không thể gửi email lời mời",
        )

    project = (
        db.query(Project)
        .filter(Project.id == project_id, Project.deleted_at.is_(None))
        .first()
    )
    if project is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dự án không tồn tại",
        )

    if body.roleCode == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể mời thành viên với vai trò owner",
        )

    role = (
        db.query(ProjectRole)
        .filter(
            ProjectRole.project_id == project_id,
            ProjectRole.code == body.roleCode,
        )
        .first()
    )
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vai trò không tồn tại trong dự án",
        )

    existing_member = (
        db.query(ProjectMember)
        .join(User, User.id == ProjectMember.user_id)
        .filter(
            ProjectMember.project_id == project_id,
            func.lower(User.email) == body.email,
        )
        .first()
    )
    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Người dùng đã là thành viên dự án",
        )

    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    invitation = (
        db.query(ProjectInvitation)
        .filter(
            ProjectInvitation.project_id == project_id,
            func.lower(ProjectInvitation.email) == body.email,
            ProjectInvitation.accepted_at.is_(None),
        )
        .first()
    )

    if invitation is None:
        invitation = ProjectInvitation(
            project_id=project_id,
            email=body.email,
            role_id=role.id,
            token_hash=token_hash,
            invited_by=actor.user_id,
            expires_at=expires_at,
        )
        db.add(invitation)
    else:
        # Cấp lại token cho cả lời mời pending và lời mời đã hết hạn.
        invitation.role_id = role.id
        invitation.token_hash = token_hash
        invitation.invited_by = actor.user_id
        invitation.expires_at = expires_at

    try:
        db.commit()
        db.refresh(invitation)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể tạo lời mời do dữ liệu đã thay đổi",
        ) from exc

    invite_url = f"{settings.FRONTEND_URL}/invitations/{raw_token}"
    try:
        send_project_invitation_email(
            recipient=invitation.email,
            project_name=project.name,
            inviter_name=actor.user.full_name,
            invite_url=invite_url,
        )
    except EmailDeliveryError as exc:
        # Lời mời vẫn được giữ để người gửi có thể thử gửi lại.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return InvitationResponse(
        id=str(invitation.id),
        email=invitation.email,
        roleCode=role.code,
        status="pending",
        expiresAt=invitation.expires_at,
        createdAt=invitation.created_at,
        inviteUrl=None,
    )


@router.get(
    "/{project_id}/invitations",
    response_model=list[InvitationResponse],
)
def get_invitations(
    project_id: uuid.UUID,
    _: Annotated[
        ProjectMember, Depends(require_project_permission("member.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Lấy toàn bộ lời mời của một dự án.

    Đầu vào:
        project_id: ID dự án.
        _: Thành viên hiện tại đã có quyền ``member.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        Danh sách InvitationResponse theo thứ tự mới nhất trước.
    """
    invitations = (
        db.query(ProjectInvitation)
        .filter(ProjectInvitation.project_id == project_id)
        .order_by(ProjectInvitation.created_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    return [
        InvitationResponse(
            id=str(invitation.id),
            email=invitation.email,
            roleCode=invitation.role.code,
            status=_invitation_status(invitation, now),
            expiresAt=invitation.expires_at,
            createdAt=invitation.created_at,
        )
        for invitation in invitations
    ]


@router.delete(
    "/{project_id}/invitations/{invite_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_invitation(
    project_id: uuid.UUID,
    invite_id: uuid.UUID,
    _: Annotated[
        ProjectMember, Depends(require_project_permission("member.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Hủy một lời mời chưa được chấp nhận.

    Đầu vào:
        project_id: ID dự án sở hữu lời mời.
        invite_id: ID lời mời cần hủy.
        _: Thành viên hiện tại đã có quyền ``member.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        HTTP 204 khi xóa thành công; phát sinh HTTP 404 hoặc 409 nếu không hợp lệ.
    """
    invitation = (
        db.query(ProjectInvitation)
        .filter(
            ProjectInvitation.id == invite_id,
            ProjectInvitation.project_id == project_id,
        )
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy lời mời",
        )
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể hủy lời mời đã được chấp nhận",
        )

    db.delete(invitation)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@invitation_router.get(
    "/{token}",
    response_model=InvitationDetailResponse,
)
def get_invitation_detail(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Lấy chi tiết lời mời bằng token dành cho người đang đăng nhập.

    Đầu vào:
        token: Token thô được gửi trong đường dẫn lời mời.
        current_user: Người dùng đã đăng nhập để đối chiếu email người nhận.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        InvitationDetailResponse chứa dự án, vai trò và trạng thái lời mời.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    invitation = (
        db.query(ProjectInvitation)
        .filter(ProjectInvitation.token_hash == token_hash)
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lời mời không tồn tại hoặc đã bị từ chối",
        )
    if invitation.email.casefold() != current_user.email.casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lời mời không dành cho tài khoản này",
        )

    return InvitationDetailResponse(
        projectId=str(invitation.project_id),
        projectName=invitation.project.name,
        projectKey=invitation.project.key,
        projectColor=invitation.project.color,
        roleCode=invitation.role.code,
        roleName=invitation.role.name,
        inviterName=invitation.inviter_member.user.full_name,
        email=invitation.email,
        status=_invitation_status(invitation),
        expiresAt=invitation.expires_at,
    )


@invitation_router.post(
    "/{token}/accept",
    response_model=AcceptInvitationResponse,
)
def accept_invitation(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Chấp nhận lời mời và thêm người dùng vào dự án.

    Đầu vào:
        token: Token thô của lời mời.
        current_user: Người dùng đang chấp nhận lời mời.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        AcceptInvitationResponse gồm thông báo thành công và ID dự án.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    invitation = (
        db.query(ProjectInvitation)
        .filter(ProjectInvitation.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lời mời không tồn tại",
        )
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lời mời đã được sử dụng",
        )
    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Lời mời đã hết hạn",
        )
    if invitation.email.casefold() != current_user.email.casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lời mời không dành cho tài khoản này",
        )

    existing_member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == invitation.project_id,
            ProjectMember.user_id == current_user.id,
        )
        .first()
    )
    if existing_member is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bạn đã là thành viên của dự án",
        )

    db.add(
        ProjectMember(
            project_id=invitation.project_id,
            user_id=current_user.id,
            role_id=invitation.role_id,
        )
    )
    invitation.accepted_at = now

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Không thể chấp nhận lời mời do dữ liệu đã thay đổi",
        ) from exc

    return AcceptInvitationResponse(
        message="Tham gia dự án thành công",
        projectId=str(invitation.project_id),
    )


@invitation_router.post(
    "/{token}/reject",
    response_model=RejectInvitationResponse,
)
def reject_invitation(
    token: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Từ chối và xóa lời mời của người dùng hiện tại.

    Đầu vào:
        token: Token thô của lời mời.
        current_user: Người dùng đang từ chối lời mời.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        RejectInvitationResponse xác nhận lời mời đã được từ chối.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc)

    invitation = (
        db.query(ProjectInvitation)
        .filter(ProjectInvitation.token_hash == token_hash)
        .with_for_update()
        .first()
    )
    if invitation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lời mời không tồn tại hoặc đã bị từ chối",
        )
    if invitation.accepted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Lời mời đã được chấp nhận",
        )
    if invitation.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Lời mời đã hết hạn",
        )
    if invitation.email.casefold() != current_user.email.casefold():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Lời mời không dành cho tài khoản này",
        )

    db.delete(invitation)
    db.commit()
    return RejectInvitationResponse(message="Đã từ chối lời mời")



