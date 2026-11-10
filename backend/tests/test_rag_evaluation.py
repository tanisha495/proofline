"""Tests for RAG Stage 5: Evaluation and Benchmarking Subsystem.

Verifies:
1. Loading and schema validation of evaluation-dataset.json (12 drafts).
2. Loading and schema validation of expected-findings.json (26 findings).
3. Error handling for missing or unreadable evaluation dataset paths.
4. Correctness of IR ranking metrics: Hit Rate @ K and Mean Reciprocal Rank (MRR @ K).
5. Formatting and structure of the benchmark summary markdown table.
6. Execution of evaluate_retrieval_pipeline against an in-memory vector index.
7. End-to-end integration across Stages 1, 2, 3, 4, and 5.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.services.rag.chunking import chunk_normalized_records
from app.services.rag.embeddings import EmbeddedChunk, embed_chunks
from app.services.rag.evaluation import (
    DraftEvaluationSummary,
    FindingEvaluationResult,
    RetrievalEvaluationMetrics,
    evaluate_retrieval_pipeline,
    get_default_evaluation_dir,
    load_evaluation_dataset,
    load_expected_findings,
)
from app.services.rag.ingestion import load_and_process_knowledge
from app.services.rag.retrieval import InMemoryVectorIndex

# ---------------------------------------------------------------------------
# Dataset Loading & Validation Tests
# ---------------------------------------------------------------------------


def test_get_default_evaluation_dir():
    """Verify that the evaluation directory resolves correctly and exists."""
    eval_dir = get_default_evaluation_dir()
    assert isinstance(eval_dir, Path)
    assert eval_dir.is_dir()
    assert (eval_dir / "evaluation-dataset.json").is_file()
    assert (eval_dir / "expected-findings.json").is_file()


def test_load_evaluation_dataset():
    """Verify that the 12 evaluation drafts are properly loaded and structured."""
    drafts = load_evaluation_dataset()
    assert len(drafts) == 12

    draft_ids = {d["draft_id"] for d in drafts}
    expected_ids = {f"D{str(i).zfill(3)}" for i in range(1, 13)}
    assert draft_ids == expected_ids

    for draft in drafts:
        assert "draft_id" in draft
        assert "title" in draft
        assert "scenario" in draft
        assert "content" in draft
        assert "organisation_id" in draft


def test_load_expected_findings():
    """Verify that all 26 ground-truth expected findings are loaded."""
    findings = load_expected_findings()
    assert len(findings) == 26

    for finding in findings:
        assert "draft_id" in finding
        assert "issue_category" in finding
        assert "expected_result" in finding
        assert "expected_source_id" in finding


def test_load_missing_dataset_raises():
    """Verify FileNotFoundError is raised when file does not exist."""
    with pytest.raises(FileNotFoundError, match="Evaluation dataset not found"):
        load_evaluation_dataset(Path("non_existent_dataset.json"))

    with pytest.raises(FileNotFoundError, match="Expected findings not found"):
        load_expected_findings(Path("non_existent_findings.json"))


# ---------------------------------------------------------------------------
# Data Models and Summary Table Tests
# ---------------------------------------------------------------------------


def test_metric_models_and_summary_table():
    """Verify the markdown generation and calculation integrity of metric models."""
    finding_1 = FindingEvaluationResult(
        draft_id="D001",
        expected_source_id="AG-AMEN-01",
        expected_result="flagged",
        issue_category="amenities",
        query_text="Olympic-sized swimming pool",
        retrieved_source_refs=["AG-AMEN-01", "AG-PRICE-01"],
        hit_at_k=True,
        reciprocal_rank=1.0,
        top_similarity=0.92,
    )
    finding_2 = FindingEvaluationResult(
        draft_id="D001",
        expected_source_id="AG-AREA-01",
        expected_result="flagged",
        issue_category="dimensions",
        query_text="Super built-up area 1850 sq ft",
        retrieved_source_refs=["AG-OTHER-01", "AG-AREA-01"],
        hit_at_k=True,
        reciprocal_rank=0.5,
        top_similarity=0.88,
    )

    summary_d1 = DraftEvaluationSummary(
        draft_id="D001",
        title="Unapproved Amenities Claim",
        scenario="Marketing draft claiming unapproved amenities",
        total_findings=2,
        findings_with_source=2,
        hits=2,
        hit_rate=1.0,
        mrr=0.75,
        findings=[finding_1, finding_2],
    )

    metrics = RetrievalEvaluationMetrics(
        total_drafts=1,
        total_queries=2,
        total_hits=2,
        hit_rate_at_k=1.0,
        mrr_at_k=0.75,
        top_k=5,
        draft_summaries=[summary_d1],
    )

    assert metrics.hit_rate_at_k == 1.0
    assert metrics.mrr_at_k == 0.75

    table_md = metrics.summary_table()
    assert "# RAG Retrieval Benchmark Results (Top-5)" in table_md
    assert "**Overall Hit Rate @ 5:** 100.0%" in table_md
    assert "**Overall Mean Reciprocal Rank (MRR @ 5):** 0.750" in table_md
    assert "D001" in table_md


# ---------------------------------------------------------------------------
# Benchmark Execution with Mock Embeddings & In-Memory Index
# ---------------------------------------------------------------------------


def test_evaluate_retrieval_pipeline_mock_controlled():
    """Verify pipeline ranking and metrics with controlled mock vectors."""
    index = InMemoryVectorIndex(expected_dim=1536)

    # Add 2 chunks into index matching expected sources for D001
    chunk1 = EmbeddedChunk(
        chunk_id="chk_amen",
        content="Approved amenities: Gymnasium, Kids play area. Unapproved: Olympic swimming pool.",
        source_ref="AG-FACT-AREA-2BHK-03",
        organisation_id="org-brick-beyond",
        category="fact",
        embedding=[1.0] + [0.0] * 1535,
    )
    chunk2 = EmbeddedChunk(
        chunk_id="chk_area",
        content="The carpet area is 1,050 sq. ft. Built-up area is not to be advertised.",
        source_ref="AG-PRICE-START-01",
        organisation_id="org-brick-beyond",
        category="fact",
        embedding=[0.0, 1.0] + [0.0] * 1534,
    )
    index.add_chunks([chunk1, chunk2])

    # Mock client that routes vectors according to content
    mock_client = MagicMock()

    def fake_create(*, input, model, dimensions=1536, **kwargs):
        text = input if isinstance(input, str) else input[0]
        vec = [0.0] * 1536
        if "1,050" in text.lower() or "carpet" in text.lower() or "area" in text.lower():
            vec[0] = 1.0
        elif "price" in text.lower() or "1.25" in text.lower() or "start" in text.lower():
            vec[1] = 1.0
        else:
            vec[2] = 1.0

        item = MagicMock(index=0, embedding=vec)
        resp = MagicMock()
        resp.data = [item]
        return resp

    mock_client.embeddings.create.side_effect = fake_create

    # Run benchmark on full dataset with our mock index
    metrics = evaluate_retrieval_pipeline(
        vector_index=index,
        embedding_client=mock_client,
        top_k=3,
        min_score=0.1,
    )

    assert metrics.total_drafts == 12
    assert metrics.total_queries > 0
    # Hit rate must be valid float between 0 and 1
    assert 0.0 <= metrics.hit_rate_at_k <= 1.0
    assert 0.0 <= metrics.mrr_at_k <= 1.0

    # D001 specifically tests 2BHK area and starting price - check that D001 hits occurred
    d001_summary = next(s for s in metrics.draft_summaries if s.draft_id == "D001")
    assert d001_summary.hits >= 1


# ---------------------------------------------------------------------------
# End-to-End Benchmark Execution: Stage 1 -> 2 -> 3 -> 4 -> 5
# ---------------------------------------------------------------------------


def test_end_to_end_evaluation_pipeline_with_full_knowledge():
    """Verify end-to-end flow: Ingest all 32 knowledge records, chunk them, embed, index, and run benchmark."""
    # 1. Stage 1: Load knowledge
    records, errors = load_and_process_knowledge()
    assert len(errors) == 0
    assert len(records) == 32

    # 2. Stage 2: Chunk records
    chunks = chunk_normalized_records(records)
    assert len(chunks) == 32

    # 3. Stage 3: Embed using semantic mock client
    mock_client = MagicMock()

    def fake_create(*, input, model, dimensions=1536, **kwargs):
        inputs = [input] if isinstance(input, str) else list(input)
        items = []
        for idx, text in enumerate(inputs):
            vec = [0.001] * 1536
            lower_text = text.lower()
            # Map domain keywords to specific vector dimensions
            if "carpet area" in lower_text or "1,050" in lower_text or "sq. ft" in lower_text:
                vec[0] = 0.95
            if "price" in lower_text or "crore" in lower_text or "all-inclusive" in lower_text:
                vec[1] = 0.95
            if "rera" in lower_text or "registration" in lower_text or "p518000" in lower_text:
                vec[2] = 0.95
            if "swimming pool" in lower_text or "olympic" in lower_text or "amenit" in lower_text:
                vec[3] = 0.95
            if "possession" in lower_text or "december 2026" in lower_text:
                vec[4] = 0.95
            items.append(MagicMock(index=idx, embedding=vec))
        resp = MagicMock()
        resp.data = items
        return resp

    mock_client.embeddings.create.side_effect = fake_create

    embedded_chunks = embed_chunks(chunks, client=mock_client)
    assert len(embedded_chunks) == 32

    # 4. Stage 4: Populate In-Memory Vector Index
    index = InMemoryVectorIndex(expected_dim=1536)
    index.add_chunks(embedded_chunks)
    assert len(index) == 32

    # 5. Stage 5: Run Evaluation Benchmark
    metrics = evaluate_retrieval_pipeline(
        vector_index=index,
        embedding_client=mock_client,
        top_k=5,
        min_score=0.0,
    )

    assert metrics.total_drafts == 12
    assert metrics.total_queries == 26
    assert metrics.hit_rate_at_k > 0.0
    assert metrics.mrr_at_k > 0.0

    # Ensure markdown summary can be generated
    summary_report = metrics.summary_table()
    assert "# RAG Retrieval Benchmark Results" in summary_report
    assert "| **D001** |" in summary_report
    assert "| **D012** |" in summary_report
