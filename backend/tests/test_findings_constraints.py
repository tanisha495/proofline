"""test_findings_constraints.py — CHECK constraints on the findings table.

Verifies three database-level rules:
1. source_ref must not be empty (ck_findings_source_ref_nonempty) — "no source, no flag".
2. end_offset must be strictly greater than start_offset (ck_findings_offsets).
3. A dismissed finding must have a non-NULL dismissal_reason (ck_findings_dismissed_reason).
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


def test_findings_empty_source_ref_fails(db_conn):
    """source_ref = '' must violate ck_findings_source_ref_nonempty."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)

    with pytest.raises(Exception):
        db_conn.execute(
            text(
                "INSERT INTO findings "
                "(id, organisation_id, draft_id, version_id, start_offset, end_offset, "
                " severity, reason, source_ref, confidence) "
                "VALUES (:id, :org, :did, :vid, 0, 5, 'blocker', 'reason', '', 'high')"
            ),
            {"id": new_id(), "org": org_id, "did": draft_id, "vid": version_id},
        )


def test_findings_bad_offsets_fails(db_conn):
    """end_offset <= start_offset must violate ck_findings_offsets."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)

    with pytest.raises(Exception):
        db_conn.execute(
            text(
                "INSERT INTO findings "
                "(id, organisation_id, draft_id, version_id, start_offset, end_offset, "
                " severity, reason, source_ref, confidence) "
                "VALUES (:id, :org, :did, :vid, 10, 5, 'blocker', 'reason', 'TONE-01', 'high')"
            ),
            {"id": new_id(), "org": org_id, "did": draft_id, "vid": version_id},
        )


def test_findings_dismissed_without_reason_fails(db_conn):
    """A dismissed finding with NULL dismissal_reason must violate ck_findings_dismissed_reason."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)

    with pytest.raises(Exception):
        db_conn.execute(
            text(
                "INSERT INTO findings "
                "(id, organisation_id, draft_id, version_id, start_offset, end_offset, "
                " severity, reason, source_ref, confidence, status, dismissal_reason) "
                "VALUES (:id, :org, :did, :vid, 0, 5, 'note', 'reason', "
                "        'TONE-01', 'low', 'dismissed', NULL)"
            ),
            {"id": new_id(), "org": org_id, "did": draft_id, "vid": version_id},
        )

