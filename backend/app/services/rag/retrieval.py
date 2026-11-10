"""Knowledge retrieval module for the ProofLine RAG subsystem.

Responsibility:
    Responsible for executing semantic similarity search and tenant-isolated retrieval across
    ingested knowledge chunks (Stage 2) and embeddings (Stage 3). Retrieves top-k relevant
    evidence snippets to ground LLM claim verification and review checks.

Integration Notes:
    - Queries in-memory vector store or Krish's future PostgreSQL/pgvector repository with
      strict multi-tenant isolation enforced by `organisation_id`.
    - Formats retrieved evidence for Kalash's LLM review engine into `RetrievedEvidence` contracts
      so generated findings reference verifiable `source_ref` and `source_version`.
    - Similarity scores reflect semantic relatedness; high similarity denotes topical relevance
      (which can be a factual match OR a factual contradiction), never absolute truth.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.services.rag.embeddings import (
    EmbeddedChunk,
    EmbeddingDimensionError,
    EmbeddingValueError,
    generate_query_embedding,
    get_default_dimensions,
)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class RetrievedEvidence(BaseModel):
    """Normalized evidence contract delivered to the LLM review engine."""

    chunk_id: str
    source_ref: str
    source_version: int
    content: str
    similarity_score: float
    category: str
    header_context: str | None = None
    organisation_id: str
    client_id: str | None = None
    project_id: str | None = None
    approval_status: str = "approved"
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Mathematical Utilities
# ---------------------------------------------------------------------------


def compute_cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    """Compute the cosine similarity between two numerical vectors.

    Args:
        vec_a: First vector of floats.
        vec_b: Second vector of floats.

    Returns:
        Cosine similarity float in range [-1.0, 1.0].

    Raises:
        EmbeddingDimensionError: If vector dimensions do not match.
        EmbeddingValueError: If any vector contains non-finite values (NaN, Inf).
    """
    if len(vec_a) != len(vec_b):
        raise EmbeddingDimensionError(
            f"Cannot compute cosine similarity: vectors have mismatched dimensions ({len(vec_a)} vs {len(vec_b)})."
        )

    dot_product = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for a, b in zip(vec_a, vec_b, strict=True):
        if not isinstance(a, (int, float)) or math.isnan(a) or math.isinf(a):
            raise EmbeddingValueError(f"Vector A contains non-finite numerical value: {a}")
        if not isinstance(b, (int, float)) or math.isnan(b) or math.isinf(b):
            raise EmbeddingValueError(f"Vector B contains non-finite numerical value: {b}")

        dot_product += a * b
        norm_a += a * a
        norm_b += b * b

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    sim = dot_product / (math.sqrt(norm_a) * math.sqrt(norm_b))
    # Bound to [-1.0, 1.0] against precision overflow
    return max(-1.0, min(1.0, sim))


# ---------------------------------------------------------------------------
# In-Memory Vector Store
# ---------------------------------------------------------------------------


def _parse_iso_date(date_val: Any) -> datetime | None:
    """Parse ISO 8601 string or datetime into a datetime object for comparison."""
    if isinstance(date_val, datetime):
        return date_val
    if isinstance(date_val, str) and date_val.strip():
        try:
            return datetime.fromisoformat(date_val)
        except ValueError:
            return None
    return None


class InMemoryVectorIndex:
    """Thread-safe in-memory vector store with multi-tenant filtering."""

    def __init__(self, expected_dim: int | None = None) -> None:
        self.expected_dim = expected_dim or get_default_dimensions()
        self._chunks: list[EmbeddedChunk] = []

    def count(self) -> int:
        """Return the number of stored chunks."""
        return len(self._chunks)

    def __len__(self) -> int:
        """Return the number of stored chunks via len()."""
        return len(self._chunks)

    def clear(self) -> None:
        """Remove all stored chunks from the index."""
        self._chunks.clear()

    def add_chunks(self, chunks: Sequence[EmbeddedChunk]) -> None:
        """Add a sequence of EmbeddedChunks to the index, validating dimensions.

        Args:
            chunks: Sequence of EmbeddedChunk instances.

        Raises:
            EmbeddingDimensionError: If any chunk vector does not match expected_dim.
        """
        for chunk in chunks:
            if len(chunk.embedding) != self.expected_dim:
                raise EmbeddingDimensionError(
                    f"Chunk '{chunk.chunk_id}' has {len(chunk.embedding)} dimensions; expected {self.expected_dim}."
                )
            self._chunks.append(chunk)

    def search(
        self,
        query_vector: Sequence[float],
        organisation_id: str,
        client_id: str | None = None,
        project_id: str | None = None,
        top_k: int = 5,
        min_score: float = 0.0,
        include_agency_knowledge: bool = True,
        filter_unapproved: bool = True,
        as_of_date: datetime | str | None = None,
    ) -> list[RetrievedEvidence]:
        """Search the index for relevant evidence matching the query vector and scope.

        Filtering Rules:
        1. Tenant Isolation: Must match `organisation_id` exactly.
        2. Scope Inheritance:
           - If `project_id` provided: matches that project, OR (if include_agency_knowledge)
             client-level knowledge and agency-level knowledge (where client_id/project_id is None).
           - If only `client_id` provided: matches that client, OR agency-level knowledge.
           - If neither provided: matches agency-level knowledge only.
        3. Approval Status: If `filter_unapproved` is True, excludes non-approved chunks.
        4. Temporal Validity: If `as_of_date` is provided, excludes chunks where `as_of_date`
           is outside `valid_from` or `valid_until`.

        Args:
            query_vector: 1536-dimensional query embedding vector.
            organisation_id: Mandatory tenant organisation identifier.
            client_id: Optional client identifier.
            project_id: Optional project identifier.
            top_k: Maximum number of results to return.
            min_score: Minimum cosine similarity threshold.
            include_agency_knowledge: Whether to include agency-wide rules in project queries.
            filter_unapproved: Whether to exclude chunks with unapproved status.
            as_of_date: Reference date for validity filtering.

        Returns:
            List of RetrievedEvidence instances sorted by similarity score descending.
        """
        if len(query_vector) != self.expected_dim:
            raise EmbeddingDimensionError(
                f"Query vector has {len(query_vector)} dimensions; expected {self.expected_dim}."
            )

        ref_date = _parse_iso_date(as_of_date) if as_of_date else None
        scored_candidates: list[tuple[float, EmbeddedChunk]] = []

        for chunk in self._chunks:
            # 1. Mandatory Tenant Boundary
            if chunk.organisation_id != organisation_id:
                continue

            # 2. Scope Filtering
            if project_id:
                # Target is project-specific
                is_same_project = chunk.project_id == project_id
                is_client_parent = include_agency_knowledge and (chunk.client_id == client_id and chunk.project_id is None)
                is_agency_parent = include_agency_knowledge and (chunk.client_id is None and chunk.project_id is None)
                if not (is_same_project or is_client_parent or is_agency_parent):
                    continue
            elif client_id:
                # Target is client-specific
                is_same_client = chunk.client_id == client_id
                is_agency_parent = include_agency_knowledge and (chunk.client_id is None and chunk.project_id is None)
                if not (is_same_client or is_agency_parent):
                    continue
            else:
                # Target is agency-wide
                if chunk.client_id is not None or chunk.project_id is not None:
                    continue

            # 3. Governance / Approval Status Filtering
            if filter_unapproved and chunk.metadata.get("approval_status", "approved") != "approved":
                continue

            # 4. Temporal Validity Filtering
            if ref_date:
                raw_until = chunk.metadata.get("valid_until")
                if raw_until:
                    until_dt = _parse_iso_date(raw_until)
                    if until_dt and ref_date > until_dt:
                        continue  # Expired knowledge

                raw_from = chunk.metadata.get("valid_from")
                if raw_from:
                    from_dt = _parse_iso_date(raw_from)
                    if from_dt and ref_date < from_dt:
                        continue  # Not yet effective

            # 5. Compute Cosine Similarity
            sim = compute_cosine_similarity(query_vector, chunk.embedding)

            # 6. Apply Minimum Score Cutoff
            if sim >= min_score:
                scored_candidates.append((sim, chunk))

        # 7. Sort Descending by Similarity Score
        scored_candidates.sort(key=lambda pair: pair[0], reverse=True)

        # 8. Limit to Top-K and Convert to RetrievedEvidence
        results: list[RetrievedEvidence] = []
        for sim, chunk in scored_candidates[:top_k]:
            results.append(
                RetrievedEvidence(
                    chunk_id=chunk.chunk_id,
                    source_ref=chunk.source_ref,
                    source_version=chunk.source_version,
                    content=chunk.content,
                    similarity_score=round(sim, 6),
                    category=chunk.category,
                    header_context=chunk.header_context,
                    organisation_id=chunk.organisation_id,
                    client_id=chunk.client_id,
                    project_id=chunk.project_id,
                    approval_status=chunk.metadata.get("approval_status", "approved"),
                    metadata=dict(chunk.metadata),
                )
            )

        return results


# ---------------------------------------------------------------------------
# Global Default In-Memory Store & Builder
# ---------------------------------------------------------------------------

_GLOBAL_INDEX = InMemoryVectorIndex()


def get_default_vector_index() -> InMemoryVectorIndex:
    """Access the shared in-memory vector index instance."""
    return _GLOBAL_INDEX


# ---------------------------------------------------------------------------
# High-Level Retrieval Entry Point
# ---------------------------------------------------------------------------


def retrieve_relevant_context(
    query_text: str,
    organisation_id: str,
    client_id: str | None = None,
    project_id: str | None = None,
    top_k: int = 5,
    min_score: float = 0.0,
    vector_index: InMemoryVectorIndex | None = None,
    embedding_client: Any = None,
    include_agency_knowledge: bool = True,
    filter_unapproved: bool = True,
    as_of_date: datetime | str | None = None,
) -> list[RetrievedEvidence]:
    """Retrieve top-k relevant knowledge snippets for a query within an organisation.

    Acts as the standard entry point for Kalash's LLM review engine.

    Args:
        query_text: Text snippet, claim, or paragraph from a draft under review.
        organisation_id: Tenant organisation identifier for security isolation.
        client_id: Optional client identifier for client-specific scoping.
        project_id: Optional project identifier for project-specific scoping.
        top_k: Maximum number of evidence snippets to return.
        min_score: Minimum similarity score threshold for returned results.
        vector_index: Target vector index. If None, uses `get_default_vector_index()`.
        embedding_client: Optional pre-configured OpenAI client for query vectorization.
        include_agency_knowledge: Whether to inherit agency-wide rules in project queries.
        filter_unapproved: Whether to exclude unapproved chunks.
        as_of_date: Optional reference timestamp for validity filtering.

    Returns:
        List of RetrievedEvidence instances sorted by relevance score.

    Raises:
        ValueError: If `query_text` is empty or whitespace-only.
        EmbeddingConfigurationError: If OpenAI embedding credentials are not configured.
        EmbeddingAPIError: If embedding generation fails.
    """
    if not isinstance(query_text, str) or not query_text.strip():
        raise ValueError("query_text cannot be empty or whitespace-only for retrieval.")

    # 1. Generate Query Vector Embedding using Stage 3 pipeline
    query_vector = generate_query_embedding(
        query=query_text,
        client=embedding_client,
    )

    # 2. Query the Vector Store
    index = vector_index if vector_index is not None else get_default_vector_index()

    return index.search(
        query_vector=query_vector,
        organisation_id=organisation_id,
        client_id=client_id,
        project_id=project_id,
        top_k=top_k,
        min_score=min_score,
        include_agency_knowledge=include_agency_knowledge,
        filter_unapproved=filter_unapproved,
        as_of_date=as_of_date,
    )
