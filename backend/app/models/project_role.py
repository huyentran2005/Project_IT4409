from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.session import Base


# Bảng nối many-to-many giữa project_roles và permissions.
project_role_permissions = Table(
    "project_role_permissions",
    Base.metadata,
    Column(
        "role_id",
        UUID(as_uuid=True),
        ForeignKey("project_roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "permission_id",
        UUID(as_uuid=True),
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "granted_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    ),
)


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    code: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        unique=True,
    )

    name: Mapped[str] = mapped_column(
        String(120),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    roles: Mapped[list[ProjectRole]] = relationship(
        "ProjectRole",
        secondary=project_role_permissions,
        back_populates="permissions",
    )


class ProjectRole(Base):
    __tablename__ = "project_roles"

    __table_args__ = (
        UniqueConstraint(
            "id",
            "project_id",
            name="project_roles_id_project_id_key",
        ),
        UniqueConstraint(
            "project_id",
            "code",
            name="project_roles_project_id_code_key",
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

    code: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )

    name: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    is_system: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    position: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
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

    project = relationship(
        "Project",
        back_populates="roles",
    )

    permissions: Mapped[list[Permission]] = relationship(
        "Permission",
        secondary=project_role_permissions,
        back_populates="roles",
    )