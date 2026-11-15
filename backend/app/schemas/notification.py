from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: str
    projectId: str | None
    taskId: str | None
    taskKey: str | None
    taskTitle: str | None
    projectName: str | None
    taskDeleted: bool
    type: str
    title: str
    readAt: datetime | None
    createdAt: datetime


class NotificationPage(BaseModel):
    items: list[NotificationResponse]
    unreadCount: int
    hasMore: bool
