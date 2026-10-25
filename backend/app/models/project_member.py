from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, ForeignKeyConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ProjectMember(Base):
    __tablename__ = "project_members"

    __table_args__ = (
        ForeignKeyConstraint(
            ["role_id", "project_id"],
            ["project_roles.id", "project_roles.project_id"],
            name="project_members_role_id_project_id_fkey",
        ),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project = relationship(
        "Project",
        back_populates="members",
        foreign_keys=[project_id],
    )

    user = relationship(
        "User",
        foreign_keys=[user_id],
    )

    # viewonly tránh xung đột khi project_id tham gia nhiều khóa ngoại.
    # Khi đổi role, cập nhật role_id trực tiếp.
    role = relationship(
        "ProjectRole",
        foreign_keys=[role_id, project_id],
        viewonly=True,
    )