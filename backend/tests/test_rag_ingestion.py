"""Tests for RAG Stage 1: Knowledge Loading, Validation, and Normalisation.

Verifies:
1. Successful loading of all existing knowledge files.
2. Expected record count based on actual files (32 records).
3. Successful normalisation of all valid records.
4. Preservation of IDs and source metadata.
5. Handling of invalid JSON files.
6. Handling of missing required fields and malformed types.
7. Detection and reporting of duplicate record IDs.
8. Ensuring drafts and evaluation files are never discovered or loaded as approved knowledge.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.rag.ingestion import (
    KnowledgeLoadingError,
    NormalizedKnowledgeRecord,
    discover_knowledge_files,
    get_default_knowledge_dir,
    load_and_process_knowledge,
    load_knowledge_file,
    load_knowledge_files,
    validate_knowledge_record,
    validate_knowledge_records,
)

# ---------------------------------------------------------------------------
# Tests on Actual Knowledge Dataset
# ---------------------------------------------------------------------------


def test_successful_loading_of_all_existing_knowledge_files():
    """Verify that all JSON files in sample-data/knowledge are discovered and loaded."""
    knowledge_dir = get_default_knowledge_dir()
    assert knowledge_dir.exists(), f"Knowledge dir not found at: {knowledge_dir}"

    files = discover_knowledge_files(knowledge_dir)
    assert len(files) == 6, f"Expected 6 knowledge files, discovered: {len(files)}"

    file_names = {f.name for f in files}
    expected_files = {
        "brand-guidelines.json",
        "terminology.json",
        "project-facts.json",
        "amenities.json",
        "pricing.json",
        "approvals.json",
    }
    assert file_names == expected_files


def test_expected_record_count():
    """Verify exact record counts matching the actual files (total 32 records)."""
    raw_records = load_knowledge_files()
    assert len(raw_records) == 32

    # Verify per-file record distribution
    counts_by_file: dict[str, int] = {}
    for r in raw_records:
        src = r["_source_file_name"]
        counts_by_file[src] = counts_by_file.get(src, 0) + 1

    assert counts_by_file["brand-guidelines.json"] == 8
    assert counts_by_file["terminology.json"] == 5
    assert counts_by_file["project-facts.json"] == 7
    assert counts_by_file["amenities.json"] == 6
    assert counts_by_file["pricing.json"] == 3
    assert counts_by_file["approvals.json"] == 3


def test_successful_normalisation_of_all_valid_records():
    """Verify that all 32 records validate and normalise cleanly without errors."""
    normalised, errors = load_and_process_knowledge(raise_on_error=True)

    assert len(errors) == 0, f"Expected 0 validation errors, got: {errors}"
    assert len(normalised) == 32
    assert all(isinstance(rec, NormalizedKnowledgeRecord) for rec in normalised)

    # Verify all records have non-empty searchable text
    for rec in normalised:
        assert rec.searchable_text.strip(), f"Searchable text is empty for {rec.id}"
        assert rec.category in {"guideline", "terminology", "fact", "amenity", "pricing", "approval"}
        assert rec.source_file.endswith(".json")


def test_preservation_of_ids_and_source_metadata():
    """Verify that original record IDs, source refs, and tenant metadata are faithfully preserved."""
    normalised, _ = load_and_process_knowledge()

    # Check a specific fact record
    fact = next(r for r in normalised if r.id == "ag-fact-loc-01")
    assert fact.source_id == "AG-FACT-LOC-01"
    assert fact.source_version == 1
    assert fact.organisation_id == "org-brick-beyond"
    assert fact.client_id == "client-asteria-developers"
    assert fact.project_id == "proj-asteria-greens"
    assert fact.approval_status == "approved"
    assert fact.valid_from == "2026-01-01T00:00:00Z"
    assert fact.valid_until == "2028-12-31T23:59:59Z"
    assert fact.source_file == "project-facts.json"
    assert "Sector 78, Gurugram" in fact.searchable_text
    assert fact.raw_data["statement"] == "Project Location"

    # Check an agency-level guideline record (client/project should be None)
    guideline = next(r for r in normalised if r.id == "bb-guide-voice-01")
    assert guideline.source_id == "BB-GUIDE-VOICE-01"
    assert guideline.client_id is None
    assert guideline.project_id is None
    assert guideline.category == "guideline"
    assert "Consultative" in guideline.searchable_text
    assert "raw_data" in guideline.model_dump()

    # Check a terminology record
    term = next(r for r in normalised if r.id == "bb-term-area-01")
    assert term.source_id == "BB-TERM-01"
    assert term.category == "terminology"
    assert "super built-up area" in term.searchable_text
    assert "carpet area" in term.searchable_text
    assert "Banned / Prohibited" in term.searchable_text


# ---------------------------------------------------------------------------
# Edge Cases, Error Handling & Temporary Test Data
# ---------------------------------------------------------------------------


def test_handling_invalid_json(tmp_path: Path):
    """Verify that malformed JSON raises KnowledgeLoadingError with line details."""
    broken_file = tmp_path / "broken.json"
    broken_file.write_text("{ this is not valid json : [", encoding="utf-8")

    with pytest.raises(KnowledgeLoadingError) as exc_info:
        load_knowledge_file(broken_file)

    assert "Invalid JSON in broken.json" in str(exc_info.value)


def test_handling_non_list_json(tmp_path: Path):
    """Verify that JSON containing a single dictionary instead of a list raises KnowledgeLoadingError."""
    dict_file = tmp_path / "single_dict.json"
    dict_file.write_text(json.dumps({"id": "item-1"}), encoding="utf-8")

    with pytest.raises(KnowledgeLoadingError) as exc_info:
        load_knowledge_file(dict_file)

    assert "expected list of records" in str(exc_info.value)


def test_handling_missing_required_fields():
    """Verify validation detects missing IDs, source versions, and category requirements."""
    # Record missing id and source_id
    bad_record = {
        "organisation_id": "org-1",
        "approval_status": "approved",
    }
    errors = validate_knowledge_record(bad_record)
    fields_with_errors = {e.field for e in errors}

    assert "id" in fields_with_errors
    assert "source_id" in fields_with_errors
    assert "source_version" in fields_with_errors

    # Guideline missing rule_title and description
    bad_guideline = {
        "id": "g-01",
        "source_id": "G-01",
        "source_version": 1,
        "organisation_id": "org-1",
        "approval_status": "approved",
        "category": "guideline",
    }
    g_errors = validate_knowledge_record(bad_guideline)
    g_fields = {e.field for e in g_errors}
    assert "rule_title" in g_fields
    assert "description" in g_fields


def test_handling_invalid_iso_dates():
    """Verify that malformed validity dates are caught."""
    record_with_bad_date = {
        "id": "rec-01",
        "source_id": "SRC-01",
        "source_version": 1,
        "organisation_id": "org-1",
        "approval_status": "approved",
        "statement": "Some statement",
        "value": "Some value",
        "valid_from": "31-12-2026",  # Not ISO 8601
    }
    errors = validate_knowledge_record(record_with_bad_date)
    assert any(e.field == "valid_from" and "Invalid ISO 8601" in e.message for e in errors)


def test_duplicate_record_id_detection():
    """Verify that duplicate record IDs across files or within a file are detected."""
    records = [
        {
            "id": "duplicate-id-123",
            "source_id": "SRC-01",
            "source_version": 1,
            "organisation_id": "org-1",
            "approval_status": "approved",
            "statement": "First statement",
            "value": "Val 1",
            "_source_file_name": "file_a.json",
        },
        {
            "id": "duplicate-id-123",  # Duplicate!
            "source_id": "SRC-02",
            "source_version": 1,
            "organisation_id": "org-1",
            "approval_status": "approved",
            "statement": "Second statement",
            "value": "Val 2",
            "_source_file_name": "file_b.json",
        },
    ]

    valid, errors = validate_knowledge_records(records)
    assert len(valid) == 1
    assert len(errors) == 1
    assert errors[0].field == "id"
    assert "Duplicate record ID found: 'duplicate-id-123'" in errors[0].message


def test_drafts_and_evaluation_not_loaded_as_approved_knowledge(tmp_path: Path):
    """Verify that discover_knowledge_files excludes drafts and evaluation datasets."""
    knowledge_dir = tmp_path / "knowledge"
    knowledge_dir.mkdir()

    # Valid knowledge file
    (knowledge_dir / "valid.json").write_text(
        json.dumps([{"id": "k1", "source_id": "S1", "source_version": 1, "organisation_id": "org", "approval_status": "approved", "statement": "Fact", "value": "Val"}]),
        encoding="utf-8",
    )

    # Subdirectory for evaluation
    eval_dir = knowledge_dir / "evaluation"
    eval_dir.mkdir()
    (eval_dir / "eval.json").write_text(json.dumps([{"fake": "data"}]), encoding="utf-8")

    # Subdirectory for seeded drafts
    drafts_dir = knowledge_dir / "seeded-drafts"
    drafts_dir.mkdir()
    (drafts_dir / "drafts.json").write_text(json.dumps([{"draft": "text"}]), encoding="utf-8")

    discovered = discover_knowledge_files(knowledge_dir)
    discovered_names = [f.name for f in discovered]

    assert "valid.json" in discovered_names
    assert "eval.json" not in discovered_names
    assert "drafts.json" not in discovered_names

