import uuid
from datetime import date
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from app.models.task import Task
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
        completedAt=task.completed_at.isoformat() if task.completed_at else None,
        overdueReason=task.overdue_reason,
        acceptanceResult=task.acceptance_result,
        comments=0,
        attachments=0,
        checklist=ChecklistSummary(completed=0, total=0),
        timesheets=[],
        commentItems=[],
    )
