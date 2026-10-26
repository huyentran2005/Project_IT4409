from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.project import CreateProjectRequest, ProjectSummary
from app.services.project_service import ProjectKeyExists, create_project

router = APIRouter(prefix="/projects", tags=["projects"])


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
