export type Severity = "blocker" | "warning" | "note";
export type Confidence = "high" | "medium" | "low";
export type FindingStatus = "open" | "accepted" | "edited" | "dismissed";

export interface Finding {
  id: string;
  draft_id: string;
  version_id: string;
  quoted_text: string;
  start: number;
  end: number;
  severity: Severity;
  reason: string;
  source_ref: string;
  source_version: number;
  confidence: Confidence;
  suggestion: string | null;
  status: FindingStatus;
  dismissal_reason: string | null;
}

export type ClaimStatus =
  | "supported"
  | "conflicts"
  | "expired_evidence"
  | "unsupported"
  | "needs_human";

