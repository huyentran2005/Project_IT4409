import uuid

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.orm import Session

from app.models.notification import Notification, NotificationSettings
from app.models.project import Project
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, ProjectRolePermission
from app.models.task import Task
from app.models.user import User


def viewable_projects(user_id):
    return select(ProjectMember.project_id).join(
        ProjectRole, and_(ProjectRole.id == ProjectMember.role_id, ProjectRole.project_id == ProjectMember.project_id)
    ).join(ProjectRolePermission, ProjectRolePermission.role_id == ProjectRole.id).join(
        Permission, Permission.id == ProjectRolePermission.permission_id
    ).join(Project, Project.id == ProjectMember.project_id).where(
        ProjectMember.user_id == user_id, Permission.code == "project.view", Project.deleted_at.is_(None)
    )


def visible_notifications(db: Session, user_id: uuid.UUID):
    # Kiểm tra lại quyền hiện tại, không để lộ dữ liệu dự án sau khi bị thu hồi quyền.
    return db.query(Notification).filter(
        Notification.user_id == user_id,
        or_(Notification.project_id.is_(None), Notification.project_id.in_(viewable_projects(user_id))),
    )


def notify_task(db: Session, task: Task, actor: User, event: str, changes: dict | None = None):
    """Thêm thông báo vào giao dịch của thao tác task; không commit riêng."""
    changes = changes or {}
    recipients = {task.reporter_id, task.reviewer_id, *(link.user_id for link in task.assignee_links)} - {None, actor.id}
    for field in ("assigneeIds", "reviewerId"):
        previous = changes.get(field, {}).get("old")
        for value in previous if isinstance(previous, list) else [previous]:
            if value:
                recipients.add(uuid.UUID(str(value)))
    recipients.discard(actor.id)
    if not recipients:
        return
    users = db.query(User).filter(
        User.id.in_(recipients), User.is_active.is_(True), User.deleted_at.is_(None),
        exists(viewable_projects(User.id).where(ProjectMember.project_id == task.project_id)),
        ~exists(select(NotificationSettings.user_id).where(
            NotificationSettings.user_id == User.id, NotificationSettings.in_app_enabled.is_(False)
        )),
    ).all()
    current_assignees = {str(link.user_id) for link in task.assignee_links}
    old_assignees = set(changes.get("assigneeIds", {}).get("old") or [])
    assigned = current_assignees - old_assignees if event == "task_created" or "assigneeIds" in changes else set()
    reviewer_changed = "reviewerId" in changes
    messages = {
        "task_created": "đã tạo công việc", "task_updated": "đã cập nhật công việc",
        "task_status_changed": "đã đổi trạng thái công việc", "task_deleted": "đã xóa công việc",
        "task_comment": "đã thêm bình luận", "task_time_logged": "đã ghi giờ làm việc",
    }
    key = f"{task.project.key.upper()}-{task.number}"
    for user in users:
        kind, message = event, messages[event]
        if str(user.id) in assigned:
            kind, message = "task_assigned", "đã giao công việc cho bạn"
        elif reviewer_changed and user.id == task.reviewer_id:
            kind, message = "task_review_requested", "đã chọn bạn làm người duyệt"
        elif "assigneeIds" in changes and str(user.id) in old_assignees - current_assignees:
            message = "đã bỏ phân công của bạn khỏi công việc"
        elif reviewer_changed and str(user.id) == changes["reviewerId"].get("old"):
            message = "đã thay đổi người duyệt công việc"
        db.add(Notification(
            user_id=user.id, project_id=task.project_id, actor_id=actor.id, type=kind,
            title=f"{actor.full_name} {message} · {key}"[:200],
            payload={"taskId": str(task.id), "taskKey": key, "taskTitle": task.title,
                     "projectName": task.project.name, "taskDeleted": event == "task_deleted"},
        ))
