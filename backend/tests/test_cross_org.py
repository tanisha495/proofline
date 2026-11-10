"""test_cross_org.py — Org-isolation enforcement via composite foreign keys.

Verifies that a child row (finding, comment) in org_b cannot reference a parent
row (draft_version, draft) belonging to org_a.  The composite FK pattern
  (parent_id, organisation_id) → parent(id, organisation_id)
rejects such cross-org references at the database level.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from tests._helpers import (
    insert_draft,
    insert_draft_version,
    insert_org,
    insert_user,
    new_id,
)


def test_cross_org_finding_blocked(db_conn):
    """A finding in org_b cannot reference a draft_version owned by org_a."""
    # --- org_a: has a draft and a version ---
    org_a = insert_org(db_conn, "cross-org-alpha")
    user_a = insert_user(db_conn, org_a)
    draft_a = insert_draft(db_conn, org_a, user_a)
    version_a = insert_draft_version(db_conn, org_a, draft_a)

    # --- org_b: empty (no drafts/versions) ---
    org_b = insert_org(db_conn, "cross-org-beta")

    with pytest.raises(Exception):
        # version_a belongs to org_a; using org_b as organisation_id means the
        # composite FK (version_id=version_a, organisation_id=org_b) has no
        # matching row in draft_versions → FK violation.
        db_conn.execute(
            text(
                "INSERT INTO findings "
                "(id, organisation_id, draft_id, version_id, start_offset, end_offset, "
                " severity, reason, source_ref, confidence) "
                "VALUES (:id, :org_b, :did, :vid, 0, 5, 'note', 'x', 'SRC-01', 'low')"
            ),
            {"id": new_id(), "org_b": org_b, "did": draft_a, "vid": version_a},
        )

