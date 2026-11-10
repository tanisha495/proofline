"""test_versioning.py — Source-table versioning rules.

Verifies:
- Inserting a second version (v2) of a guideline rule succeeds.
- Two *active* versions of the same rule_id in the same org are rejected
  by the partial unique index ix_guideline_rules_one_active.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from tests._helpers import insert_org, insert_user, new_id


def test_versioning_second_version_inserts(db_conn):
    """Inserting v1 (inactive) + v2 (inactive) of the same rule_id must succeed."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)

    for version in (1, 2):
        db_conn.execute(
            text(
                "INSERT INTO guideline_rules "
                "(id, organisation_id, rule_id, text, version, is_active, created_by) "
                "VALUES (:id, :org, :rule_id, :txt, :version, false, :created_by)"
            ),
            {
                "id": new_id(),
                "org": org_id,
                "rule_id": "TONE-01",
                "txt": f"Rule text v{version}",
                "version": version,
                "created_by": user_id,
            },
        )
    # Both inserts succeeded — test passes if no exception raised.


def test_versioning_two_active_versions_fails(db_conn):
    """Two active versions of the same rule_id in the same org must be rejected."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)

    # Insert active v1 — must succeed.
    db_conn.execute(
        text(
            "INSERT INTO guideline_rules "
            "(id, organisation_id, rule_id, text, version, is_active, created_by) "
            "VALUES (:id, :org, 'TONE-02', 'Version 1', 1, true, :created_by)"
        ),
        {"id": new_id(), "org": org_id, "created_by": user_id},
    )

    with pytest.raises(Exception):
        # Insert another active version for the same rule_id — partial unique
        # index ix_guideline_rules_one_active must reject this.
        db_conn.execute(
            text(
                "INSERT INTO guideline_rules "
                "(id, organisation_id, rule_id, text, version, is_active, created_by) "
                "VALUES (:id, :org, 'TONE-02', 'Version 2 active', 2, true, :created_by)"
            ),
            {"id": new_id(), "org": org_id, "created_by": user_id},
        )

