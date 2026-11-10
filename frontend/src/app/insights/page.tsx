"use client";

import { useEffect, useState } from "react";
import { getRuleInsights } from "@/lib/api";

export default function InsightsPage() {
  const [insights, setInsights] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRuleInsights()
      .then(setInsights)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-xs">
        <h1 className="text-2xl font-black text-gray-950 tracking-tight">Guideline Health & Analytics</h1>
        <p className="text-xs text-gray-600 mt-1">
          Identifies confusing, obsolete, or overly restrictive brand guidelines by monitoring creator dismissals and overrides.
        </p>

        <div className="mt-4 p-3 bg-gray-50 border border-gray-200 rounded text-xs text-gray-600 space-y-1">
          <strong className="text-gray-900 block font-semibold">How Guideline Health Scoring Works:</strong>
          <p>
            When creators frequently dismiss a rule (e.g. creative exceptions, false positives), the rule&apos;s
            Health Score drops. Admins use this feedback loop to revise unclear guidelines into newer versions.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="p-12 text-center text-xs text-gray-500">Loading rule health metrics...</div>
      ) : insights.length === 0 ? (
        <div className="bg-white border border-gray-300 rounded-lg p-12 text-center space-y-2">
          <p className="text-xs text-gray-500">No rule triggers recorded yet.</p>
          <p className="text-[11px] text-gray-400">
            Audit some drafts and accept/dismiss findings to generate guideline health analytics.
          </p>
        </div>
      ) : (
        <div className="bg-white border border-gray-300 rounded-lg overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead className="bg-gray-100 border-b border-gray-300 font-semibold text-gray-700">
              <tr>
                <th className="p-3">Rule ID</th>
                <th className="p-3">Total Triggers</th>
                <th className="p-3">Dismissals</th>
                <th className="p-3">Acceptance Rate</th>
                <th className="p-3">Guideline Health Score</th>
                <th className="p-3">Admin Recommendation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {insights.map((item) => {
                const score = item.health_score ?? 100;
                let badgeClass = "bg-emerald-50 text-emerald-800 border-emerald-300";
                let rec = "Healthy brand rule";
                if (score < 60) {
                  badgeClass = "bg-red-50 text-red-800 border-red-300 font-bold";
                  rec = "High friction: rule needs revision";
                } else if (score < 85) {
                  badgeClass = "bg-amber-50 text-amber-800 border-amber-300 font-bold";
                  rec = "Moderate friction: monitor feedback";
                }

                return (
                  <tr key={item.rule_id} className="hover:bg-gray-50">
                    <td className="p-3 font-mono font-bold text-gray-900">{item.rule_id}</td>
                    <td className="p-3 font-mono">{item.trigger_count}</td>
                    <td className="p-3 font-mono text-gray-600">{item.dismissal_count ?? 0}</td>
                    <td className="p-3 font-mono font-bold text-gray-800">
                      {Math.round((item.acceptance_rate ?? 1.0) * 100)}%
                    </td>
                    <td className="p-3">
                      <span className={`px-2 py-0.5 rounded border text-[11px] ${badgeClass}`}>
                        {score} / 100
                      </span>
                    </td>
                    <td className="p-3 text-gray-600 font-medium">{rec}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
