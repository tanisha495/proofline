"""AuditLog model — strictly append-only."""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, JSONB_TYPE, UUID_TYPE, utc_now


class AuditLog(Base):
    """Immutable record of every significant action in the system.

    ``user_id`` is nullable to allow system/automated actions.
    """

    __tablename__ = "audit_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_audit_log_organisation"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_audit_log_user"),
        nullable=True,
    )
    action: Mapped[str] = mapped_column(sa.Text, nullable=False)
    entity: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID_TYPE, nullable=True)
    details: Mapped[dict | None] = mapped_column(JSONB_TYPE, nullable=True)
    guideline_versions: Mapped[dict | None] = mapped_column(JSONB_TYPE, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.Index("ix_audit_log_organisation_created_at", "organisation_id", "created_at"),
        sa.Index("ix_audit_log_organisation_id", "organisation_id"),
    )
