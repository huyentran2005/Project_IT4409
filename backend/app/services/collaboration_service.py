"""Timesheet (time_entries) và bình luận (comments) của công việc.

Quyền:
  - Xem timesheet / bình luận, viết bình luận : là thành viên dự án
  - Ghi nhận giờ làm                           : có quyền task.manage
  - Xóa bản ghi giờ / bình luận                : tác giả/ chủ dự án
"""
import uuid
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.collaboration import Comment, TimeEntry
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.task import ActivityLog, Task
from app.models.user import User
from app.schemas.collaboration import (
    CommentCreate,
    TimesheetCreate,
    TimesheetListResponse,
    TimesheetSummaryResponse,
)
from app.schemas.task import TaskCommentSchema, TimesheetEntrySchema
from app.schemas.user import user_to_summary
from app.services.auth_service import sanitize_ip
from app.services.task_service import TaskServiceError, check_task_manage_permission

LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
DEFAULT_START_HOUR = 8  # form "ngày + số giờ" quy ước bắt đầu lúc 08:00


# helpers
def _minutes(entry: TimeEntry) -> int:
    return int((entry.ended_at - entry.started_at).total_seconds() // 60)


def _fmt(minutes: int) -> str:
    return f"{minutes // 60}h {minutes % 60}m"


def _local_date(dt: datetime) -> date:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(LOCAL_TZ).date()


def _day_bounds(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=LOCAL_TZ)


def _get_task(db: Session, task_id: uuid.UUID) -> Task:
    task = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None)).first()
    if not task:
        raise TaskServiceError("not_found", "Không tìm thấy công việc.")
    return task


def _ensure_member(db: Session, project_id: uuid.UUID, user: User) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.deleted_at.is_(None)).first()
    if not project:
        raise TaskServiceError("not_found", "Không tìm thấy dự án.")
    member = (
        db.query(ProjectMember)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user.id)
        .first()
    )
    if not member:
        raise TaskServiceError("forbidden", "Bạn không phải là thành viên của dự án này.")
    return project


def _entry_schema(entry: TimeEntry, user: User, task: Task | None = None, project: Project | None = None) -> TimesheetEntrySchema:
    return TimesheetEntrySchema(
        id=str(entry.id),
        user=user_to_summary(user),
        startTime=entry.started_at.isoformat(),
        endTime=entry.ended_at.isoformat(),
        minutes=_minutes(entry),
        note=entry.note or "",
        isOvertime=bool(entry.is_overtime),
        date=_local_date(entry.started_at).isoformat(),
        taskId=str(entry.task_id),
        taskKey=f"{project.key.upper()}-{task.number}" if task and project else None,
        taskTitle=task.title if task else None,
        projectId=str(entry.project_id),
        projectName=project.name if project else None,
    )


def _comment_schema(comment: Comment, author: User) -> TaskCommentSchema:
    return TaskCommentSchema(
        id=str(comment.id),
        author=user_to_summary(author),
        body=comment.body,
        createdAt=comment.created_at.isoformat() if comment.created_at else datetime.now(timezone.utc).isoformat(),
        parentId=str(comment.parent_id) if comment.parent_id else None,
    )


def _resolve_times(payload: TimesheetCreate) -> tuple[datetime, datetime]:
    if payload.startTime is not None and payload.endTime is not None:
        start, end = payload.startTime, payload.endTime
        if start.tzinfo is None:
            start = start.replace(tzinfo=LOCAL_TZ)
        if end.tzinfo is None:
            end = end.replace(tzinfo=LOCAL_TZ)
    else:
        assert payload.date is not None and payload.hours is not None
        start = datetime.combine(payload.date, time(DEFAULT_START_HOUR, 0), tzinfo=LOCAL_TZ)
        end = start + timedelta(minutes=round(payload.hours * 60))
    minutes = int((end - start).total_seconds() // 60)
    if minutes < 1:
        raise TaskServiceError("bad_request", "Thời gian làm việc phải từ 1 phút trở lên.")
    if minutes > 24 * 60:
        raise TaskServiceError("bad_request", "Một bản ghi không được vượt quá 24 giờ.")
    return start, end


def _log(db: Session, *, project_id, actor, entity_type, entity_id, action, description, changes, ip) -> None:
    db.add(
        ActivityLog(
            project_id=project_id,
            actor_id=actor.id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            description=description,
            changes=changes,
            ip_address=sanitize_ip(ip),
        )
    )


# nạp sẵn cho Board / TaskResponse
def load_task_collaboration(
    db: Session, tasks: list[Task], project: Project
) -> tuple[dict[uuid.UUID, list[TimesheetEntrySchema]], dict[uuid.UUID, list[TaskCommentSchema]]]:
    """Nạp timesheet và bình luận cho cả danh sách task bằng 2 truy vấn."""
    ids = [t.id for t in tasks]
    timesheets: dict[uuid.UUID, list[TimesheetEntrySchema]] = {i: [] for i in ids}
    comments: dict[uuid.UUID, list[TaskCommentSchema]] = {i: [] for i in ids}
    if not ids:
        return timesheets, comments
    task_by_id = {t.id: t for t in tasks}

    rows = (
        db.query(TimeEntry, User)
        .join(User, User.id == TimeEntry.user_id)
        .filter(TimeEntry.task_id.in_(ids))
        .order_by(TimeEntry.started_at.desc())
        .all()
    )
    for entry, user in rows:
        timesheets[entry.task_id].append(_entry_schema(entry, user, task_by_id[entry.task_id], project))

    crows = (
        db.query(Comment, User)
        .join(User, User.id == Comment.author_id)
        .filter(Comment.task_id.in_(ids), Comment.deleted_at.is_(None))
        .order_by(Comment.created_at.asc())
        .all()
    )
    for comment, author in crows:
        comments[comment.task_id].append(_comment_schema(comment, author))
    return timesheets, comments


# ---------------------------------------------------------------------- timesheet
def list_task_time_entries(db: Session, *, task_id: uuid.UUID, user: User) -> list[TimesheetEntrySchema]:
    task = _get_task(db, task_id)
    project = _ensure_member(db, task.project_id, user)
    return load_task_collaboration(db, [task], project)[0][task.id]


def create_time_entry(
    db: Session, *, task_id: uuid.UUID, user: User, payload: TimesheetCreate, client_ip: str | None = None
) -> TimesheetEntrySchema:
    task = _get_task(db, task_id)
    project = check_task_manage_permission(db, task.project_id, user.id)
    start, end = _resolve_times(payload)

    entry = TimeEntry(
        task_id=task.id,
        project_id=task.project_id,
        user_id=user.id,
        started_at=start,
        ended_at=end,
        note=payload.note or None,
        is_overtime=payload.isOvertime,
    )
    db.add(entry)
    db.flush()
    minutes = _minutes(entry)
    key = f"{project.key.upper()}-{task.number}"
    _log(
        db,
        project_id=task.project_id,
        actor=user,
        entity_type="timesheet",
        entity_id=entry.id,
        action="logged_time",
        description=f"Đã ghi nhận {_fmt(minutes)}{' (OT)' if payload.isOvertime else ''} vào {key}",
        changes={"taskKey": key, "minutes": minutes, "isOvertime": payload.isOvertime},
        ip=client_ip,
    )
    db.commit()
    db.refresh(entry)
    return _entry_schema(entry, user, task, project)


def delete_time_entry(db: Session, *, entry_id: uuid.UUID, user: User, client_ip: str | None = None) -> None:
    entry = db.query(TimeEntry).filter(TimeEntry.id == entry_id).first()
    if not entry:
        raise TaskServiceError("not_found", "Không tìm thấy bản ghi timesheet.")
    project = _ensure_member(db, entry.project_id, user)
    if entry.user_id != user.id and project.owner_id != user.id:
        raise TaskServiceError("forbidden", "Chỉ người ghi hoặc chủ dự án mới được xóa bản ghi này.")
    minutes = _minutes(entry)
    _log(
        db,
        project_id=entry.project_id,
        actor=user,
        entity_type="timesheet",
        entity_id=entry.id,
        action="deleted",
        description=f"Đã xóa bản ghi timesheet {_fmt(minutes)}",
        changes={"minutes": minutes},
        ip=client_ip,
    )
    db.delete(entry)
    db.commit()


def list_my_time_entries(
    db: Session,
    *,
    user: User,
    date_from: date | None = None,
    date_to: date | None = None,
    overtime_only: bool = False,
    project_id: uuid.UUID | None = None,
) -> TimesheetListResponse:
    q = (
        db.query(TimeEntry, Task, Project)
        .join(Task, Task.id == TimeEntry.task_id)
        .join(Project, Project.id == TimeEntry.project_id)
        .filter(
            TimeEntry.user_id == user.id,
            Task.deleted_at.is_(None),
            Project.deleted_at.is_(None),
        )
    )
    if date_from:
        q = q.filter(TimeEntry.started_at >= _day_bounds(date_from))
    if date_to:
        q = q.filter(TimeEntry.started_at < _day_bounds(date_to + timedelta(days=1)))
    if overtime_only:
        q = q.filter(TimeEntry.is_overtime.is_(True))
    if project_id:
        q = q.filter(TimeEntry.project_id == project_id)
    rows = q.order_by(TimeEntry.started_at.desc()).all()

    entries = [_entry_schema(e, user, t, p) for e, t, p in rows]
    return TimesheetListResponse(
        entries=entries,
        totalMinutes=sum(e.minutes for e in entries),
        overtimeMinutes=sum(e.minutes for e in entries if e.isOvertime),
    )


def my_time_summary(db: Session, *, user: User, today: date | None = None) -> TimesheetSummaryResponse:
    """Số liệu cho Dashboard: giờ log hôm nay / tuần này và số ngày làm việc còn thiếu log."""
    today = today or datetime.now(LOCAL_TZ).date()
    monday = today - timedelta(days=today.weekday())
    rows = (
        db.query(TimeEntry)
        .filter(
            TimeEntry.user_id == user.id,
            TimeEntry.started_at >= _day_bounds(monday),
            TimeEntry.started_at < _day_bounds(monday + timedelta(days=7)),
        )
        .all()
    )
    logged_days = {_local_date(e.started_at) for e in rows}
    week_minutes = sum(_minutes(e) for e in rows)
    ot_minutes = sum(_minutes(e) for e in rows if e.is_overtime)
    today_minutes = sum(_minutes(e) for e in rows if _local_date(e.started_at) == today)

    missing: list[str] = []
    day = monday
    while day < today:  # chỉ tính các ngày đã qua, không tính hôm nay
        if day.weekday() < 5 and day not in logged_days:
            missing.append(day.isoformat())
        day += timedelta(days=1)
    return TimesheetSummaryResponse(
        todayMinutes=today_minutes,
        weekMinutes=week_minutes,
        weekOvertimeMinutes=ot_minutes,
        missingDays=len(missing),
        missingDates=missing,
    )


# ------------------------------------------------------------------- bình luận
def list_comments(db: Session, *, task_id: uuid.UUID, user: User) -> list[TaskCommentSchema]:
    task = _get_task(db, task_id)
    project = _ensure_member(db, task.project_id, user)
    return load_task_collaboration(db, [task], project)[1][task.id]


def create_comment(db: Session, *, task_id: uuid.UUID, user: User, payload: CommentCreate) -> TaskCommentSchema:
    task = _get_task(db, task_id)
    project = _ensure_member(db, task.project_id, user)
    if project.is_archived:
        raise TaskServiceError("bad_request", "Dự án đã được lưu trữ, không thể bình luận.")
    if payload.parentId:
        parent = (
            db.query(Comment)
            .filter(Comment.id == payload.parentId, Comment.task_id == task.id, Comment.deleted_at.is_(None))
            .first()
        )
        if not parent:
            raise TaskServiceError("bad_request", "Bình luận được trả lời không tồn tại.")
    comment = Comment(task_id=task.id, author_id=user.id, parent_id=payload.parentId, body=payload.body)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return _comment_schema(comment, user)


def delete_comment(db: Session, *, comment_id: uuid.UUID, user: User) -> None:
    comment = db.query(Comment).filter(Comment.id == comment_id, Comment.deleted_at.is_(None)).first()
    if not comment:
        raise TaskServiceError("not_found", "Không tìm thấy bình luận.")
    task = _get_task(db, comment.task_id)
    project = _ensure_member(db, task.project_id, user)
    if comment.author_id != user.id and project.owner_id != user.id:
        raise TaskServiceError("forbidden", "Chỉ tác giả hoặc chủ dự án mới được xóa bình luận.")
    comment.deleted_at = datetime.now(timezone.utc)
    db.commit()
