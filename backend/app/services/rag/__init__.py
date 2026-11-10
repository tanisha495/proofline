"""RAG (Retrieval-Augmented Generation) Subsystem for ProofLine.

Responsibility:
    This package serves as the core foundation for knowledge ingestion,
    document chunking, semantic embedding generation, vector/keyword retrieval,
    and retrieval evaluation for brand governance and review checking.

Submodules:
    - document_parser: Parses unstructured/semi-structured brand guidelines and knowledge files.
    - chunking: Splits parsed documents into semantically coherent, bounded chunks.
    - embeddings: Handles embedding model client integration for generating vector embeddings.
    - ingestion: Orchestrates parsing, chunking, embedding, and indexing into the storage layer.
    - retrieval: Searches and retrieves relevant guideline/fact context to ground LLM reviews.
    - evaluation: Evaluates retrieval quality (precision, recall, MRR) against ground truth datasets.

Note:
    All components in this package are currently foundational scaffolds and provisional
    interfaces. Core implementations depend on finalized contracts with Krish (Database)
    and Kalash (LLM Review Subsystem).
"""

from app.services.rag.evaluation import (
    DraftEvaluationSummary,
    FindingEvaluationResult,
    RetrievalEvaluationMetrics,
    evaluate_retrieval_pipeline,
    load_evaluation_dataset,
    load_expected_findings,
)
from app.services.rag.retrieval import (
    InMemoryVectorIndex,
    RetrievedEvidence,
    compute_cosine_similarity,
    retrieve_relevant_context,
)

__all__ = [
    "DraftEvaluationSummary",
    "FindingEvaluationResult",
    "InMemoryVectorIndex",
    "RetrievalEvaluationMetrics",
    "RetrievedEvidence",
    "chunking",
    "compute_cosine_similarity",
    "document_parser",
    "embeddings",
    "evaluate_retrieval_pipeline",
    "evaluation",
    "ingestion",
    "load_evaluation_dataset",
    "load_expected_findings",
    "retrieval",
    "retrieve_relevant_context",
]

