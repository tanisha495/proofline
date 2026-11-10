"""Test the Finding Pydantic schema contract."""

import pytest
from pydantic import ValidationError

from app.schemas.finding import Finding


def test_finding_rejects_empty_source_ref():
    """source_ref must not be empty – this is a core contract rule."""
    with pytest.raises(ValidationError) as exc_info:
        Finding(
            id="f-1",
            draft_id="d-1",
            version_id="v-1",
            quoted_text="some text",
            start=0,
            end=9,
            severity="blocker",
            reason="Test reason",
            source_ref="",
            source_version=1,
            confidence="high",
            suggestion=None,
            status="open",
            dismissal_reason=None,
        )
    assert "source_ref" in str(exc_info.value)


def test_finding_rejects_whitespace_only_source_ref():
    """source_ref with only whitespace must also be rejected."""
    with pytest.raises(ValidationError):
        Finding(
            id="f-1",
            draft_id="d-1",
            version_id="v-1",
            quoted_text="some text",
            start=0,
            end=9,
            severity="blocker",
            reason="Test reason",
            source_ref="   ",
            source_version=1,
            confidence="high",
            suggestion=None,
            status="open",
            dismissal_reason=None,
        )


def test_finding_accepts_valid_data():
    """A well-formed Finding should be accepted."""
    f = Finding(
        id="f-1",
        draft_id="d-1",
        version_id="v-1",
        quoted_text="some text",
        start=0,
        end=9,
        severity="blocker",
        reason="Test reason",
        source_ref="TONE-01",
        source_version=1,
        confidence="high",
        suggestion=None,
        status="open",
        dismissal_reason=None,
    )
    assert f.source_ref == "TONE-01"
    assert f.severity == "blocker"

