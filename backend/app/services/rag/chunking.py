"""Document chunking and token management for the ProofLine RAG subsystem.

Responsibility:
    Responsible for segmenting parsed knowledge documents and normalized records into
    semantically coherent, size-bounded chunks suitable for vector embedding and retrieval.
    Preserves hierarchical context (e.g., policy headings, section numbers, rule IDs),
    character offsets, and source metadata.

Integration Notes:
    - Chunk boundaries preserve source references (e.g., `source_ref`, `source_version`)
      so that downstream findings cite exact source rules without losing context.
    - Supports both structured knowledge records (`NormalizedKnowledgeRecord`) and long-form
      markdown/text policy documents (`sample-data/documents/*.md`).
    - Operates entirely in-memory with zero external API dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.services.rag.ingestion import NormalizedKnowledgeRecord

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class DocumentChunk(BaseModel):
    """A bounded, semantically coherent unit of text with source traceability."""

    chunk_id: str
    content: str
    source_ref: str
    source_version: int = 1
    organisation_id: str = "org-brick-beyond"
    client_id: str | None = None
    project_id: str | None = None
    category: str = "general"
    header_context: str | None = None
    char_start: int | None = None
    char_end: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Low-Level Recursive Text Splitting
# ---------------------------------------------------------------------------


def split_text_with_overlap(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    separators: list[str] | None = None,
) -> list[tuple[str, int, int]]:
    """Recursively split text into bounded overlapping chunks, tracking character offsets.

    Args:
        text: Input text string.
        chunk_size: Maximum character length per chunk (must be > chunk_overlap).
        chunk_overlap: Overlapping character count between consecutive chunks.
        separators: Priority list of delimiter strings. Defaults to ["\n\n", "\n", ". ", " "].

    Returns:
        List of tuples: (chunk_text, start_offset, end_offset).
    """
    if chunk_size <= chunk_overlap:
        raise ValueError(f"chunk_size ({chunk_size}) must be greater than chunk_overlap ({chunk_overlap})")

    stripped = text.strip()
    if not stripped:
        return []

    if len(text) <= chunk_size:
        return [(text, 0, len(text))]

    if separators is None:
        separators = ["\n\n", "\n", ". ", " "]

    # Find the first separator present in the text
    chosen_sep = ""
    for sep in separators:
        if sep in text:
            chosen_sep = sep
            break

    if not chosen_sep:
        # Fallback to hard character slicing if no separator matches
        chunks: list[tuple[str, int, int]] = []
        start = 0
        text_len = len(text)
        step = chunk_size - chunk_overlap
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunks.append((text[start:end], start, end))
            if end >= text_len:
                break
            start += step
        return chunks

    # Split into raw splits and compute their offsets
    raw_splits = text.split(chosen_sep)
    split_items: list[tuple[str, int, int]] = []
    current_idx = 0

    for i, piece in enumerate(raw_splits):
        idx = text.find(piece, current_idx)
        split_items.append((piece, idx, idx + len(piece)))
        current_idx = idx + len(piece) + len(chosen_sep)

    # Recombine small splits into chunks respecting chunk_size and chunk_overlap
    results: list[tuple[str, int, int]] = []
    i = 0
    n = len(split_items)

    while i < n:
        start_idx = split_items[i][1]
        chunk_pieces: list[str] = []
        end_idx = start_idx
        j = i

        while j < n:
            piece, p_start, p_end = split_items[j]
            candidate_len = (p_end - start_idx)

            # If single piece exceeds chunk_size, recursively split with next separators
            if len(piece) > chunk_size and len(chunk_pieces) == 0:
                sub_seps = [s for s in separators if s != chosen_sep]
                sub_chunks = split_text_with_overlap(piece, chunk_size, chunk_overlap, sub_seps)
                for sub_text, sub_start, sub_end in sub_chunks:
                    results.append((sub_text, p_start + sub_start, p_start + sub_end))
                j += 1
                i = j
                break

            if candidate_len <= chunk_size or len(chunk_pieces) == 0:
                chunk_pieces.append(piece)
                end_idx = p_end
                j += 1
            else:
                break

        if chunk_pieces:
            chunk_content = text[start_idx:end_idx]
            results.append((chunk_content, start_idx, end_idx))

            if j >= n:
                break

            # Rewind j to implement chunk_overlap
            target_start = end_idx - chunk_overlap
            rewound_j = j
            while rewound_j > i and split_items[rewound_j - 1][1] > target_start:
                rewound_j -= 1
            if rewound_j == i:
                # Guarantee progress
                i = j
            else:
                i = rewound_j

    return results


# ---------------------------------------------------------------------------
# Header-Aware Markdown Chunking
# ---------------------------------------------------------------------------


def chunk_markdown(
    content: str,
    source_ref: str,
    source_version: int = 1,
    chunk_size: int = 600,
    chunk_overlap: int = 60,
    organisation_id: str = "org-brick-beyond",
    client_id: str | None = None,
    project_id: str | None = None,
    category: str = "document",
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Chunk a Markdown document while preserving section header hierarchy.

    Args:
        content: Markdown content string.
        source_ref: Document reference identifier.
        source_version: Version integer.
        chunk_size: Maximum character size per chunk.
        chunk_overlap: Overlapping characters between consecutive chunks within a section.
        organisation_id: Tenant organisation identifier.
        client_id: Optional client identifier.
        project_id: Optional project identifier.
        category: Knowledge category label.
        metadata: Base metadata dictionary to include in each chunk.

    Returns:
        List of DocumentChunk instances.
    """
    base_meta = dict(metadata or {})
    chunks: list[DocumentChunk] = []

    # Regex matching markdown headers (# through ####)
    header_pattern = re.compile(r"^(#{1,4})\s+(.+)$", re.MULTILINE)
    matches = list(header_pattern.finditer(content))

    if not matches:
        # No headers found; fall back to recursive text splitting
        raw_chunks = split_text_with_overlap(content, chunk_size, chunk_overlap)
        for idx, (chunk_str, c_start, c_end) in enumerate(raw_chunks):
            cid = f"{source_ref}_chk_{idx + 1:03d}"
            chunks.append(
                DocumentChunk(
                    chunk_id=cid,
                    content=chunk_str.strip(),
                    source_ref=source_ref,
                    source_version=source_version,
                    organisation_id=organisation_id,
                    client_id=client_id,
                    project_id=project_id,
                    category=category,
                    header_context=None,
                    char_start=c_start,
                    char_end=c_end,
                    metadata=base_meta,
                )
            )
        return chunks

    # Build sections bounded by headers
    header_levels: dict[int, str] = {}
    sections: list[dict[str, Any]] = []

    # Pre-header preamble if present
    if matches[0].start() > 0:
        preamble = content[: matches[0].start()].strip()
        if preamble:
            sections.append({
                "header_path": "Preamble",
                "text": preamble,
                "start": 0,
                "end": matches[0].start(),
            })

    for i, match in enumerate(matches):
        level = len(match.group(1))
        title = match.group(2).strip()

        # Update hierarchy: retain parents above current level, clear deeper levels
        header_levels = {k: v for k, v in header_levels.items() if k < level}
        header_levels[level] = title
        header_path = " > ".join(header_levels[k] for k in sorted(header_levels))

        body_start = match.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        body_text = content[body_start:body_end].strip()

        if body_text:
            sections.append({
                "header_path": header_path,
                "text": body_text,
                "start": body_start,
                "end": body_end,
            })

    # Segment each section into bounded chunks
    chunk_counter = 1
    for sec in sections:
        sec_text = sec["text"]
        header_path = sec["header_path"]
        sec_start = sec["start"]

        if len(sec_text) <= chunk_size:
            cid = f"{source_ref}_chk_{chunk_counter:03d}"
            # Embed header context into content for richer semantic matching
            formatted_content = f"[{header_path}]\n{sec_text}"
            chunks.append(
                DocumentChunk(
                    chunk_id=cid,
                    content=formatted_content,
                    source_ref=source_ref,
                    source_version=source_version,
                    organisation_id=organisation_id,
                    client_id=client_id,
                    project_id=project_id,
                    category=category,
                    header_context=header_path,
                    char_start=sec_start,
                    char_end=sec["end"],
                    metadata=base_meta,
                )
            )
            chunk_counter += 1
        else:
            sub_splits = split_text_with_overlap(sec_text, chunk_size, chunk_overlap)
            for sub_str, sub_start, sub_end in sub_splits:
                sub_clean = sub_str.strip()
                if not sub_clean:
                    continue
                cid = f"{source_ref}_chk_{chunk_counter:03d}"
                formatted_content = f"[{header_path}]\n{sub_clean}"
                chunks.append(
                    DocumentChunk(
                        chunk_id=cid,
                        content=formatted_content,
                        source_ref=source_ref,
                        source_version=source_version,
                        organisation_id=organisation_id,
                        client_id=client_id,
                        project_id=project_id,
                        category=category,
                        header_context=header_path,
                        char_start=sec_start + sub_start,
                        char_end=sec_start + sub_end,
                        metadata=base_meta,
                    )
                )
                chunk_counter += 1

    return chunks


# ---------------------------------------------------------------------------
# Normalized Knowledge Record Chunking
# ---------------------------------------------------------------------------


def chunk_normalized_record(
    record: NormalizedKnowledgeRecord,
    max_chunk_size: int = 1000,
    chunk_overlap: int = 100,
) -> list[DocumentChunk]:
    """Convert a single NormalizedKnowledgeRecord into one or more DocumentChunks.

    Atomic records <= max_chunk_size produce a single DocumentChunk. Oversized records
    are gracefully segmented while preserving all metadata and source provenance.

    Args:
        record: NormalizedKnowledgeRecord instance.
        max_chunk_size: Maximum character length for a single chunk.
        chunk_overlap: Overlap length if oversized record must be split.

    Returns:
        List of DocumentChunk instances.
    """
    text = record.searchable_text
    meta = dict(record.raw_data)

    if len(text) <= max_chunk_size:
        return [
            DocumentChunk(
                chunk_id=f"chk_{record.id}",
                content=text,
                source_ref=record.source_id,
                source_version=record.source_version,
                organisation_id=record.organisation_id,
                client_id=record.client_id,
                project_id=record.project_id,
                category=record.category,
                header_context=f"Knowledge Record: {record.source_id} ({record.category})",
                char_start=0,
                char_end=len(text),
                metadata=meta,
            )
        ]

    # Handle oversized record
    splits = split_text_with_overlap(text, max_chunk_size, chunk_overlap)
    chunks: list[DocumentChunk] = []
    for idx, (sub_text, s_start, s_end) in enumerate(splits):
        cid = f"chk_{record.id}_{idx + 1:02d}"
        chunks.append(
            DocumentChunk(
                chunk_id=cid,
                content=sub_text.strip(),
                source_ref=record.source_id,
                source_version=record.source_version,
                organisation_id=record.organisation_id,
                client_id=record.client_id,
                project_id=record.project_id,
                category=record.category,
                header_context=f"Knowledge Record: {record.source_id} ({record.category})",
                char_start=s_start,
                char_end=s_end,
                metadata=meta,
            )
        )
    return chunks


def chunk_normalized_records(
    records: list[NormalizedKnowledgeRecord],
    max_chunk_size: int = 1000,
    chunk_overlap: int = 100,
) -> list[DocumentChunk]:
    """Batch convert a list of NormalizedKnowledgeRecords into DocumentChunks.

    Args:
        records: List of NormalizedKnowledgeRecord instances.
        max_chunk_size: Maximum chunk character length.
        chunk_overlap: Overlap character count.

    Returns:
        Flattened list of all generated DocumentChunk instances.
    """
    all_chunks: list[DocumentChunk] = []
    for record in records:
        all_chunks.extend(chunk_normalized_record(record, max_chunk_size, chunk_overlap))
    return all_chunks


# ---------------------------------------------------------------------------
# High-Level Document File Chunking
# ---------------------------------------------------------------------------


def chunk_document_file(
    file_path: Path | str,
    source_ref: str | None = None,
    source_version: int = 1,
    chunk_size: int = 600,
    chunk_overlap: int = 60,
    organisation_id: str = "org-brick-beyond",
    client_id: str | None = None,
    project_id: str | None = None,
    category: str = "document",
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Read a document file (.md, .txt) and segment it into structured DocumentChunks.

    Args:
        file_path: Path to the target document.
        source_ref: Optional explicit source reference (defaults to file stem in uppercase).
        source_version: Document version integer.
        chunk_size: Target character limit per chunk.
        chunk_overlap: Overlap between consecutive chunks.
        organisation_id: Tenant organisation identifier.
        client_id: Client identifier.
        project_id: Project identifier.
        category: Document category label.
        metadata: Base metadata dictionary.

    Returns:
        List of DocumentChunk instances.
    """
    path = Path(file_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Document file not found: {path}")

    content = path.read_text(encoding="utf-8")
    ref = source_ref or path.stem.upper().replace("-", "_")

    return chunk_markdown(
        content=content,
        source_ref=ref,
        source_version=source_version,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        organisation_id=organisation_id,
        client_id=client_id,
        project_id=project_id,
        category=category,
        metadata={"file_name": path.name, **(metadata or {})},
    )


def chunk_document(
    content: str,
    source_ref: str,
    source_version: int = 1,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    organisation_id: str = "org-brick-beyond",
    client_id: str | None = None,
    project_id: str | None = None,
    category: str = "document",
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Universal chunking entry point supporting plain text and markdown.

    Args:
        content: The text content of the document.
        source_ref: Identifier of the source document or rule.
        source_version: Document version integer.
        chunk_size: Target character size per chunk.
        chunk_overlap: Overlapping characters between consecutive chunks.
        organisation_id: Tenant organisation identifier.
        client_id: Client identifier.
        project_id: Project identifier.
        category: Category label.
        metadata: Optional source-level metadata dictionary.

    Returns:
        List of DocumentChunk instances.
    """
    return chunk_markdown(
        content=content,
        source_ref=source_ref,
        source_version=source_version,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        organisation_id=organisation_id,
        client_id=client_id,
        project_id=project_id,
        category=category,
        metadata=metadata,
    )
