import uuid
from datetime import date as date_type, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.schemas.task import TimesheetEntrySchema


class TimesheetCreate(BaseModel):
    """Hai cách nhập (chọn một):
    - startTime + endTime  (form trong chi tiết công việc)
    - date + hours         (form "Thêm bản ghi timesheet")
    """

    startTime: datetime | None = None
    endTime: datetime | None = None
    date: date_type | None = None
    hours: float | None = Field(default=None, gt=0, le=24)
    isOvertime: bool = False
    note: str = Field(default="", max_length=2000)

    @field_validator("note")
    @classmethod
    def _strip_note(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def _check_mode(self) -> "TimesheetCreate":
        by_range = self.startTime is not None and self.endTime is not None
        by_hours = self.date is not None and self.hours is not None
        if not by_range and not by_hours:
            raise ValueError("Cần nhập (giờ bắt đầu và kết thúc) hoặc (ngày và số giờ)")
        if by_range and self.endTime <= self.startTime:  # type: ignore[operator]
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        return self


class TimesheetListResponse(BaseModel):
    entries: list[TimesheetEntrySchema] = Field(default_factory=list)
    totalMinutes: int = 0
    overtimeMinutes: int = 0


class TimesheetSummaryResponse(BaseModel):
    todayMinutes: int = 0
    weekMinutes: int = 0
    weekOvertimeMinutes: int = 0
    missingDays: int = 0
    missingDates: list[str] = Field(default_factory=list)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=5000)
    parentId: uuid.UUID | None = None

    @field_validator("body")
    @classmethod
    def _strip_body(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Nội dung bình luận không được để trống")
        return v
