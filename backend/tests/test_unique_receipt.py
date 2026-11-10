"""test_unique_receipt.py — Exactly one claim receipt per approved version.

Verifies:
- Inserting a receipt for a draft version succeeds.
- Inserting a second receipt for the same version_id fails due to
  uq_claim_receipts_version_id (UNIQUE constraint).
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
    sha256,
)


def test_unique_receipt_per_version(db_conn):
    """A second claim_receipt for the same version_id must fail (UNIQUE constraint)."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)
    content = "approved content"

    def _insert(receipt_id: str):
        db_conn.execute(
            text(
                "INSERT INTO claim_receipts "
                "(id, organisation_id, draft_id, version_id, approved_by, approved_at, "
                " content_hash, claims_snapshot, guideline_versions) "
                "VALUES (:id, :org, :did, :vid, :user, now(), :hash, '{}', '{}')"
            ),
            {
                "id": receipt_id,
                "org": org_id,
                "did": draft_id,
                "vid": version_id,
                "user": user_id,
                "hash": sha256(content),
            },
        )

    _insert(new_id())  # first receipt — succeeds

    with pytest.raises(Exception):
        _insert(new_id())  # second receipt for same version_id — fails
