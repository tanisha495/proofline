# ProofLine RAG Subsystem Architecture

## 1. Executive Summary & Purpose

The **ProofLine RAG (Retrieval-Augmented Generation) Subsystem** provides semantic and lexical retrieval capabilities to ground the pre-publication brand-governance review engine in verifiable organisational truth.

Instead of relying solely on the LLM's parametric memory, the review engine uses this RAG subsystem to retrieve verified brand guidelines, official facts, and approved terminology for any uploaded draft or claim under review.

> **Status Notice**: The RAG subsystem is currently in the **foundation / scaffolding phase**. The folder structure, modules, and provisional interfaces are defined, but actual ingestion, embedding, vector storage, and retrieval logic are planned and pending cross-team interface finalisation.

---

## 2. Core Responsibilities

The RAG subsystem (`backend/app/services/rag/`) is organized into dedicated functional modules:

| Module | File | Responsibility | Current Status |
| :--- | :--- | :--- | :--- |
| **Package Init** | `rag/__init__.py` | Package namespace exports and subsystem overview | Scaffolded |
| **Document Parser** | `rag/document_parser.py` | Extracts text and structural metadata from PDF, DOCX, and text policy files | Provisional Scaffold |
| **Chunking** | `rag/chunking.py` | Splits documents into bounded, semantically coherent passages preserving source IDs | Provisional Scaffold |
| **Embeddings** | `rag/embeddings.py` | Integrates with embedding model client to produce vector representations | Provisional Scaffold |
| **Ingestion** | `rag/ingestion.py` | Orchestrates the end-to-end ingestion pipeline (parse -> chunk -> embed -> store) | Provisional Scaffold |
| **Retrieval** | `rag/retrieval.py` | Executes semantic/hybrid search to retrieve top-k grounding evidence for drafts | Provisional Scaffold |
| **Evaluation** | `rag/evaluation.py` | Benchmarks retrieval quality (Hit Rate@K, MRR, Precision/Recall) against golden datasets | Provisional Scaffold |

---

## 3. Subsystem Lifecycle & Workflows

### 3.1 Knowledge Ingestion Workflow (Planned)

1. **Source Document Receipt**: An administrator uploads a brand guideline document (e.g., PDF or DOCX) or submits structured guidelines/facts via `/sources` API routes.
2. **Document Parsing (`document_parser.py`)**: PyMuPDF or python-docx extracts raw text along with document hierarchy (headings, bullet points, table cells).
3. **Chunking (`chunking.py`)**: Text is divided into bounded chunks (e.g., 300–500 tokens with 50-token overlap). Every chunk retains essential metadata:
   - `source_ref` (e.g., `TONE-01`, `FACT-03`, `TERM-05`)
   - `source_version` (integer version tracking document changes)
   - `organisation_id` (enforcing multi-tenant isolation)
4. **Embedding Generation (`embeddings.py`)**: Dense vector embeddings are generated for each chunk.
5. **Persistence (`ingestion.py`)**: Vector embeddings, chunk texts, and metadata are persisted in the database subsystem.
6. **Audit Logging**: An audit entry is recorded via `app.core.audit.log_action` recording the ingestion event.

### 3.2 Chunking and Embedding Generation Strategy (Planned)

- **Semantic & Header-Aware Chunking**: Brand rulebooks are structured by categories (e.g., *Health Claims*, *Tone of Voice*, *Trademark Usage*). Chunks must not cross major rule boundaries to ensure each chunk represents an atomic, citable policy.
- **Traceability Metadata**: Downstream findings require an exact source reference (`FindingBase.source_ref`, non-empty) and `source_version`. Each chunk carries these fields forward.
- **Embedding Provider**: Embeddings will align with the project's LLM configuration in `app.config.Settings` (supporting `mock_ai=True` for local offline testing).

---

## 4. Cross-Subsystem Integrations

```
  +-------------------------------------------------------------+
  |                   ProofLine Review Pipeline                 |
  +-------------------------------------------------------------+
                                 |
                                 v
     [Draft Text / Claims]                [Evaluation Datasets]
               |                                    |
               v                                    v
  +--------------------------+             +-------------------+
  |   rag/retrieval.py       |             | rag/evaluation.py |
  +--------------------------+             +-------------------+
        |              ^
        | Query        | Top-K
        v              | Evidence
  +--------------------------+             +-----------------------+
  | Database Subsystem       |             | LLM Review Subsystem  |
  | (Krish's Implementation) |             | (Kalash's Impl)       |
  | - PostgreSQL / pgvector  |             | - Prompt Assembly     |
  | - Tenant Isolation       |             | - Claim Verification  |
  | - Sources & Chunks Table |             | - Finding Generation  |
  +--------------------------+             +-----------------------+
```

### 4.1 Communication with Krish's Database Subsystem

- **Multi-Tenant Security**: Every query executed by `retrieval.retrieve_relevant_context` must include `organisation_id` to prevent cross-tenant data leakage.
- **Storage Layer**: Krish's database layer will manage the persistent tables for chunks and vector indexes (e.g., PostgreSQL with `pgvector` or relational source tables).
- **Session Management**: RAG database operations will accept standard SQLAlchemy `Session` instances from `app.db.get_db`.

### 4.2 Passing Evidence to Kalash's LLM Subsystem

- **Structured Evidence Contract**: When the review engine analyzes a draft version, `retrieval.py` provides `list[RetrievedEvidence]`.
- **Evidence Structure**:
  ```python
  @dataclass
  class RetrievedEvidence:
      chunk_id: str
      source_ref: str          # Matches Finding.source_ref (e.g., "TONE-01")
      source_version: int      # Matches Finding.source_version
      content: str             # The exact policy or fact statement
      similarity_score: float  # Confidence/similarity metric
      metadata: dict           # Category, expiration dates, etc.
  ```
- **Context Injection**: Kalash's LLM prompt templates incorporate this structured evidence into the system context. The LLM can then quote rules, identify discrepancies, and construct compliant `Finding` objects (`quoted_text`, `start`, `end`, `severity`, `source_ref`, `suggestion`).

---

## 5. Retrieval Evaluation Framework (`evaluation.py`)

To ensure retrieval quality and prevent hallucinated or missed policy checks:

1. **Benchmark Datasets**: Test suites stored in `sample-data/evaluation/` contain query-evidence pairs:
   - Input: Draft excerpt or controversial claim.
   - Ground Truth: Expected `source_ref` (e.g., `FACT-03`), relevant chunk IDs, and expected rule citations.
2. **Metrics Measured**:
   - **Hit Rate @ K**: Percentage of queries where the true relevant guideline is present in the top-K retrieved results.
   - **Mean Reciprocal Rank (MRR @ K)**: Measures the rank position of the first relevant result.
   - **Context Precision & Recall**: Verifies that retrieved snippets contain sufficient signal without excessive noise.
3. **CI/CD Regression Testing**: Future automated test runs will evaluate retrieval accuracy before model or chunking changes are promoted.

---

## 6. Supporting Sample Data Directories

The following directories have been initialized under `sample-data/` to support the RAG subsystem:

- `sample-data/knowledge/`: For raw policy manuals, brand styleguides, and compliance documents (.pdf, .docx, .md).
- `sample-data/documents/`: For sample drafts and marketing copy used to test multi-document retrieval.
- `sample-data/evaluation/`: For benchmark datasets mapping draft queries to ground-truth source citations.

---

## 7. Interface Alignment & Open Decisions

The following architectural and data contract interfaces require formal alignment across team members before active implementation:

| Interface / Decision | Stakeholder | Description & Open Questions |
| :--- | :--- | :--- |
| **Vector Storage & Indexing** | Krish (Database) | Agree on vector extension (`pgvector` vs external store), table schema for chunk embeddings, and index types (HNSW vs IVFFlat). |
| **Embedding Model & Dimensions** | Kalash (LLM) & Krish (DB) | Select embedding model (e.g., Google `text-embedding-004` vs local sentence-transformer), determine vector dimensions (e.g., 768 or 1536), and confirm dependencies. |
| **LLM Context & Prompt Format** | Kalash (LLM) | Finalize the exact schema of `RetrievedEvidence` passed into the LLM review prompt and token budget allocation for retrieved context. |
| **Shared Document Parsing** | Core Team | Coordinate with `app.services.parsing` so that PDF/DOCX extraction utilities are shared between user draft uploads and knowledge source uploads without code duplication. |
| **New Package Approvals** | Full Team | Confirm whether external packages (e.g. `google-genai` / vector search libraries) will be added to `pyproject.toml`. |

