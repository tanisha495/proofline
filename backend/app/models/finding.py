"""Finding model.

Column naming note
------------------
The API contract uses ``start`` and ``end`` as field names (see
app/schemas/finding.py).  ``end`` is an SQL reserved word, so the database
columns are named ``start_offset`` and ``end_offset``.  The Pydantic schema
bridges the gap via Field aliases.
"""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import (
    Base,
    FINDING_CONFIDENCE_VALUES,
    FINDING_SEVERITY_VALUES,
    FINDING_STATUS_VALUES,
    SOURCE_TYPE_VALUES,
    UUID_TYPE,
    enum_type,
    utc_now,
)


class Finding(Base):
    """A single flag raised by the review engine against a draft version."""

    __tablename__ = "findings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_findings_organisation"),
        nullable=False,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    quoted_text: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    start_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    end_offset: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    severity: Mapped[str] = mapped_column(
        enum_type(FINDING_SEVERITY_VALUES, "finding_severity"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_type: Mapped[str | None] = mapped_column(
        enum_type(SOURCE_TYPE_VALUES, "source_type"),
        nullable=True,
    )
    source_ref: Mapped[str] = mapped_column(sa.Text, nullable=False)
    source_version: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    confidence: Mapped[str] = mapped_column(
        enum_type(FINDING_CONFIDENCE_VALUES, "finding_confidence"),
        nullable=False,
    )
    suggestion: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        enum_type(FINDING_STATUS_VALUES, "finding_status"),
        nullable=False,
        default="open",
        server_default="open",
    )
    dismissal_reason: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_findings_resolved_by"),
        nullable=True,
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
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_findings_version_org",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("source_ref <> ''", name="ck_findings_source_ref_nonempty"),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_findings_offsets",
        ),
        sa.CheckConstraint(
            "status <> 'dismissed' OR dismissal_reason IS NOT NULL",
            name="ck_findings_dismissed_reason",
        ),
        sa.Index("ix_findings_version_id", "version_id"),
        sa.Index("ix_findings_organisation_source_ref", "organisation_id", "source_ref"),
        sa.Index("ix_findings_organisation_id", "organisation_id"),
    )
