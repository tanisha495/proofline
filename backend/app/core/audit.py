"""Audit logging service for ProofLine API."""
from __future__ import annotations

import uuid
from typing import Any, Dict, Optional, Union
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def log_action(
    db: Session,
    organisation_id: Union[str, uuid.UUID],
    user_id: Optional[Union[str, uuid.UUID]],
    action: str,
    entity: Optional[str] = None,
    entity_id: Optional[Union[str, uuid.UUID]] = None,
    details: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Insert an entry into audit_log in the same session and transaction as the caller.

    Does not commit so caller controls the transaction boundary.
    Never include passwords, tokens or credentials in details.
    """
    parsed_org_id = (
        uuid.UUID(str(organisation_id))
        if not isinstance(organisation_id, uuid.UUID)
        else organisation_id
    )
    parsed_user_id = (
        uuid.UUID(str(user_id))
        if user_id and not isinstance(user_id, uuid.UUID)
        else user_id
    )
    parsed_entity_id = None
    if entity_id:
        try:
            parsed_entity_id = (
                uuid.UUID(str(entity_id))
                if not isinstance(entity_id, uuid.UUID)
                else entity_id
            )
        except (ValueError, TypeError):
            parsed_entity_id = None

    safe_details = details.copy() if details else {}
    for key in ("password", "password_hash", "token", "access_token"):
        safe_details.pop(key, None)

    entry = AuditLog(
        organisation_id=parsed_org_id,
        user_id=parsed_user_id,
        action=action,
        entity=entity,
        entity_id=parsed_entity_id,
        details=safe_details,
    )
    db.add(entry)
    db.flush()
    return entry
