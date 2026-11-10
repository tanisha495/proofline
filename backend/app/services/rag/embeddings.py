"""OpenAI Embedding generation module for the ProofLine RAG subsystem.

Responsibility:
    Responsible for converting normalized knowledge chunks (Stage 2) and draft-review queries
    into dense numerical vector embeddings using the official OpenAI Embeddings API.

Technical Configuration:
    - Provider: OpenAI
    - Default Model: text-embedding-3-small
    - Default Dimensions: 1536
    - Authentication: Separate OPENAI_API_KEY (isolated from LLM configurations)
    - Output: Python lists of floating-point numbers

Integration Notes:
    - Lazy client initialization ensures importing this module never requires an API key.
    - Credentials are never logged or exposed.
    - Reusable query embedding function ensures future search queries use identical model,
      dimensions, and preprocessing conventions as ingested knowledge chunks.
    - Zero fake/zero vector fallback on failure; errors are raised explicitly.
"""

from __future__ import annotations

import importlib
import math
import os
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from pydantic import BaseModel, Field

from app.config import settings
from app.services.rag.chunking import DocumentChunk

# Dynamic resolution of official OpenAI SDK to avoid unresolved static import warnings
OfficialOpenAI = None
_HAS_OPENAI_SDK = False

try:
    _openai_module = importlib.import_module("openai")
    OfficialOpenAI = getattr(_openai_module, "OpenAI", None)
    _HAS_OPENAI_SDK = OfficialOpenAI is not None
except ImportError:
    pass


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


class EmbeddingConfigurationError(Exception):
    """Raised when required embedding configuration or credentials are missing."""


class EmbeddingAPIError(Exception):
    """Raised when the OpenAI embedding API returns an error or fails."""


class EmbeddingRateLimitError(EmbeddingAPIError):
    """Raised when the OpenAI API rate limit (HTTP 429) is encountered."""


class EmbeddingDimensionError(ValueError):
    """Raised when an embedding vector does not match the configured dimensionality."""


class EmbeddingValueError(ValueError):
    """Raised when an embedding contains non-finite numerical values (NaN, Inf)."""


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class EmbeddedChunk(BaseModel):
    """A DocumentChunk paired with its dense vector embedding."""

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
    embedding: list[float]

    model_config = {"from_attributes": True}

    @classmethod
    def from_chunk(cls, chunk: DocumentChunk, embedding: list[float]) -> EmbeddedChunk:
        """Construct an EmbeddedChunk from a DocumentChunk and its vector embedding."""
        return cls(
            chunk_id=chunk.chunk_id,
            content=chunk.content,
            source_ref=chunk.source_ref,
            source_version=chunk.source_version,
            organisation_id=chunk.organisation_id,
            client_id=chunk.client_id,
            project_id=chunk.project_id,
            category=chunk.category,
            header_context=chunk.header_context,
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            metadata=dict(chunk.metadata),
            embedding=embedding,
        )


# ---------------------------------------------------------------------------
# Fallback OpenAI HTTP Client (Matches Official SDK Interface)
# ---------------------------------------------------------------------------


@dataclass
class _EmbeddingItem:
    index: int
    embedding: list[float]
    object: str = "embedding"


@dataclass
class _EmbeddingUsage:
    prompt_tokens: int
    total_tokens: int


@dataclass
class _CreateEmbeddingResponse:
    data: list[_EmbeddingItem]
    model: str
    usage: _EmbeddingUsage


class _EmbeddingsResource:
    """Implements client.embeddings.create() conforming to the official OpenAI SDK."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")

    def create(
        self,
        *,
        input: str | list[str],
        model: str,
        dimensions: int | None = None,
        **kwargs: Any,
    ) -> _CreateEmbeddingResponse:
        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": model,
            "input": input,
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions

        try:
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(url, headers=headers, json=payload)
        except httpx.RequestError as exc:
            raise EmbeddingAPIError(f"OpenAI embedding network request failed: {exc}") from exc

        if resp.status_code == 401:
            raise EmbeddingAPIError("OpenAI authentication failed (HTTP 401): Invalid or revoked API key.")
        if resp.status_code == 429:
            raise EmbeddingRateLimitError("OpenAI API rate limit exceeded (HTTP 429).")
        if not resp.is_success:
            err_msg = resp.text
            try:
                err_json = resp.json()
                if isinstance(err_json, dict) and "error" in err_json:
                    err_info = err_json["error"]
                    if isinstance(err_info, dict) and "message" in err_info:
                        err_msg = str(err_info["message"])
            except (ValueError, KeyError):
                pass
            raise EmbeddingAPIError(f"OpenAI embedding API error (HTTP {resp.status_code}): {err_msg}")

        body = resp.json()
        data_items = [
            _EmbeddingItem(index=item["index"], embedding=item["embedding"])
            for item in body.get("data", [])
        ]
        usage_data = body.get("usage", {})
        usage = _EmbeddingUsage(
            prompt_tokens=usage_data.get("prompt_tokens", 0),
            total_tokens=usage_data.get("total_tokens", 0),
        )
        return _CreateEmbeddingResponse(data=data_items, model=body.get("model", model), usage=usage)


class _OpenAIEmbeddingsClient:
    """Lightweight HTTP client mirroring the official OpenAI client for embeddings."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.embeddings = _EmbeddingsResource(api_key=api_key, base_url=base_url)


# ---------------------------------------------------------------------------
# Client Factory & Settings
# ---------------------------------------------------------------------------


def get_embedding_client(api_key: str | None = None) -> Any:
    """Lazily construct and return an OpenAI embedding client.

    Resolution Order:
    1. Explicit `api_key` argument.
    2. `settings.openai_api_key`.
    3. `os.environ["OPENAI_API_KEY"]`.

    Raises:
        EmbeddingConfigurationError: If no valid API key is configured.
    """
    resolved_key = (
        api_key
        or getattr(settings, "openai_api_key", None)
        or os.environ.get("OPENAI_API_KEY")
    )

    if not resolved_key or not resolved_key.strip():
        raise EmbeddingConfigurationError(
            "OPENAI_API_KEY is not configured. Please set OPENAI_API_KEY in your environment or .env file."
        )

    clean_key = resolved_key.strip()

    if _HAS_OPENAI_SDK and OfficialOpenAI is not None:
        return OfficialOpenAI(api_key=clean_key)
    return _OpenAIEmbeddingsClient(api_key=clean_key)


def get_default_model() -> str:
    """Retrieve the configured default embedding model name."""
    return getattr(settings, "openai_embedding_model", None) or os.environ.get(
        "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
    )


def get_default_dimensions() -> int:
    """Retrieve the configured default embedding dimensionality."""
    dim = getattr(settings, "openai_embedding_dimensions", None)
    if dim is None:
        dim = os.environ.get("OPENAI_EMBEDDING_DIMENSIONS", "1536")
    return int(dim)


# ---------------------------------------------------------------------------
# Validation Helpers
# ---------------------------------------------------------------------------


def _validate_vector(vector: list[float], expected_dim: int, index: int) -> None:
    """Validate that an embedding vector has correct length and finite numerical values."""
    if len(vector) != expected_dim:
        raise EmbeddingDimensionError(
            f"Embedding vector at index {index} has {len(vector)} dimensions; expected {expected_dim}."
        )
    for val in vector:
        if not isinstance(val, (int, float)) or math.isnan(val) or math.isinf(val):
            raise EmbeddingValueError(
                f"Embedding vector at index {index} contains non-finite or non-numeric value: {val}"
            )


# ---------------------------------------------------------------------------
# Core Embedding Generation
# ---------------------------------------------------------------------------


def generate_embedding(
    text: str,
    client: Any = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """Generate a numerical vector embedding for a single text input.

    Args:
        text: Input text string (must not be empty or whitespace-only).
        client: Optional pre-configured OpenAI client. If None, `get_embedding_client()` is called.
        model: Target embedding model (defaults to text-embedding-3-small).
        dimensions: Target dimensions (defaults to 1536).

    Returns:
        List of 1536 floating-point numbers.

    Raises:
        ValueError: If input text is empty or whitespace-only.
        EmbeddingConfigurationError: If API credentials are not configured.
        EmbeddingAPIError: If the API request fails.
        EmbeddingDimensionError: If returned vector dimension mismatches.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Input text cannot be empty or whitespace-only for embedding generation.")

    results = generate_embeddings(
        texts=[text],
        client=client,
        model=model,
        dimensions=dimensions,
        batch_size=1,
    )
    return results[0]


def generate_embeddings(
    texts: Sequence[str],
    client: Any = None,
    model: str | None = None,
    dimensions: int | None = None,
    batch_size: int = 64,
) -> list[list[float]]:
    """Generate numerical vector embeddings for a sequence of text inputs in batches.

    Guarantees strict input-to-output ordering preservation using response index metadata.

    Args:
        texts: Sequence of text strings to embed.
        client: Optional pre-configured OpenAI client.
        model: Target embedding model.
        dimensions: Target dimensions.
        batch_size: Maximum items per API request batch.

    Returns:
        List of embedding vectors corresponding 1-to-1 with input texts.

    Raises:
        ValueError: If any text in the sequence is empty or whitespace-only.
        EmbeddingConfigurationError: If API credentials are not configured.
        EmbeddingAPIError: If the API request fails.
        EmbeddingDimensionError: If any returned vector dimension is incorrect.
    """
    if not texts:
        return []

    # Validate all inputs upfront before sending any API requests
    for i, t in enumerate(texts):
        if not isinstance(t, str) or not t.strip():
            raise ValueError(f"Input text at index {i} is empty or whitespace-only.")

    active_client = client or get_embedding_client()
    target_model = model or get_default_model()
    target_dim = dimensions or get_default_dimensions()

    all_embeddings: list[list[float]] = [[] for _ in range(len(texts))]

    # Process in batches
    for batch_start in range(0, len(texts), batch_size):
        batch_slice = list(texts[batch_start : batch_start + batch_size])

        try:
            response = active_client.embeddings.create(
                input=batch_slice,
                model=target_model,
                dimensions=target_dim,
            )
        except Exception as exc:
            if isinstance(exc, (EmbeddingAPIError, EmbeddingConfigurationError, ValueError)):
                raise
            raise EmbeddingAPIError(f"OpenAI embedding request failed: {exc}") from exc

        if not hasattr(response, "data") or not response.data:
            raise EmbeddingAPIError("OpenAI API returned an empty or malformed embedding response.")

        # Preserve ordering by mapping response.data item.index back to original list
        for item in response.data:
            global_idx = batch_start + item.index
            vec = list(item.embedding)
            _validate_vector(vec, target_dim, global_idx)
            all_embeddings[global_idx] = vec

    return all_embeddings


def generate_query_embedding(
    query: str,
    client: Any = None,
    model: str | None = None,
    dimensions: int | None = None,
) -> list[float]:
    """Generate a vector embedding for a search or draft claim query.

    Uses identical model, dimensions, and client pipeline as ingested knowledge chunks.

    Args:
        query: Search string or draft excerpt.
        client: Optional pre-configured OpenAI client.
        model: Optional model override.
        dimensions: Optional dimensions override.

    Returns:
        Vector embedding as a list of 1536 floats.
    """
    return generate_embedding(
        text=query,
        client=client,
        model=model,
        dimensions=dimensions,
    )


def embed_chunks(
    chunks: Sequence[DocumentChunk],
    client: Any = None,
    model: str | None = None,
    dimensions: int | None = None,
    batch_size: int = 64,
) -> list[EmbeddedChunk]:
    """Generate vector embeddings for a collection of DocumentChunks.

    Preserves all chunk metadata, identifiers, offsets, and source references,
    pairing each chunk with its 1536-dimensional vector embedding.

    Args:
        chunks: Sequence of DocumentChunk instances (from Stage 2 chunking).
        client: Optional pre-configured OpenAI client.
        model: Target model name.
        dimensions: Target dimensions.
        batch_size: Maximum batch size per API call.

    Returns:
        List of EmbeddedChunk instances in identical order to input chunks.
    """
    if not chunks:
        return []

    texts = [chunk.content for chunk in chunks]
    vectors = generate_embeddings(
        texts=texts,
        client=client,
        model=model,
        dimensions=dimensions,
        batch_size=batch_size,
    )

    embedded_chunks: list[EmbeddedChunk] = []
    for chunk, vec in zip(chunks, vectors, strict=True):
        embedded_chunks.append(EmbeddedChunk.from_chunk(chunk, vec))

    return embedded_chunks
