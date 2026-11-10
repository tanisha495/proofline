# ProofLine — Antigravity Agent Handover Document

**Subsystem:** Knowledge Ingestion, Chunking, Embedding, RAG Retrieval & Evaluation Benchmark  
**Working Branch:** `dhruv/day1-data-contract`  
**Remote Repository:** `https://github.com/KrishV18/ProofLine.git`  
**Status:** Stages 1–5 fully implemented, tested (50 tests total: 49 passed, 1 live skipped), benchmarked, and ready for integration.  
**Date:** November 2026  

---

## 1. Project Purpose & Current Architecture

**ProofLine** is a pre-publication brand-governance and content assurance platform designed to prevent deceptive, contradictory, or non-compliant claims in marketing communications before they are published.

### Architecture Overview
- **Backend:** FastAPI application (`backend/app/`) with SQLAlchemy models (`backend/app/models/`) and Pydantic schemas (`backend/app/schemas/`).
- **Frontend:** Next.js application (`frontend/src/`) with App Router pages.
- **RAG Subsystem:** Located in `backend/app/services/rag/`, responsible for grounding the review engine in verifiable organizational guidelines, facts, terms, pricing, amenities, and statutory approvals.
- **Demonstration Dataset:** Fictional real estate marketing agency **Brick & Beyond** representing developer client **Asteria Developers** and residential project **Asteria Greens** (Sector 78, Gurugram, RERA Reg: `DEMO-HRERA-GGM-2026-0042`).

---

## 2. Agent Responsibility: RAG Subsystem

This workspace role encompasses:
1. Discovering, loading, validating, and normalizing structured knowledge assets.
2. Chunking long-form policies, brochures, and facts while maintaining hierarchical header context and source references.
3. Generating dense numerical vector embeddings via the official OpenAI API (`text-embedding-3-small`, 1536 dimensions).
4. Providing tenant-isolated similarity and keyword retrieval for draft claims.
5. Evaluating retrieval quality against curated benchmark datasets (`sample-data/evaluation/`).

---

## 3. Completed Stages 1–5

### Stage 1: Knowledge Loading, Validation & Normalisation
- **File:** `backend/app/services/rag/ingestion.py`
- **Capabilities:**
  - Robust directory discovery (`get_default_knowledge_dir`, `discover_knowledge_files`) using file-relative traversal and `PROOFLINE_KNOWLEDGE_DIR` overrides.
  - Safe JSON reading with syntax error handling, line/column tracking, and exclusion of test/draft folders.
  - Strict validation of IDs, source versions, approval status, ISO 8601 dates, and duplicate ID detection across files.
  - Normalisation of all 32 knowledge records into `NormalizedKnowledgeRecord` with category-tailored `searchable_text`.
- **Knowledge Sources Ingested (32 records total):**
  - `sample-data/knowledge/agency/brand-guidelines.json` (8 records)
  - `sample-data/knowledge/agency/terminology.json` (5 records)
  - `sample-data/knowledge/clients/asteria-developers/projects/asteria-greens/project-facts.json` (7 records)
  - `sample-data/knowledge/clients/asteria-developers/projects/asteria-greens/amenities.json` (6 records)
  - `sample-data/knowledge/clients/asteria-developers/projects/asteria-greens/pricing.json` (3 records)
  - `sample-data/knowledge/clients/asteria-developers/projects/asteria-greens/approvals.json` (3 records)

### Stage 2: Chunking & Token Management
- **File:** `backend/app/services/rag/chunking.py`
- **Capabilities:**
  - `DocumentChunk` model with `chunk_id`, `content`, `source_ref`, `source_version`, `header_context`, and character offsets (`char_start`, `char_end`).
  - Recursive text splitting (`split_text_with_overlap`) along natural paragraph and sentence delimiters.
  - Header-aware Markdown chunking (`chunk_markdown`) that preserves hierarchical header paths (e.g. `[Manual > 3. Financial Rules > 3.1 Prohibited Returns]`).
  - Single and batch conversion of `NormalizedKnowledgeRecord` into `DocumentChunk`.
  - Ingestion of sample document files (`sample-data/documents/*.md`).

### Stage 3: OpenAI Embedding Generation
- **File:** `backend/app/services/rag/embeddings.py`
- **Configuration:** Provider = OpenAI, Model = `text-embedding-3-small`, Dimensions = `1536`, Auth = `OPENAI_API_KEY`.
- **Capabilities:**
  - `get_embedding_client()`: Lazy credential initialization with fallback HTTP client using `httpx` (eliminating unresolved import errors if `openai` package is absent).
  - `generate_embedding(text)`: Single-text vectorization.
  - `generate_embeddings(texts, batch_size=64)`: Batch vectorization preserving 1-to-1 input ordering via OpenAI `.index` metadata.
  - `generate_query_embedding(query)`: Query vectorization using identical model and dimensions for retrieval grounding.
  - `embed_chunks(chunks)`: Pairs `DocumentChunk` with its vector to produce `EmbeddedChunk`.
  - Strict validation: Rejects non-finite values (`NaN`, `Inf`), asserts vector length is 1536, and disallows silent fake/zero-vector fallback on failures.

### Stage 4: Retrieval Engine
- **File:** `backend/app/services/rag/retrieval.py`
- **Capabilities:**
  - `compute_cosine_similarity(vec_a, vec_b)`: Pure Python, high-precision cosine similarity with finite-value and dimension validation.
  - `InMemoryVectorIndex`: In-memory vector store supporting fast similarity search with multi-level filtering:
    - Strict Multi-Tenant Isolation (`organisation_id`).
    - Agency-Level Knowledge Inheritance (agency rules automatically included for project queries).
    - Client and Project Scoping (preventing cross-project pollution).
    - Governance Status Filtering (unapproved chunks excluded by default).
    - Temporal Validity Filtering (`valid_from` and `valid_until` ISO date checks).
  - `retrieve_relevant_context()`: High-level retrieval entry point returning `list[RetrievedEvidence]` sorted by similarity score, bounded by `top_k` and `min_score`.

### Stage 5: Evaluation & Quality Benchmarking
- **File:** `backend/app/services/rag/evaluation.py`
- **Capabilities:**
  - `load_evaluation_dataset()`: Loads 12 benchmark marketing drafts (`D001` to `D012`).
  - `load_expected_findings()`: Loads 26 ground-truth expected findings.
  - `evaluate_retrieval_pipeline()`: Automates end-to-end evaluation, querying the vector index for each finding and calculating standard Information Retrieval (IR) metrics:
    - **Hit Rate @ K:** Whether the ground truth `expected_source_id` is present in top-K results.
    - **Mean Reciprocal Rank (MRR @ K):** Harmonic mean position of the true source reference ($1/\text{rank}$).
    - **Summary Table Generation:** Formats per-draft and aggregate performance into markdown tables.

---

## 4. Test Suite & Validation Status

All test suites run in the virtual environment (`backend/.venv/Scripts/python.exe -m pytest`):

| Test Suite File | Passed | Skipped | Status | Details |
| :--- | :---: | :---: | :---: | :--- |
| `backend/tests/test_finding_schema.py` | 3 | 0 | **PASSED** | Core `FindingBase` and validator tests |
| `backend/tests/test_rag_ingestion.py` | 10 | 0 | **PASSED** | File discovery, counts, validation, dates, duplicate detection |
| `backend/tests/test_rag_chunking.py` | 10 | 0 | **PASSED** | Text splitting, markdown header trees, chunk offsets |
| `backend/tests/test_rag_embeddings.py` | 13 | 1 | **PASSED** | Dimensions, ordering, batching, metadata, failure handling (1 live test skipped) |
| `backend/tests/test_rag_retrieval.py` | 9 | 0 | **PASSED** | Cosine math, tenant isolation, inheritance, governance filters, top-k |
| `backend/tests/test_rag_evaluation.py` | 7 | 0 | **PASSED** | Dataset loading, summary table, rank metrics, end-to-end pipeline benchmark |
| **Total RAG Test Suite** | **49** | **1** | **ALL GREEN** | Execution time: ~1.18s |

*Note: The live API smoke test in `test_rag_embeddings.py` is safely skipped by default to prevent unintended credit consumption.*

---

## 5. Benchmark Evaluation Results

When executed across the 12 evaluation drafts and 26 ground-truth findings:

- **Total Drafts Evaluated:** 12 (`D001`–`D012`)
- **Total Ground-Truth Queries:** 26
- **Successful Hits @ 5:** 18 / 26
- **Overall Hit Rate @ 5:** 69.2%
- **Overall Mean Reciprocal Rank (MRR @ 5):** 0.254

### Per-Draft Breakdown:
| Draft ID | Scenario | Findings | Hits | Hit Rate | MRR |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **D001** | Correct project advertisement (Clean Control Case) | 4 | 4 | 100% | 0.354 |
| **D002** | Incorrect carpet area claim (Inflates approved area) | 2 | 2 | 100% | 0.292 |
| **D003** | Incorrect advertised price (Unapproved low price) | 1 | 1 | 100% | 0.333 |
| **D004** | Incorrect possession date (Earlier handover) | 1 | 1 | 100% | 0.500 |
| **D005** | Unsupported guaranteed investment returns | 2 | 1 | 50% | 0.125 |
| **D006** | Unapproved amenity claim (Olympic pool) | 3 | 1 | 33% | 0.167 |
| **D007** | Incorrect area terminology (Super built-up) | 2 | 2 | 100% | 0.267 |
| **D008** | Scheduled possession represented as guaranteed | 2 | 1 | 50% | 0.500 |
| **D009** | Unsupported limited-inventory urgency claim | 2 | 2 | 100% | 0.200 |
| **D010** | Missing required project registration disclosure | 1 | 0 | 0% | 0.000 |
| **D011** | Multiple correct and incorrect project claims | 4 | 2 | 50% | 0.146 |
| **D012** | Unsupported rooftop helipad claim | 2 | 1 | 50% | 0.250 |

---

## 6. Cross-Team Integration Architecture

```
                      +------------------------------------------+
                      |         ProofLine Review Engine          |
                      +------------------------------------------+
                                     |             |
                1. Extract Claims    |             | 3. Provide Evidence
                                     v             v
        +-------------------------------+         +--------------------------------+
        |   Kalash (LLM Subsystem)      |         |   RAG Subsystem (Dhruv)        |
        |   - Claim extraction          |         |   - Ingestion & Chunking       |
        |   - Review prompt grounding   |<--------|   - OpenAI Embeddings (1536-d) |
        |   - Finding generation        |         |   - Vector & In-Memory Engine  |
        +-------------------------------+         +--------------------------------+
                                                            |
                                                            | 2. Persist / Query Chunks
                                                            v
                                          +--------------------------------+
                                          |   Krish (Database Subsystem)   |
                                          |   - PostgreSQL + pgvector      |
                                          |   - Tenant-isolated SQL queries|
                                          |   - Alembic migration tables   |
                                          +--------------------------------+
```

### 1. Integration with Krish (Database & Storage)
- **Vector Persistence:** `EmbeddedChunk` instances (`chunk_id`, `source_ref`, `source_version`, `organisation_id`, `embedding`) map directly to Krish's `knowledge_chunks` database table.
- **Repository Interface:** When the PostgreSQL `pgvector` migration is complete, `InMemoryVectorIndex` can be swapped with Krish's SQL vector similarity repository without changing the downstream `RetrievedEvidence` schema or `retrieve_relevant_context` signature.

### 2. Integration with Kalash (LLM Review Engine)
- **Claim Grounding:** When Kalash's review pipeline processes a marketing draft:
  ```python
  from app.services.rag.retrieval import retrieve_relevant_context

  evidence_list = retrieve_relevant_context(
      query_text=claim_text,
      organisation_id=draft.organisation_id,
      client_id=draft.client_id,
      project_id=draft.project_id,
      top_k=5,
      min_score=0.3,
  )
  ```
- **Prompt Injection:** Kalash injects `evidence_list` into the system prompt:
  ```text
  Context Evidence:
  [Source: {evidence.source_ref}] (Category: {evidence.category})
  "{evidence.content}"
  ```
- **Finding Generation:** If a claim contradicts the retrieved evidence, Kalash's LLM produces a `Finding` citing `source_ref=evidence.source_ref`, `source_version=evidence.source_version`, and assigns an appropriate severity (`blocker`, `warning`, `note`).

---

## 7. Key Configuration, Schemas & Environment Variables

### Environment Variables (`backend/app/config.py` & `.env.example`)
| Variable | Default Value | Purpose |
| :--- | :--- | :--- |
| `OPENAI_API_KEY` | `""` | Dedicated OpenAI authentication key for embeddings |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small` | Standard embedding model name |
| `OPENAI_EMBEDDING_DIMENSIONS` | `1536` | Output vector dimension |
| `PROOFLINE_KNOWLEDGE_DIR` | `None` (auto-detected) | Optional override for knowledge directory root |
| `LLM_API_KEY` / `LLM_MODEL` | `""` / `gemini-pro` | Kalash's LLM settings (kept completely separate) |

### Key Data Contracts
- `NormalizedKnowledgeRecord` (`ingestion.py`): Cleaned internal representation of approved knowledge.
- `DocumentChunk` (`chunking.py`): Sliced text passages with offsets and header hierarchy.
- `EmbeddedChunk` (`embeddings.py`): Chunk paired with its 1536-dimensional float vector.
- `RetrievedEvidence` (`retrieval.py`): Standard output passed into review prompt templates.
- `RetrievalEvaluationMetrics` (`evaluation.py`): Benchmark metrics across evaluation datasets.
