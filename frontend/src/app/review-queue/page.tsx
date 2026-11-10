"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listDrafts } from "@/lib/api";

export default function ReviewQueuePage() {
  const [drafts, setDrafts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDrafts()
      .then((data) => setDrafts(data.filter((d) => d.status === "review_requested" || d.status === "reviewed")))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-xs">
        <h1 className="text-2xl font-black text-gray-950 tracking-tight">Reviewer Approval Queue</h1>
        <p className="text-xs text-gray-600 mt-1">
          Role-Based Governance Matrix: content is quarantined until verified by authorized compliance officers.
        </p>

        {/* Risk-Tier Legend */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-4 pt-4 border-t border-gray-200 text-xs">
          <div className="border border-red-200 bg-red-50 p-2.5 rounded">
            <span className="font-bold text-red-900 block">Level 3: High Risk</span>
            <span className="text-[11px] text-red-700">Blockers, pricing or health claims &rarr; Legal / Senior Reviewer</span>
          </div>
          <div className="border border-amber-200 bg-amber-50 p-2.5 rounded">
            <span className="font-bold text-amber-900 block">Level 2: Medium Risk</span>
            <span className="text-[11px] text-amber-700">Promo copy, warnings &rarr; Department Manager</span>
          </div>
          <div className="border border-emerald-200 bg-emerald-50 p-2.5 rounded">
            <span className="font-bold text-emerald-900 block">Level 1: Low Risk</span>
            <span className="text-[11px] text-emerald-700">Minor grammar & phrasing &rarr; Creator quick sign-off</span>
          </div>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-gray-500">Loading queue...</div>
      ) : drafts.length === 0 ? (
        <div className="bg-white border border-gray-300 rounded-lg p-12 text-center space-y-2">
          <p className="text-xs text-gray-500">No drafts currently awaiting review.</p>
          <p className="text-[11px] text-gray-400">
            Submit a draft from &ldquo;New Draft&rdquo; and click &ldquo;Submit for Review&rdquo; to populate this queue.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-300 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-100 border-b border-gray-300 font-semibold text-gray-700">
              <tr>
                <th className="p-3">Draft ID</th>
                <th className="p-3">Channel</th>
                <th className="p-3">Preview</th>
                <th className="p-3">Status</th>
                <th className="p-3">Review Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {drafts.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="p-3 font-mono font-bold text-gray-900">{d.id.slice(0, 8)}...</td>
                  <td className="p-3 uppercase font-semibold text-gray-700">{d.channel || "General"}</td>
                  <td className="p-3 text-gray-600 max-w-sm truncate font-mono">{d.content_preview}</td>
                  <td className="p-3">
                    <span className="bg-amber-100 text-amber-900 border border-amber-300 font-bold uppercase text-[10px] px-1.5 py-0.5 rounded">
                      {d.status}
                    </span>
                  </td>
                  <td className="p-3">
                    <Link
                      href={`/drafts/${d.id}`}
                      className="bg-black text-white hover:bg-gray-800 text-[11px] font-bold px-3 py-1 rounded inline-block"
                    >
                      Audit & Approve &rarr;
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
