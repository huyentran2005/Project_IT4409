import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_project_permission
from app.db.session import get_db
from app.models.project_member import ProjectMember
from app.models.project_role import (
    Permission,
    ProjectRole,
    project_role_permissions,
)
from app.schemas.project_member import (
    ProjectMemberResponse,
    RolePermissionResponse,
    RoleSummary,
    UpdateMemberRoleRequest,
    UpdateRolePermissionsRequest,
)
from app.schemas.user import get_user_initials


router = APIRouter(prefix="/projects", tags=["project-permissions"])


def _member_response(member: ProjectMember) -> ProjectMemberResponse:
    """Mục đích:
        Chuyển bản ghi thành viên thành dữ liệu trả về cho frontend.

    Đầu vào:
        member: Bản ghi ProjectMember đã liên kết với User và ProjectRole.
    Đầu ra:
        ProjectMemberResponse chứa thông tin người dùng và vai trò trong dự án.
    """
    user = member.user
    role = member.role
    return ProjectMemberResponse(
        id=str(user.id),
        name=user.full_name,
        email=user.email,
        avatarUrl=user.avatar_url,
        initials=get_user_initials(user.full_name),
        color=user.avatar_color or "#5B5CE2",
        role=RoleSummary(id=str(role.id), code=role.code, name=role.name),
        joinedAt=member.joined_at,
    )


def _permission_response(
    permission: Permission, project_id: uuid.UUID
) -> RolePermissionResponse:
    """Mục đích:
        Chuyển một quyền thành dữ liệu ma trận phân quyền của dự án.

    Đầu vào:
        permission: Quyền cần chuyển đổi.
        project_id: ID dự án dùng để lọc các vai trò liên quan.
    Đầu ra:
        RolePermissionResponse gồm thông tin quyền và các role được cấp quyền.
    """
    roles = sorted(
        (role for role in permission.roles if role.project_id == project_id),
        key=lambda role: role.position,
    )
    return RolePermissionResponse(
        key=permission.code,
        label=permission.name,
        description=permission.description or "",
        roles=[role.code for role in roles],
    )


def _get_member(
    db: Session, project_id: uuid.UUID, user_id: uuid.UUID
) -> ProjectMember:
    """Mục đích:
        Tìm một thành viên theo dự án và người dùng.

    Đầu vào:
        db: Phiên kết nối cơ sở dữ liệu.
        project_id: ID dự án.
        user_id: ID người dùng cần tìm.
    Đầu ra:
        Bản ghi ProjectMember; phát sinh HTTP 404 nếu không tìm thấy.
    """
    member = (
        db.query(ProjectMember)
        .filter(
            ProjectMember.project_id == project_id,
            ProjectMember.user_id == user_id,
        )
        .first()
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy thành viên trong dự án",
        )
    return member


@router.get(
    "/{project_id}/members",
    response_model=list[ProjectMemberResponse],
)
def get_members(
    project_id: uuid.UUID,
    _: Annotated[
        ProjectMember, Depends(require_project_permission("project.view"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Lấy danh sách thành viên của dự án.

    Đầu vào:
        project_id: ID dự án lấy từ URL.
        _: Thành viên hiện tại đã được kiểm tra quyền ``project.view``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        Danh sách ProjectMemberResponse, sắp xếp theo thời gian tham gia.
    """
    members = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id)
        .order_by(ProjectMember.joined_at, ProjectMember.user_id)
        .all()
    )
    return [_member_response(member) for member in members]


@router.patch(
    "/{project_id}/members/{user_id}/role",
    status_code=status.HTTP_204_NO_CONTENT,
)
def update_member_role(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    actor: Annotated[
        ProjectMember, Depends(require_project_permission("member.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Cập nhật vai trò của một thành viên trong dự án.

    Đầu vào:
        project_id: ID dự án.
        user_id: ID thành viên cần đổi vai trò.
        body: Mã vai trò mới.
        actor: Thành viên thực hiện thao tác, đã có quyền ``member.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        HTTP 204 khi cập nhật thành công; phát sinh HTTP 403/404 nếu không hợp lệ.
    """
    target = _get_member(db, project_id, user_id)

    if target.role.code == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể thay đổi vai trò owner bằng API này",
        )
    if body.roleCode == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Hãy dùng chức năng chuyển quyền sở hữu dự án",
        )
    if actor.role.code != "owner" and target.role.code == "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ owner có thể thay đổi vai trò manager",
        )

    new_role = (
        db.query(ProjectRole)
        .filter(
            ProjectRole.project_id == project_id,
            ProjectRole.code == body.roleCode,
        )
        .first()
    )
    if new_role is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Vai trò không tồn tại trong dự án",
        )
    if actor.role.code != "owner" and new_role.code == "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ owner có thể cấp vai trò manager",
        )
    if actor.user_id == target.user_id and new_role.id != target.role_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bạn không thể tự thay đổi vai trò của mình",
        )

    target.role_id = new_role.id
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.delete(
    "/{project_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_member(
    project_id: uuid.UUID,
    user_id: uuid.UUID,
    actor: Annotated[
        ProjectMember, Depends(require_project_permission("member.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Xóa một thành viên khỏi dự án.

    Đầu vào:
        project_id: ID dự án.
        user_id: ID thành viên cần xóa.
        actor: Thành viên thực hiện thao tác, đã có quyền ``member.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        HTTP 204 khi xóa thành công; phát sinh lỗi nếu vi phạm quy tắc vai trò.
    """
    target = _get_member(db, project_id, user_id)

    if target.role.code == "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể xóa owner khỏi dự án",
        )
    if actor.user_id == target.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không thể tự xóa mình bằng API quản lý thành viên",
        )
    if actor.role.code != "owner" and target.role.code == "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chỉ owner có thể xóa manager",
        )

    db.delete(target)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Không thể xóa thành viên đang được tham chiếu bởi công việc "
                "hoặc dữ liệu khác"
            ),
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{project_id}/role-permissions",
    response_model=list[RolePermissionResponse],
)
def get_role_permissions(
    project_id: uuid.UUID,
    _: Annotated[
        ProjectMember, Depends(require_project_permission("project.view"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Lấy ma trận quyền của các vai trò trong dự án.

    Đầu vào:
        project_id: ID dự án.
        _: Thành viên hiện tại đã có quyền ``project.view``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        Danh sách RolePermissionResponse dùng để hiển thị ma trận phân quyền.
    """
    permissions = db.query(Permission).order_by(Permission.code).all()
    return [
        _permission_response(permission, project_id)
        for permission in permissions
    ]


@router.put(
    "/{project_id}/role-permissions",
    response_model=list[RolePermissionResponse],
)
def update_role_permissions(
    project_id: uuid.UUID,
    body: UpdateRolePermissionsRequest,
    _: Annotated[
        ProjectMember, Depends(require_project_permission("project.manage"))
    ],
    db: Annotated[Session, Depends(get_db)],
):
    """Mục đích:
        Thay thế cấu hình quyền của các vai trò trong dự án.

    Đầu vào:
        project_id: ID dự án.
        body: Ma trận permission-role mới từ request.
        _: Thành viên hiện tại đã có quyền ``project.manage``.
        db: Phiên kết nối cơ sở dữ liệu.
    Đầu ra:
        Danh sách RolePermissionResponse sau khi cập nhật thành công.
    """
    roles = (
        db.query(ProjectRole)
        .filter(ProjectRole.project_id == project_id)
        .order_by(ProjectRole.position)
        .all()
    )
    role_by_code = {role.code: role for role in roles}
    permissions = db.query(Permission).order_by(Permission.code).all()
    permission_by_code = {
        permission.code: permission for permission in permissions
    }

    request_by_code = {item.key: set(item.roles) for item in body.permissions}
    if len(request_by_code) != len(body.permissions):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Danh sách quyền chứa key bị trùng",
        )
    if set(request_by_code) != set(permission_by_code):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Request phải chứa đầy đủ và đúng các permission hiện có",
        )

    available_role_codes = set(role_by_code)
    for permission_code, requested_roles in request_by_code.items():
        if not requested_roles <= available_role_codes:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Role không hợp lệ cho quyền {permission_code}",
            )
        if "owner" not in requested_roles:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Owner phải luôn có mọi quyền",
            )

    if request_by_code.get("project.view") != available_role_codes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mọi vai trò phải có quyền project.view",
        )

    role_ids = [role.id for role in roles]
    if role_ids:
        db.execute(
            delete(project_role_permissions).where(
                project_role_permissions.c.role_id.in_(role_ids)
            )
        )

    rows = [
        {
            "role_id": role_by_code[role_code].id,
            "permission_id": permission_by_code[permission_code].id,
        }
        for permission_code, role_codes in request_by_code.items()
        for role_code in role_codes
    ]
    if rows:
        db.execute(insert(project_role_permissions), rows)

    db.commit()
    db.expire_all()
    permissions = db.query(Permission).order_by(Permission.code).all()
    return [
        _permission_response(permission, project_id)
        for permission in permissions
    ]
