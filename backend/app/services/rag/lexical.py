"""Lexical fallback search over Dhruv's RAG knowledge chunks when OpenAI embeddings are not configured."""
from __future__ import annotations

import re
from typing import Any, Dict, List

from app.config import settings
from app.services.rag.chunking import chunk_normalized_records
from app.services.rag.ingestion import load_and_process_knowledge


def search_rag_knowledge(query: str, top_k: int = 5) -> Dict[str, Any]:
    """Search ingested RAG knowledge records via vector search (if OpenAI key set) or lexical fallback."""
    records, _ = load_and_process_knowledge()
    chunks = chunk_normalized_records(records)

    # Try vector search if OPENAI_API_KEY is configured
    if getattr(settings, "openai_api_key", "").strip():
        try:
            from app.services.rag.embeddings import embed_chunks
            from app.services.rag.retrieval import InMemoryVectorIndex, retrieve_relevant_context

            embedded = embed_chunks(chunks)
            idx = InMemoryVectorIndex()
            idx.add_chunks(embedded)
            org_id = chunks[0].organisation_id if chunks else "default"
            results = retrieve_relevant_context(
                query_text=query,
                organisation_id=org_id,
                top_k=top_k,
                vector_index=idx,
            )
            return {
                "mode": "vector_openai",
                "total_chunks_indexed": len(chunks),
                "results": [r.model_dump() for r in results],
            }
        except Exception:
            pass

    # Deterministic token-overlap fallback
    query_tokens = {tok for tok in re.findall(r"[a-z0-9]+", query.lower()) if len(tok) > 2}
    scored: List[tuple[float, Any]] = []

    for chunk in chunks:
        if chunk.metadata.get("approval_status", "approved") != "approved":
            continue
        chunk_tokens = set(re.findall(r"[a-z0-9]+", chunk.content.lower()))
        if not query_tokens or not chunk_tokens:
            continue
        overlap = len(query_tokens & chunk_tokens)
        if overlap > 0:
            score = round(overlap / len(query_tokens), 4)
            scored.append((score, chunk))

    scored.sort(key=lambda item: item[0], reverse=True)
    return {
        "mode": "lexical_fallback",
        "total_chunks_indexed": len(chunks),
        "results": [
            {
                "chunk_id": chunk.chunk_id,
                "source_ref": chunk.source_ref,
                "source_version": chunk.source_version,
                "category": chunk.category,
                "content": chunk.content,
                "similarity_score": score,
                "client_id": chunk.client_id,
                "project_id": chunk.project_id,
            }
            for score, chunk in scored[:top_k]
        ],
    }
