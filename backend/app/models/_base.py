"""ProofLine SQLAlchemy declarative base, mixins and shared enum definitions.

All models import from this module to ensure a single metadata object and
consistent column conventions across every table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import Enum as PgEnum, JSON, String, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# ---------------------------------------------------------------------------
# PostgreSQL native ENUM type names
# ---------------------------------------------------------------------------
# These are defined here so both the ORM and the migration can reference the
# same string names, preventing drift.

USER_ROLE_VALUES       = ("creator", "reviewer", "admin")
DRAFT_STATUS_VALUES    = ("draft", "in_review", "changes_requested", "approved")
FINDING_SEVERITY_VALUES = ("blocker", "warning", "note")
FINDING_CONFIDENCE_VALUES = ("high", "medium", "low")
FINDING_STATUS_VALUES  = ("open", "accepted", "edited", "dismissed")
CLAIM_STATUS_VALUES    = ("supported", "conflicts", "expired_evidence", "unsupported", "needs_human")
SOURCE_TYPE_VALUES     = ("guideline", "fact", "term")
DECISION_TYPE_VALUES   = ("approved", "changes_requested")

# Cross-dialect column types (PostgreSQL native in prod, portable on SQLite)
UUID_TYPE = Uuid(as_uuid=True)
JSONB_TYPE = JSON().with_variant(JSONB(), "postgresql")


def enum_type(values: tuple[str, ...], name: str) -> sa.types.TypeEngine:
    """Return a VARCHAR column on SQLite and native PostgreSQL ENUM on Postgres."""
    return String(50).with_variant(
        PgEnum(*values, name=name, create_type=False),
        "postgresql",
    )


def utc_now() -> datetime:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Declarative base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """Shared declarative base for all ProofLine ORM models."""
    pass


# ---------------------------------------------------------------------------
# Reusable column helpers
# ---------------------------------------------------------------------------

def _uuid_pk() -> Mapped[uuid.UUID]:
    """Standard UUID primary key compatible with PostgreSQL and SQLite."""
    return mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )


def _timestamptz_now(nullable: bool = False) -> sa.Column:
    """TIMESTAMPTZ column defaulting to current timestamp."""
    return sa.Column(
        sa.TIMESTAMP(timezone=True),
        nullable=nullable,
        default=utc_now,
        server_default=func.current_timestamp(),
    )
