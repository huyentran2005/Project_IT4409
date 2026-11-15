from uuid import UUID

from pydantic import BaseModel, Field


class ProjectChatAskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=6000)
    session_id: UUID | None = None
    top_k: int = Field(default=6, ge=1, le=20)
    document_ids: list[UUID] = Field(default_factory=list, max_length=50)
