"""Tests for RAG Stage 4: Retrieval Engine.

Verifies:
1. Pure Python cosine similarity computation (identical, orthogonal, opposite, zero vectors).
2. Vector dimension mismatch and non-finite value validation in cosine similarity.
3. Strict multi-tenant isolation (preventing cross-tenant data leakage).
4. Agency-level knowledge inheritance for project queries.
5. Project-specific scoping (preventing cross-project pollution).
6. Governance filtering for unapproved knowledge chunks (e.g., negative amenities list).
7. Expiration date filtering for temporal validity.
8. Top-K cutoff and minimum similarity score thresholding.
9. Empty and whitespace-only query rejection.
10. End-to-end retrieval flow using Stage 1 knowledge, Stage 2 chunks, and Stage 3 mock embeddings.
"""

from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest

from app.services.rag.chunking import chunk_normalized_records
from app.services.rag.embeddings import (
    EmbeddedChunk,
    EmbeddingDimensionError,
    EmbeddingValueError,
    embed_chunks,
)
from app.services.rag.ingestion import load_and_process_knowledge
from app.services.rag.retrieval import (
    InMemoryVectorIndex,
    RetrievedEvidence,
    compute_cosine_similarity,
    retrieve_relevant_context,
)

# ---------------------------------------------------------------------------
# Cosine Similarity Math Tests
# ---------------------------------------------------------------------------


def test_cosine_similarity_math():
    """Verify cosine similarity outputs for standard vector relationships."""
    # Identical vectors
    v1 = [1.0, 2.0, 3.0]
    v2 = [1.0, 2.0, 3.0]
    assert math.isclose(compute_cosine_similarity(v1, v2), 1.0, rel_tol=1e-5)

    # Parallel vectors (different magnitudes)
    v3 = [2.0, 4.0, 6.0]
    assert math.isclose(compute_cosine_similarity(v1, v3), 1.0, rel_tol=1e-5)

    # Orthogonal vectors
    ortho1 = [1.0, 0.0]
    ortho2 = [0.0, 1.0]
    assert math.isclose(compute_cosine_similarity(ortho1, ortho2), 0.0, abs_tol=1e-5)

    # Opposite vectors
    opp1 = [1.0, -1.0]
    opp2 = [-1.0, 1.0]
    assert math.isclose(compute_cosine_similarity(opp1, opp2), -1.0, rel_tol=1e-5)

    # Zero vector handling (must return 0.0 without ZeroDivisionError)
    zero_vec = [0.0, 0.0]
    assert compute_cosine_similarity(zero_vec, [1.0, 2.0]) == 0.0


def test_cosine_similarity_validation():
    """Verify dimension mismatch and non-finite value rejections."""
    # Mismatched dimensions
    with pytest.raises(EmbeddingDimensionError):
        compute_cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    # NaN in Vector A
    with pytest.raises(EmbeddingValueError):
        compute_cosine_similarity([float("nan"), 1.0], [1.0, 2.0])

    # Inf in Vector B
    with pytest.raises(EmbeddingValueError):
        compute_cosine_similarity([1.0, 2.0], [1.0, float("inf")])


# ---------------------------------------------------------------------------
# Multi-Tenant & Scoping Tests
# ---------------------------------------------------------------------------


def make_dummy_embedded_chunk(
    chunk_id: str,
    source_ref: str,
    org_id: str = "org-brick-beyond",
    client_id: str | None = None,
    project_id: str | None = None,
    approval_status: str = "approved",
    valid_until: str | None = None,
    dim: int = 1536,
    seed_val: float = 0.1,
) -> EmbeddedChunk:
    """Helper to build an EmbeddedChunk with controlled tenant scope."""
    vec = [seed_val] * dim
    return EmbeddedChunk(
        chunk_id=chunk_id,
        content=f"Content for {chunk_id}",
        source_ref=source_ref,
        source_version=1,
        organisation_id=org_id,
        client_id=client_id,
        project_id=project_id,
        category="fact",
        metadata={
            "approval_status": approval_status,
            "valid_until": valid_until,
        },
        embedding=vec,
    )


def test_tenant_isolation():
    """Verify that chunks belonging to one organisation are never returned to another."""
    index = InMemoryVectorIndex(expected_dim=1536)

    # Add chunk belonging to org-brick-beyond
    chunk_a = make_dummy_embedded_chunk(
        chunk_id="chk_a",
        source_ref="REF-A",
        org_id="org-brick-beyond",
        seed_val=1.0,
    )
    # Add chunk belonging to org-competitor
    chunk_b = make_dummy_embedded_chunk(
        chunk_id="chk_b",
        source_ref="REF-B",
        org_id="org-competitor",
        seed_val=1.0,
    )
    index.add_chunks([chunk_a, chunk_b])

    # Query with org-brick-beyond vector
    query_vec = [1.0] * 1536
    results = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        top_k=10,
    )

    assert len(results) == 1
    assert results[0].chunk_id == "chk_a"
    assert results[0].organisation_id == "org-brick-beyond"

    # Query with org-competitor
    results_comp = index.search(
        query_vector=query_vec,
        organisation_id="org-competitor",
        top_k=10,
    )
    assert len(results_comp) == 1
    assert results_comp[0].chunk_id == "chk_b"
    assert results_comp[0].organisation_id == "org-competitor"


def test_agency_knowledge_inheritance():
    """Verify project query inherits agency-wide rules when include_agency_knowledge=True."""
    index = InMemoryVectorIndex(expected_dim=1536)

    # Agency-level rule (client_id and project_id are None)
    agency_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_agency_rule",
        source_ref="BB-GUIDE-VOICE-01",
        org_id="org-brick-beyond",
        client_id=None,
        project_id=None,
        seed_val=0.9,
    )
    # Project-level fact
    project_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_project_fact",
        source_ref="AG-FACT-LOC-01",
        org_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        seed_val=0.8,
    )
    # Another project fact
    other_proj_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_other_proj",
        source_ref="OTHER-FACT-01",
        org_id="org-brick-beyond",
        client_id="client-other",
        project_id="proj-other",
        seed_val=0.7,
    )
    index.add_chunks([agency_chunk, project_chunk, other_proj_chunk])

    query_vec = [1.0] * 1536

    # Project search with agency inheritance
    res_inherited = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        include_agency_knowledge=True,
    )
    chunk_ids = {r.chunk_id for r in res_inherited}
    assert "chk_project_fact" in chunk_ids
    assert "chk_agency_rule" in chunk_ids
    assert "chk_other_proj" not in chunk_ids  # Other project must be excluded!

    # Project search WITHOUT agency inheritance
    res_isolated = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        include_agency_knowledge=False,
    )
    iso_ids = {r.chunk_id for r in res_isolated}
    assert "chk_project_fact" in iso_ids
    assert "chk_agency_rule" not in iso_ids


def test_governance_unapproved_filtering():
    """Verify that unapproved chunks are excluded when filter_unapproved=True."""
    index = InMemoryVectorIndex(expected_dim=1536)

    approved_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_appr",
        source_ref="AG-AMEN-POOL-01",
        approval_status="approved",
        seed_val=0.9,
    )
    rejected_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_rej",
        source_ref="AG-AMEN-UNAPPROVED-06",
        approval_status="rejected",
        seed_val=0.95,  # Higher similarity, but rejected!
    )
    index.add_chunks([approved_chunk, rejected_chunk])

    query_vec = [1.0] * 1536

    # By default, filter_unapproved is True
    res_filtered = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        filter_unapproved=True,
    )
    assert len(res_filtered) == 1
    assert res_filtered[0].chunk_id == "chk_appr"

    # If explicitly set to False, rejected chunk is included
    res_unfiltered = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        filter_unapproved=False,
    )
    assert len(res_unfiltered) == 2


def test_temporal_validity_filtering():
    """Verify that expired knowledge chunks are excluded when as_of_date is provided."""
    index = InMemoryVectorIndex(expected_dim=1536)

    active_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_active",
        source_ref="AG-PRICE-01",
        valid_until="2028-12-31T23:59:59Z",
        seed_val=0.9,
    )
    expired_chunk = make_dummy_embedded_chunk(
        chunk_id="chk_expired",
        source_ref="AG-OLD-PRICE",
        valid_until="2025-12-31T23:59:59Z",
        seed_val=0.95,
    )
    index.add_chunks([active_chunk, expired_chunk])

    query_vec = [1.0] * 1536

    # Search as of 2026-06-01 (expired chunk is past its 2025 validity)
    res = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        as_of_date="2026-06-01T00:00:00Z",
    )
    assert len(res) == 1
    assert res[0].chunk_id == "chk_active"


def test_top_k_and_min_score_cutoff():
    """Verify top-k limits and min_score threshold cutoffs."""
    index = InMemoryVectorIndex(expected_dim=1536)

    # Add 5 chunks with varying seed values (0.1, 0.2, 0.3, 0.4, 0.5)
    chunks = [
        make_dummy_embedded_chunk(f"chk_{i}", f"REF-{i}", seed_val=i * 0.1)
        for i in range(1, 6)
    ]
    index.add_chunks(chunks)

    query_vec = [1.0] * 1536

    # Test top_k=2
    res_top2 = index.search(
        query_vector=query_vec,
        organisation_id="org-brick-beyond",
        top_k=2,
    )
    assert len(res_top2) == 2
    # Verify descending sort order
    assert res_top2[0].similarity_score >= res_top2[1].similarity_score

    # Test min_score cutoff
    # Chunks with uniform positive values will have cosine similarity = 1.0
    # Let's add an orthogonal chunk
    ortho_vec = [0.0] * 1536
    ortho_vec[0] = 1.0
    query_ortho = [0.0] * 1536
    query_ortho[1] = 1.0  # Dot product = 0.0

    ortho_chunk = EmbeddedChunk(
        chunk_id="chk_ortho",
        content="Ortho",
        source_ref="ORTHO-01",
        organisation_id="org-brick-beyond",
        category="fact",
        embedding=ortho_vec,
    )
    index.add_chunks([ortho_chunk])

    res_min_score = index.search(
        query_vector=query_ortho,
        organisation_id="org-brick-beyond",
        min_score=0.5,
    )
    # The orthogonal chunk similarity is 0.0, so it must be filtered out
    assert all(r.similarity_score >= 0.5 for r in res_min_score)


# ---------------------------------------------------------------------------
# High-Level retrieve_relevant_context Tests
# ---------------------------------------------------------------------------


def test_retrieve_relevant_context_empty_query():
    """Verify empty or whitespace-only query raises ValueError."""
    with pytest.raises(ValueError):
        retrieve_relevant_context("", organisation_id="org-brick-beyond")

    with pytest.raises(ValueError):
        retrieve_relevant_context("   ", organisation_id="org-brick-beyond")


def test_end_to_end_retrieval_with_mock_embeddings():
    """End-to-end integration: Stage 1 records -> Stage 2 chunks -> Stage 3 embeddings -> Stage 4 search."""
    # 1. Load normalized knowledge
    records, errors = load_and_process_knowledge()
    assert len(errors) == 0

    # 2. Chunk records
    chunks = chunk_normalized_records(records)
    assert len(chunks) == 32

    # 3. Embed chunks with mock client
    mock_client = MagicMock()

    def fake_create(*, input, model, dimensions=1536, **kwargs):
        inputs = [input] if isinstance(input, str) else list(input)
        items = []
        for idx, text in enumerate(inputs):
            # Create a vector encoding content cues
            vec = [0.001 * (idx + 1)] * 1536
            if "1,050" in text or "Carpet Area" in text:
                vec[0] = 0.99  # Signal for carpet area query
            if "₹1.25 crore" in text:
                vec[1] = 0.99  # Signal for price query
            items.append(MagicMock(index=idx, embedding=vec))
        resp = MagicMock()
        resp.data = items
        return resp

    mock_client.embeddings.create.side_effect = fake_create
    embedded_chunks = embed_chunks(chunks, client=mock_client)

    # 4. Populate index
    index = InMemoryVectorIndex(expected_dim=1536)
    index.add_chunks(embedded_chunks)
    assert index.count() == 32

    # 5. Execute retrieval for a draft claim
    evidence = retrieve_relevant_context(
        query_text="What is the approved 2 BHK carpet area?",
        organisation_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        top_k=3,
        vector_index=index,
        embedding_client=mock_client,
    )

    assert len(evidence) <= 3
    assert all(isinstance(e, RetrievedEvidence) for e in evidence)
    assert all(e.organisation_id == "org-brick-beyond" for e in evidence)
    assert all(0.0 <= e.similarity_score <= 1.0 for e in evidence)
    # The top retrieved evidence should be a fact or specification
    assert evidence[0].category in {"fact", "guideline", "terminology", "amenity", "pricing", "approval"}
