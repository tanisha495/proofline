"""Claim and ClaimReceipt models."""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, CLAIM_STATUS_VALUES, JSONB_TYPE, UUID_TYPE, enum_type, utc_now


class Claim(Base):
    """A factual claim extracted from a draft version and checked against facts."""

    __tablename__ = "claims"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_claims_organisation"),
        nullable=False,
    )
    version_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    claim_text: Mapped[str] = mapped_column(sa.Text, nullable=False)
    claim_type: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        enum_type(CLAIM_STATUS_VALUES, "claim_status"),
        nullable=False,
    )
    evidence_fact_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    evidence_version: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_claims_version_org",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_claims_id_org"),
        sa.Index("ix_claims_organisation_id", "organisation_id"),
        sa.Index("ix_claims_version_id", "version_id"),
    )


class ClaimReceipt(Base):
    """Immutable record created when a draft version is approved.

    One receipt per approved version (UNIQUE version_id).
    """

    __tablename__ = "claim_receipts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_claim_receipts_organisation"),
        nullable=False,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    version_id: Mapped[uuid.UUID] = mapped_column(UUID_TYPE, nullable=False)
    approved_by: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_claim_receipts_approved_by"),
        nullable=False,
    )
    approved_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    claims_snapshot: Mapped[dict] = mapped_column(
        JSONB_TYPE,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    guideline_versions: Mapped[dict] = mapped_column(
        JSONB_TYPE,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    override_reasons: Mapped[list] = mapped_column(
        JSONB_TYPE,
        nullable=False,
        default=list,
        server_default=text("'[]'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_claim_receipts_version_org",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("version_id", name="uq_claim_receipts_version_id"),
        sa.Index("ix_claim_receipts_organisation_id", "organisation_id"),
    )
