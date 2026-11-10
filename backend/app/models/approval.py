"""Approval model — append-only decisions on drafts."""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, DECISION_TYPE_VALUES, UUID_TYPE, enum_type, utc_now


class Approval(Base):
    """Human approval/rejection decision. Rows are never updated or deleted."""

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_approvals_organisation"),
        nullable=False,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    reviewer_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    decision: Mapped[str] = mapped_column(
        enum_type(DECISION_TYPE_VALUES, "decision_type"),
        nullable=False,
    )
    override_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["draft_id", "organisation_id"],
            ["drafts.id", "drafts.organisation_id"],
            name="fk_approvals_draft_org",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_approvals_reviewer_org",
            ondelete="RESTRICT",
        ),
        sa.Index("ix_approvals_organisation_id", "organisation_id"),
        sa.Index("ix_approvals_draft_id", "draft_id"),
    )
