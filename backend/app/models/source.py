"""Source models: GuidelineRule, Fact, Term.

All three follow the same versioning pattern:
- human-readable ID (rule_id / fact_key / term) is not the PK
- each edit creates version + 1 rather than updating in place
- only one active version per (organisation_id, human_id)

Important: The GuidelineRule column holding the rule body is named 'text' in
the database.  The ORM attribute is 'rule_text' to avoid shadowing the
sqlalchemy.text() helper (which would cause a TypeError at class-definition
time).  Callers must use 'rule_text' or '.text' property; the DB column remains 'text'.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.expression import text as sa_text

from app.models._base import Base, UUID_TYPE, utc_now


class GuidelineRule(Base):
    """Brand or compliance rule.  rule_id like 'TONE-01' is the human ID."""

    __tablename__ = "guideline_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_guideline_rules_organisation"),
        nullable=False,
    )
    rule_id: Mapped[str] = mapped_column(sa.Text, nullable=False)
    category: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # ORM attribute 'rule_text' maps to the DB column named 'text' (avoids
    # shadowing the sqlalchemy.text() function in this module's namespace).
    rule_text: Mapped[str] = mapped_column("text", sa.Text, nullable=False)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa_text("1"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_guideline_rules_created_by"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    @property
    def text(self) -> str:
        """Alias for rule_text to match API schema."""
        return self.rule_text

    @text.setter
    def text(self, val: str) -> None:
        self.rule_text = val

    __table_args__ = (
        sa.UniqueConstraint(
            "organisation_id", "rule_id", "version",
            name="uq_guideline_rules_org_ruleid_version",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_guideline_rules_id_org"),
        sa.Index(
            "uq_guideline_rules_active",
            "organisation_id",
            "rule_id",
            unique=True,
            sqlite_where=sa_text("is_active = 1"),
            postgresql_where=sa_text("is_active = true"),
        ),
        sa.Index("ix_guideline_rules_organisation_id", "organisation_id"),
    )


class Fact(Base):
    """Factual claim that can be cited in findings.  fact_key like 'FACT-01'."""

    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_facts_organisation"),
        nullable=False,
    )
    fact_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    statement: Mapped[str] = mapped_column(sa.Text, nullable=False)
    value: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    owner: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    source: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    expires_on: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa_text("1"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("users.id", ondelete="RESTRICT", name="fk_facts_created_by"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organisation_id", "fact_key", "version",
            name="uq_facts_org_factkey_version",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_facts_id_org"),
        sa.Index(
            "uq_facts_active",
            "organisation_id",
            "fact_key",
            unique=True,
            sqlite_where=sa_text("is_active = 1"),
            postgresql_where=sa_text("is_active = true"),
        ),
        sa.Index("ix_facts_organisation_id", "organisation_id"),
    )


class Term(Base):
    """Brand terminology entry — preferred / banned word pairs."""

    __tablename__ = "terms"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        primary_key=True,
        default=uuid.uuid4,
    )
    organisation_id: Mapped[uuid.UUID] = mapped_column(
        UUID_TYPE,
        sa.ForeignKey("organisations.id", ondelete="RESTRICT", name="fk_terms_organisation"),
        nullable=False,
    )
    term: Mapped[str] = mapped_column(sa.Text, nullable=False)
    preferred: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    banned: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa_text("false"))
    notes: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    version: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=1, server_default=sa_text("1"))
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa_text("true"))
    created_at: Mapped[datetime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.current_timestamp(),
    )

    __table_args__ = (
        sa.UniqueConstraint(
            "organisation_id", "term", "version",
            name="uq_terms_org_term_version",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_terms_id_org"),
        sa.Index(
            "uq_terms_active",
            "organisation_id",
            "term",
            unique=True,
            sqlite_where=sa_text("is_active = 1"),
            postgresql_where=sa_text("is_active = true"),
        ),
        sa.Index("ix_terms_organisation_id", "organisation_id"),
    )
