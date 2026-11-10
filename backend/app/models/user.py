"""User model."""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, USER_ROLE_VALUES, UUID_TYPE, enum_type, utc_now


class User(Base):
    """ProofLine user. Belongs to exactly one organisation."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_users_organisation"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        # Lowercasing is enforced at application level; uniqueness is global.
    )
    password_hash: Mapped[str] = mapped_column(sa.Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    role: Mapped[str] = mapped_column(
        enum_type(USER_ROLE_VALUES, "user_role"),
        nullable=False,
        default="creator",
        server_default="creator",
    )
    is_active: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        # Email is globally unique (not per-org, as per spec).
        sa.UniqueConstraint("email", name="uq_users_email"),
        # Support composite FK from org-scoped children.
        sa.UniqueConstraint("id", "organisation_id", name="uq_users_id_org"),
        sa.Index("ix_users_organisation_id", "organisation_id"),
    )
