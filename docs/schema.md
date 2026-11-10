# ProofLine — Database Schema Reference

> **Branch:** `feat/db-schema` | **PostgreSQL 16** | **SQLAlchemy 2.x** | **Alembic**

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    organisations {
        uuid id PK
        text name UK
        timestamptz created_at
    }

    users {
        uuid id PK
        uuid organisation_id FK
        text email UK
        text password_hash
        text full_name
        user_role role
        bool is_active
        timestamptz created_at
        timestamptz updated_at
    }

    guideline_rules {
        uuid id PK
        uuid organisation_id FK
        text rule_id
        text category
        text text
        int version
        bool is_active
        uuid created_by FK
        timestamptz created_at
    }

    facts {
        uuid id PK
        uuid organisation_id FK
        text fact_key
        text statement
        text value
        text owner
        text source
        date expires_on
        int version
        bool is_active
        uuid created_by FK
        timestamptz created_at
    }

    terms {
        uuid id PK
        uuid organisation_id FK
        text term
        text preferred
        bool banned
        text notes
        int version
        bool is_active
        timestamptz created_at
    }

    drafts {
        uuid id PK
        uuid organisation_id FK
        uuid owner_id FK
        text title
        text channel
        draft_status status
        jsonb intent_lock
        int current_version_number
        timestamptz created_at
        timestamptz updated_at
    }

    draft_versions {
        uuid id PK
        uuid organisation_id FK
        uuid draft_id FK
        int version_number
        text content
        char64 content_hash
        uuid created_by FK
        timestamptz created_at
    }

    findings {
        uuid id PK
        uuid organisation_id FK
        uuid draft_id FK
        uuid version_id FK
        text quoted_text
        int start_offset
        int end_offset
        finding_severity severity
        text reason
        source_type source_type
        text source_ref
        int source_version
        finding_confidence confidence
        text suggestion
        finding_status status
        text dismissal_reason
        uuid resolved_by FK
        timestamptz created_at
        timestamptz updated_at
    }

    claims {
        uuid id PK
        uuid organisation_id FK
        uuid version_id FK
        text claim_text
        text claim_type
        claim_status status
        text evidence_fact_key
        int evidence_version
        timestamptz created_at
    }

    claim_receipts {
        uuid id PK
        uuid organisation_id FK
        uuid draft_id FK
        uuid version_id FK_UK
        uuid approved_by FK
        timestamptz approved_at
        char64 content_hash
        jsonb claims_snapshot
        jsonb guideline_versions
        jsonb override_reasons
        timestamptz created_at
    }

    comments {
        uuid id PK
        uuid organisation_id FK
        uuid draft_id FK
        uuid version_id FK
        uuid author_id FK
        text body
        int range_start
        int range_end
        timestamptz created_at
    }

    approvals {
        uuid id PK
        uuid organisation_id FK
        uuid draft_id FK
        uuid version_id FK
        uuid reviewer_id FK
        decision_type decision
        text override_reason
        text note
        timestamptz created_at
    }

    audit_log {
        uuid id PK
        uuid organisation_id FK
        uuid user_id FK
        text action
        text entity
        uuid entity_id
        jsonb details
        jsonb guideline_versions
        timestamptz created_at
    }

    organisations ||--o{ users : "has"
    organisations ||--o{ guideline_rules : "owns"
    organisations ||--o{ facts : "owns"
    organisations ||--o{ terms : "owns"
    organisations ||--o{ drafts : "owns"
    organisations ||--o{ draft_versions : "owns"
    organisations ||--o{ findings : "owns"
    organisations ||--o{ claims : "owns"
    organisations ||--o{ claim_receipts : "owns"
    organisations ||--o{ comments : "owns"
    organisations ||--o{ approvals : "owns"
    organisations ||--o{ audit_log : "owns"

    users ||--o{ drafts : "owns"
    users ||--o{ guideline_rules : "created_by"
    users ||--o{ facts : "created_by"
    users ||--o{ draft_versions : "created_by"
    users ||--o{ findings : "resolved_by"
    users ||--o{ claim_receipts : "approved_by"
    users ||--o{ comments : "authored"
    users ||--o{ approvals : "made"
    users ||--o{ audit_log : "performed"

    drafts ||--o{ draft_versions : "has"
    drafts ||--o{ findings : "has"
    drafts ||--o{ comments : "has"
    drafts ||--o{ approvals : "has"
    drafts ||--o{ claim_receipts : "has"

    draft_versions ||--o{ findings : "flags"
    draft_versions ||--o{ claims : "contains"
    draft_versions ||--o{ comments : "annotates"
    draft_versions ||--o{ approvals : "decided on"
    draft_versions ||--|{ claim_receipts : "receipted by"
```

---

## Enums

| Enum | Values |
|------|--------|
| `user_role` | `creator`, `reviewer`, `admin` |
| `draft_status` | `draft`, `in_review`, `changes_requested`, `approved` |
| `finding_severity` | `blocker`, `warning`, `note` |
| `finding_confidence` | `high`, `medium`, `low` |
| `finding_status` | `open`, `accepted`, `edited`, `dismissed` |
| `claim_status` | `supported`, `conflicts`, `expired_evidence`, `unsupported`, `needs_human` |
| `source_type` | `guideline`, `fact`, `term` |
| `decision_type` | `approved`, `changes_requested` |

All enums are **PostgreSQL native types** created by the initial migration.

---

## Tables

### `organisations`

Top-level tenant boundary. Every other table belongs to exactly one organisation.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK, `gen_random_uuid()` | Surrogate key |
| `name` | `text` | `uq_organisations_name` | Display name, globally unique |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation timestamp |

---

### `users`

ProofLine users. Each user belongs to exactly one organisation; email is globally unique (stored lowercase by application).

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations, NOT NULL | Tenant scope |
| `email` | `text` | `uq_users_email`, NOT NULL | Login credential; must be lowercase |
| `password_hash` | `text` | NOT NULL | Bcrypt hash |
| `full_name` | `text` | nullable | Display name |
| `role` | `user_role` | NOT NULL | Permissions tier |
| `is_active` | `bool` | NOT NULL, default `true` | Soft-disable flag |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |
| `updated_at` | `timestamptz` | NOT NULL, `now()` | Last modification |

**Additional constraints:** `uq_users_id_org (id, organisation_id)` — enables composite FK from child tables.

---

### `guideline_rules`

Versioned brand/compliance rules. `rule_id` (e.g. `TONE-01`) is the human identifier. Editing a rule means inserting a new row with `version + 1`; never updating in place.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `rule_id` | `text` | NOT NULL | Human-readable ID (`TONE-01`) |
| `category` | `text` | nullable | Grouping label |
| `text` | `text` | NOT NULL | Rule body *(ORM attribute: `rule_text`)* |
| `version` | `int` | NOT NULL, default `1` | Monotonically increasing per `rule_id` |
| `is_active` | `bool` | NOT NULL, default `true` | Flags the current active version |
| `created_by` | `uuid` | FK → users, nullable | Author |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

**Additional constraints:**
- `uq_guideline_rules_org_ruleid_version (organisation_id, rule_id, version)` — prevents duplicate versions.
- **Partial unique index** `ix_guideline_rules_one_active` on `(organisation_id, rule_id) WHERE is_active = true` — only one active version per rule per org.

---

### `facts`

Versioned facts that can be cited in findings. Same versioning pattern as `guideline_rules`.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `fact_key` | `text` | NOT NULL | Human ID (`FACT-01`) |
| `statement` | `text` | NOT NULL | Fact body |
| `value` | `text` | nullable | Machine-readable value (e.g. a price) |
| `owner` | `text` | nullable | Team responsible |
| `source` | `text` | nullable | URL or citation |
| `expires_on` | `date` | nullable | Evidence expiry |
| `version` | `int` | NOT NULL, default `1` | Monotonically increasing |
| `is_active` | `bool` | NOT NULL, default `true` | Flags active version |
| `created_by` | `uuid` | FK → users, nullable | Author |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

**Additional constraints:** `uq_facts_org_factkey_version` + partial unique index `ix_facts_one_active`.

---

### `terms`

Brand terminology — preferred spellings and banned words.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `term` | `text` | NOT NULL | The word/phrase |
| `preferred` | `text` | nullable | Replacement to suggest |
| `banned` | `bool` | NOT NULL, default `false` | True = never use this term |
| `notes` | `text` | nullable | Context or rationale |
| `version` | `int` | NOT NULL, default `1` | Monotonically increasing |
| `is_active` | `bool` | NOT NULL, default `true` | Flags active version |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

**Additional constraints:** `uq_terms_org_term_version` + partial unique index `ix_terms_one_active`.

---

### `drafts`

A document being reviewed through the ProofLine workflow.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `owner_id` | `uuid` | FK → users | Creator/owner |
| `title` | `text` | nullable | Display name |
| `channel` | `text` | nullable | Publication channel (web, email, …) |
| `status` | `draft_status` | NOT NULL, default `draft` | Lifecycle state |
| `intent_lock` | `jsonb` | NOT NULL, default `{}` | AI intent snapshot for drift detection |
| `current_version_number` | `int` | NOT NULL, default `1` | Current active version |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |
| `updated_at` | `timestamptz` | NOT NULL, `now()` | Last change |

**Indexes:** `ix_drafts_organisation_status (organisation_id, status)`.

---

### `draft_versions`

Immutable snapshot of draft content at a point in time. Rows are blocked from UPDATE (of `content`/`content_hash`) and DELETE by a database trigger.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `draft_id` | `uuid` | composite FK → drafts | Parent draft |
| `version_number` | `int` | NOT NULL | Sequential within a draft |
| `content` | `text` | NOT NULL | Full document text at this version |
| `content_hash` | `char(64)` | NOT NULL | SHA-256 hex digest of `content` |
| `created_by` | `uuid` | FK → users, nullable | Who saved this version |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Snapshot timestamp |

**Additional constraints:**
- `uq_draft_versions_draft_version (draft_id, version_number)` — unique version numbers within a draft.
- `uq_draft_versions_id_org (id, organisation_id)` — enables composite FK from child tables.
- Composite FK `fk_draft_versions_draft_org (draft_id, organisation_id) → drafts (id, organisation_id)` — org isolation.
- **Trigger** `trg_draft_versions_immutable` calls `trg_fn_immutable_content` which blocks UPDATE of `content` or `content_hash` and blocks DELETE entirely.

---

### `findings`

A single issue flagged by the review engine against a specific draft version.

> **Column naming:** The API exposes `start` and `end` (see [Field alias note](#field-alias-note-startend-vs-start_offsetend_offset)). The DB columns are `start_offset` and `end_offset` because `end` is an SQL reserved word.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `draft_id` | `uuid` | NOT NULL | Parent draft |
| `version_id` | `uuid` | composite FK → draft_versions | Specific version flagged |
| `quoted_text` | `text` | nullable | Verbatim excerpt |
| `start_offset` | `int` | NOT NULL, ≥ 0 | Byte/char start of flagged range |
| `end_offset` | `int` | NOT NULL, > start_offset | Byte/char end (exclusive) |
| `severity` | `finding_severity` | NOT NULL | Criticality |
| `reason` | `text` | NOT NULL | Human-readable explanation |
| `source_type` | `source_type` | nullable | Guideline / fact / term |
| `source_ref` | `text` | NOT NULL, NOT EMPTY | Citation (rule_id or fact_key) |
| `source_version` | `int` | nullable | Version of the cited source |
| `confidence` | `finding_confidence` | NOT NULL | AI confidence level |
| `suggestion` | `text` | nullable | Proposed fix |
| `status` | `finding_status` | NOT NULL, default `open` | Resolution state |
| `dismissal_reason` | `text` | nullable | Required when `status = dismissed` |
| `resolved_by` | `uuid` | FK → users, nullable | Who resolved it |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |
| `updated_at` | `timestamptz` | NOT NULL, `now()` | Last modification |

**CHECK constraints:**
- `ck_findings_source_ref_nonempty`: `source_ref <> ''` — enforces "no source, no flag" at DB level.
- `ck_findings_offsets`: `start_offset >= 0 AND end_offset > start_offset`.
- `ck_findings_dismissed_reason`: `status <> 'dismissed' OR dismissal_reason IS NOT NULL`.

---

### `claims`

A factual claim extracted from a draft version and checked against `facts`.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `version_id` | `uuid` | composite FK → draft_versions | Source version |
| `claim_text` | `text` | NOT NULL | Verbatim claim |
| `claim_type` | `text` | nullable | Category (`price`, `statistic`, …) |
| `status` | `claim_status` | NOT NULL | Verification outcome |
| `evidence_fact_key` | `text` | nullable | The fact that supports/refutes |
| `evidence_version` | `int` | nullable | Version of that fact |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

---

### `claim_receipts`

Immutable record created when a draft version is approved. One receipt per approved version. Rows are blocked from UPDATE and DELETE by a trigger.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `draft_id` | `uuid` | NOT NULL | Parent draft |
| `version_id` | `uuid` | UNIQUE, composite FK | Exactly one receipt per approved version |
| `approved_by` | `uuid` | FK → users | Approver |
| `approved_at` | `timestamptz` | NOT NULL | Approval timestamp |
| `content_hash` | `char(64)` | NOT NULL | SHA-256 of content at approval time |
| `claims_snapshot` | `jsonb` | NOT NULL | Snapshot of all claims at approval |
| `guideline_versions` | `jsonb` | NOT NULL | Active guideline versions used |
| `override_reasons` | `jsonb` | NOT NULL, default `[]` | Blocker overrides with rationale |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

---

### `comments`

Reviewer comment on a draft, optionally anchored to a text range.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `draft_id` | `uuid` | composite FK → drafts | Parent draft |
| `version_id` | `uuid` | NOT NULL | Version being commented on |
| `author_id` | `uuid` | composite FK → users | Commenter |
| `body` | `text` | NOT NULL | Comment text |
| `range_start` | `int` | nullable | Start offset of anchored range |
| `range_end` | `int` | nullable | End offset (must be > range_start) |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Row creation |

**CHECK:** `ck_comments_range`: `range_end IS NULL OR range_start IS NULL OR range_end > range_start`.

---

### `approvals`

Human approval/rejection decision on a specific draft version. Rows are **never updated or deleted** (enforced by application convention — no trigger, as approvals are not append-only by DB trigger).

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `draft_id` | `uuid` | composite FK → drafts | Target draft |
| `version_id` | `uuid` | NOT NULL | Specific version decided on |
| `reviewer_id` | `uuid` | composite FK → users | Decision maker |
| `decision` | `decision_type` | NOT NULL | `approved` or `changes_requested` |
| `override_reason` | `text` | nullable | Reason when overriding a blocker |
| `note` | `text` | nullable | Free-form reviewer note |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Decision timestamp |

---

### `audit_log`

Append-only record of every significant action. UPDATE, DELETE, and TRUNCATE are blocked by the `trg_audit_log_immutable` trigger.

| Column | Type | Constraints | Purpose |
|--------|------|-------------|---------|
| `id` | `uuid` | PK | Surrogate key |
| `organisation_id` | `uuid` | FK → organisations | Tenant scope |
| `user_id` | `uuid` | FK → users, nullable | Null = system/automated action |
| `action` | `text` | NOT NULL | Verb (e.g. `draft.submitted`) |
| `entity` | `text` | nullable | Table name affected |
| `entity_id` | `uuid` | nullable | Affected row |
| `details` | `jsonb` | nullable | Additional context |
| `guideline_versions` | `jsonb` | nullable | Active rules at time of action |
| `created_at` | `timestamptz` | NOT NULL, `now()` | Event timestamp |

**Index:** `ix_audit_log_organisation_created_at (organisation_id, created_at DESC)`.

---

## Rules the Database Enforces

| Rule | Mechanism |
|------|-----------|
| **No source, no flag** | `ck_findings_source_ref_nonempty`: `source_ref <> ''` — an empty string is rejected at the DB layer. |
| **Versioned sources** | `UNIQUE (organisation_id, rule_id/fact_key/term, version)` prevents duplicate version numbers. Partial unique index prevents two active versions of the same source. |
| **Immutable draft versions** | Trigger `trg_draft_versions_immutable` calls `trg_fn_immutable_content`: UPDATE of `content` or `content_hash` raises; DELETE raises. |
| **Append-only audit log** | Trigger `trg_audit_log_immutable` calls `trg_fn_immutable_row`: UPDATE, DELETE, and TRUNCATE on `audit_log` raise. |
| **Immutable claim receipts** | Trigger `trg_claim_receipts_immutable` calls `trg_fn_immutable_row`: UPDATE and DELETE on `claim_receipts` raise. |
| **One receipt per approved version** | `uq_claim_receipts_version_id (version_id)` — a second receipt for the same version is rejected. |
| **Org isolation (composite FK)** | Every child table that references an org-scoped parent uses a composite FK `(parent_id, organisation_id) → parent (id, organisation_id)`. A row in org B cannot reference a parent row in org A because no `(parent_id, org_B)` tuple exists in the parent's composite unique. |
| **Offset sanity** | `ck_findings_offsets`: `start_offset >= 0 AND end_offset > start_offset`. |
| **Dismissal requires reason** | `ck_findings_dismissed_reason`: `status <> 'dismissed' OR dismissal_reason IS NOT NULL`. |
| **Range sanity (comments)** | `ck_comments_range`: if both range values are provided, `range_end > range_start`. |

---

## Rules the Application Layer Must Still Enforce

These invariants cannot be enforced by the database alone and must be implemented in service or repository code:

| Rule | Why DB cannot enforce it |
|------|--------------------------|
| **Role-based access control** (only `reviewer`/`admin` may approve; only `admin` may manage rules) | Multi-row check; no SQL predicate covers it cleanly. |
| **Approval state transitions** (a draft in `draft` status cannot skip to `approved`) | Requires knowing the previous `status` value and the actor's role simultaneously. |
| **Blocker override** (a reviewer may approve a draft with open `blocker` findings only if `override_reason` is supplied in the approval and stored in the receipt) | Business logic spanning multiple tables. |
| **Email must be stored lowercase** | The `CHECK LOWER(email) = email` pattern is legal SQL but was intentionally left to the application to avoid implicit transformation surprises. |
| **SHA-256 of `content` must equal `content_hash`** | Computed value; DB cannot re-derive it without a function call in a trigger. |
| **`current_version_number` on drafts** | Must be incremented by the application each time a new `draft_versions` row is inserted. |

---

## Field Alias Note — `start`/`end` vs `start_offset`/`end_offset`

The external API contract (documented in the OpenAPI spec and the TypeScript client types) uses `start` and `end` as field names for the character offsets of a finding's flagged range.

`end` is an SQL reserved word and cannot be used as a column name without quoting in every query. The database therefore uses `start_offset` and `end_offset`.

The bridge is in [app/schemas/finding.py](../backend/app/schemas/finding.py):

```python
start_offset: int = Field(
    ...,
    validation_alias=AliasChoices("start", "start_offset"),
    serialization_alias="start",
)
end_offset: int = Field(
    ...,
    validation_alias=AliasChoices("end", "end_offset"),
    serialization_alias="end",
)
```

- **Request JSON → Pydantic:** `start` and `end` are accepted (as well as `start_offset`/`end_offset` for internal use).
- **Pydantic → Response JSON:** serialised as `start` and `end`.
- **ORM → Pydantic:** `from_attributes=True` reads `start_offset` and `end_offset` directly from the SQLAlchemy model.

No other layer should use `start`/`end` as Python identifiers or SQL column names.

---

## Migration Commands

```bash
# Apply schema
alembic upgrade head

# Roll back everything
alembic downgrade base

# Re-apply (idempotency check)
alembic upgrade head
```

Migration file: [`alembic/versions/0001_initial_schema.py`](../backend/alembic/versions/0001_initial_schema.py)

---

## Table Summary

| Table | Columns | Key features |
|-------|---------|--------------|
| `organisations` | 3 | Root tenant; no org_id |
| `users` | 9 | Global unique email; composite uq for child FKs |
| `guideline_rules` | 9 | Versioned; partial idx for single active version |
| `facts` | 12 | Versioned; expiry date; partial idx |
| `terms` | 9 | Versioned; banned flag |
| `drafts` | 10 | JSONB intent_lock; indexed by (org, status) |
| `draft_versions` | 8 | Immutable content; trigger-protected |
| `findings` | 19 | 3 CHECK constraints; composite FK for org isolation |
| `claims` | 9 | Composite FK to draft_versions |
| `claim_receipts` | 11 | Unique per version; trigger-immutable |
| `comments` | 9 | Optional text range; composite FKs |
| `approvals` | 9 | Composite FKs; append-only by convention |
| `audit_log` | 9 | Trigger-immutable; DESC index on created_at |

