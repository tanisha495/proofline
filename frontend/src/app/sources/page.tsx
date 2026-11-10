"use client";

import { useEffect, useState } from "react";
import { createFact, createGuideline, createTerm, getSources, seedSources } from "@/lib/api";

export default function SourcesPage() {
  const [sources, setSources] = useState<any>({ guidelines: [], facts: [], terms: [] });
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<"guidelines" | "facts" | "terms">("guidelines");

  // Form states
  const [newRule, setNewRule] = useState({ rule_id: "", text: "", category: "Tone" });
  const [newFact, setNewFact] = useState({ statement: "", value: "", owner: "Ops", source: "", expires_on: "" });
  const [newTerm, setNewTerm] = useState({ term: "", preferred: "", banned: false, notes: "" });
  const [message, setMessage] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const data = await getSources();
      setSources(data);
    } catch (err: any) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSeed = async () => {
    try {
      await seedSources();
      setMessage("Sample data seeded successfully!");
      loadData();
    } catch (e: any) {
      setMessage("Error seeding: " + e.message);
    }
  };

  const handleAddGuideline = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createGuideline(newRule);
      setNewRule({ rule_id: "", text: "", category: "Tone" });
      setMessage("Guideline rule added!");
      loadData();
    } catch (e: any) {
      setMessage("Error: " + e.message);
    }
  };

  const handleAddFact = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createFact(newFact);
      setNewFact({ statement: "", value: "", owner: "Ops", source: "", expires_on: "" });
      setMessage("Approved fact added!");
      loadData();
    } catch (e: any) {
      setMessage("Error: " + e.message);
    }
  };

  const handleAddTerm = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await createTerm(newTerm);
      setNewTerm({ term: "", preferred: "", banned: false, notes: "" });
      setMessage("Terminology added!");
      loadData();
    } catch (e: any) {
      setMessage("Error: " + e.message);
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="bg-white border border-gray-300 rounded-lg p-6 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-black text-gray-950 tracking-tight">Brand Source of Truth</h1>
          <p className="text-xs text-gray-600 mt-1">
            Rules, approved corporate facts, and terminology indexed by the review engine.
          </p>
        </div>
        <button
          onClick={handleSeed}
          className="bg-black hover:bg-gray-800 text-white text-xs font-semibold px-4 py-2 rounded transition-colors"
        >
          ⚡ Re-seed Defaults
        </button>
      </div>

      {message && (
        <div className="p-3 bg-gray-100 border border-gray-300 text-xs rounded text-gray-900 font-medium">
          {message}
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex border-b border-gray-300 text-xs font-semibold">
        <button
          onClick={() => setActiveTab("guidelines")}
          className={`px-4 py-2.5 border-b-2 transition-colors ${
            activeTab === "guidelines"
              ? "border-black text-black bg-white"
              : "border-transparent text-gray-500 hover:text-black"
          }`}
        >
          Brand Guidelines ({sources.guidelines?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("facts")}
          className={`px-4 py-2.5 border-b-2 transition-colors ${
            activeTab === "facts"
              ? "border-black text-black bg-white"
              : "border-transparent text-gray-500 hover:text-black"
          }`}
        >
          Approved Facts ({sources.facts?.length || 0})
        </button>
        <button
          onClick={() => setActiveTab("terms")}
          className={`px-4 py-2.5 border-b-2 transition-colors ${
            activeTab === "terms"
              ? "border-black text-black bg-white"
              : "border-transparent text-gray-500 hover:text-black"
          }`}
        >
          Terminology ({sources.terms?.length || 0})
        </button>
      </div>

      {/* Tab 1: Guidelines */}
      {activeTab === "guidelines" && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-300 rounded-lg p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-3">Add Guideline Rule</h3>
            <form onSubmit={handleAddGuideline} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <input
                  type="text"
                  placeholder="Rule ID (e.g. TONE-03)"
                  value={newRule.rule_id}
                  onChange={(e) => setNewRule({ ...newRule, rule_id: e.target.value })}
                  required
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div>
                <input
                  type="text"
                  placeholder="Category (e.g. Social, Legal)"
                  value={newRule.category}
                  onChange={(e) => setNewRule({ ...newRule, category: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div className="sm:col-span-2 flex gap-2">
                <input
                  type="text"
                  placeholder="Rule specification text..."
                  value={newRule.text}
                  onChange={(e) => setNewRule({ ...newRule, text: e.target.value })}
                  required
                  className="flex-1 px-2.5 py-1.5 border border-gray-300 rounded"
                />
                <button type="submit" className="bg-black text-white px-3 py-1.5 rounded font-medium">
                  Add Rule
                </button>
              </div>
            </form>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {sources.guidelines?.map((g: any) => (
              <div key={g.id} className="bg-white border border-gray-300 rounded p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-xs bg-gray-100 border border-gray-300 px-2 py-0.5 rounded">
                    {g.rule_id}
                  </span>
                  <span className="text-[11px] text-gray-500 font-medium">v{g.version} · {g.category}</span>
                </div>
                <p className="text-xs text-gray-800 leading-relaxed">{g.text}</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Tab 2: Facts */}
      {activeTab === "facts" && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-300 rounded-lg p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-3">Add Approved Fact</h3>
            <form onSubmit={handleAddFact} className="grid grid-cols-1 sm:grid-cols-5 gap-3 text-xs">
              <div className="sm:col-span-2">
                <input
                  type="text"
                  placeholder="Statement (e.g. Number of retail locations)"
                  value={newFact.statement}
                  onChange={(e) => setNewFact({ ...newFact, statement: e.target.value })}
                  required
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div>
                <input
                  type="text"
                  placeholder="Approved Value (e.g. 127)"
                  value={newFact.value}
                  onChange={(e) => setNewFact({ ...newFact, value: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div>
                <input
                  type="date"
                  placeholder="Expires On"
                  value={newFact.expires_on}
                  onChange={(e) => setNewFact({ ...newFact, expires_on: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div>
                <button type="submit" className="w-full bg-black text-white py-1.5 rounded font-medium">
                  Add Fact
                </button>
              </div>
            </form>
          </div>

          <div className="bg-white border border-gray-300 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-100 border-b border-gray-300 font-semibold text-gray-700">
                <tr>
                  <th className="p-3">Fact Statement</th>
                  <th className="p-3">Approved Value</th>
                  <th className="p-3">Source & Owner</th>
                  <th className="p-3">Expires On</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {sources.facts?.map((f: any) => {
                  const isExpired = f.expires_on && new Date(f.expires_on) < new Date();
                  return (
                    <tr key={f.id} className="hover:bg-gray-50">
                      <td className="p-3 font-semibold text-gray-900">{f.statement}</td>
                      <td className="p-3 font-mono font-bold text-gray-800">{f.value || "—"}</td>
                      <td className="p-3 text-gray-600">{f.source} ({f.owner})</td>
                      <td className="p-3 font-mono">
                        {f.expires_on ? (
                          <span className={`px-1.5 py-0.5 rounded border text-[11px] ${
                            isExpired ? "bg-red-50 text-red-800 border-red-200 font-bold" : "bg-gray-50 border-gray-300"
                          }`}>
                            {f.expires_on} {isExpired && "⚠️ EXPIRED"}
                          </span>
                        ) : (
                          "Never"
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Terminology */}
      {activeTab === "terms" && (
        <div className="space-y-6">
          <div className="bg-white border border-gray-300 rounded-lg p-4">
            <h3 className="text-xs font-bold uppercase tracking-wider text-gray-600 mb-3">Add Brand Term</h3>
            <form onSubmit={handleAddTerm} className="grid grid-cols-1 sm:grid-cols-4 gap-3 text-xs">
              <div>
                <input
                  type="text"
                  placeholder="Term (e.g. java)"
                  value={newTerm.term}
                  onChange={(e) => setNewTerm({ ...newTerm, term: e.target.value })}
                  required
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div>
                <input
                  type="text"
                  placeholder="Preferred Alternative"
                  value={newTerm.preferred}
                  onChange={(e) => setNewTerm({ ...newTerm, preferred: e.target.value })}
                  className="w-full px-2.5 py-1.5 border border-gray-300 rounded"
                />
              </div>
              <div className="flex items-center gap-2">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={newTerm.banned}
                    onChange={(e) => setNewTerm({ ...newTerm, banned: e.target.checked })}
                    className="rounded border-gray-300"
                  />
                  <span>Banned Term (Blocker)</span>
                </label>
              </div>
              <div>
                <button type="submit" className="w-full bg-black text-white py-1.5 rounded font-medium">
                  Add Term
                </button>
              </div>
            </form>
          </div>

          <div className="bg-white border border-gray-300 rounded-lg overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-100 border-b border-gray-300 font-semibold text-gray-700">
                <tr>
                  <th className="p-3">Brand Term</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Preferred Substitution</th>
                  <th className="p-3">Usage Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {sources.terms?.map((t: any) => (
                  <tr key={t.id} className="hover:bg-gray-50">
                    <td className="p-3 font-mono font-bold text-gray-900">{t.term}</td>
                    <td className="p-3">
                      {t.banned ? (
                        <span className="bg-red-100 text-red-800 border border-red-300 px-1.5 py-0.5 rounded text-[10px] font-bold">
                          BANNED
                        </span>
                      ) : (
                        <span className="bg-gray-100 text-gray-700 border border-gray-300 px-1.5 py-0.5 rounded text-[10px]">
                          RESTRICTED
                        </span>
                      )}
                    </td>
                    <td className="p-3 text-emerald-800 font-medium">{t.preferred || "—"}</td>
                    <td className="p-3 text-gray-500">{t.notes || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
