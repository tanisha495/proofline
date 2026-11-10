"""ProofLine database utilities.

Organisation-scoped query helper
---------------------------------
Every repository function that reads or writes data MUST use ``org_scoped``
(or add the equivalent ``WHERE organisation_id = :org_id`` clause manually).
This is the application's primary defence against cross-organisation data leaks.

Usage::

    from app.db_utils import org_scoped
    from app.models.draft import Draft

    drafts = db.execute(org_scoped(select(Draft), Draft, org_id)).scalars().all()

The function accepts both ``Select`` statements and ``Update``/``Delete``
statements and adds ``.where(Model.organisation_id == organisation_id)``.
"""
from __future__ import annotations

import uuid
from typing import TypeVar

import sqlalchemy as sa

T = TypeVar("T")


def org_scoped(
    stmt: T,
    model: type,
    organisation_id: uuid.UUID,
) -> T:
    """Return *stmt* with an additional ``organisation_id`` filter applied.

    Args:
        stmt: A SQLAlchemy ``select``, ``update`` or ``delete`` statement.
        model: The SQLAlchemy ORM model class whose table is being queried.
        organisation_id: The UUID of the requesting organisation.

    Returns:
        The same statement type with an extra WHERE clause.

    Raises:
        AttributeError: If *model* does not have an ``organisation_id`` column.

    Example::

        stmt = org_scoped(
            sa.select(Finding).where(Finding.status == "open"),
            Finding,
            current_user.organisation_id,
        )
        findings = session.scalars(stmt).all()
    """
    col = getattr(model, "organisation_id", None)
    if col is None:
        raise AttributeError(
            f"{model.__name__} does not have an organisation_id column. "
            "Only org-scoped tables can use org_scoped()."
        )
    return stmt.where(col == organisation_id)  # type: ignore[return-value]

