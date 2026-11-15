import uuid
from datetime import timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import require_project_permission
from app.db.session import get_db
from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.task import ActivityLog
from app.models.user import User
from app.schemas.activity_log import ActivityLogResponse
from app.schemas.user import get_user_initials
from app.services.activity_log_service import describe_changes, referenced_users


router = APIRouter(prefix="/projects", tags=["activity-logs"])


@router.get("/{project_id}/activity-logs", response_model=list[ActivityLogResponse])
def get_activity_logs(
    project_id: uuid.UUID,
    _: Annotated[ProjectMember, Depends(require_project_permission("project.view"))],
    db: Annotated[Session, Depends(get_db)],
):
    """Đọc nhật ký dự án theo quyền project.view, mới nhất trước."""
    project = db.query(Project).filter(
        Project.id == project_id, Project.deleted_at.is_(None)
    ).first()
    if project is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy dự án")

    entries = (
        db.query(ActivityLog, User)
        .outerjoin(User, User.id == ActivityLog.actor_id)
        .filter(ActivityLog.project_id == project_id)
        .order_by(ActivityLog.created_at.desc(), ActivityLog.id.desc())
        .all()
    )
    user_ids = set()
    for entry, _actor in entries:
        user_ids.update(referenced_users(entry.changes or {}))
    names = {
        str(user.id): user.full_name + (" (đã xóa)" if user.deleted_at else "")
        for user in db.query(User).filter(User.id.in_(user_ids)).all()
    } if user_ids else {}
    statuses = {code: name for code, name in db.query(Status.code, Status.name).filter(Status.project_id == project_id).all()}
    result = []
    for entry, user in entries:
        actor = user.full_name if user and user.deleted_at is None else "Người dùng đã xóa"
        created_at = entry.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        result.append(ActivityLogResponse(
            id=str(entry.id),
            actor=actor,
            actorInitials=get_user_initials(actor),
            action=entry.action,
            entityType=entry.entity_type,
            description=entry.description,
            createdAt=created_at,
            changeCount=len(entry.changes or {}),
            changeDetails=describe_changes(entry.changes or {}, names, statuses, project.timezone),
        ))
    return result
