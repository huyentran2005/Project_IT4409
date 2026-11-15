import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.task import ActivityLog, Task, TaskAssignee, TaskComment, TimeEntry
from app.models.user import User
from app.schemas.task import (
    CommentRequest, TimeEntryRequest, UpdateTaskRequest, comment_to_response,
    task_to_response, time_entry_to_response, utc_iso,
)
from app.services.auth_service import sanitize_ip
from app.services.task_service import TaskServiceError, check_task_manage_permission


def get_task(db: Session, task_id: uuid.UUID, user: User, *, write: bool = False) -> Task:
    query = db.query(Task).filter(Task.id == task_id, Task.deleted_at.is_(None))
    if write:
        query = query.with_for_update()
    task = query.first()
    if task is None:
        raise TaskServiceError("not_found", "Không tìm thấy công việc hoặc công việc đã bị xóa.")
    if write:
        check_task_manage_permission(db, task.project_id, user.id)
    else:
        allowed = db.query(ProjectMember).join(ProjectRole, (ProjectRole.id == ProjectMember.role_id)
            & (ProjectRole.project_id == ProjectMember.project_id)).join(
            ProjectRolePermission, ProjectRolePermission.role_id == ProjectRole.id
        ).join(Permission, Permission.id == ProjectRolePermission.permission_id).filter(
            ProjectMember.project_id == task.project_id, ProjectMember.user_id == user.id,
            Permission.code == "project.view",
        ).first()
        if allowed is None:
            raise TaskServiceError("forbidden", "Bạn không có quyền xem công việc trong dự án này.")
        project = db.get(Project, task.project_id)
        if project is None or project.deleted_at is not None:
            raise TaskServiceError("not_found", "Không tìm thấy dự án.")
    return task


def project_users(db: Session, project_id: uuid.UUID, ids: list[uuid.UUID]) -> dict[uuid.UUID, User]:
    if not ids:
        return {}
    users = db.query(User).join(ProjectMember, ProjectMember.user_id == User.id).filter(
        ProjectMember.project_id == project_id, User.id.in_(ids),
        User.deleted_at.is_(None), User.is_active.is_(True),
    ).all()
    if len(users) != len(set(ids)):
        raise TaskServiceError("bad_request", "Người thực hiện/người duyệt phải là thành viên đang hoạt động của dự án.")
    return {user.id: user for user in users}


def record_activity(db: Session, task: Task, user: User, action: str, description: str,
                    changes: dict, client_ip: str | None, *, entity_type="task", entity_id=None):
    db.add(ActivityLog(
        project_id=task.project_id, actor_id=user.id, action=action,
        entity_type=entity_type, entity_id=entity_id or task.id,
        description=f"{description} · {task.project.key.upper()}-{task.number}: {task.title}",
        changes=changes, ip_address=sanitize_ip(client_ip),
    ))


def task_snapshot(task: Task) -> dict:
    return {
        "title": task.title, "description": task.description, "type": task.type,
        "priority": task.priority, "status": task.status.code,
        "position": str(task.position), "startDate": task.start_date.isoformat(),
        "endDate": task.end_date.isoformat(),
        "assigneeIds": sorted(str(link.user_id) for link in task.assignee_links),
        "reviewerId": str(task.reviewer_id) if task.reviewer_id else None,
        "overdueReason": task.overdue_reason, "acceptanceResult": task.acceptance_result,
        "completedAt": utc_iso(task.completed_at) if task.completed_at else None,
    }


def update_task(db: Session, task_id: uuid.UUID, user: User, payload: UpdateTaskRequest,
                client_ip: str | None):
    task = get_task(db, task_id, user, write=True)
    data = payload.model_dump(exclude_unset=True)
    before = task_snapshot(task)
    start = data.get("startDate", task.start_date)
    end = data.get("endDate", task.end_date)
    if end < start:
        raise TaskServiceError("bad_request", "Ngày kết thúc không được trước ngày bắt đầu.")

    status_code = data.get("status", task.status.code)
    target = db.query(Status).filter(Status.project_id == task.project_id, Status.code == status_code).first()
    if target is None:
        raise TaskServiceError("bad_request", "Trạng thái không tồn tại trong dự án.")
    moving = target.id != task.status_id
    reviewer_id = data.get("reviewerId", task.reviewer_id)
    if target.code == "review" and not reviewer_id:
        raise TaskServiceError("bad_request", "Cần chọn người duyệt trước khi chuyển sang Đang duyệt.")
    member_ids = list(data.get("assigneeIds", []))
    if reviewer_id:
        member_ids.append(reviewer_id)
    users = project_users(db, task.project_id, member_ids)

    if moving:
        zone = ZoneInfo(task.project.timezone)
        reference = task.completed_at or datetime.now(timezone.utc)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=timezone.utc)
        if reference.astimezone(zone).date() > end and not data.get("overdueReason", task.overdue_reason):
            raise TaskServiceError("bad_request", "Cần nhập lý do quá hạn trước khi chuyển trạng thái.")
        # Khóa cột đích để kiểm tra giới hạn công việc trong cùng giao dịch.
        db.query(Status).filter(Status.id == target.id).with_for_update().one()
        if target.wip_limit is not None:
            count = db.query(func.count(Task.id)).filter(
                Task.status_id == target.id, Task.deleted_at.is_(None), Task.id != task.id,
            ).scalar()
            if count >= target.wip_limit:
                raise TaskServiceError("bad_request", "Cột đích đã đạt giới hạn công việc.")

    for api_field, field in {
        "title": "title", "description": "description", "type": "type", "priority": "priority",
        "startDate": "start_date", "endDate": "end_date", "position": "position",
        "overdueReason": "overdue_reason", "acceptanceResult": "acceptance_result",
    }.items():
        if api_field in data:
            value = data[api_field]
            if api_field in ("overdueReason", "acceptanceResult"):
                value = value or None
            setattr(task, field, value)
    if "assigneeIds" in data:
        wanted = list(dict.fromkeys(data["assigneeIds"]))
        existing = {link.user_id: link for link in task.assignee_links}
        task.assignee_links[:] = [
            existing[uid] if uid in existing else TaskAssignee(
                task_id=task.id, project_id=task.project_id, user_id=uid, user=users[uid]
            ) for uid in wanted
        ]
    if "reviewerId" in data:
        task.reviewer_id = reviewer_id
        task.reviewer = users.get(reviewer_id)
    if moving:
        task.status_id = target.id
        task.status = target
        task.completed_at = datetime.now(timezone.utc) if target.category == "done" else None
    after = task_snapshot(task)
    # Decimal có thể khác biểu diễn (0 / 0.0000000000) nhưng cùng giá trị.
    if "position" in data and payload.position == Decimal(before["position"]):
        after["position"] = before["position"]
    changes = {key: {"old": before[key], "new": value} for key, value in after.items() if before[key] != value}
    if changes:
        description = f"đã chuyển trạng thái từ {before['status']} sang {after['status']}" if moving else "đã cập nhật công việc"
        record_activity(db, task, user, "updated", description, changes, client_ip)
        task.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)
    return task_to_response(task)


def add_time(db: Session, task_id: uuid.UUID, user: User, payload: TimeEntryRequest, client_ip: str | None):
    task = get_task(db, task_id, user, write=True)
    entry = TimeEntry(task_id=task.id, project_id=task.project_id, user_id=user.id, user=user,
                      started_at=payload.startTime.astimezone(timezone.utc),
                      ended_at=payload.endTime.astimezone(timezone.utc), note=payload.note)
    db.add(entry)
    db.flush()
    record_activity(db, task, user, "logged_time", "đã ghi nhận thời gian làm việc",
                    payload.model_dump(mode="json"), client_ip, entity_type="timesheet", entity_id=entry.id)
    db.commit()
    db.refresh(entry)
    return time_entry_to_response(entry)


def add_comment(db: Session, task_id: uuid.UUID, user: User, payload: CommentRequest, client_ip: str | None):
    task = get_task(db, task_id, user, write=True)
    comment = TaskComment(task_id=task.id, author_id=user.id, author=user, body=payload.body)
    db.add(comment)
    db.flush()
    record_activity(db, task, user, "updated", "đã thêm bình luận",
                    {"comment": {"old": None, "new": {"id": str(comment.id), "body": comment.body}}}, client_ip)
    db.commit()
    db.refresh(comment)
    return comment_to_response(comment)
