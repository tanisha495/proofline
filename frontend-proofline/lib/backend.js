/**
 * Live ProofLine FastAPI Backend Bridge for frontend-proofline.
 * Connects Tanisha's Studio North workspace to Kalash's 4-layer Groq LLM review engine,
 * Krish's RBAC/DB API, and Dhruv's RAG subsystem.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const JWT_KEY = "proofline.jwt";

const DEMO_ACCOUNTS = {
  writer: { email: "writer@studionorth.demo", password: "proofline-demo" },
  manager: { email: "manager@studionorth.demo", password: "proofline-demo" },
};

export function getBackendToken() {
  if (typeof window === "undefined") return null;
  try {
    return sessionStorage.getItem(JWT_KEY);
  } catch {
    return null;
  }
}

export function clearBackendToken() {
  if (typeof window === "undefined") return;
  try {
    sessionStorage.removeItem(JWT_KEY);
  } catch {}
}

async function apiRequest(path, options = {}, tokenOverride = null) {
  const token = tokenOverride || getBackendToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = await res.json();
      detail = err.detail || detail;
    } catch {}
    throw new Error(detail);
  }
  return res.json();
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_URL}/health`);
    if (!res.ok) return false;
    const data = await res.json();
    return data?.status === "ok";
  } catch {
    return false;
  }
}

export async function loginBackendRole(role) {
  const creds = DEMO_ACCOUNTS[role];
  if (!creds) return null;
  try {
    const data = await apiRequest("/auth/login", {
      method: "POST",
      body: JSON.stringify(creds),
    });
    if (typeof window !== "undefined" && data.access_token) {
      sessionStorage.setItem(JWT_KEY, data.access_token);
    }
    return data;
  } catch {
    return null;
  }
}

function capitalize(str) {
  if (!str) return "";
  return str.charAt(0).toUpperCase() + str.slice(1).toLowerCase();
}

function mapClaimStatus(status) {
  const map = {
    supported: "Supported",
    conflicts: "Conflicts",
    expired_evidence: "Expired evidence",
    unsupported: "Unsupported",
    needs_human: "Needs a human",
  };
  return map[status] || "Needs a human";
}

export async function runBackendReview(draft) {
  // Always ensure we have a creator/writer token for POST /drafts and /review
  let writerToken = getBackendToken();
  const authRes = await loginBackendRole("writer");
  if (authRes?.access_token) {
    writerToken = authRes.access_token;
  }
  if (!writerToken) {
    throw new Error("Could not authenticate with ProofLine backend");
  }

  let backendDraftId = draft.backendId;
  let versionNumber = 1;

  if (!backendDraftId) {
    const created = await apiRequest(
      "/drafts",
      {
        method: "POST",
        body: JSON.stringify({
          title: draft.title || "Untitled Draft",
          content: draft.text,
          channel: draft.channel || "Email",
          intent_lock: draft.intent || {},
        }),
      },
      writerToken
    );
    backendDraftId = created.id;
  } else {
    const ver = await apiRequest(
      `/drafts/${backendDraftId}/versions`,
      {
        method: "POST",
        body: JSON.stringify({
          content: draft.text,
          intent_lock: draft.intent || {},
        }),
      },
      writerToken
    );
    versionNumber = ver.version_number;
  }

  const reviewSummary = await apiRequest(
    `/drafts/${backendDraftId}/review`,
    { method: "POST" },
    writerToken
  );

  const [findingsRaw, claimsRaw] = await Promise.all([
    apiRequest(
      `/drafts/${backendDraftId}/versions/${reviewSummary.version || versionNumber}/findings`,
      { method: "GET" },
      writerToken
    ),
    apiRequest(
      `/drafts/${backendDraftId}/versions/${reviewSummary.version || versionNumber}/claims`,
      { method: "GET" },
      writerToken
    ),
  ]);

  const mappedFindings = findingsRaw.map((f) => ({
    id: `AI-${f.id}`,
    backendFindingId: f.id,
    start: f.start ?? 0,
    original: f.quoted_text || "",
    source: {
      id: f.source_ref,
      title: `${f.source_ref} (AI Grounded)`,
      type:
        f.source_type === "fact"
          ? "Approved facts"
          : f.source_type === "term"
          ? "Terminology"
          : "Guidelines",
      version: f.source_version || 1,
    },
    title: `${capitalize(f.severity)}: ${f.source_ref}`,
    severity: capitalize(f.severity),
    reason: f.reason,
    suggested: f.suggestion || null,
    confidence: capitalize(f.confidence),
    decision: f.status === "open" ? "open" : f.status,
    note: f.dismissal_reason || "",
  }));

  const mappedClaims = claimsRaw.map((c) => ({
    text: c.quoted_text || "",
    status: mapClaimStatus(c.status),
    source: {
      id: c.source_ref || "FACT-LEDGER",
      title: c.source_ref || "Fact Ledger",
      version: c.evidence_version || 1,
    },
  }));

  return {
    backendId: backendDraftId,
    findings: mappedFindings,
    claims: mappedClaims,
    summary: reviewSummary,
  };
}

export async function syncBackendDecision(backendDraftId, decision, reason) {
  if (!backendDraftId) return null;
  try {
    const authRes = await loginBackendRole("manager");
    const token = authRes?.access_token;
    if (!token) return null;
    return await apiRequest(
      `/drafts/${backendDraftId}/decision`,
      {
        method: "POST",
        body: JSON.stringify({
          decision: decision === "approved" ? "approved" : "changes_requested",
          reason: reason || "Reviewed in ProofLine workspace",
        }),
      },
      token
    );
  } catch {
    return null;
  }
}

export async function searchBackendRag(query) {
  try {
    const authRes = await loginBackendRole("writer");
    const token = authRes?.access_token;
    if (!token) return null;
    return await apiRequest(
      `/sources/rag-search?query=${encodeURIComponent(query)}&top_k=5`,
      { method: "GET" },
      token
    );
  } catch {
    return null;
  }
}

