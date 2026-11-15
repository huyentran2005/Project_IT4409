"""API timesheet + bình luận.

  GET    /api/tasks/{task_id}/timesheets        danh sách giờ làm của task
  POST   /api/tasks/{task_id}/timesheets        ghi nhận giờ (task.manage)
  DELETE /api/timesheets/{entry_id}             xóa bản ghi (tác giả/chủ dự án)
  GET    /api/timesheets                        nhật ký giờ làm của tôi (lọc ngày, OT, dự án)
  GET    /api/timesheets/summary                số liệu Dashboard (giờ tuần này, ngày thiếu log)
  GET    /api/tasks/{task_id}/comments          danh sách bình luận
  POST   /api/tasks/{task_id}/comments          thêm bình luận
  DELETE /api/comments/{comment_id}             xóa bình luận (tác giả/chủ dự án)
"""
import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.collaboration import (
    CommentCreate,
    TimesheetCreate,
    TimesheetListResponse,
    TimesheetSummaryResponse,
)
from app.schemas.task import TaskCommentSchema, TimesheetEntrySchema
from app.services import collaboration_service as svc
from app.services.task_service import TaskServiceError

router = APIRouter(tags=["timesheets & comments"])

_STATUS = {
    "not_found": status.HTTP_404_NOT_FOUND,
    "forbidden": status.HTTP_403_FORBIDDEN,
    "bad_request": status.HTTP_400_BAD_REQUEST,
    "conflict": status.HTTP_409_CONFLICT,
}


def _http(exc: TaskServiceError) -> HTTPException:
    return HTTPException(status_code=_STATUS.get(exc.code, status.HTTP_400_BAD_REQUEST), detail=exc.message)


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


# NOTE: /timesheets/summary phải khai báo trước /timesheets/{entry_id}
@router.get("/timesheets/summary", response_model=TimesheetSummaryResponse)
def read_my_timesheet_summary(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return svc.my_time_summary(db, user=user)


@router.get("/timesheets", response_model=TimesheetListResponse)
def read_my_timesheets(
    date_from: date | None = None,
    date_to: date | None = None,
    overtime_only: bool = False,
    project_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return svc.list_my_time_entries(
        db, user=user, date_from=date_from, date_to=date_to, overtime_only=overtime_only, project_id=project_id
    )


@router.get("/tasks/{task_id}/timesheets", response_model=list[TimesheetEntrySchema])
def read_task_timesheets(task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return svc.list_task_time_entries(db, task_id=task_id, user=user)
    except TaskServiceError as exc:
        raise _http(exc)


@router.post("/tasks/{task_id}/timesheets", response_model=TimesheetEntrySchema, status_code=status.HTTP_201_CREATED)
def create_task_timesheet(
    task_id: uuid.UUID,
    payload: TimesheetCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        return svc.create_time_entry(db, task_id=task_id, user=user, payload=payload, client_ip=_ip(request))
    except TaskServiceError as exc:
        raise _http(exc)


@router.delete("/timesheets/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_timesheet(
    entry_id: uuid.UUID, request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        svc.delete_time_entry(db, entry_id=entry_id, user=user, client_ip=_ip(request))
    except TaskServiceError as exc:
        raise _http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}/comments", response_model=list[TaskCommentSchema])
def read_task_comments(task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        return svc.list_comments(db, task_id=task_id, user=user)
    except TaskServiceError as exc:
        raise _http(exc)


@router.post("/tasks/{task_id}/comments", response_model=TaskCommentSchema, status_code=status.HTTP_201_CREATED)
def create_task_comment(
    task_id: uuid.UUID, payload: CommentCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    try:
        return svc.create_comment(db, task_id=task_id, user=user, payload=payload)
    except TaskServiceError as exc:
        raise _http(exc)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_comment(comment_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    try:
        svc.delete_comment(db, comment_id=comment_id, user=user)
    except TaskServiceError as exc:
        raise _http(exc)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
