"""Retrieval evaluation and benchmarking module for the ProofLine RAG subsystem.

Responsibility:
    Responsible for measuring and benchmarking retrieval performance against curated
    ground-truth evaluation datasets (`sample-data/evaluation/`). Computes standard
    Information Retrieval (IR) metrics to validate chunking, embeddings, and retrieval.

Key Metrics:
    - Hit Rate @ K: Frequency with which the true expected source_id is present in top-K results.
    - Mean Reciprocal Rank (MRR @ K): Harmonic mean of the rank positions of expected sources.
    - Context Coverage & Precision: Validation that evidence context is present for LLM claim checking.

Integration Notes:
    - Runs against in-memory index or persistent database vector stores.
    - Operates with mock embedding clients in offline unit tests and production clients in live runs.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.services.rag.ingestion import get_default_knowledge_dir
from app.services.rag.retrieval import (
    InMemoryVectorIndex,
    RetrievedEvidence,
    get_default_vector_index,
    retrieve_relevant_context,
)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


class FindingEvaluationResult(BaseModel):
    """Detailed evaluation result for an individual ground-truth finding."""

    draft_id: str
    expected_source_id: str
    expected_result: str
    issue_category: str
    query_text: str
    retrieved_source_refs: list[str]
    hit_at_k: bool
    reciprocal_rank: float
    top_similarity: float | None = None


class DraftEvaluationSummary(BaseModel):
    """Aggregated evaluation metrics for a single marketing draft."""

    draft_id: str
    title: str
    scenario: str
    total_findings: int
    findings_with_source: int
    hits: int
    hit_rate: float
    mrr: float
    findings: list[FindingEvaluationResult] = Field(default_factory=list)


@dataclass
class RetrievalEvaluationMetrics:
    """Comprehensive benchmark metrics across the entire evaluation dataset."""

    total_drafts: int
    total_queries: int
    total_hits: int
    hit_rate_at_k: float
    mrr_at_k: float
    top_k: int
    draft_summaries: list[DraftEvaluationSummary] = field(default_factory=list)

    def summary_table(self) -> str:
        """Render a formatted markdown summary table."""
        lines = [
            f"# RAG Retrieval Benchmark Results (Top-{self.top_k})",
            "",
            f"- **Total Drafts Evaluated:** {self.total_drafts}",
            f"- **Total Queries Evaluated:** {self.total_queries}",
            f"- **Successful Hits @ {self.top_k}:** {self.total_hits} / {self.total_queries}",
            f"- **Overall Hit Rate @ {self.top_k}:** {self.hit_rate_at_k * 100:.1f}%",
            f"- **Overall Mean Reciprocal Rank (MRR @ {self.top_k}):** {self.mrr_at_k:.3f}",
            "",
            "| Draft ID | Scenario | Findings | Hits | Hit Rate | MRR |",
            "| :--- | :--- | :---: | :---: | :---: | :---: |",
        ]
        for d in self.draft_summaries:
            lines.append(
                f"| **{d.draft_id}** | {d.scenario[:45]}... | {d.findings_with_source} | {d.hits} | {d.hit_rate * 100:.0f}% | {d.mrr:.3f} |"
            )
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Dataset Discovery & Loading
# ---------------------------------------------------------------------------


def get_default_evaluation_dir() -> Path:
    """Resolve the directory containing evaluation datasets."""
    knowledge_dir = get_default_knowledge_dir()
    return knowledge_dir.parent / "evaluation"


def load_evaluation_dataset(dataset_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the 12 evaluation drafts (D001–D012)."""
    target = Path(dataset_path) if dataset_path else get_default_evaluation_dir() / "evaluation-dataset.json"
    if not target.is_file():
        raise FileNotFoundError(f"Evaluation dataset not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


def load_expected_findings(findings_path: Path | str | None = None) -> list[dict[str, Any]]:
    """Load the 26 ground-truth expected findings."""
    target = Path(findings_path) if findings_path else get_default_evaluation_dir() / "expected-findings.json"
    if not target.is_file():
        raise FileNotFoundError(f"Expected findings not found: {target}")
    return json.loads(target.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Benchmark Runner
# ---------------------------------------------------------------------------


def evaluate_retrieval_pipeline(
    vector_index: InMemoryVectorIndex | None = None,
    embedding_client: Any = None,
    top_k: int = 5,
    min_score: float = 0.0,
    dataset_path: Path | str | None = None,
    findings_path: Path | str | None = None,
) -> RetrievalEvaluationMetrics:
    """Run an automated benchmark evaluation of the retrieval engine against ground truth.

    Args:
        vector_index: Target vector index (defaults to shared index).
        embedding_client: Client for generating query embeddings.
        top_k: Ranking cutoff.
        min_score: Minimum similarity score threshold.
        dataset_path: Optional override for evaluation-dataset.json.
        findings_path: Optional override for expected-findings.json.

    Returns:
        RetrievalEvaluationMetrics containing overall and per-draft scores.
    """
    drafts = load_evaluation_dataset(dataset_path)
    all_findings = load_expected_findings(findings_path)
    index = vector_index if vector_index is not None else get_default_vector_index()

    # Group expected findings by draft_id
    findings_by_draft: dict[str, list[dict[str, Any]]] = {}
    for finding in all_findings:
        did = finding["draft_id"]
        findings_by_draft.setdefault(did, []).append(finding)

    draft_summaries: list[DraftEvaluationSummary] = []
    total_evaluated_queries = 0
    total_hits = 0
    accumulated_rr = 0.0

    for draft in drafts:
        did = draft["draft_id"]
        org_id = draft.get("organisation_id", "org-brick-beyond")
        client_id = draft.get("client_id")
        project_id = draft.get("project_id")
        title = draft.get("title", "")
        scenario = draft.get("scenario", "")

        draft_findings = findings_by_draft.get(did, [])
        finding_eval_results: list[FindingEvaluationResult] = []

        draft_hits = 0
        draft_rr_sum = 0.0
        query_count = 0

        for f in draft_findings:
            expected_src = f.get("expected_source_id")
            if not expected_src:
                continue  # Skip findings without specific source ID (e.g. general omissions)

            query_count += 1
            affected_text = f.get("affected_text")
            query_text = affected_text if affected_text else draft.get("content", title)

            evidence_items: list[RetrievedEvidence] = retrieve_relevant_context(
                query_text=query_text,
                organisation_id=org_id,
                client_id=client_id,
                project_id=project_id,
                top_k=top_k,
                min_score=min_score,
                vector_index=index,
                embedding_client=embedding_client,
                include_agency_knowledge=True,
                filter_unapproved=False,  # Include unapproved so negative list citations can be evaluated
            )

            retrieved_refs = [e.source_ref for e in evidence_items]
            top_sim = evidence_items[0].similarity_score if evidence_items else None

            # Calculate Hit and Reciprocal Rank
            hit = expected_src in retrieved_refs
            rr = 0.0
            if hit:
                rank = retrieved_refs.index(expected_src) + 1
                rr = 1.0 / rank
                draft_hits += 1

            draft_rr_sum += rr

            finding_eval_results.append(
                FindingEvaluationResult(
                    draft_id=did,
                    expected_source_id=expected_src,
                    expected_result=f.get("expected_result", "supported"),
                    issue_category=f.get("issue_category", "general"),
                    query_text=query_text,
                    retrieved_source_refs=retrieved_refs,
                    hit_at_k=hit,
                    reciprocal_rank=rr,
                    top_similarity=top_sim,
                )
            )

        total_evaluated_queries += query_count
        total_hits += draft_hits
        accumulated_rr += draft_rr_sum

        hit_rate = (draft_hits / query_count) if query_count > 0 else 1.0
        mrr = (draft_rr_sum / query_count) if query_count > 0 else 1.0

        draft_summaries.append(
            DraftEvaluationSummary(
                draft_id=did,
                title=title,
                scenario=scenario,
                total_findings=len(draft_findings),
                findings_with_source=query_count,
                hits=draft_hits,
                hit_rate=hit_rate,
                mrr=mrr,
                findings=finding_eval_results,
            )
        )

    overall_hit_rate = (total_hits / total_evaluated_queries) if total_evaluated_queries > 0 else 0.0
    overall_mrr = (accumulated_rr / total_evaluated_queries) if total_evaluated_queries > 0 else 0.0

    return RetrievalEvaluationMetrics(
        total_drafts=len(drafts),
        total_queries=total_evaluated_queries,
        total_hits=total_hits,
        hit_rate_at_k=overall_hit_rate,
        mrr_at_k=overall_mrr,
        top_k=top_k,
        draft_summaries=draft_summaries,
    )
