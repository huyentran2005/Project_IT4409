import uuid
from contextlib import contextmanager

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.tasks import _raise_http_error
from app.db.session import get_db
from app.models.user import User
from app.schemas.task import (
    CommentRequest, MoveTaskRequest, ReviewerRequest, TaskCommentSchema, TaskResponse,
    TimeEntryRequest, TimesheetEntrySchema, UpdateTaskRequest, comment_to_response, time_entry_to_response, task_to_response,
)
from app.services import task_actions
from app.services.task_service import TaskServiceError

router = APIRouter(prefix="/tasks", tags=["tasks"])


@contextmanager
def action_transaction(db: Session):
    try:
        yield
    except TaskServiceError as exc:
        db.rollback()
        _raise_http_error(exc)
    except Exception:
        db.rollback()
        raise


@router.get("/{task_id}", response_model=TaskResponse)
def read_task(task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_to_response(task_actions.get_task(db, task_id, user))


@router.patch("/{task_id}", response_model=TaskResponse)
@router.patch("/{task_id}/properties", response_model=TaskResponse)
def update_task(task_id: uuid.UUID, payload: UpdateTaskRequest, request: Request,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_actions.update_task(db, task_id, user, payload, request.client.host if request.client else None)


@router.patch("/{task_id}/move", response_model=TaskResponse)
def move_task(task_id: uuid.UUID, payload: MoveTaskRequest, request: Request,
              db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_actions.update_task(db, task_id, user, payload, request.client.host if request.client else None)


@router.patch("/{task_id}/reviewer", response_model=TaskResponse)
def set_reviewer(task_id: uuid.UUID, payload: ReviewerRequest, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_actions.update_task(db, task_id, user, UpdateTaskRequest(**payload.model_dump()),
                                        request.client.host if request.client else None)


@router.get("/{task_id}/timesheets", response_model=list[TimesheetEntrySchema])
def list_timesheets(task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        task = task_actions.get_task(db, task_id, user)
        return [time_entry_to_response(entry) for entry in task.time_entries]


@router.post("/{task_id}/timesheets", response_model=TimesheetEntrySchema, status_code=status.HTTP_201_CREATED)
def log_time(task_id: uuid.UUID, payload: TimeEntryRequest, request: Request,
             db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_actions.add_time(db, task_id, user, payload, request.client.host if request.client else None)


@router.get("/{task_id}/comments", response_model=list[TaskCommentSchema])
def list_comments(task_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        task = task_actions.get_task(db, task_id, user)
        return [comment_to_response(entry) for entry in task.comment_entries if entry.deleted_at is None]


@router.post("/{task_id}/comments", response_model=TaskCommentSchema, status_code=status.HTTP_201_CREATED)
def add_comment(task_id: uuid.UUID, payload: CommentRequest, request: Request,
                db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    with action_transaction(db):
        return task_actions.add_comment(db, task_id, user, payload, request.client.host if request.client else None)
