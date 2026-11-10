"""Shared helper functions for ProofLine database tests.

Imported by test_*.py modules; not a test file itself.
"""
from __future__ import annotations

import hashlib
import uuid

from sqlalchemy import text


def new_id() -> str:
    return str(uuid.uuid4())


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def insert_org(conn, name: str | None = None) -> str:
    """Insert an organisation and return its id."""
    org_id = new_id()
    name = name or f"org-{org_id[:8]}"
    conn.execute(
        text("INSERT INTO organisations (id, name) VALUES (:id, :name)"),
        {"id": org_id, "name": name},
    )
    return org_id


def insert_user(conn, org_id: str) -> str:
    """Insert a minimal user and return its id."""
    user_id = new_id()
    conn.execute(
        text(
            "INSERT INTO users (id, organisation_id, email, password_hash, role) "
            "VALUES (:id, :org, :email, :pw, 'creator')"
        ),
        {"id": user_id, "org": org_id, "email": f"{user_id}@example.com", "pw": "x"},
    )
    return user_id


def insert_draft(conn, org_id: str, owner_id: str) -> str:
    """Insert a draft and return its id."""
    d_id = new_id()
    conn.execute(
        text(
            "INSERT INTO drafts (id, organisation_id, owner_id, title) "
            "VALUES (:id, :org, :owner, 'Test draft')"
        ),
        {"id": d_id, "org": org_id, "owner": owner_id},
    )
    return d_id


def insert_draft_version(conn, org_id: str, draft_id: str, vnum: int = 1) -> str:
    """Insert a draft_version and return its id."""
    v_id = new_id()
    content = f"content-v{vnum}"
    conn.execute(
        text(
            "INSERT INTO draft_versions "
            "(id, organisation_id, draft_id, version_number, content, content_hash) "
            "VALUES (:id, :org, :did, :vnum, :content, :hash)"
        ),
        {
            "id": v_id,
            "org": org_id,
            "did": draft_id,
            "vnum": vnum,
            "content": content,
            "hash": sha256(content),
        },
    )
    return v_id

