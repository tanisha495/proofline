"""Knowledge ingestion, validation, and normalisation for the ProofLine RAG subsystem.

Responsibility:
    Responsible for reliably locating, discovering, loading, validating, and normalising
    organisational brand guidelines, facts, terminology, amenities, pricing, and approvals
    from JSON knowledge sources into a uniform, searchable internal representation.

Integration Notes:
    - Independent of external vector databases, embedding APIs, or relational databases.
    - Preserves exact source provenance (`source_id`, `source_version`, `source_file`)
      and tenant boundaries (`organisation_id`, `client_id`, `project_id`).
    - Disallows loading of drafts or evaluation datasets as approved knowledge.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Custom Exceptions & Validation Models
# ---------------------------------------------------------------------------


class KnowledgeLoadingError(Exception):
    """Raised when knowledge discovery or JSON file loading fails."""


@dataclass
class ValidationErrorDetail:
    """Detailed description of an invalid field within a knowledge record."""

    file_path: str
    record_id: str | None
    field: str
    message: str

    def __str__(self) -> str:
        rec = f"record '{self.record_id}'" if self.record_id else "unknown record"
        return f"[{self.file_path}] {rec} - field '{self.field}': {self.message}"


class NormalizedKnowledgeRecord(BaseModel):
    """Consistent internal representation for all ingested knowledge records."""

    id: str
    category: str  # "guideline", "terminology", "fact", "amenity", "pricing", "approval"
    searchable_text: str
    organisation_id: str
    client_id: str | None = None
    project_id: str | None = None
    source_id: str
    source_version: int
    approval_status: str
    valid_from: str | None = None
    valid_until: str | None = None
    source_file: str
    raw_data: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Knowledge Discovery & Loading
# ---------------------------------------------------------------------------


def get_default_knowledge_dir() -> Path:
    """Locate the knowledge directory reliably across environments.

    Checks:
    1. PROOFLINE_KNOWLEDGE_DIR environment variable if set.
    2. Relative repository traversal from this module's location.
    3. Current working directory fallback.
    """
    env_dir = os.environ.get("PROOFLINE_KNOWLEDGE_DIR")
    if env_dir:
        candidate = Path(env_dir).resolve()
        if candidate.is_dir():
            return candidate

    # Traverse upwards from backend/app/services/rag/ingestion.py
    current_file = Path(__file__).resolve()
    for parent in current_file.parents:
        candidate = parent / "sample-data" / "knowledge"
        if candidate.is_dir():
            return candidate

    # Fallback to current working directory
    cwd_candidate = Path.cwd() / "sample-data" / "knowledge"
    if cwd_candidate.is_dir():
        return cwd_candidate

    # Return standard calculated path even if not yet created (useful in tests)
    return current_file.parents[4] / "sample-data" / "knowledge"


def discover_knowledge_files(knowledge_dir: Path | str | None = None) -> list[Path]:
    """Discover all JSON knowledge files inside the specified knowledge directory.

    Explicitly excludes drafts, evaluation datasets, hidden folders, and non-JSON files.

    Args:
        knowledge_dir: Path to search. If None, uses `get_default_knowledge_dir()`.

    Returns:
        Sorted list of discovered JSON file paths.

    Raises:
        KnowledgeLoadingError: If the directory does not exist or is not a directory.
    """
    target_dir = Path(knowledge_dir).resolve() if knowledge_dir else get_default_knowledge_dir()

    if not target_dir.exists():
        raise KnowledgeLoadingError(f"Knowledge directory does not exist: {target_dir}")
    if not target_dir.is_dir():
        raise KnowledgeLoadingError(f"Knowledge path is not a directory: {target_dir}")

    discovered: list[Path] = []
    excluded_markers = {"seeded-drafts", "evaluation", ".git", "__pycache__"}

    for path in target_dir.rglob("*.json"):
        # Ensure path does not traverse into excluded test/evaluation folders
        parts_set = set(path.parts)
        if parts_set.intersection(excluded_markers):
            continue
        discovered.append(path)

    return sorted(discovered)


def load_knowledge_file(file_path: Path | str) -> list[dict[str, Any]]:
    """Safely load and parse a single JSON knowledge file.

    Args:
        file_path: Path to the target JSON file.

    Returns:
        List of raw record dictionaries with `_source_file` metadata attached.

    Raises:
        KnowledgeLoadingError: If the file is missing, contains invalid JSON,
                               or has an invalid top-level data structure.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise KnowledgeLoadingError(f"Knowledge file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as err:
        raise KnowledgeLoadingError(f"Failed to read knowledge file {path.name}: {err}") from err

    try:
        data = json.loads(content)
    except json.JSONDecodeError as err:
        raise KnowledgeLoadingError(
            f"Invalid JSON in {path.name} (line {err.lineno}, col {err.colno}): {err.msg}"
        ) from err

    if not isinstance(data, list):
        raise KnowledgeLoadingError(
            f"Unexpected data structure in {path.name}: expected list of records, got {type(data).__name__}"
        )

    # Attach relative source file path for tracking
    file_rel = path.name
    results: list[dict[str, Any]] = []
    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            raise KnowledgeLoadingError(
                f"Unexpected item type in {path.name} at index {idx}: expected dict, got {type(item).__name__}"
            )
        record_copy = dict(item)
        record_copy["_source_file"] = str(path)
        record_copy["_source_file_name"] = file_rel
        results.append(record_copy)

    return results


def load_knowledge_files(knowledge_dir: Path | str | None = None) -> list[dict[str, Any]]:
    """Discover and load all JSON knowledge files into a flat list of raw records.

    Args:
        knowledge_dir: Path to the knowledge root directory.

    Returns:
        Combined list of all raw knowledge record dictionaries.
    """
    files = discover_knowledge_files(knowledge_dir)
    all_records: list[dict[str, Any]] = []
    for file_path in files:
        records = load_knowledge_file(file_path)
        all_records.extend(records)
    return all_records


# ---------------------------------------------------------------------------
# Validation Logic
# ---------------------------------------------------------------------------


def infer_record_category(record: dict[str, Any], source_file: str = "") -> str:
    """Infer the knowledge category of a record from its fields and source filename."""
    fname = source_file.lower()

    if "brand-guidelines" in fname or ("rule_title" in record and "description" in record):
        return "guideline"
    if "terminology" in fname or ("term" in record and "preferred" in record):
        return "terminology"
    if "project-facts" in fname or ("statement" in record and "value" in record):
        return "fact"
    if "amenities" in fname or ("amenity_name" in record and "specifications" in record):
        return "amenity"
    if "pricing" in fname or ("pricing_type" in record and "formatted_price" in record):
        return "pricing"
    if "approvals" in fname or ("approval_type" in record and "registration_number" in record):
        return "approval"

    # Default fallback
    return record.get("category", "unknown").lower()


def _validate_iso_date(date_str: Any, field_name: str, file_path: str, record_id: str | None) -> ValidationErrorDetail | None:
    """Validate that a date string is formatted in valid ISO 8601."""
    if not isinstance(date_str, str):
        return ValidationErrorDetail(file_path, record_id, field_name, f"Expected ISO 8601 string, got {type(date_str).__name__}")
    try:
        # Support trailing Z
        normalized = date_str.replace("Z", "+00:00")
        datetime.fromisoformat(normalized)
        return None
    except ValueError:
        return ValidationErrorDetail(file_path, record_id, field_name, f"Invalid ISO 8601 date string: '{date_str}'")


def validate_knowledge_record(
    record: dict[str, Any],
    seen_ids: set[str] | None = None,
) -> list[ValidationErrorDetail]:
    """Validate a single knowledge record against schema and business rules.

    Args:
        record: Raw record dictionary.
        seen_ids: Optional set of already encountered record IDs for uniqueness checking.

    Returns:
        List of ValidationErrorDetail instances (empty if valid).
    """
    errors: list[ValidationErrorDetail] = []
    file_path = record.get("_source_file_name", record.get("_source_file", "unknown"))

    # 1. Identifier validation
    rec_id = record.get("id")
    if not rec_id or not isinstance(rec_id, str) or not rec_id.strip():
        errors.append(ValidationErrorDetail(file_path, None, "id", "Record ID is required and must be a non-empty string"))
    else:
        rec_id_str = str(rec_id)
        if seen_ids is not None:
            if rec_id_str in seen_ids:
                errors.append(ValidationErrorDetail(file_path, rec_id_str, "id", f"Duplicate record ID found: '{rec_id_str}'"))
            else:
                seen_ids.add(rec_id_str)

    record_id_ref = str(rec_id) if rec_id else None

    # 2. Source ID & Version
    source_id = record.get("source_id")
    if not source_id or not isinstance(source_id, str) or not source_id.strip():
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "source_id", "source_id is required and must be a non-empty string"))

    source_version = record.get("source_version")
    if source_version is None or not isinstance(source_version, int) or source_version < 1:
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "source_version", "source_version must be an integer >= 1"))

    # 3. Organisation & Scope Metadata
    org_id = record.get("organisation_id")
    if not org_id or not isinstance(org_id, str) or not org_id.strip():
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "organisation_id", "organisation_id is required and must be a non-empty string"))

    client_id = record.get("client_id")
    if client_id is not None and not isinstance(client_id, str):
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "client_id", "client_id must be a string or null"))

    project_id = record.get("project_id")
    if project_id is not None and not isinstance(project_id, str):
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "project_id", "project_id must be a string or null"))

    # 4. Approval Status
    status = record.get("approval_status")
    if not status or not isinstance(status, str) or not status.strip():
        errors.append(ValidationErrorDetail(file_path, record_id_ref, "approval_status", "approval_status is required and must be a string"))

    # 5. Validity Dates
    if "valid_from" in record and record["valid_from"] is not None:
        date_err = _validate_iso_date(record["valid_from"], "valid_from", file_path, record_id_ref)
        if date_err:
            errors.append(date_err)

    if "valid_until" in record and record["valid_until"] is not None:
        date_err = _validate_iso_date(record["valid_until"], "valid_until", file_path, record_id_ref)
        if date_err:
            errors.append(date_err)

    # 6. Category-specific Content Validation
    category = infer_record_category(record, file_path)

    if category == "guideline":
        if not record.get("rule_title") or not isinstance(record["rule_title"], str) or not record["rule_title"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "rule_title", "Guideline requires non-empty 'rule_title'"))
        if not record.get("description") or not isinstance(record["description"], str) or not record["description"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "description", "Guideline requires non-empty 'description'"))

    elif category == "terminology":
        if not record.get("term") or not isinstance(record["term"], str) or not record["term"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "term", "Terminology requires non-empty 'term'"))
        if not record.get("preferred") or not isinstance(record["preferred"], str) or not record["preferred"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "preferred", "Terminology requires non-empty 'preferred'"))
        if not isinstance(record.get("banned"), bool):
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "banned", "Terminology requires boolean 'banned' field"))

    elif category == "fact":
        if not record.get("statement") or not isinstance(record["statement"], str) or not record["statement"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "statement", "Fact requires non-empty 'statement'"))
        if "value" not in record or (record["value"] is not None and not isinstance(record["value"], str)):
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "value", "Fact requires 'value' (string or null)"))

    elif category == "amenity":
        if not record.get("amenity_name") or not isinstance(record["amenity_name"], str) or not record["amenity_name"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "amenity_name", "Amenity requires non-empty 'amenity_name'"))
        if not record.get("specifications") or not isinstance(record["specifications"], str) or not record["specifications"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "specifications", "Amenity requires non-empty 'specifications'"))

    elif category == "pricing":
        if not record.get("pricing_type") or not isinstance(record["pricing_type"], str) or not record["pricing_type"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "pricing_type", "Pricing requires non-empty 'pricing_type'"))
        if not record.get("description") or not isinstance(record["description"], str) or not record["description"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "description", "Pricing requires non-empty 'description'"))

    elif category == "approval":
        if not record.get("approval_type") or not isinstance(record["approval_type"], str) or not record["approval_type"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "approval_type", "Approval requires non-empty 'approval_type'"))
        if not record.get("registration_number") or not isinstance(record["registration_number"], str) or not record["registration_number"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "registration_number", "Approval requires non-empty 'registration_number'"))
        if not record.get("authority_name") or not isinstance(record["authority_name"], str) or not record["authority_name"].strip():
            errors.append(ValidationErrorDetail(file_path, record_id_ref, "authority_name", "Approval requires non-empty 'authority_name'"))

    return errors


def validate_knowledge_records(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[ValidationErrorDetail]]:
    """Validate a collection of raw knowledge records.

    Args:
        records: List of raw record dictionaries.

    Returns:
        Tuple of (valid_records, validation_errors).
    """
    valid_records: list[dict[str, Any]] = []
    all_errors: list[ValidationErrorDetail] = []
    seen_ids: set[str] = set()

    for record in records:
        record_errors = validate_knowledge_record(record, seen_ids=seen_ids)
        if record_errors:
            all_errors.extend(record_errors)
        else:
            valid_records.append(record)

    return valid_records, all_errors


# ---------------------------------------------------------------------------
# Normalisation Logic
# ---------------------------------------------------------------------------


def _build_searchable_text(category: str, record: dict[str, Any]) -> str:
    """Build a comprehensive searchable text representation tailored to the record's category."""
    source_id = record.get("source_id", "")

    if category == "guideline":
        rule_title = record.get("rule_title", "")
        cat = record.get("category", "General")
        desc = record.get("description", "")
        return f"Brand Guideline [{source_id} - {cat}]: {rule_title}. Policy: {desc}"

    if category == "terminology":
        term = record.get("term", "")
        pref = record.get("preferred", "")
        banned = record.get("banned", False)
        notes = record.get("notes", "")
        status = "Banned / Prohibited" if banned else "Permitted"
        text = f"Terminology Rule [{source_id}]: Term '{term}' ({status}). Preferred Expression: '{pref}'."
        if notes:
            text += f" Guidance: {notes}"
        return text

    if category == "fact":
        stmt = record.get("statement", "")
        val = record.get("value", "")
        cat = record.get("category", "General")
        notes = record.get("notes")
        src = record.get("source")
        text = f"Project Fact [{source_id} - {cat}]: {stmt}: {val}."
        if notes:
            text += f" Notes: {notes}."
        if src:
            text += f" Source Reference: {src}."
        return text

    if category == "amenity":
        name = record.get("amenity_name", "")
        cat = record.get("category", "General")
        status = str(record.get("approval_status", "")).upper()
        specs = record.get("specifications", "")
        return f"Project Amenity [{source_id} - {cat}]: {name} (Status: {status}). Specifications: {specs}"

    if category == "pricing":
        ptype = record.get("pricing_type", "")
        utype = record.get("unit_type", "All Units")
        fprice = record.get("formatted_price", "")
        val_inr = record.get("value_inr")
        desc = record.get("description", "")
        price_info = fprice or (f"INR {val_inr}" if val_inr else "N/A")
        return f"Pricing Specification [{source_id}]: {ptype} for {utype} - {price_info}. Details: {desc}"

    if category == "approval":
        atype = record.get("approval_type", "")
        reg_no = record.get("registration_number", "")
        auth = record.get("authority_name", "")
        portal = record.get("authority_portal")
        desc = record.get("description", "")
        text = f"Regulatory Approval [{source_id}]: {atype} (Reg No: {reg_no}) issued by {auth}."
        if portal:
            text += f" Authority Portal: {portal}."
        if desc:
            text += f" Scope: {desc}"
        return text

    # Generic fallback
    return f"Knowledge Record [{source_id} - {category}]: " + " | ".join(
        f"{k}: {v}" for k, v in record.items() if not k.startswith("_") and isinstance(v, (str, int, float, bool))
    )


def normalise_knowledge_record(record: dict[str, Any]) -> NormalizedKnowledgeRecord:
    """Normalise a single validated raw knowledge record into `NormalizedKnowledgeRecord`.

    Args:
        record: Validated raw record dictionary.

    Returns:
        NormalizedKnowledgeRecord with synthesized searchable text and preserved metadata.
    """
    file_rel = record.get("_source_file_name", record.get("_source_file", "unknown"))
    category = infer_record_category(record, file_rel)
    searchable_text = _build_searchable_text(category, record)

    # Clean internal markers from raw_data payload
    raw_payload = {k: v for k, v in record.items() if not k.startswith("_")}

    return NormalizedKnowledgeRecord(
        id=str(record["id"]),
        category=category,
        searchable_text=searchable_text,
        organisation_id=str(record["organisation_id"]),
        client_id=str(record["client_id"]) if record.get("client_id") else None,
        project_id=str(record["project_id"]) if record.get("project_id") else None,
        source_id=str(record["source_id"]),
        source_version=int(record["source_version"]),
        approval_status=str(record["approval_status"]),
        valid_from=str(record["valid_from"]) if record.get("valid_from") else None,
        valid_until=str(record["valid_until"]) if record.get("valid_until") else None,
        source_file=file_rel,
        raw_data=raw_payload,
    )


def normalise_knowledge_records(records: list[dict[str, Any]]) -> list[NormalizedKnowledgeRecord]:
    """Normalise a list of validated raw knowledge records.

    Args:
        records: List of validated record dictionaries.

    Returns:
        List of NormalizedKnowledgeRecord instances.
    """
    return [normalise_knowledge_record(record) for record in records]


# ---------------------------------------------------------------------------
# High-Level Orchestrator
# ---------------------------------------------------------------------------


def load_and_process_knowledge(
    knowledge_dir: Path | str | None = None,
    raise_on_error: bool = False,
) -> tuple[list[NormalizedKnowledgeRecord], list[ValidationErrorDetail]]:
    """Execute end-to-end knowledge loading, validation, and normalisation.

    Args:
        knowledge_dir: Path to knowledge root directory (defaults to sample-data/knowledge).
        raise_on_error: If True, raises KnowledgeLoadingError on first validation error.

    Returns:
        Tuple of (normalised_records, validation_errors).

    Raises:
        KnowledgeLoadingError: If directory discovery fails or raise_on_error is True with errors.
    """
    raw_records = load_knowledge_files(knowledge_dir)
    valid_records, validation_errors = validate_knowledge_records(raw_records)

    if raise_on_error and validation_errors:
        err_msg = "; ".join(str(e) for e in validation_errors)
        raise KnowledgeLoadingError(f"Knowledge validation failed with {len(validation_errors)} error(s): {err_msg}")

    normalised = normalise_knowledge_records(valid_records)
    return normalised, validation_errors


# ---------------------------------------------------------------------------
# Provisional Future Placeholders (Kept for downstream pipeline alignment)
# ---------------------------------------------------------------------------


@dataclass
class IngestionResult:
    """Provisional outcome metrics for an ingestion run."""

    source_id: str
    chunks_created: int
    embeddings_generated: int
    status: str
    details: dict[str, Any] | None = None


def ingest_knowledge_document(
    file_path: Path | str,
    organisation_id: UUID | str,
    source_ref: str,
    version: int = 1,
) -> IngestionResult:
    """Provisional placeholder for future vector database ingestion (Stage 2)."""
    raise NotImplementedError("ingestion.ingest_knowledge_document is a provisional placeholder.")
