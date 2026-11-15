import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationPage, NotificationResponse
from app.services.notification_service import visible_notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


def notification_response(entry: Notification):
    payload = entry.payload or {}
    return NotificationResponse(
        id=str(entry.id), projectId=str(entry.project_id) if entry.project_id else None,
        taskId=payload.get("taskId"), taskKey=payload.get("taskKey"), taskTitle=payload.get("taskTitle"),
        projectName=payload.get("projectName"), taskDeleted=bool(payload.get("taskDeleted", False)),
        type=entry.type, title=entry.title,
        readAt=(entry.read_at.replace(tzinfo=timezone.utc) if entry.read_at and not entry.read_at.tzinfo else entry.read_at),
        createdAt=entry.created_at.replace(tzinfo=timezone.utc) if not entry.created_at.tzinfo else entry.created_at,
    )


@router.get("", response_model=NotificationPage)
def get_notifications(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0),
                      db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = visible_notifications(db, user.id)
    unread = query.filter(Notification.read_at.is_(None)).count()
    entries = query.order_by(Notification.created_at.desc(), Notification.id.desc()).offset(offset).limit(limit + 1).all()
    return NotificationPage(items=[notification_response(item) for item in entries[:limit]],
                             unreadCount=unread, hasMore=len(entries) > limit)


@router.patch("/read-all", status_code=204)
def read_all(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    visible_notifications(db, user.id).filter(Notification.read_at.is_(None)).update(
        {Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False
    )
    db.commit()
    return Response(status_code=204)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    query = visible_notifications(db, user.id).filter(Notification.id == notification_id)
    entry = query.first()
    if entry is None:
        raise HTTPException(404, "Không tìm thấy thông báo")
    query.filter(Notification.read_at.is_(None)).update({Notification.read_at: datetime.now(timezone.utc)}, synchronize_session=False)
    db.commit()
    db.refresh(entry)
    return notification_response(entry)
