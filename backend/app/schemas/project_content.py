import datetime as dt
from urllib.parse import urlparse
from pydantic import BaseModel, Field, field_validator, model_validator


class MeetingCreate(BaseModel):
    """Khớp MeetingDraft ở frontend (types/meeting.ts)."""

    title: str = Field(min_length=1, max_length=200)
    date: dt.date
    startTime: dt.time
    endTime: dt.time
    location: str = Field(min_length=1, max_length=255)
    meetingUrl: str = Field(min_length=1, max_length=2000)
    description: str | None = Field(default=None, max_length=5000)

    @field_validator("title", "location")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Không được để trống")
        return v

    @field_validator("meetingUrl")
    @classmethod
    def _http_url(cls, v: str) -> str:
        v = v.strip()
        parsed = urlparse(v)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise ValueError("Link tham gia phải bắt đầu bằng http:// hoặc https://")
        return v

    @field_validator("description")
    @classmethod
    def _clean_desc(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return v or None

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.endTime <= self.startTime:
            raise ValueError("Giờ kết thúc phải sau giờ bắt đầu")
        return self


class MeetingOut(BaseModel):
    id: str
    projectId: str
    title: str
    date: str
    startTime: str
    endTime: str
    location: str
    meetingUrl: str
    description: str


class DocumentOut(BaseModel):
    """Khớp ProjectDocument ở frontend (types/project.ts)."""

    id: str
    name: str
    type: str
    size: str
    updatedAt: str
    updatedBy: str
