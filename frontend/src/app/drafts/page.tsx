"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listDrafts } from "@/lib/api";

export default function DraftsPage() {
  const [drafts, setDrafts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDrafts()
      .then(setDrafts)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-xs flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black text-gray-950 tracking-tight">All Drafts</h1>
          <p className="text-xs text-gray-600 mt-1">Review pipeline and history of audited content.</p>
        </div>
        <Link
          href="/drafts/new"
          className="bg-black hover:bg-gray-800 text-white text-xs font-bold px-4 py-2 rounded transition-colors"
        >
          + New Draft
        </Link>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-gray-500">Loading drafts...</div>
      ) : drafts.length === 0 ? (
        <div className="bg-white border border-gray-300 rounded-lg p-12 text-center space-y-3">
          <p className="text-xs text-gray-500">No drafts created yet.</p>
          <Link
            href="/drafts/new"
            className="inline-block bg-black text-white text-xs font-semibold px-4 py-2 rounded"
          >
            Create Your First Draft
          </Link>
        </div>
      ) : (
        <div className="bg-white border border-gray-300 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-100 border-b border-gray-300 font-semibold text-gray-700">
              <tr>
                <th className="p-3">Channel</th>
                <th className="p-3">Content Preview</th>
                <th className="p-3">Status</th>
                <th className="p-3">Version</th>
                <th className="p-3">Created</th>
                <th className="p-3">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {drafts.map((d) => (
                <tr key={d.id} className="hover:bg-gray-50">
                  <td className="p-3 font-bold uppercase text-gray-900 font-mono text-[11px]">
                    {d.channel || "General"}
                  </td>
                  <td className="p-3 text-gray-600 max-w-xs truncate font-mono">
                    {d.content_preview}
                  </td>
                  <td className="p-3">
                    <span
                      className={`text-[10px] font-bold uppercase px-1.5 py-0.5 rounded border ${
                        d.status === "approved"
                          ? "bg-emerald-50 text-emerald-800 border-emerald-300"
                          : d.status === "review_requested"
                          ? "bg-amber-50 text-amber-800 border-amber-300"
                          : "bg-gray-100 text-gray-800 border-gray-300"
                      }`}
                    >
                      {d.status}
                    </span>
                  </td>
                  <td className="p-3 font-mono font-medium">v{d.latest_version}</td>
                  <td className="p-3 text-gray-400 text-[11px]">{d.created_at?.slice(0, 10)}</td>
                  <td className="p-3">
                    <Link
                      href={`/drafts/${d.id}`}
                      className="text-black font-bold hover:underline font-mono text-[11px]"
                    >
                      Audit & Triage &rarr;
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
