"""Tests for RAG Stage 2: Chunking & Token Management.

Verifies:
1. Low-level text splitting with overlap and accurate character offset tracking.
2. Handling of invalid chunking parameters (e.g., chunk_size <= chunk_overlap).
3. Header-aware Markdown chunking with hierarchical context preservation.
4. Fallback chunking for documents lacking Markdown headers.
5. Normalisation and preservation of metadata when chunking NormalizedKnowledgeRecords.
6. Graceful handling of oversized knowledge records.
7. End-to-end chunking of actual policy and marketing documents in sample-data/documents/.
8. Proper error handling for missing files.
"""

from __future__ import annotations

import pytest

from app.services.rag.chunking import (
    DocumentChunk,
    chunk_document_file,
    chunk_markdown,
    chunk_normalized_record,
    chunk_normalized_records,
    split_text_with_overlap,
)
from app.services.rag.ingestion import NormalizedKnowledgeRecord, load_and_process_knowledge

# ---------------------------------------------------------------------------
# Low-level Text Splitting Tests
# ---------------------------------------------------------------------------


def test_split_text_short_string():
    """Verify that text shorter than chunk_size returns a single intact chunk."""
    text = "Short policy guideline statement."
    chunks = split_text_with_overlap(text, chunk_size=100, chunk_overlap=20)

    assert len(chunks) == 1
    chunk_text, start, end = chunks[0]
    assert chunk_text == text
    assert start == 0
    assert end == len(text)


def test_split_text_with_overlap_offsets():
    """Verify that long multi-paragraph text splits properly and offsets match substrings."""
    paragraphs = [
        "First section: The developer must strictly disclose RERA carpet area in square feet.",
        "Second section: Super built-up area must not be advertised without explicit carpet area disclosure.",
        "Third section: Investment returns and guaranteed appreciation promises are strictly prohibited.",
    ]
    full_text = "\n\n".join(paragraphs)

    chunks = split_text_with_overlap(full_text, chunk_size=120, chunk_overlap=30)
    assert len(chunks) >= 2

    for chunk_text, start, end in chunks:
        # Verify offset slices exact text
        assert full_text[start:end] == chunk_text
        assert len(chunk_text) <= 120


def test_split_text_invalid_parameters():
    """Verify that chunk_size <= chunk_overlap raises ValueError."""
    with pytest.raises(ValueError) as exc:
        split_text_with_overlap("sample text", chunk_size=50, chunk_overlap=50)
    assert "must be greater than" in str(exc.value)


# ---------------------------------------------------------------------------
# Header-Aware Markdown Chunking Tests
# ---------------------------------------------------------------------------


def test_chunk_markdown_hierarchy():
    """Verify that markdown headers build nested hierarchical paths."""
    md_text = """# Brick & Beyond Policy Manual

## 3. Financial Rules

### 3.1 Prohibited Returns
No marketing communication may guarantee, promise, or assure financial returns.
"""
    chunks = chunk_markdown(
        content=md_text,
        source_ref="BB-MANUAL",
        source_version=1,
        chunk_size=500,
        chunk_overlap=50,
        organisation_id="org-brick-beyond",
    )

    assert len(chunks) >= 1
    # Check that header context carries hierarchical chain
    rule_chunk = next(c for c in chunks if "3.1 Prohibited Returns" in (c.header_context or ""))
    assert "Brick & Beyond Policy Manual" in rule_chunk.header_context
    assert "3. Financial Rules" in rule_chunk.header_context
    assert "3.1 Prohibited Returns" in rule_chunk.header_context
    assert rule_chunk.source_ref == "BB-MANUAL"
    assert rule_chunk.source_version == 1
    assert "No marketing communication may guarantee" in rule_chunk.content


def test_chunk_markdown_without_headers():
    """Verify that markdown lacking headers falls back gracefully to recursive text chunking."""
    plain_text = "Standard plain text without any markdown hashes or titles. Just a plain paragraph."
    chunks = chunk_markdown(
        content=plain_text,
        source_ref="PLAIN-01",
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1
    assert chunks[0].chunk_id == "PLAIN-01_chk_001"
    assert chunks[0].header_context is None
    assert chunks[0].content == plain_text


# ---------------------------------------------------------------------------
# Normalized Knowledge Records Chunking Tests
# ---------------------------------------------------------------------------


def test_chunk_normalized_record_preserves_metadata():
    """Verify that a NormalizedKnowledgeRecord converts to DocumentChunk preserving all fields."""
    record = NormalizedKnowledgeRecord(
        id="ag-fact-loc-01",
        category="fact",
        searchable_text="Project Fact [AG-FACT-LOC-01]: Sector 78, Gurugram.",
        organisation_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        source_id="AG-FACT-LOC-01",
        source_version=1,
        approval_status="approved",
        valid_from="2026-01-01T00:00:00Z",
        valid_until="2028-12-31T23:59:59Z",
        source_file="project-facts.json",
        raw_data={"statement": "Project Location", "value": "Sector 78, Gurugram"},
    )

    chunks = chunk_normalized_record(record, max_chunk_size=500)
    assert len(chunks) == 1

    chunk = chunks[0]
    assert chunk.chunk_id == "chk_ag-fact-loc-01"
    assert chunk.source_ref == "AG-FACT-LOC-01"
    assert chunk.source_version == 1
    assert chunk.organisation_id == "org-brick-beyond"
    assert chunk.client_id == "client-asteria-developers"
    assert chunk.project_id == "proj-asteria-greens"
    assert chunk.category == "fact"
    assert chunk.content == record.searchable_text
    assert chunk.metadata["statement"] == "Project Location"


def test_chunk_normalized_record_oversized():
    """Verify that an oversized knowledge record splits into multiple indexed chunks."""
    long_content = "Word " * 200  # 1000 characters
    record = NormalizedKnowledgeRecord(
        id="long-rec-01",
        category="guideline",
        searchable_text=long_content,
        organisation_id="org-brick-beyond",
        source_id="LONG-01",
        source_version=1,
        approval_status="approved",
        source_file="long.json",
    )

    chunks = chunk_normalized_record(record, max_chunk_size=300, chunk_overlap=50)
    assert len(chunks) > 1
    assert chunks[0].chunk_id == "chk_long-rec-01_01"
    assert chunks[1].chunk_id == "chk_long-rec-01_02"
    for c in chunks:
        assert c.source_ref == "LONG-01"
        assert c.source_version == 1


def test_chunk_all_32_actual_normalized_records():
    """Verify batch chunking of all 32 knowledge records loaded via Stage 1."""
    records, errors = load_and_process_knowledge()
    assert len(errors) == 0
    assert len(records) == 32

    chunks = chunk_normalized_records(records)
    assert len(chunks) == 32
    assert all(isinstance(c, DocumentChunk) for c in chunks)


# ---------------------------------------------------------------------------
# Document File Ingestion Chunking Tests
# ---------------------------------------------------------------------------


def test_chunk_actual_sample_data_document_files():
    """Verify chunking of the 3 markdown files in sample-data/documents/."""
    from app.services.rag.ingestion import get_default_knowledge_dir

    knowledge_dir = get_default_knowledge_dir()
    docs_dir = knowledge_dir.parent / "documents"

    # Test Agency Brand Manual
    manual_path = docs_dir / "agency-brand-manual.md"
    assert manual_path.exists()
    manual_chunks = chunk_document_file(manual_path, chunk_size=600, chunk_overlap=60)
    assert len(manual_chunks) >= 5
    assert any("Prohibition of Guaranteed Returns" in c.content for c in manual_chunks)

    # Test Project Brochure
    brochure_path = docs_dir / "asteria-greens-project-brochure.md"
    assert brochure_path.exists()
    brochure_chunks = chunk_document_file(brochure_path, chunk_size=600, chunk_overlap=60)
    assert len(brochure_chunks) >= 5
    assert any("Curated Residences" in (c.header_context or "") for c in brochure_chunks)

    # Test Information Sheet
    sheet_path = docs_dir / "asteria-greens-project-information-sheet.md"
    assert sheet_path.exists()
    sheet_chunks = chunk_document_file(sheet_path, chunk_size=600, chunk_overlap=60)
    assert len(sheet_chunks) >= 5
    assert any("Statutory & Licensing Record" in (c.header_context or "") for c in sheet_chunks)


def test_chunk_document_file_missing_raises_error():
    """Verify FileNotFoundError is raised when file does not exist."""
    with pytest.raises(FileNotFoundError):
        chunk_document_file("non_existent_document_file.md")

