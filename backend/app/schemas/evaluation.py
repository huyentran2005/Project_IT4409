from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.schemas.user import UserSummary

Grade = Literal["excellent", "good", "pass", "needs_improvement", "insufficient"]
TaskResultCode = Literal["on_time", "late", "not_submitted"]


class EvaluationRules(BaseModel):
    """Quy tắc tính điểm, trả về để giao diện hiển thị công thức cho người xem."""

    minTasks: int
    returnPenalty: float
    timelinessWeight: float
    qualityWeight: float
    thresholds: dict[str, int]


class MemberEvaluation(BaseModel):
    user: UserSummary
    evaluatedTasks: int
    submittedTasks: int
    onTimeTasks: int
    lateTasks: int
    returnCount: int
    firstPassRate: float | None = None
    timelinessScore: float | None = None
    qualityScore: float | None = None
    score: float | None = None
    grade: Grade
    gradeLabel: str


class ProjectEvaluationResponse(BaseModel):
    projectId: str
    dateFrom: date | None = None
    dateTo: date | None = None
    canViewAll: bool
    rules: EvaluationRules
    members: list[MemberEvaluation]


class TaskEvaluationItem(BaseModel):
    id: str
    key: str
    title: str
    deadline: date
    status: str
    statusName: str
    submittedAt: datetime | None = None
    completedAt: datetime | None = None
    result: TaskResultCode
    returnCount: int
    qualityScore: float | None = None


class MemberEvaluationDetail(MemberEvaluation):
    tasks: list[TaskEvaluationItem]
