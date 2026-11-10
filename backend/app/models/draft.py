"""Draft and DraftVersion models."""
from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models._base import Base, DRAFT_STATUS_VALUES, JSONB_TYPE, UUID_TYPE, enum_type, utc_now


class Draft(Base):
    """A document being reviewed through the ProofLine workflow."""

    __tablename__ = "drafts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_drafts_organisation"),
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_drafts_owner"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    channel: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        enum_type(DRAFT_STATUS_VALUES, "draft_status"),
        nullable=False,
        default="draft",
        server_default="draft",
    )
    intent_lock: Mapped[dict] = mapped_column(
        JSONB_TYPE,
        nullable=False,
        default=dict,
        server_default=text("'{}'"),
    )
    current_version_number: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        default=1,
        server_default=text("1"),
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
        sa.UniqueConstraint("id", "organisation_id", name="uq_drafts_id_org"),
        sa.Index("ix_drafts_organisation_status", "organisation_id", "status"),
        sa.Index("ix_drafts_organisation_id", "organisation_id"),
    )


class DraftVersion(Base):
    """Immutable snapshot of draft content at a point in time."""

    __tablename__ = "draft_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_draft_versions_organisation"),
        nullable=False,
    )
    draft_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        nullable=False,
    )
    version_number: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    content: Mapped[str] = mapped_column(sa.Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(sa.CHAR(64), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_draft_versions_created_by"),
        nullable=True,
    )
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
            name="fk_draft_versions_draft_org",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_draft_versions_id_org"),
        sa.UniqueConstraint("draft_id", "version_number", name="uq_draft_versions_draft_version"),
        sa.Index("ix_draft_versions_organisation_id", "organisation_id"),
        sa.Index("ix_draft_versions_draft_id", "draft_id"),
    )
