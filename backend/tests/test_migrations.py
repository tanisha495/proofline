"""test_migrations.py — upgrade / downgrade / upgrade cycle.

Requires the ProofLine database container to be running:
    docker compose up -d db

The ``db_engine`` fixture in conftest.py will FAIL (not skip) the session
if PostgreSQL is not reachable, so this test always runs or errors explicitly.
"""
from __future__ import annotations

from alembic import command
from sqlalchemy import inspect as sa_inspect


def test_upgrade_downgrade_upgrade(db_engine, alembic_cfg):
    """The migration must be fully reversible and re-applicable.

    1. upgrade head   — create all tables / triggers / enums
    2. downgrade base — drop everything in reverse dependency order
    3. upgrade head   — re-create from scratch (idempotency check)
    """
    expected = {
        "organisations", "users", "guideline_rules", "facts", "terms",
        "drafts", "draft_versions", "findings", "claims", "claim_receipts",
        "comments", "approvals", "audit_log",
    }

    # 1. Up
    command.upgrade(alembic_cfg, "head")
    tables_up = set(sa_inspect(db_engine).get_table_names())
    missing = expected - tables_up
    assert not missing, f"Tables missing after upgrade: {missing}"

    # 2. Down
    command.downgrade(alembic_cfg, "base")
    tables_down = set(sa_inspect(db_engine).get_table_names()) - {"alembic_version"}
    assert not tables_down, f"Tables still present after downgrade: {tables_down}"

    # 3. Up again (idempotency)
    command.upgrade(alembic_cfg, "head")
    tables_up2 = set(sa_inspect(db_engine).get_table_names())
    missing2 = expected - tables_up2
    assert not missing2, f"Tables missing after second upgrade: {missing2}"
