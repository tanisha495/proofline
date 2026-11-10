"""Tests for RAG Stage 3: OpenAI Embedding Generation.

Verifies:
1. Single-text embedding generation.
2. Batch embedding generation with configurable batch sizes.
3. Correct vector dimensionality (1536 dimensions).
4. Strict input-to-output ordering preservation using response index metadata.
5. Correct model ("text-embedding-3-small") and dimensions (1536) passed to the API.
6. Chunk metadata preservation when calling embed_chunks.
7. Empty and whitespace-only input handling.
8. Missing API key handling.
9. API failure and rate limit handling.
10. Detection and rejection of invalid vector dimensions.
11. Query embedding consistency with knowledge chunk embeddings.
12. Rejection of fake/zero fallback embeddings on failure.
13. Optional live API smoke test (skipped by default unless OPENAI_API_KEY is present).
"""

from __future__ import annotations

import math
import os
from unittest.mock import MagicMock

import pytest

from app.services.rag.chunking import DocumentChunk
from app.services.rag.embeddings import (
    EmbeddedChunk,
    EmbeddingAPIError,
    EmbeddingConfigurationError,
    EmbeddingDimensionError,
    EmbeddingRateLimitError,
    EmbeddingValueError,
    embed_chunks,
    generate_embedding,
    generate_embeddings,
    generate_query_embedding,
    get_embedding_client,
)

# ---------------------------------------------------------------------------
# Test Fixtures & Mock Helpers
# ---------------------------------------------------------------------------


def create_mock_openai_client(
    dimensions: int = 1536,
    reverse_order: bool = False,
    force_dim: bool = False,
):
    """Construct a mock OpenAI client returning valid vector embeddings."""
    mock_client = MagicMock()

    def fake_create(*, input, model, dimensions=dimensions, **kwargs):
        actual_dim = dimensions if not force_dim else 512
        inputs = [input] if isinstance(input, str) else list(input)
        items = []

        for idx, text in enumerate(inputs):
            # Create distinct, deterministic vector for each input
            vec = [(idx + 1) * 0.001 + (j * 0.0001) for j in range(actual_dim)]
            mock_item = MagicMock()
            mock_item.index = idx
            mock_item.embedding = vec
            items.append(mock_item)

        if reverse_order:
            # Simulate out-of-order response from async/distributed workers
            items.reverse()

        response = MagicMock()
        response.data = items
        response.model = model
        return response

    mock_client.embeddings.create.side_effect = fake_create
    return mock_client


# ---------------------------------------------------------------------------
# Core Mocked Unit Tests
# ---------------------------------------------------------------------------


def test_single_text_embedding_generation():
    """Verify single-text embedding generation returns a valid 1536-dim vector."""
    mock_client = create_mock_openai_client(dimensions=1536)
    vector = generate_embedding("Approved 2 BHK carpet area is 1,050 sq. ft.", client=mock_client)

    assert isinstance(vector, list)
    assert len(vector) == 1536
    assert all(isinstance(v, float) and not math.isnan(v) for v in vector)
    assert mock_client.embeddings.create.call_count == 1


def test_batch_embedding_generation_and_batch_sizes():
    """Verify batch processing splits inputs into batches and recombines them cleanly."""
    texts = [f"Knowledge snippet {i}" for i in range(5)]
    mock_client = create_mock_openai_client(dimensions=1536)

    # 5 items with batch_size=2 requires 3 API calls (2 + 2 + 1)
    vectors = generate_embeddings(texts, client=mock_client, batch_size=2)

    assert len(vectors) == 5
    assert mock_client.embeddings.create.call_count == 3
    for vec in vectors:
        assert len(vec) == 1536


def test_correct_vector_dimensionality():
    """Verify vector dimensionality matches exactly 1536."""
    mock_client = create_mock_openai_client(dimensions=1536)
    vector = generate_embedding("Sample text", client=mock_client)
    assert len(vector) == 1536


def test_correct_input_output_ordering_with_scrambled_response():
    """Verify that input-to-output ordering is preserved even if the API returns items out of order."""
    texts = ["First query", "Second query", "Third query"]
    # Mock client returns reversed items (index 2, 1, 0)
    mock_client = create_mock_openai_client(dimensions=1536, reverse_order=True)

    vectors = generate_embeddings(texts, client=mock_client)
    assert len(vectors) == 3

    # In our mock client, index 0 vector starts with 0.001, index 1 with 0.002, index 2 with 0.003
    assert math.isclose(vectors[0][0], 0.001, rel_tol=1e-5)
    assert math.isclose(vectors[1][0], 0.002, rel_tol=1e-5)
    assert math.isclose(vectors[2][0], 0.003, rel_tol=1e-5)


def test_correct_model_and_dimensions_passed_to_api():
    """Verify agreed model 'text-embedding-3-small' and dimensions=1536 are passed explicitly."""
    mock_client = create_mock_openai_client(dimensions=1536)
    generate_embedding("Verification text", client=mock_client)

    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["dimensions"] == 1536


def test_chunk_metadata_preservation():
    """Verify embed_chunks preserves all chunk IDs, tenant data, offsets, and source metadata."""
    chunk = DocumentChunk(
        chunk_id="chk_ag-fact-area-01",
        content="2 BHK carpet area is 1,050 sq. ft.",
        source_ref="AG-FACT-AREA-2BHK-03",
        source_version=1,
        organisation_id="org-brick-beyond",
        client_id="client-asteria-developers",
        project_id="proj-asteria-greens",
        category="fact",
        header_context="Unit Specifications > 2 BHK",
        char_start=12,
        char_end=46,
        metadata={"unit": "2 BHK", "sqft": 1050},
    )

    mock_client = create_mock_openai_client(dimensions=1536)
    embedded = embed_chunks([chunk], client=mock_client)

    assert len(embedded) == 1
    item = embedded[0]
    assert isinstance(item, EmbeddedChunk)
    assert item.chunk_id == "chk_ag-fact-area-01"
    assert item.source_ref == "AG-FACT-AREA-2BHK-03"
    assert item.source_version == 1
    assert item.organisation_id == "org-brick-beyond"
    assert item.client_id == "client-asteria-developers"
    assert item.project_id == "proj-asteria-greens"
    assert item.category == "fact"
    assert item.header_context == "Unit Specifications > 2 BHK"
    assert item.char_start == 12
    assert item.char_end == 46
    assert item.metadata["sqft"] == 1050
    assert len(item.embedding) == 1536


def test_empty_and_whitespace_input_handling():
    """Verify empty or whitespace-only inputs are rejected before sending API requests."""
    mock_client = create_mock_openai_client()

    with pytest.raises(ValueError) as exc:
        generate_embedding("", client=mock_client)
    assert "cannot be empty" in str(exc.value)

    with pytest.raises(ValueError) as exc:
        generate_embedding("    ", client=mock_client)
    assert "cannot be empty" in str(exc.value)

    # Empty list returns empty list with 0 API calls
    assert generate_embeddings([], client=mock_client) == []
    assert mock_client.embeddings.create.call_count == 0


def test_missing_api_key_handling(monkeypatch):
    """Verify that calling get_embedding_client without configured key raises EmbeddingConfigurationError."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    from app.config import settings
    monkeypatch.setattr(settings, "openai_api_key", "")

    with pytest.raises(EmbeddingConfigurationError) as exc:
        get_embedding_client()
    assert "OPENAI_API_KEY is not configured" in str(exc.value)


def test_api_failure_and_rate_limit_handling():
    """Verify that API errors and rate limits raise appropriate EmbeddingAPIError subclasses."""
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = EmbeddingRateLimitError("Rate limit exceeded")

    with pytest.raises(EmbeddingRateLimitError):
        generate_embedding("Test text", client=mock_client)

    # Generic network failure
    mock_client.embeddings.create.side_effect = ConnectionError("Connection refused")
    with pytest.raises(EmbeddingAPIError) as exc:
        generate_embedding("Test text", client=mock_client)
    assert "OpenAI embedding request failed" in str(exc.value)


def test_invalid_vector_dimensions_detected():
    """Verify that unexpected vector dimensions (e.g. 512 instead of 1536) raise EmbeddingDimensionError."""
    # Mock client incorrectly returning 512 dimensions
    mock_client = create_mock_openai_client(force_dim=True)

    with pytest.raises(EmbeddingDimensionError) as exc:
        generate_embedding("Dimension check", client=mock_client, dimensions=1536)
    assert "has 512 dimensions; expected 1536" in str(exc.value)


def test_non_finite_vector_values_detected():
    """Verify that NaN or Inf values in returned embeddings raise EmbeddingValueError."""
    mock_client = MagicMock()
    bad_vec = [float("nan")] * 1536
    mock_resp = MagicMock()
    mock_item = MagicMock(index=0, embedding=bad_vec)
    mock_resp.data = [mock_item]
    mock_client.embeddings.create.return_value = mock_resp

    with pytest.raises(EmbeddingValueError) as exc:
        generate_embedding("NaN check", client=mock_client)
    assert "contains non-finite" in str(exc.value)


def test_query_embedding_uses_identical_model_and_dimensions():
    """Verify that generate_query_embedding routes through the exact same model and dimensions."""
    mock_client = create_mock_openai_client(dimensions=1536)
    query_vector = generate_query_embedding("What is the carpet area?", client=mock_client)

    assert len(query_vector) == 1536
    call_kwargs = mock_client.embeddings.create.call_args.kwargs
    assert call_kwargs["model"] == "text-embedding-3-small"
    assert call_kwargs["dimensions"] == 1536


def test_no_fake_embeddings_returned_on_failure():
    """Verify that no fake zero-vectors or placeholder embeddings are ever returned when the API fails."""
    mock_client = MagicMock()
    mock_client.embeddings.create.side_effect = RuntimeError("Fatal API error")

    with pytest.raises(EmbeddingAPIError):
        generate_embeddings(["Snippet 1", "Snippet 2"], client=mock_client)


# ---------------------------------------------------------------------------
# Optional Live API Smoke Test
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY", "").startswith("your-"),
    reason="Live OPENAI_API_KEY not configured in environment. Skipping live API call.",
)
def test_live_openai_api_smoke_test():
    """Live smoke test that executes against OpenAI API only when a valid key is provided."""
    vector = generate_embedding("ProofLine real estate compliance test embedding.")
    assert isinstance(vector, list)
    assert len(vector) == 1536
    assert all(isinstance(x, float) and not math.isnan(x) for x in vector)
