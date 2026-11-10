"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { healthCheck, seedSources } from "@/lib/api";

export default function HomePage() {
  const [health, setHealth] = useState<any>(null);
  const [seeding, setSeeding] = useState(false);
  const [seedResult, setSeedResult] = useState<string | null>(null);

  useEffect(() => {
    healthCheck()
      .then(setHealth)
      .catch((err) => setHealth({ status: "offline", error: err.message }));
  }, []);

  const handleSeed = async () => {
    setSeeding(true);
    setSeedResult(null);
    try {
      const res = await seedSources();
      setSeedResult(`Seeded successfully! Guidelines: ${res.guidelines}, Facts: ${res.facts}, Terms: ${res.terms}`);
    } catch (e: any) {
      setSeedResult("Error: " + e.message);
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto space-y-8">
      {/* Hero */}
      <section className="bg-white border border-gray-300 rounded-lg p-8 shadow-xs">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="inline-block bg-black text-white text-xs font-mono px-2.5 py-0.5 rounded font-bold">
              ROUND 2 TESTING CONSOLE
            </div>
            <h1 className="text-3xl font-black text-gray-950 tracking-tight">
              ProofLine Brand Governance Platform
            </h1>
            <p className="text-gray-600 text-base max-w-2xl leading-relaxed">
              Every marketing and brand claim linked to its verified source of truth.
              Strictly enforces the design tenet: <strong className="text-gray-900">&ldquo;No source, no flag.&rdquo;</strong>
            </p>
          </div>
          <div className="bg-gray-50 border border-gray-200 p-4 rounded-md min-w-[220px] text-xs space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-gray-500">Backend API:</span>
              <span
                className={`font-mono font-bold px-2 py-0.5 rounded ${
                  health?.status === "ok"
                    ? "bg-emerald-100 text-emerald-800"
                    : "bg-red-100 text-red-800"
                }`}
              >
                {health?.status === "ok" ? "LIVE :8000" : "OFFLINE"}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-gray-500">AI Engine:</span>
              <span className="font-semibold text-gray-800 font-mono">Groq LLaMA/GPT-120B</span>
            </div>
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="w-full mt-2 bg-gray-900 hover:bg-black text-white text-xs font-medium py-1.5 px-3 rounded transition-colors"
            >
              {seeding ? "Seeding..." : "⚡ Seed Demo Brand Data"}
            </button>
            {seedResult && (
              <p className="text-[11px] text-gray-700 bg-white p-1.5 border border-gray-200 rounded">
                {seedResult}
              </p>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-8 pt-6 border-t border-gray-200">
          <Link
            href="/drafts/new"
            className="flex flex-col justify-between p-4 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded transition-colors group"
          >
            <div>
              <span className="text-xs font-mono font-bold text-gray-500">TEST FLOW 01</span>
              <h3 className="font-bold text-gray-900 text-base group-hover:text-black">
                Submit & Audit Draft &rarr;
              </h3>
              <p className="text-xs text-gray-600 mt-1">
                Paste copy, upload PDF/DOCX, test Intent Lock, and run the 4-layer AI engine.
              </p>
            </div>
          </Link>

          <Link
            href="/review-queue"
            className="flex flex-col justify-between p-4 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded transition-colors group"
          >
            <div>
              <span className="text-xs font-mono font-bold text-gray-500">TEST FLOW 02</span>
              <h3 className="font-bold text-gray-900 text-base group-hover:text-black">
                Review Queue & Approval &rarr;
              </h3>
              <p className="text-xs text-gray-600 mt-1">
                Risk-tier assessment (Level 1/2/3), inline reviewer comments, and Claim Receipts.
              </p>
            </div>
          </Link>

          <Link
            href="/insights"
            className="flex flex-col justify-between p-4 bg-gray-50 hover:bg-gray-100 border border-gray-300 rounded transition-colors group"
          >
            <div>
              <span className="text-xs font-mono font-bold text-gray-500">TEST FLOW 03</span>
              <h3 className="font-bold text-gray-900 text-base group-hover:text-black">
                Guideline Health & Analytics &rarr;
              </h3>
              <p className="text-xs text-gray-600 mt-1">
                Identify which rules creators dismiss most frequently and track health scores.
              </p>
            </div>
          </Link>
        </div>
      </section>

      {/* 4-Layer Architecture Checklist for Testers */}
      <section className="bg-white border border-gray-300 rounded-lg p-6 space-y-4">
        <h2 className="text-lg font-bold text-gray-900 border-b border-gray-200 pb-2">
          Architecture Checklist (Round 2 Deliverables)
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
          <div className="border border-gray-200 p-3.5 rounded bg-gray-50 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-blue-600"></span>
              <h4 className="font-bold text-gray-900">Layer 1: Deterministic Engine</h4>
            </div>
            <p className="text-gray-600">
              Regex matching for banned terms (e.g. <code className="bg-white px-1 border rounded">java</code>),
              preferred term substitutions, and Flesch-Kincaid readability scoring via textstat.
            </p>
          </div>

          <div className="border border-gray-200 p-3.5 rounded bg-gray-50 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-purple-600"></span>
              <h4 className="font-bold text-gray-900">Layer 2: Claim Ledger</h4>
            </div>
            <p className="text-gray-600">
              Extracts atomic factual claims and benchmarks against approved records. Detects contradictions
              (e.g. 500 vs 127 stores) and expired citation dates.
            </p>
          </div>

          <div className="border border-gray-200 p-3.5 rounded bg-gray-50 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-600"></span>
              <h4 className="font-bold text-gray-900">Layer 3: Grounded AI Tone (Groq)</h4>
            </div>
            <p className="text-gray-600">
              Audits against active rules (<code className="bg-white px-1 border rounded">TONE-01</code> health claims,
              <code className="bg-white px-1 border rounded">TONE-02</code> sales pressure) using your live Groq LLM.
            </p>
          </div>

          <div className="border border-gray-200 p-3.5 rounded bg-gray-50 space-y-1.5">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
              <h4 className="font-bold text-gray-900">Layer 4: Source Validator</h4>
            </div>
            <p className="text-gray-600">
              Strictly enforces <em>&ldquo;No source, no flag.&rdquo;</em> Strips any hallucinated or ungrounded objections
              lacking an indexed corporate source citation.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
