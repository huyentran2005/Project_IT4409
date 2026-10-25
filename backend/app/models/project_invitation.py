from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


class ProjectInvitation(Base):
    __tablename__ = "project_invitations"

    __table_args__ = (
        ForeignKeyConstraint(
            ["role_id", "project_id"],
            ["project_roles.id", "project_roles.project_id"],
            name="project_invitations_role_id_project_id_fkey",
        ),
        ForeignKeyConstraint(
            ["project_id", "invited_by"],
            ["project_members.project_id", "project_members.user_id"],
            name="project_invitations_project_id_invited_by_fkey",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
    )

    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
    )

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    token_hash: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        unique=True,
    )

    invited_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )

    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    accepted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    project = relationship(
        "Project",
        back_populates="invitations",
        foreign_keys=[project_id],
    )

    role = relationship(
        "ProjectRole",
        foreign_keys=[role_id, project_id],
        viewonly=True,
    )

    # Đại diện cho người đã gửi lời mời trong project_members.
    inviter_member = relationship(
        "ProjectMember",
        foreign_keys=[project_id, invited_by],
        viewonly=True,
    )