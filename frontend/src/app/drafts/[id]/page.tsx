"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import {
  addComment,
  computeDiff,
  getClaims,
  getClaimReceipt,
  getComments,
  getDraft,
  getFindings,
  recordDecision,
  requestReview,
  reviewDraft,
  updateFinding,
} from "@/lib/api";

export default function DraftDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const resolvedParams = use(params);
  const draftId = resolvedParams.id;

  const [draft, setDraft] = useState<any>(null);
  const [findings, setFindings] = useState<any[]>([]);
  const [claims, setClaims] = useState<any[]>([]);
  const [comments, setComments] = useState<any[]>([]);
  const [receipt, setReceipt] = useState<any>(null);
  const [diffData, setDiffData] = useState<any>(null);

  const [loading, setLoading] = useState(true);
  const [actionMsg, setActionMsg] = useState<string | null>(null);
  const [newComment, setNewComment] = useState("");
  const [reviewRisk, setReviewRisk] = useState<any>(null);

  const loadAll = async () => {
    setLoading(true);
    try {
      const d = await getDraft(draftId);
      setDraft(d);

      const f = await getFindings(draftId, d.latest_version || 1);
      setFindings(f);

      const c = await getClaims(draftId, d.latest_version || 1);
      setClaims(c);

      const cm = await getComments(draftId);
      setComments(cm);

      if (d.status === "approved") {
        const rc = await getClaimReceipt(draftId);
        setReceipt(rc);
      }
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAll();
  }, [draftId]);

  const handleTriage = async (findingId: string, status: string) => {
    let reason = undefined;
    if (status === "dismissed") {
      const promptReason = prompt("Reason for dismissing this brand rule:", "Creative exception approved");
      if (promptReason === null) return;
      reason = promptReason;
    }
    try {
      await updateFinding(findingId, { status, dismissal_reason: reason });
      setActionMsg(`Finding marked as ${status}.`);
      loadAll();
    } catch (e: any) {
      alert("Error updating finding: " + e.message);
    }
  };

  const handleReAudit = async () => {
    setActionMsg("Re-running 4-layer review engine...");
    try {
      await reviewDraft(draftId);
      setActionMsg("Review complete!");
      loadAll();
    } catch (e: any) {
      alert("Error: " + e.message);
    }
  };

  const handleRequestReview = async () => {
    try {
      const res = await requestReview(draftId);
      setReviewRisk(res);
      setActionMsg(`Submitted for human review! Risk tier assigned: ${res.risk_tier}`);
      loadAll();
    } catch (e: any) {
      alert("Error: " + e.message);
    }
  };

  const handleDecision = async (decision: string) => {
    try {
      await recordDecision(draftId, decision, "Reviewed in test console");
      setActionMsg(`Decision recorded: ${decision.toUpperCase()}`);
      loadAll();
    } catch (e: any) {
      alert("Error: " + e.message);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    try {
      await addComment(draftId, newComment);
      setNewComment("");
      const cm = await getComments(draftId);
      setComments(cm);
    } catch (e: any) {
      alert("Error adding comment: " + e.message);
    }
  };

  const handleShowDiff = async () => {
    // Construct revised text by applying all accepted suggestions
    let revised = draft.content;
    findings
      .filter((f) => f.status === "accepted" && f.suggestion)
      .forEach((f) => {
        revised = revised.replace(f.quoted_text, f.suggestion);
      });

    try {
      const res = await computeDiff(draftId, draft.content, revised);
      setDiffData({ ...res, revisedText: revised });
    } catch (e: any) {
      alert("Error computing diff: " + e.message);
    }
  };

  if (loading && !draft) {
    return <div className="p-12 text-center text-xs text-gray-500">Loading draft details...</div>;
  }

  const blockers = findings.filter((f) => f.severity === "blocker");
  const warnings = findings.filter((f) => f.severity === "warning");

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono font-bold bg-gray-100 border border-gray-300 px-2 py-0.5 rounded uppercase">
              {draft?.channel || "General Copy"}
            </span>
            <span
              className={`text-xs font-bold px-2 py-0.5 rounded border uppercase ${
                draft?.status === "approved"
                  ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                  : draft?.status === "review_requested"
                  ? "bg-amber-50 text-amber-800 border-amber-300"
                  : "bg-gray-100 text-gray-800 border-gray-300"
              }`}
            >
              Status: {draft?.status}
            </span>
            <span className="text-xs text-gray-500 font-mono">v{draft?.latest_version || 1}</span>
          </div>
          <h1 className="text-xl font-black text-gray-950 mt-1">Draft Review & Governance Triage</h1>
          <p className="text-[11px] text-gray-500 font-mono mt-0.5">ID: {draftId}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleReAudit}
            className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded text-xs font-semibold text-gray-800"
          >
            🔄 Re-Audit Draft
          </button>
          <button
            onClick={handleRequestReview}
            className="px-4 py-1.5 bg-black hover:bg-gray-800 text-white rounded text-xs font-bold shadow-xs"
          >
            Submit for Review &rarr;
          </button>
        </div>
      </div>

      {actionMsg && (
        <div className="p-3 bg-gray-100 border border-gray-300 text-xs font-medium rounded text-gray-900">
          {actionMsg}
        </div>
      )}

      {/* Review Metrics Summary */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <div className="bg-white border border-gray-300 p-4 rounded text-center">
          <div className="text-2xl font-black text-red-600">{blockers.length}</div>
          <div className="text-[11px] font-bold text-gray-500 uppercase mt-0.5">Blockers</div>
        </div>
        <div className="bg-white border border-gray-300 p-4 rounded text-center">
          <div className="text-2xl font-black text-amber-600">{warnings.length}</div>
          <div className="text-[11px] font-bold text-gray-500 uppercase mt-0.5">Warnings</div>
        </div>
        <div className="bg-white border border-gray-300 p-4 rounded text-center">
          <div className="text-2xl font-black text-purple-600">{claims.length}</div>
          <div className="text-[11px] font-bold text-gray-500 uppercase mt-0.5">Verified Claims</div>
        </div>
        <div className="bg-white border border-gray-300 p-4 rounded text-center">
          <div className="text-2xl font-black text-emerald-600">
            {findings.filter((f) => f.status === "accepted").length}
          </div>
          <div className="text-[11px] font-bold text-gray-500 uppercase mt-0.5">Accepted Fixes</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Original Draft & Claim Ledger */}
        <div className="lg:col-span-1 space-y-6">
          {/* Draft Content Card */}
          <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600">Draft Copy</h3>
            <div className="p-3 bg-gray-50 border border-gray-200 rounded font-mono text-xs text-gray-900 leading-relaxed whitespace-pre-wrap">
              {draft?.content}
            </div>

            {draft?.intent_lock && (
              <div className="p-3 bg-gray-100 border border-gray-200 rounded text-[11px] space-y-1">
                <span className="font-bold text-gray-800">🔒 Intent Lock Parameters:</span>
                <div>Key Message: <em>{draft.intent_lock.key_message}</em></div>
                <div>Target Audience: <em>{draft.intent_lock.audience}</em></div>
                <div>CTA: <em>{draft.intent_lock.call_to_action}</em></div>
              </div>
            )}
          </div>

          {/* Layer 2: Claim Ledger */}
          <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600">
              Layer 2: Claim Ledger ({claims.length})
            </h3>
            {claims.length === 0 ? (
              <p className="text-xs text-gray-500">No atomic factual assertions detected.</p>
            ) : (
              <div className="space-y-2">
                {claims.map((c) => (
                  <div key={c.id} className="p-2.5 border border-gray-200 rounded bg-gray-50 text-xs space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-mono text-gray-700">&ldquo;{c.quoted_text}&rdquo;</span>
                      <span
                        className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                          c.status === "supported"
                            ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                            : c.status === "conflicts"
                            ? "bg-red-50 text-red-800 border-red-300"
                            : c.status === "expired_evidence"
                            ? "bg-amber-50 text-amber-800 border-amber-300"
                            : "bg-gray-100 text-gray-700 border-gray-300"
                        }`}
                      >
                        {c.status}
                      </span>
                    </div>
                    {c.source_ref && (
                      <div className="text-[11px] text-gray-500">
                        Mapped to: <strong className="text-gray-700">{c.source_ref}</strong>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Reviewer Sign-Off Box */}
          <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600">Reviewer Actions</h3>
            <p className="text-[11px] text-gray-500">
              Sign off on draft or request changes according to the Risk-Based Governance Matrix.
            </p>
            <div className="flex flex-col gap-2 pt-2">
              <button
                onClick={() => handleDecision("approved")}
                className="w-full bg-emerald-600 hover:bg-emerald-700 text-white py-2 rounded text-xs font-bold"
              >
                ✅ Approve Draft & Generate Receipt
              </button>
              <button
                onClick={() => handleDecision("needs_changes")}
                className="w-full bg-amber-500 hover:bg-amber-600 text-white py-2 rounded text-xs font-bold"
              >
                ⚠️ Request Changes (Return to Creator)
              </button>
              <button
                onClick={() => handleDecision("rejected")}
                className="w-full bg-red-600 hover:bg-red-700 text-white py-2 rounded text-xs font-bold"
              >
                ⛔ Reject Draft
              </button>
            </div>
          </div>
        </div>

        {/* Right: Findings List & Diffs */}
        <div className="lg:col-span-2 space-y-6">
          {/* Findings List (Layer 4 Validator Output) */}
          <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-4">
            <div className="flex items-center justify-between border-b border-gray-200 pb-3">
              <div>
                <h3 className="text-sm font-bold text-gray-900">
                  Audited Findings ({findings.length})
                </h3>
                <span className="text-[11px] text-gray-500">
                  Core rule: &ldquo;No source, no flag.&rdquo; Every objection links directly to proof.
                </span>
              </div>
              <button
                onClick={handleShowDiff}
                className="text-xs bg-gray-100 hover:bg-gray-200 border border-gray-300 px-3 py-1 rounded font-semibold text-gray-800"
              >
                🔍 Side-by-Side Diff
              </button>
            </div>

            {findings.length === 0 ? (
              <div className="p-6 text-center text-xs text-gray-500 bg-gray-50 rounded">
                ✅ Zero compliance or tone objections found! Draft is clean.
              </div>
            ) : (
              <div className="space-y-3">
                {findings.map((f) => (
                  <div
                    key={f.id}
                    className={`p-4 border rounded-md text-xs space-y-2 ${
                      f.severity === "blocker"
                        ? "border-red-200 bg-red-50/30"
                        : f.severity === "warning"
                        ? "border-amber-200 bg-amber-50/30"
                        : "border-gray-200 bg-gray-50/30"
                    }`}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span
                          className={`font-mono font-bold text-[10px] px-1.5 py-0.5 rounded border uppercase ${
                            f.severity === "blocker"
                              ? "bg-red-100 text-red-900 border-red-300"
                              : f.severity === "warning"
                              ? "bg-amber-100 text-amber-900 border-amber-300"
                              : "bg-blue-100 text-blue-900 border-blue-300"
                          }`}
                        >
                          {f.severity}
                        </span>
                        <span className="font-mono font-bold bg-white border border-gray-300 px-2 py-0.5 rounded text-[11px]">
                          Cites: {f.source_ref} (v{f.source_version})
                        </span>
                        <span className="text-[10px] text-gray-400 uppercase font-semibold">
                          Confidence: {f.confidence}
                        </span>
                      </div>

                      <span
                        className={`text-[10px] font-bold uppercase px-2 py-0.5 rounded ${
                          f.status === "accepted"
                            ? "bg-emerald-100 text-emerald-800"
                            : f.status === "dismissed"
                            ? "bg-gray-200 text-gray-700"
                            : "bg-white border text-gray-700"
                        }`}
                      >
                        Status: {f.status}
                      </span>
                    </div>

                    <div className="font-mono text-gray-900 bg-white p-2 border border-gray-200 rounded">
                      &ldquo;{f.quoted_text}&rdquo;
                    </div>

                    <p className="text-gray-700 leading-relaxed">{f.reason}</p>

                    {f.suggestion && (
                      <div className="p-2.5 bg-emerald-50 border border-emerald-200 rounded text-emerald-900">
                        <strong className="block text-[11px] text-emerald-800">Constructive Suggested Fix:</strong>
                        {f.suggestion}
                      </div>
                    )}

                    {f.dismissal_reason && (
                      <p className="text-[11px] text-gray-500 italic">
                        Dismissal Note: &ldquo;{f.dismissal_reason}&rdquo;
                      </p>
                    )}

                    {/* Triage buttons */}
                    <div className="flex items-center gap-2 pt-1 border-t border-gray-200">
                      <button
                        onClick={() => handleTriage(f.id, "accepted")}
                        className="px-2.5 py-1 bg-emerald-600 hover:bg-emerald-700 text-white rounded font-medium text-[11px]"
                      >
                        Accept Fix
                      </button>
                      <button
                        onClick={() => handleTriage(f.id, "dismissed")}
                        className="px-2.5 py-1 bg-gray-100 hover:bg-gray-200 text-gray-800 border border-gray-300 rounded font-medium text-[11px]"
                      >
                        Dismiss Finding...
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Side-by-Side Diff Section */}
          {diffData && (
            <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600">
                Intent Lock & Visual Diff Inspection
              </h3>
              <div className="p-3 bg-gray-50 border border-gray-200 rounded font-mono text-xs leading-relaxed">
                {diffData.diff_tokens?.map((token: any, i: number) => {
                  if (token.type === "insert") {
                    return (
                      <span key={i} className="bg-emerald-200 text-emerald-900 font-bold px-0.5 rounded">
                        {token.text}
                      </span>
                    );
                  }
                  if (token.type === "delete") {
                    return (
                      <span key={i} className="bg-red-200 text-red-900 line-through px-0.5 rounded">
                        {token.text}
                      </span>
                    );
                  }
                  return <span key={i}>{token.text}</span>;
                })}
              </div>

              {diffData.intent_preservation && (
                <div className="p-3 bg-white border border-gray-300 rounded text-xs space-y-1">
                  <div className="flex items-center justify-between font-bold">
                    <span>Message Survival Verdict:</span>
                    <span className={diffData.intent_preservation.intent_preserved ? "text-emerald-700" : "text-red-700"}>
                      {diffData.intent_preservation.intent_preserved ? "✅ INTENT PRESERVED" : "❌ INTENT DILUTED"}
                    </span>
                  </div>
                  <p className="text-gray-600 text-[11px]">{diffData.intent_preservation.details}</p>
                </div>
              )}
            </div>
          )}

          {/* Claim Receipt (Audit Log & Evidence Trail) */}
          {receipt && receipt.receipts?.length > 0 && (
            <div className="bg-white border-2 border-emerald-500 rounded-lg p-5 space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-black text-emerald-900 uppercase tracking-tight">
                  📜 Official Claim Receipt (Approved)
                </h3>
                <span className="text-[10px] font-mono bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded">
                  Immutable Evidence Trail
                </span>
              </div>
              <div className="space-y-2">
                {receipt.receipts.map((r: any) => {
                  const data = r.receipt_data || {};
                  return (
                    <div key={r.id} className="p-3 bg-emerald-50/50 border border-emerald-200 rounded text-xs font-mono space-y-1">
                      <div>Receipt ID: <strong>{data.receipt_id}</strong></div>
                      <div>Claim Audited: &ldquo;{data.claim_quoted_text}&rdquo;</div>
                      <div>Verification Status: <strong>{data.claim_status?.toUpperCase()}</strong></div>
                      <div>Evidence Reference: <strong>{data.source_ref}</strong></div>
                      <div>Sign-off: <strong>{data.approved_by_email}</strong> ({data.approved_by_role}) at {data.approval_timestamp}</div>
                      <div className="text-[11px] text-emerald-800 italic pt-1">
                        Motto: &ldquo;{data.integrity_motto}&rdquo;
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Comments Section */}
          <div className="bg-white border border-gray-300 rounded-lg p-5 space-y-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600">Inline Reviewer Comments</h3>
            <div className="space-y-2">
              {comments.map((cm) => (
                <div key={cm.id} className="p-3 bg-gray-50 border border-gray-200 rounded text-xs space-y-1">
                  <p className="text-gray-900">{cm.text}</p>
                  <span className="text-[10px] text-gray-400">{cm.created_at}</span>
                </div>
              ))}
              {comments.length === 0 && (
                <p className="text-xs text-gray-400">No reviewer comments yet.</p>
              )}
            </div>

            <form onSubmit={handleAddComment} className="flex gap-2">
              <input
                type="text"
                placeholder="Add reviewer feedback or compliance notes..."
                value={newComment}
                onChange={(e) => setNewComment(e.target.value)}
                className="flex-1 p-2 border border-gray-300 rounded text-xs"
              />
              <button type="submit" className="bg-black text-white px-3 py-1.5 rounded text-xs font-bold">
                Comment
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
