"""Đánh giá mức độ hoàn thành công việc của từng thành viên trong một dự án.

Hai tiêu chí, tính trực tiếp từ bảng tasks, task_assignees và activity_logs
(không thêm bảng mới):

1. Đúng hạn (T): task được nộp lần đầu không muộn hơn ngày kết thúc (end_date).
   "Nộp" là lần đầu task vào cột "Đang duyệt" (hoặc cột thuộc nhóm "done" nếu bỏ
   qua bước duyệt). Task cũ không có log thì dùng completed_at.
2. Bị return (Q): task bị người KHÔNG phải người thực hiện kéo lùi từ "Đang duyệt"
   hoặc "Hoàn thành" về một cột đứng trước. Mỗi lần trừ RETURN_PENALTY điểm của task.

Điểm tổng = TIMELINESS_WEIGHT * T + QUALITY_WEIGHT * Q (thang 0-100).
"""
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import false, or_, select
from sqlalchemy.orm import Session

from app.models.project import Project, Status
from app.models.project_member import ProjectMember
from app.models.project_role import Permission, ProjectRole, project_role_permissions
from app.models.task import ActivityLog, Task, TaskAssignee
from app.models.user import User

# ---- Quy tắc tính điểm (đã thống nhất với nhóm) ----
MIN_EVALUATED_TASKS = 3          # dưới ngưỡng này: "Chưa đủ dữ liệu"
RETURN_PENALTY = 0.25            # mỗi lần return trừ 25% điểm của task
TIMELINESS_WEIGHT = 0.5
QUALITY_WEIGHT = 0.5
GRADE_THRESHOLDS = (("excellent", 90), ("good", 75), ("pass", 60))
GRADE_LABELS = {
    "excellent": "Xuất sắc",
    "good": "Tốt",
    "pass": "Đạt",
    "needs_improvement": "Cần cải thiện",
    "insufficient": "Chưa đủ dữ liệu",
}
REVIEW_CODE = "review"           # mã cột "Đang duyệt" (cùng quy ước với task_actions.py)


@dataclass
class TaskResult:
    id: uuid.UUID
    key: str
    title: str
    deadline: date
    status_code: str
    status_name: str
    completed_at: datetime | None
    submitted_at: datetime | None
    on_time: bool
    returns: int

    @property
    def result(self) -> str:
        if self.on_time:
            return "on_time"
        return "late" if self.submitted_at is not None else "not_submitted"

    @property
    def quality(self) -> float | None:
        """Hệ số chất lượng 0..1 của task; None nếu task chưa từng được nộp."""
        if self.submitted_at is None:
            return None
        return max(0.0, 1.0 - RETURN_PENALTY * self.returns)


@dataclass
class MemberSummary:
    evaluated: int
    submitted: int
    on_time: int
    late: int
    returns: int
    first_pass_rate: float | None
    timeliness: float | None
    quality: float | None
    score: float | None
    grade: str


def _round1(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _as_utc(value: datetime) -> datetime:
    # SQLite trả datetime không múi giờ; PostgreSQL trả có múi giờ.
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _local_date(value: datetime, zone: ZoneInfo) -> date:
    return _as_utc(value).astimezone(zone).date()


def grade_for(score: float | None, evaluated: int) -> str:
    if score is None or evaluated < MIN_EVALUATED_TASKS:
        return "insufficient"
    for grade, threshold in GRADE_THRESHOLDS:
        if score >= threshold:
            return grade
    return "needs_improvement"


def has_project_permission(db: Session, project_id: uuid.UUID, user_id: uuid.UUID, code: str) -> bool:
    """Giống điều kiện trong deps.require_project_permission, dùng khi cần kiểm tra thêm một quyền."""
    row = (
        db.query(ProjectMember.user_id)
        .join(ProjectRole, (ProjectRole.id == ProjectMember.role_id)
              & (ProjectRole.project_id == ProjectMember.project_id))
        .join(project_role_permissions, project_role_permissions.c.role_id == ProjectRole.id)
        .join(Permission, Permission.id == project_role_permissions.c.permission_id)
        .filter(ProjectMember.project_id == project_id, ProjectMember.user_id == user_id,
                Permission.code == code)
        .first()
    )
    return row is not None


def _status_change(changes: dict) -> tuple[str | None, str | None] | None:
    """Đọc (cột cũ, cột mới) từ log; hỗ trợ cả hai định dạng log hiện có trong hệ thống."""
    raw = changes.get("status")
    if isinstance(raw, dict) and "new" in raw:
        return raw.get("old"), raw.get("new")
    if "toStatus" in changes:
        return changes.get("fromStatus"), changes.get("toStatus")
    return None


def load_task_results(
    db: Session, project: Project, date_from: date | None = None, date_to: date | None = None,
    today: date | None = None,
) -> dict[uuid.UUID, list[TaskResult]]:
    """Trả về {user_id: [kết quả từng task được đánh giá]} cho các người thực hiện.

    Task được đánh giá: chưa xóa, có người thực hiện, và (đã Hoàn thành HOẶC đã quá hạn).
    Bộ lọc from/to áp dụng lên ngày kết thúc (end_date) của task.
    """
    zone = ZoneInfo(project.timezone)
    today = today or datetime.now(zone).date()

    statuses = db.query(Status.id, Status.code, Status.name, Status.category, Status.position).filter(
        Status.project_id == project.id).all()
    by_id = {s.id: s for s in statuses}
    by_code = {s.code: s for s in statuses}
    done_ids = [s.id for s in statuses if s.category == "done"]

    conditions = [Task.project_id == project.id, Task.deleted_at.is_(None)]
    if date_from:
        conditions.append(Task.end_date >= date_from)
    if date_to:
        conditions.append(Task.end_date <= date_to)
    finished = Task.status_id.in_(done_ids) if done_ids else false()
    conditions.append(or_(finished, Task.end_date < today))

    # Chỉ lấy các cột cần thiết (Task có quan hệ selectin nặng nếu nạp cả đối tượng).
    rows = (
        db.query(Task.id, Task.number, Task.title, Task.end_date, Task.completed_at, Task.status_id,
                 TaskAssignee.user_id)
        .join(TaskAssignee, TaskAssignee.task_id == Task.id)
        .filter(*conditions)
        .all()
    )
    if not rows:
        return {}

    tasks: dict[uuid.UUID, dict] = {}
    for row in rows:
        entry = tasks.setdefault(row.id, {"row": row, "assignees": set()})
        entry["assignees"].add(row.user_id)

    log_filters = [
        ActivityLog.project_id == project.id,
        ActivityLog.entity_type == "task",
        ActivityLog.action == "updated",
        ActivityLog.entity_id.in_(select(Task.id).where(*conditions)),
    ]
    if db.get_bind().dialect.name == "postgresql":
        # Chỉ lấy log có đổi trạng thái (bỏ log bình luận, ghi giờ...) để giảm dữ liệu đọc về.
        log_filters.append(or_(ActivityLog.changes.has_key("status"), ActivityLog.changes.has_key("fromStatus")))
    logs = (
        db.query(ActivityLog.entity_id, ActivityLog.actor_id, ActivityLog.created_at, ActivityLog.changes)
        .filter(*log_filters)
        .order_by(ActivityLog.created_at, ActivityLog.id)
        .all()
    )
    transitions: dict[uuid.UUID, list] = {}
    for log in logs:
        change = _status_change(log.changes or {})
        if change is not None:
            transitions.setdefault(log.entity_id, []).append((log.actor_id, log.created_at, *change))

    project_key = project.key.upper()
    per_user: dict[uuid.UUID, list[TaskResult]] = {}
    for task_id, entry in tasks.items():
        row, assignees = entry["row"], entry["assignees"]
        status = by_id.get(row.status_id)
        submitted_at: datetime | None = None
        returns = 0
        for actor_id, created_at, old_code, new_code in transitions.get(task_id, []):
            new_status, old_status = by_code.get(new_code), by_code.get(old_code)
            if new_status is None:
                continue
            if submitted_at is None and (new_code == REVIEW_CODE or new_status.category == "done"):
                submitted_at = created_at
            came_from_review_or_done = old_status is not None and (
                old_code == REVIEW_CODE or old_status.category == "done")
            if came_from_review_or_done and new_status.position < old_status.position \
                    and actor_id not in assignees:
                returns += 1
        if submitted_at is None and row.completed_at is not None:
            submitted_at = row.completed_at  # task cũ chưa có log
        on_time = submitted_at is not None and _local_date(submitted_at, zone) <= row.end_date
        result = TaskResult(
            id=task_id, key=f"{project_key}-{row.number}", title=row.title, deadline=row.end_date,
            status_code=status.code if status else "", status_name=status.name if status else "",
            completed_at=row.completed_at, submitted_at=submitted_at, on_time=on_time, returns=returns,
        )
        for user_id in assignees:
            per_user.setdefault(user_id, []).append(result)
    return per_user


def summarize(results: list[TaskResult]) -> MemberSummary:
    evaluated = len(results)
    submitted = [r for r in results if r.submitted_at is not None]
    on_time = sum(1 for r in results if r.on_time)
    timeliness = on_time / evaluated * 100 if evaluated else None
    quality = sum(r.quality for r in submitted) / len(submitted) * 100 if submitted else None
    first_pass = sum(1 for r in submitted if r.returns == 0) / len(submitted) * 100 if submitted else None
    score = None
    if evaluated >= MIN_EVALUATED_TASKS:
        score = _round1(TIMELINESS_WEIGHT * timeliness + QUALITY_WEIGHT * (quality or 0.0))
    return MemberSummary(
        evaluated=evaluated, submitted=len(submitted), on_time=on_time, late=evaluated - on_time,
        returns=sum(r.returns for r in results),
        first_pass_rate=_round1(first_pass) if first_pass is not None else None,
        timeliness=_round1(timeliness) if timeliness is not None else None,
        quality=_round1(quality) if quality is not None else None,
        score=score, grade=grade_for(score, evaluated),
    )


def project_members(db: Session, project: Project) -> list[User]:
    return (
        db.query(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project.id, User.deleted_at.is_(None))
        .order_by(User.full_name, User.id)
        .all()
    )
