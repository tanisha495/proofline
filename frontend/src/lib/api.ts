/**
 * ProofLine API client for testing frontend.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function getToken(): string | null {
  if (typeof window !== "undefined") {
    return localStorage.getItem("proofline_token");
  }
  return null;
}

export function setToken(token: string) {
  if (typeof window !== "undefined") {
    localStorage.setItem("proofline_token", token);
  }
}

export function clearToken() {
  if (typeof window !== "undefined") {
    localStorage.removeItem("proofline_token");
    localStorage.removeItem("proofline_user");
  }
}

export function getCurrentUser() {
  if (typeof window !== "undefined") {
    const raw = localStorage.getItem("proofline_user");
    if (raw) {
      try {
        return JSON.parse(raw);
      } catch {
        return null;
      }
    }
  }
  return null;
}

export function setCurrentUser(user: any) {
  if (typeof window !== "undefined") {
    localStorage.setItem("proofline_user", JSON.stringify(user));
  }
}

export async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
  });

  if (!res.ok) {
    let errorDetail = res.statusText;
    try {
      const err = await res.json();
      errorDetail = err.detail || JSON.stringify(err);
    } catch {}
    throw new Error(errorDetail || `API request failed with status ${res.status}`);
  }

  return res.json() as Promise<T>;
}

// 1. Auth API
export async function login(email: string, password: string) {
  const res = await apiFetch<{ access_token: string }>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
  setToken(res.access_token);
  // Fetch user profile
  const me = await apiFetch<any>("/auth/me");
  setCurrentUser(me);
  return me;
}

// 2. Sources API
export async function getSources() {
  return apiFetch<{ guidelines: any[]; facts: any[]; terms: any[] }>("/sources");
}

export async function seedSources() {
  return apiFetch<any>("/sources/seed", { method: "POST" });
}

export async function createGuideline(data: { rule_id: string; text: string; category?: string }) {
  return apiFetch<any>("/sources/guidelines", { method: "POST", body: JSON.stringify(data) });
}

export async function createFact(data: { statement: string; value?: string; owner?: string; source?: string; expires_on?: string }) {
  return apiFetch<any>("/sources/facts", { method: "POST", body: JSON.stringify(data) });
}

export async function createTerm(data: { term: string; preferred?: string; banned: boolean; notes?: string }) {
  return apiFetch<any>("/sources/terms", { method: "POST", body: JSON.stringify(data) });
}

// 3. Drafts API
export async function listDrafts() {
  return apiFetch<any[]>("/drafts");
}

export async function getDraft(id: string) {
  return apiFetch<any>(`/drafts/${id}`);
}

export async function createDraft(data: { content: string; channel?: string; intent_lock?: any }) {
  return apiFetch<any>("/drafts", { method: "POST", body: JSON.stringify(data) });
}

export async function reviewDraft(id: string) {
  return apiFetch<any>(`/drafts/${id}/review`, { method: "POST" });
}

export async function getFindings(draftId: string, version: number = 1) {
  return apiFetch<any[]>(`/drafts/${draftId}/versions/${version}/findings`);
}

export async function getClaims(draftId: string, version: number = 1) {
  return apiFetch<any[]>(`/drafts/${draftId}/versions/${version}/claims`);
}

export async function updateFinding(findingId: string, data: { status: string; dismissal_reason?: string }) {
  return apiFetch<any>(`/findings/${findingId}`, { method: "PATCH", body: JSON.stringify(data) });
}

export async function requestReview(draftId: string) {
  return apiFetch<any>(`/drafts/${draftId}/request-review`, { method: "POST" });
}

export async function computeDiff(draftId: string, originalText: string, revisedText: string) {
  return apiFetch<any>(`/drafts/${draftId}/diff`, {
    method: "POST",
    body: JSON.stringify({ original_text: originalText, revised_text: revisedText }),
  });
}

export async function addComment(draftId: string, text: string, rangeStart?: number, rangeEnd?: number) {
  return apiFetch<any>(`/drafts/${draftId}/comments`, {
    method: "POST",
    body: JSON.stringify({ text, range_start: rangeStart, range_end: rangeEnd }),
  });
}

export async function getComments(draftId: string) {
  return apiFetch<any[]>(`/drafts/${draftId}/comments`);
}

export async function recordDecision(draftId: string, decision: string, reason?: string) {
  return apiFetch<any>(`/drafts/${draftId}/decision`, {
    method: "POST",
    body: JSON.stringify({ decision, reason }),
  });
}

export async function getClaimReceipt(draftId: string) {
  return apiFetch<any>(`/drafts/${draftId}/receipt`);
}

// 4. Insights API
export async function getRuleInsights() {
  return apiFetch<any[]>("/insights/rules");
}

// 5. Health Check
export async function healthCheck() {
  return apiFetch<{ status: string; service: string }>("/health");
}
