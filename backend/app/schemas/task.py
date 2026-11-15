import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator
from app.models.task import Task, TaskComment, TimeEntry
from app.schemas.user import UserSummary, user_to_summary

TaskStatusLiteral = Literal["backlog", "in-progress", "review", "done"]
TaskPriorityLiteral = Literal["urgent", "high", "medium", "low"]
TaskTypeLiteral = Literal["epic", "story", "task", "bug"]


class TaskLabelSchema(BaseModel):
    id: str
    name: str
    color: str


class TimesheetEntrySchema(BaseModel):
    id: str
    user: UserSummary
    startTime: str
    endTime: str
    minutes: int
    note: str


class TaskCommentSchema(BaseModel):
    id: str
    author: UserSummary
    body: str
    createdAt: str


class ChecklistSummary(BaseModel):
    completed: int = 0
    total: int = 0


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    description: str = Field(min_length=1)
    type: TaskTypeLiteral = "task"
    priority: TaskPriorityLiteral = "medium"
    startDate: date
    endDate: date
    assigneeIds: list[uuid.UUID] = Field(default_factory=list)
    status: str = Field(default="backlog", min_length=1, max_length=40)

    @field_validator("title")
    @classmethod
    def _clean_title(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Tiêu đề công việc không được để trống")
        if len(v) > 300:
            raise ValueError("Tiêu đề công việc không được vượt quá 300 ký tự")
        return v

    @field_validator("description")
    @classmethod
    def _clean_description(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Mô tả công việc không được để trống")
        return v

    @field_validator("assigneeIds")
    @classmethod
    def _dedupe_assignees(cls, v: list[uuid.UUID]) -> list[uuid.UUID]:
        seen: set[uuid.UUID] = set()
        unique: list[uuid.UUID] = []
        for item in v:
            if item not in seen:
                seen.add(item)
                unique.append(item)
        return unique

    @model_validator(mode="after")
    def _validate_dates(self) -> "CreateTaskRequest":
        if self.endDate < self.startDate:
            raise ValueError("Ngày kết thúc không được trước ngày bắt đầu")
        return self


class TaskResponse(BaseModel):
    id: str
    key: str
    title: str
    description: str
    type: TaskTypeLiteral
    priority: TaskPriorityLiteral
    status: str
    assignees: list[UserSummary] = Field(default_factory=list)
    reviewer: UserSummary | None = None
    labels: list[TaskLabelSchema] = Field(default_factory=list)
    startDate: str
    endDate: str
    completedAt: str | None = None
    overdueReason: str | None = None
    acceptanceResult: str | None = None
    comments: int = 0
    attachments: int = 0
    checklist: ChecklistSummary = Field(default_factory=ChecklistSummary)
    timesheets: list[TimesheetEntrySchema] = Field(default_factory=list)
    commentItems: list[TaskCommentSchema] = Field(default_factory=list)


class UpdateTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str | None = Field(default=None, min_length=1, max_length=300)
    description: str | None = Field(default=None, min_length=1)
    type: TaskTypeLiteral | None = None
    priority: TaskPriorityLiteral | None = None
    startDate: date | None = None
    endDate: date | None = None
    assigneeIds: list[uuid.UUID] | None = None
    reviewerId: uuid.UUID | None = None
    overdueReason: str | None = None
    acceptanceResult: str | None = None
    status: str | None = Field(default=None, min_length=1, max_length=40)
    position: Decimal | None = Field(default=None, max_digits=20, decimal_places=10, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_update(self):
        for field in self.model_fields_set - {"reviewerId"}:
            if getattr(self, field) is None:
                raise ValueError(f"{field} không được để null")
        if self.startDate and self.endDate and self.endDate < self.startDate:
            raise ValueError("Ngày kết thúc không được trước ngày bắt đầu")
        return self


class MoveTaskRequest(UpdateTaskRequest):
    status: str = Field(min_length=1, max_length=40)


class ReviewerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewerId: uuid.UUID | None


class TimeEntryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    startTime: AwareDatetime
    endTime: AwareDatetime
    note: str = Field(min_length=1, max_length=10000)

    @model_validator(mode="after")
    def validate_duration(self):
        seconds = (self.endTime - self.startTime).total_seconds()
        if seconds < 60 or seconds // 60 > 2147483647:
            raise ValueError("Khoảng thời gian phải từ 1 phút và không vượt giới hạn cho phép")
        return self


class CommentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    body: str = Field(min_length=1, max_length=10000)


def utc_iso(value: datetime) -> str:
    return (value if value.tzinfo else value.replace(tzinfo=timezone.utc)).isoformat()


def time_entry_to_response(entry: TimeEntry) -> TimesheetEntrySchema:
    return TimesheetEntrySchema(
        id=str(entry.id), user=user_to_summary(entry.user),
        startTime=utc_iso(entry.started_at), endTime=utc_iso(entry.ended_at),
        minutes=int((entry.ended_at - entry.started_at).total_seconds() // 60), note=entry.note or "",
    )


def comment_to_response(comment: TaskComment) -> TaskCommentSchema:
    return TaskCommentSchema(id=str(comment.id), author=user_to_summary(comment.author),
                             body=comment.body, createdAt=utc_iso(comment.created_at))


class BoardColumnResponse(BaseModel):
    id: str
    title: str
    accent: str
    limit: int | None = None
    tasks: list[TaskResponse] = Field(default_factory=list)


class ProjectSummaryResponse(BaseModel):
    id: str
    key: str
    name: str
    description: str
    color: str
    progress: int = 0
    members: list[UserSummary] = Field(default_factory=list)


class BoardDataResponse(BaseModel):
    project: ProjectSummaryResponse
    columns: list[BoardColumnResponse] = Field(default_factory=list)


def task_to_response(
    task: Task,
    *,
    project_key: str | None = None,
    status_code: str | None = None,
) -> TaskResponse:
    resolved_project_key = (
        project_key or (task.project.key if task.project else "TASK")
    ).upper()
    resolved_status = status_code or (task.status.code if task.status else "backlog")
    assignees = [
        user_to_summary(link.user)
        for link in (task.assignee_links or [])
        if link.user is not None
    ]
    reviewer = user_to_summary(task.reviewer) if task.reviewer else None
    comments = [comment_to_response(item) for item in task.comment_entries if item.deleted_at is None]

    return TaskResponse(
        id=str(task.id),
        key=f"{resolved_project_key}-{task.number}",
        title=task.title,
        description=task.description,
        type=task.type,  # type: ignore[arg-type]
        priority=task.priority,  # type: ignore[arg-type]
        status=resolved_status,
        assignees=assignees,
        reviewer=reviewer,
        labels=[],
        startDate=task.start_date.isoformat(),
        endDate=task.end_date.isoformat(),
        completedAt=utc_iso(task.completed_at) if task.completed_at else None,
        overdueReason=task.overdue_reason,
        acceptanceResult=task.acceptance_result,
        comments=len(comments),
        attachments=0,
        checklist=ChecklistSummary(completed=0, total=0),
        timesheets=[time_entry_to_response(item) for item in task.time_entries],
        commentItems=comments,
    )
