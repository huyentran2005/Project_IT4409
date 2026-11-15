from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import CreateProjectRequest, ProjectSummary
from app.services.project_service import (
    ProjectKeyExists,
    create_project,
    list_user_projects,
)

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectSummary])
def list_projects_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lấy danh sách tất cả các dự án (chưa xóa) mà người dùng hiện tại là thành viên.

    Input (Đầu vào):
        - Authorization Header: Bearer <access_token>.

    Output (Đầu ra):
        - 200 OK: Danh sách list[ProjectSummary] (gồm id, key, name, description, color, progress, members).
        - 401 Unauthorized: Chưa đăng nhập hoặc token hết hạn.
    """
    return list_user_projects(db, current_user)


@router.post("", response_model=ProjectSummary, status_code=status.HTTP_201_CREATED)
def create_project_endpoint(
    payload: CreateProjectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Tạo dự án mới; người tạo trở thành owner.

    Input: Header Authorization Bearer; JSON {name, key (1-8 chữ/số), description, color (#RRGGBB)}.
    Output: 201 ProjectSummary; 409 nếu key đã tồn tại; 422 nếu dữ liệu sai; 401 nếu chưa đăng nhập.
    Ghi vào: projects, project_roles (4 vai trò), project_role_permissions, project_members, statuses (4 cột).
    """
    try:
        return create_project(db, current_user, payload)
    except ProjectKeyExists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Mã dự án '{payload.key}' đã tồn tại. Hãy chọn mã khác.",
        )
