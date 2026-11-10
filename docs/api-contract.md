# ProofLine API Contract

Base URL: `http://localhost:8000`

---

## Role-Based Permission Matrix

Every endpoint enforces role-based access control according to the table below. Access is evaluated before route execution:
- Unauthenticated requests to protected endpoints return `401 Unauthorized` (`{"detail": "Not authenticated"}`).
- Authenticated requests with a disallowed role return `403 Forbidden` (`{"detail": "Not allowed for your role"}`).
- Allowed requests proceed to the handler (returning `200` for implemented endpoints or `501 Not Implemented` for stubs).

| Endpoint | Method | Allowed Roles | Description |
|---|---|---|---|
| `/auth/login` | POST | Public | User authentication and JWT issuance |
| `/auth/me` | GET | Any logged-in user (`creator`, `reviewer`, `admin`) | Current user profile |
| `/health` | GET | Public | Service health probe |
| `/sources` | GET | `creator`, `reviewer`, `admin` | List guidelines, facts, and terminology |
| `/sources/guidelines` | POST | `admin` | Upload or create guideline rule |
| `/sources/facts` | POST | `admin` | Upload or create fact entry |
| `/sources/terms` | POST | `admin` | Upload or create terminology entry |
| `/drafts` | POST | `creator` | Create new draft document |
| `/drafts/{id}/review` | POST | `creator` | Trigger automated review |
| `/drafts/{id}/versions/{v}/findings` | GET | `creator`, `reviewer` | Retrieve findings for draft version |
| `/findings/{id}` | PATCH | `creator` | Update finding status or dismissal |
| `/drafts/{id}/request-review` | POST | `creator` | Request human review |
| `/drafts/{id}/comments` | POST | `creator`, `reviewer` | Add comment on draft |
| `/drafts/{id}/decision` | POST | `reviewer` | Record approval decision |
| `/drafts/{id}/receipt` | GET | `creator`, `reviewer`, `admin` | View review receipt |
| `/insights/rules` | GET | `reviewer`, `admin` | View rule performance analytics |
| `/audit` | GET | `admin` | View audit trail entries |

---

## Health Check

### `GET /health`

Returns the service health status.

- **Auth:** None (Public)
- **Roles:** Any
- **Request body:** None
- **Response (200):**
  ```json
  { "status": "ok", "service": "proofline-api" }
  ```

---

## Authentication

### `POST /auth/login`

Authenticate a user with credentials and receive a signed JWT access token.
Emails are automatically trimmed and lowercased. Unknown emails and incorrect passwords both return identical `401` responses with constant-time verification to prevent user enumeration or timing attacks.

- **Auth:** None (Public)
- **Roles:** Public
- **Request body:**
  ```json
  {
    "email": "user@example.com",
    "password": "string"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "id": "11111111-1111-1111-1111-111111111111",
      "email": "user@example.com",
      "full_name": "Test User",
      "role": "creator",
      "organisation_id": "22222222-2222-2222-2222-222222222222"
    }
  }
  ```
- **Response (401 Unauthorized):**
  ```json
  {
    "detail": "Invalid email or password"
  }
  ```
- **Status:** Implemented

### `GET /auth/me`

Returns the currently authenticated user's profile. User details (including role and organisation) are loaded fresh from the database row on every request.

- **Auth:** Bearer JWT
- **Roles:** Any logged-in user (`creator`, `reviewer`, `admin`)
- **Request body:** None
- **Response (200 OK):**
  ```json
  {
    "id": "11111111-1111-1111-1111-111111111111",
    "email": "user@example.com",
    "full_name": "Test User",
    "role": "creator",
    "organisation_id": "22222222-2222-2222-2222-222222222222"
  }
  ```
- **Response (401 Unauthorized):**
  ```json
  {
    "detail": "Not authenticated"
  }
  ```
- **Status:** Implemented

---

## Sources

### `POST /sources/guidelines`

Upload or create guideline rules for the organisation.

- **Auth:** Bearer JWT
- **Roles:** `admin`
- **Request body:**
  ```json
  { "rule_id": "string", "text": "string", "category": "string" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "rule_id": "string", "text": "string", "category": "string", "version": 1, "is_active": true }
  ```
- **Status:** 501 Not Implemented

### `POST /sources/facts`

Upload or create fact entries for the organisation.

- **Auth:** Bearer JWT
- **Roles:** `admin`
- **Request body:**
  ```json
  { "statement": "string", "value": "string", "owner": "string", "source": "string", "expires_on": "date | null" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "statement": "string", "value": "string", "owner": "string", "source": "string", "expires_on": "date | null", "version": 1 }
  ```
- **Status:** 501 Not Implemented

### `POST /sources/terms`

Upload or create terminology entries for the organisation.

- **Auth:** Bearer JWT
- **Roles:** `admin`
- **Request body:**
  ```json
  { "term": "string", "preferred": "string", "banned": false, "notes": "string | null" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "term": "string", "preferred": "string", "banned": false, "notes": "string | null" }
  ```
- **Status:** 501 Not Implemented

### `GET /sources`

List all sources (guidelines, facts, terminology) for the organisation.

- **Auth:** Bearer JWT
- **Roles:** `creator`, `reviewer`, `admin`
- **Request body:** None
- **Response (200):**
  ```json
  {
    "guidelines": [{ "id": "uuid", "rule_id": "string", "text": "string", "category": "string", "version": 1, "is_active": true }],
    "facts": [{ "id": "uuid", "statement": "string", "value": "string", "owner": "string", "source": "string", "expires_on": "date | null", "version": 1 }],
    "terms": [{ "id": "uuid", "term": "string", "preferred": "string", "banned": false, "notes": "string | null" }]
  }
  ```
- **Status:** 501 Not Implemented

---

## Drafts

### `POST /drafts`

Create a new draft document.

- **Auth:** Bearer JWT
- **Roles:** `creator`
- **Request body:**
  ```json
  { "content": "string", "channel": "string | null" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "organisation_id": "uuid", "created_by": "uuid", "channel": "string | null", "status": "draft", "created_at": "datetime" }
  ```
- **Status:** 501 Not Implemented

### `POST /drafts/{id}/review`

Trigger an automated review of the draft's latest version.

- **Auth:** Bearer JWT
- **Roles:** `creator`
- **Request body:** None
- **Response (202):**
  ```json
  { "draft_id": "uuid", "version": 1, "findings_count": 0, "status": "review_started" }
  ```
- **Status:** 501 Not Implemented

### `GET /drafts/{id}/versions/{v}/findings`

Get all findings for a specific draft version.

- **Auth:** Bearer JWT
- **Roles:** `creator`, `reviewer`
- **Request body:** None
- **Response (200):**
  ```json
  [
    {
      "id": "string",
      "draft_id": "string",
      "version_id": "string",
      "quoted_text": "string",
      "start": 0,
      "end": 10,
      "severity": "blocker | warning | note",
      "reason": "string",
      "source_ref": "string",
      "source_version": 1,
      "confidence": "high | medium | low",
      "suggestion": "string | null",
      "status": "open | accepted | edited | dismissed",
      "dismissal_reason": "string | null"
    }
  ]
  ```
- **Status:** 501 Not Implemented

### `POST /drafts/{id}/request-review`

Request a human review of the draft.

- **Auth:** Bearer JWT
- **Roles:** `creator`
- **Request body:** None
- **Response (202):**
  ```json
  { "draft_id": "uuid", "status": "review_requested" }
  ```
- **Status:** 501 Not Implemented

### `POST /drafts/{id}/comments`

Add a comment to a draft, optionally anchored to a text range.

- **Auth:** Bearer JWT
- **Roles:** `creator`, `reviewer`
- **Request body:**
  ```json
  { "text": "string", "range_start": "int | null", "range_end": "int | null" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "draft_id": "uuid", "user_id": "uuid", "text": "string", "range_start": "int | null", "range_end": "int | null", "created_at": "datetime" }
  ```
- **Status:** 501 Not Implemented

### `POST /drafts/{id}/decision`

Record an approval decision on a draft.

- **Auth:** Bearer JWT
- **Roles:** `reviewer`
- **Request body:**
  ```json
  { "decision": "approved | rejected | needs_changes", "reason": "string | null" }
  ```
- **Response (201):**
  ```json
  { "id": "uuid", "draft_id": "uuid", "user_id": "uuid", "decision": "string", "reason": "string | null", "created_at": "datetime" }
  ```
- **Status:** 501 Not Implemented

### `GET /drafts/{id}/receipt`

Get the review receipt for a draft.

- **Auth:** Bearer JWT
- **Roles:** `creator`, `reviewer`, `admin`
- **Request body:** None
- **Response (200):**
  ```json
  { "id": "uuid", "claim_id": "uuid", "organisation_id": "uuid", "receipt_data": {} }
  ```
- **Status:** 501 Not Implemented

---

## Findings

### `PATCH /findings/{id}`

Update the status or dismissal reason of a finding.

- **Auth:** Bearer JWT
- **Roles:** `creator`
- **Request body:**
  ```json
  { "status": "open | accepted | edited | dismissed", "dismissal_reason": "string | null" }
  ```
- **Response (200):**
  ```json
  { "id": "string", "status": "string", "dismissal_reason": "string | null" }
  ```
- **Status:** 501 Not Implemented

---

## Insights

### `GET /insights/rules`

Get rule performance analytics (most triggered rules, acceptance rates, etc.).

- **Auth:** Bearer JWT
- **Roles:** `reviewer`, `admin`
- **Request body:** None
- **Response (200):**
  ```json
  [
    { "rule_id": "string", "trigger_count": 0, "acceptance_rate": 0.0 }
  ]
  ```
- **Status:** 501 Not Implemented

---

## Audit

### `GET /audit`

Get the audit log entries.

- **Auth:** Bearer JWT
- **Roles:** `admin`
- **Request body:** None
- **Response (200):**
  ```json
  [
    {
      "id": "uuid",
      "user_id": "uuid | null",
      "action": "string",
      "entity": "string",
      "entity_id": "uuid | null",
      "details": {},
      "created_at": "datetime"
    }
  ]
  ```
- **Status:** 501 Not Implemented
