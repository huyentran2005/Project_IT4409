from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ActivityLogChange(BaseModel):
    field: str
    label: str
    hasPreviousValue: bool
    oldValue: str | None = None
    newValue: str | None = None


class ActivityLogResponse(BaseModel):
    id: str
    actor: str
    actorInitials: str
    action: Literal["created", "updated", "deleted", "logged_time", "meeting_created"]
    entityType: Literal["task", "timesheet", "member", "document", "meeting"]
    description: str
    createdAt: datetime
    changeCount: int
    changeDetails: list[ActivityLogChange] = Field(default_factory=list)
