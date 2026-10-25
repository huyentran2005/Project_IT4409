import uuid
from typing import Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import and_
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.security import decode_access_token
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, project_role_permissions
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Mục đích:
        Lấy người dùng hiện tại từ access token.

    Đầu vào:
        token: Bearer access token lấy từ header Authorization.
        db: Phiên kết nối cơ sở dữ liệu do FastAPI cung cấp.
    Đầu ra:
        Đối tượng User đang đăng nhập; phát sinh HTTP 401 nếu xác thực thất bại.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chưa cung cấp token xác thực",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token không hợp lệ hoặc đã hết hạn",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token chứa định danh người dùng không hợp lệ",
        )

    user = (
        db.query(User)
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )

    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tài khoản không tồn tại hoặc đã bị khóa",
        )

    return user


def require_project_permission(permission_code: str):
    """Mục đích:
        Tạo dependency dùng để kiểm tra một quyền trong dự án.

    Đầu vào:
        permission_code: Mã quyền cần kiểm tra, ví dụ ``member.manage``.
    Đầu ra:
        Hàm dependency ``check_permission`` để FastAPI sử dụng tại endpoint.
    """

    def check_permission(
        project_id: uuid.UUID,
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[Session, Depends(get_db)],
    ) -> ProjectMember:
        """Mục đích:
            Kiểm tra người dùng có quyền yêu cầu trong dự án hay không.

        Đầu vào:
            project_id: ID dự án lấy từ URL.
            current_user: Người dùng đã được xác thực.
            db: Phiên kết nối cơ sở dữ liệu.
        Đầu ra:
            Bản ghi ProjectMember nếu có quyền; phát sinh HTTP 403 nếu không có.
        """
        member = (
            db.query(ProjectMember)
            .join(
                ProjectRole,
                and_(
                    ProjectRole.id == ProjectMember.role_id,
                    ProjectRole.project_id == ProjectMember.project_id,
                ),
            )
            .join(
                project_role_permissions,
                project_role_permissions.c.role_id == ProjectRole.id,
            )
            .join(
                Permission,
                Permission.id == project_role_permissions.c.permission_id,
            )
            .filter(
                ProjectMember.project_id == project_id,
                ProjectMember.user_id == current_user.id,
                Permission.code == permission_code,
            )
            .first()
        )

        if member is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Bạn không có quyền thực hiện thao tác này trong dự án",
            )

        return member

    return check_permission

