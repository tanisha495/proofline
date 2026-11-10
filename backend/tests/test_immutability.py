"""test_immutability.py — Trigger-enforced immutability rules.

Verifies that the following operations are blocked by database triggers:
- UPDATE on audit_log                   (trg_fn_immutable_row)
- DELETE on audit_log                   (trg_fn_immutable_row)
- UPDATE content/hash on draft_versions (trg_fn_immutable_content)
- DELETE on claim_receipts              (trg_fn_immutable_row)
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


def test_audit_log_update_blocked(db_conn):
    """UPDATE on audit_log must be blocked by the immutable-row trigger."""
    org_id = insert_org(db_conn)
    log_id = new_id()
    db_conn.execute(
        text(
            "INSERT INTO audit_log (id, organisation_id, action, entity) "
            "VALUES (:id, :org, 'test_action', 'test_entity')"
        ),
        {"id": log_id, "org": org_id},
    )
    with pytest.raises(Exception, match="immutable"):
        db_conn.execute(
            text("UPDATE audit_log SET action = 'changed' WHERE id = :id"),
            {"id": log_id},
        )


def test_audit_log_delete_blocked(db_conn):
    """DELETE on audit_log must be blocked by the immutable-row trigger."""
    org_id = insert_org(db_conn)
    log_id = new_id()
    db_conn.execute(
        text(
            "INSERT INTO audit_log (id, organisation_id, action, entity) "
            "VALUES (:id, :org, 'delete_me', 'test_entity')"
        ),
        {"id": log_id, "org": org_id},
    )
    with pytest.raises(Exception, match="immutable"):
        db_conn.execute(
            text("DELETE FROM audit_log WHERE id = :id"),
            {"id": log_id},
        )


def test_draft_version_content_update_blocked(db_conn):
    """UPDATE of draft_versions.content must be blocked by trg_fn_immutable_content."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)

    with pytest.raises(Exception, match="immutable"):
        db_conn.execute(
            text(
                "UPDATE draft_versions SET content = 'tampered', "
                "content_hash = :h WHERE id = :id"
            ),
            {"h": sha256("tampered"), "id": version_id},
        )


def test_claim_receipts_delete_blocked(db_conn):
    """DELETE on claim_receipts must be blocked by the immutable-row trigger."""
    org_id = insert_org(db_conn)
    user_id = insert_user(db_conn, org_id)
    draft_id = insert_draft(db_conn, org_id, user_id)
    version_id = insert_draft_version(db_conn, org_id, draft_id)

    receipt_id = new_id()
    content = "approved content"
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

    with pytest.raises(Exception, match="immutable"):
        db_conn.execute(
            text("DELETE FROM claim_receipts WHERE id = :id"),
            {"id": receipt_id},
        )
