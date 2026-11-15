from dataclasses import dataclass

from pydantic import BaseModel, Field


@dataclass
class Block:
    """Biểu diễn một heading hoặc đoạn văn đã trích xuất."""

    text: str
    level: int = 0
    page: int | None = None


class AskRequest(BaseModel):
    """Kiểm tra dữ liệu đầu vào của endpoint hỏi đáp."""

    question: str = Field(min_length=2)
    top_k: int = Field(default=6, ge=1, le=20)


class IngestRequest(BaseModel):
    """Kiểm tra đường dẫn tương đối cần đưa vào Qdrant."""

    path: str | None = None

