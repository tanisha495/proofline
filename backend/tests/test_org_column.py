"""test_org_column.py — Metadata check: every table has organisation_id.

This test inspects SQLAlchemy metadata only; no live database required.
"""
from __future__ import annotations

import app.models as m


def test_org_column():
    """Every table except 'organisations' must have an organisation_id column."""
    for table_name, table in m.Base.metadata.tables.items():
        if table_name == "organisations":
            continue
        col_names = {c.name for c in table.columns}
        assert "organisation_id" in col_names, (
            f"Table '{table_name}' is missing organisation_id column"
        )

