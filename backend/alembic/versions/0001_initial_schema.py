"""ProofLine initial database schema.

Revision ID: 0001_initial_schema
Revises:     (none)
Create Date: 2026-11-09

Replaces the placeholder scaffold migration with the full production schema.

Upgrade creates:
  - Extensions: vector, pgcrypto (for gen_random_uuid on PG < 13)
  - 8 PostgreSQL native ENUM types (created first, used directly in table DDL)
  - 13 tables with named constraints and indexes
  - 3 trigger functions:
      trg_fn_immutable_row     — blocks UPDATE/DELETE/TRUNCATE on audit_log
                                 and claim_receipts
      trg_fn_immutable_content — blocks UPDATE of content/content_hash on
                                 draft_versions and blocks DELETE

Downgrade reverses everything in dependency order.
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# ---------------------------------------------------------------------------
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None
# ---------------------------------------------------------------------------

# SQL for trigger functions ------------------------------------------------- #

_TRG_FN_IMMUTABLE_ROW = """
CREATE OR REPLACE FUNCTION trg_fn_immutable_row()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Rows in table % are immutable and cannot be updated, '
                    'deleted or truncated.', TG_TABLE_NAME;
END;
$$;
"""

_TRG_FN_IMMUTABLE_CONTENT = """
CREATE OR REPLACE FUNCTION trg_fn_immutable_content()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'draft_versions rows are immutable and cannot be deleted.';
    END IF;
    -- UPDATE path: block changes to content and content_hash only.
    IF NEW.content IS DISTINCT FROM OLD.content OR
       NEW.content_hash IS DISTINCT FROM OLD.content_hash THEN
        RAISE EXCEPTION 'draft_versions.content and content_hash are immutable.';
    END IF;
    RETURN NEW;
END;
$$;
"""


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # Extensions                                                           #
    # ------------------------------------------------------------------ #
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ------------------------------------------------------------------ #
    # Trigger functions (create before tables that use them)              #
    # ------------------------------------------------------------------ #
    op.execute(_TRG_FN_IMMUTABLE_ROW)
    op.execute(_TRG_FN_IMMUTABLE_CONTENT)

    # ------------------------------------------------------------------ #
    # Enum types (create before tables so columns can reference them)     #
    # ------------------------------------------------------------------ #
    op.execute("CREATE TYPE user_role AS ENUM ('creator', 'reviewer', 'admin')")
    op.execute("CREATE TYPE draft_status AS ENUM ('draft', 'in_review', 'changes_requested', 'approved')")
    op.execute("CREATE TYPE finding_severity AS ENUM ('blocker', 'warning', 'note')")
    op.execute("CREATE TYPE finding_confidence AS ENUM ('high', 'medium', 'low')")
    op.execute("CREATE TYPE finding_status AS ENUM ('open', 'accepted', 'edited', 'dismissed')")
    op.execute("CREATE TYPE claim_status AS ENUM ('supported', 'conflicts', 'expired_evidence', 'unsupported', 'needs_human')")
    op.execute("CREATE TYPE source_type AS ENUM ('guideline', 'fact', 'term')")
    op.execute("CREATE TYPE decision_type AS ENUM ('approved', 'changes_requested')")

    # ------------------------------------------------------------------ #
    # organisations                                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "organisations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.UniqueConstraint("name", name="uq_organisations_name"),
    )

    # ------------------------------------------------------------------ #
    # users                                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text, nullable=False),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("full_name", sa.Text, nullable=True),
        sa.Column("role", sa.Enum("creator", "reviewer", "admin",
                                name="user_role", create_type=False),
                  nullable=False, server_default=sa.text("'creator'::user_role")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_users_organisation", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_users_id_org"),
    )
    op.create_index("ix_users_organisation_id", "users", ["organisation_id"])

    # ------------------------------------------------------------------ #
    # guideline_rules                                                      #
    # ------------------------------------------------------------------ #
    op.create_table(
        "guideline_rules",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_id", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=True),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_guideline_rules_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_guideline_rules_created_by", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "rule_id", "version",
                            name="uq_guideline_rules_org_ruleid_version"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_guideline_rules_id_org"),
    )
    op.create_index("ix_guideline_rules_organisation_id", "guideline_rules", ["organisation_id"])
    # Partial unique index: only ONE active version per (organisation_id, rule_id).
    op.create_index(
        "uix_guideline_rules_one_active",
        "guideline_rules",
        ["organisation_id", "rule_id"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ------------------------------------------------------------------ #
    # facts                                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "facts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("fact_key", sa.Text, nullable=False),
        sa.Column("statement", sa.Text, nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("owner", sa.Text, nullable=True),
        sa.Column("source", sa.Text, nullable=True),
        sa.Column("expires_on", sa.Date, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_facts_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_facts_created_by", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "fact_key", "version",
                            name="uq_facts_org_factkey_version"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_facts_id_org"),
    )
    op.create_index("ix_facts_organisation_id", "facts", ["organisation_id"])
    op.create_index(
        "uix_facts_one_active",
        "facts",
        ["organisation_id", "fact_key"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ------------------------------------------------------------------ #
    # terms                                                                #
    # ------------------------------------------------------------------ #
    op.create_table(
        "terms",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("term", sa.Text, nullable=False),
        sa.Column("preferred", sa.Text, nullable=True),
        sa.Column("banned", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("version", sa.Integer, nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_terms_organisation", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("organisation_id", "term", "version",
                            name="uq_terms_org_term_version"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_terms_id_org"),
    )
    op.create_index("ix_terms_organisation_id", "terms", ["organisation_id"])
    op.create_index(
        "uix_terms_one_active",
        "terms",
        ["organisation_id", "term"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    # ------------------------------------------------------------------ #
    # drafts                                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "drafts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("channel", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("draft", "in_review", "changes_requested", "approved",
                                   name="draft_status", create_type=False),
                  nullable=False, server_default=sa.text("'draft'::draft_status")),
        sa.Column("intent_lock", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("current_version_number", sa.Integer, nullable=False,
                  server_default=sa.text("1")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_drafts_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"],
            name="fk_drafts_owner", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_drafts_id_org"),
    )
    op.create_index("ix_drafts_organisation_id", "drafts", ["organisation_id"])
    op.create_index("ix_drafts_organisation_status", "drafts", ["organisation_id", "status"])

    # ------------------------------------------------------------------ #
    # draft_versions  (immutable rows)                                     #
    # ------------------------------------------------------------------ #
    op.create_table(
        "draft_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_draft_versions_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "organisation_id"], ["drafts.id", "drafts.organisation_id"],
            name="fk_draft_versions_draft_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"],
            name="fk_draft_versions_created_by", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("draft_id", "version_number", name="uq_draft_versions_draft_version"),
        sa.UniqueConstraint("id", "organisation_id", name="uq_draft_versions_id_org"),
    )
    op.create_index("ix_draft_versions_organisation_id", "draft_versions", ["organisation_id"])
    op.create_index("ix_draft_versions_draft_id", "draft_versions", ["draft_id"])
    # Trigger: block content updates and deletes.
    op.execute("""
        CREATE TRIGGER trg_draft_versions_immutable_content
        BEFORE UPDATE OR DELETE ON draft_versions
        FOR EACH ROW EXECUTE FUNCTION trg_fn_immutable_content()
    """)

    # ------------------------------------------------------------------ #
    # findings                                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "findings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("quoted_text", sa.Text, nullable=True),
        sa.Column("start_offset", sa.Integer, nullable=False),
        sa.Column("end_offset", sa.Integer, nullable=False),
        sa.Column("severity", sa.Enum("blocker", "warning", "note",
                                     name="finding_severity", create_type=False),
                  nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("source_type", sa.Enum("guideline", "fact", "term",
                                         name="source_type", create_type=False),
                  nullable=True),
        sa.Column("source_ref", sa.Text, nullable=False),
        sa.Column("source_version", sa.Integer, nullable=True),
        sa.Column("confidence", sa.Enum("high", "medium", "low",
                                        name="finding_confidence", create_type=False),
                  nullable=False),
        sa.Column("suggestion", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("open", "accepted", "edited", "dismissed",
                                    name="finding_status", create_type=False),
                  nullable=False, server_default=sa.text("'open'::finding_status")),
        sa.Column("dismissal_reason", sa.Text, nullable=True),
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_findings_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_findings_version_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"],
            name="fk_findings_resolved_by", ondelete="RESTRICT",
        ),
        sa.CheckConstraint("source_ref <> ''", name="ck_findings_source_ref_nonempty"),
        sa.CheckConstraint(
            "start_offset >= 0 AND end_offset > start_offset",
            name="ck_findings_offsets",
        ),
        sa.CheckConstraint(
            "status::text <> 'dismissed' OR dismissal_reason IS NOT NULL",
            name="ck_findings_dismissed_reason",
        ),
    )
    op.create_index("ix_findings_version_id", "findings", ["version_id"])
    op.create_index("ix_findings_organisation_source_ref", "findings", ["organisation_id", "source_ref"])
    op.create_index("ix_findings_organisation_id", "findings", ["organisation_id"])

    # ------------------------------------------------------------------ #
    # claims                                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "claims",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("claim_text", sa.Text, nullable=False),
        sa.Column("claim_type", sa.Text, nullable=True),
        sa.Column("status", sa.Enum("supported", "conflicts", "expired_evidence",
                                   "unsupported", "needs_human",
                                   name="claim_status", create_type=False),
                  nullable=False),
        sa.Column("evidence_fact_key", sa.Text, nullable=True),
        sa.Column("evidence_version", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_claims_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_claims_version_org", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("id", "organisation_id", name="uq_claims_id_org"),
    )
    op.create_index("ix_claims_organisation_id", "claims", ["organisation_id"])
    op.create_index("ix_claims_version_id", "claims", ["version_id"])

    # ------------------------------------------------------------------ #
    # comments                                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "comments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", UUID(as_uuid=True), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("range_start", sa.Integer, nullable=True),
        sa.Column("range_end", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_comments_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "organisation_id"],
            ["drafts.id", "drafts.organisation_id"],
            name="fk_comments_draft_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["author_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_comments_author_org", ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "range_end IS NULL OR range_start IS NULL OR range_end > range_start",
            name="ck_comments_range",
        ),
    )
    op.create_index("ix_comments_organisation_id", "comments", ["organisation_id"])
    op.create_index("ix_comments_draft_id", "comments", ["draft_id"])

    # ------------------------------------------------------------------ #
    # approvals  (append-only)                                             #
    # ------------------------------------------------------------------ #
    op.create_table(
        "approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("reviewer_id", UUID(as_uuid=True), nullable=False),
        sa.Column("decision", sa.Enum("approved", "changes_requested",
                                     name="decision_type", create_type=False),
                  nullable=False),
        sa.Column("override_reason", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_approvals_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["draft_id", "organisation_id"],
            ["drafts.id", "drafts.organisation_id"],
            name="fk_approvals_draft_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["reviewer_id", "organisation_id"],
            ["users.id", "users.organisation_id"],
            name="fk_approvals_reviewer_org", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_approvals_organisation_id", "approvals", ["organisation_id"])
    op.create_index("ix_approvals_draft_id", "approvals", ["draft_id"])

    # ------------------------------------------------------------------ #
    # audit_log  (strictly append-only, trigger blocks changes)           #
    # ------------------------------------------------------------------ #
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("entity", sa.Text, nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("details", JSONB, nullable=True),
        sa.Column("guideline_versions", JSONB, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_audit_log_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_audit_log_user", ondelete="RESTRICT",
        ),
    )
    op.create_index("ix_audit_log_organisation_id", "audit_log", ["organisation_id"])
    op.create_index("ix_audit_log_organisation_created_at", "audit_log",
                    ["organisation_id", "created_at"])
    op.execute("""
        CREATE TRIGGER trg_audit_log_immutable
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION trg_fn_immutable_row()
    """)
    op.execute("""
        CREATE TRIGGER trg_audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION trg_fn_immutable_row()
    """)

    # ------------------------------------------------------------------ #
    # claim_receipts  (immutable: one per approved version)               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "claim_receipts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("organisation_id", UUID(as_uuid=True), nullable=False),
        sa.Column("draft_id", UUID(as_uuid=True), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", UUID(as_uuid=True), nullable=False),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("content_hash", sa.CHAR(64), nullable=False),
        sa.Column("claims_snapshot", JSONB, nullable=False),
        sa.Column("guideline_versions", JSONB, nullable=False),
        sa.Column("override_reasons", JSONB, nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(
            ["organisation_id"], ["organisations.id"],
            name="fk_claim_receipts_organisation", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id", "organisation_id"],
            ["draft_versions.id", "draft_versions.organisation_id"],
            name="fk_claim_receipts_version_org", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["approved_by"], ["users.id"],
            name="fk_claim_receipts_approved_by", ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("version_id", name="uq_claim_receipts_version_id"),
    )
    op.create_index("ix_claim_receipts_organisation_id", "claim_receipts", ["organisation_id"])
    op.execute("""
        CREATE TRIGGER trg_claim_receipts_immutable
        BEFORE UPDATE OR DELETE ON claim_receipts
        FOR EACH ROW EXECUTE FUNCTION trg_fn_immutable_row()
    """)
    op.execute("""
        CREATE TRIGGER trg_claim_receipts_no_truncate
        BEFORE TRUNCATE ON claim_receipts
        FOR EACH STATEMENT EXECUTE FUNCTION trg_fn_immutable_row()
    """)


# --------------------------------------------------------------------------- #
# DOWNGRADE — full reversal in dependency order                               #
# --------------------------------------------------------------------------- #

def downgrade() -> None:
    # Drop triggers first (they depend on functions and tables)
    op.execute("DROP TRIGGER IF EXISTS trg_claim_receipts_no_truncate ON claim_receipts")
    op.execute("DROP TRIGGER IF EXISTS trg_claim_receipts_immutable ON claim_receipts")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    op.execute("DROP TRIGGER IF EXISTS trg_draft_versions_immutable_content ON draft_versions")

    # Drop tables in reverse dependency order
    op.drop_table("claim_receipts")
    op.drop_table("audit_log")
    op.drop_table("approvals")
    op.drop_table("comments")
    op.drop_table("claims")
    op.drop_table("findings")
    op.drop_table("draft_versions")
    op.drop_table("drafts")
    op.drop_table("terms")
    op.drop_table("facts")
    op.drop_table("guideline_rules")
    op.drop_table("users")
    op.drop_table("organisations")

    # Drop trigger functions
    op.execute("DROP FUNCTION IF EXISTS trg_fn_immutable_content()")
    op.execute("DROP FUNCTION IF EXISTS trg_fn_immutable_row()")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS decision_type")
    op.execute("DROP TYPE IF EXISTS source_type")
    op.execute("DROP TYPE IF EXISTS claim_status")
    op.execute("DROP TYPE IF EXISTS finding_status")
    op.execute("DROP TYPE IF EXISTS finding_confidence")
    op.execute("DROP TYPE IF EXISTS finding_severity")
    op.execute("DROP TYPE IF EXISTS draft_status")
    op.execute("DROP TYPE IF EXISTS user_role")

    # Drop extensions
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
    op.execute("DROP EXTENSION IF EXISTS vector")
