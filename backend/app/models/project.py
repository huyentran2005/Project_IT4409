from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(160),
        nullable=False,
    )

    key: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    color: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#5B5CE2",
    )

    icon: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )

    timezone: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Asia/Ho_Chi_Minh",
    )

    task_sequence: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
    )

    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Người tạo/chủ sở hữu dự án
    owner = relationship(
        "User",
        foreign_keys=[owner_id],
    )

    # Các vai trò thuộc dự án
    roles = relationship(
        "ProjectRole",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Các thành viên thuộc dự án
    members = relationship(
        "ProjectMember",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    # Các lời mời đang chờ
    invitations = relationship(
        "ProjectInvitation",
        back_populates="project",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )