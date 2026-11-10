"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { createDraft, reviewDraft } from "@/lib/api";

const sampleViolations =
  "Grab a hot cup of fresh java! Our artisanal roast cures all morning fatigue completely. We now operate 500 retail locations across the country. ACT NOW BEFORE SUPPLIES RUN OUT!";

const sampleCompliant =
  "Welcome to Northwind Coffee. Founded in 1985 in Portland, Oregon, our passion is crafting balanced, nuanced roasts for your morning ritual. We now proudly serve guests across 127 retail locations nationwide. Explore our freshly roasted beans and enjoy a peaceful brew.";

export default function NewDraftPage() {
  const router = useRouter();
  const [content, setContent] = useState("");
  const [channel, setChannel] = useState("instagram_post");
  const [keyMessage, setKeyMessage] = useState("premium morning coffee");
  const [audience, setAudience] = useState("coffee lovers & commuters");
  const [cta, setCta] = useState("explore our roast online");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim() && !uploadFile) {
      setError("Please paste copy or select a file to upload.");
      return;
    }

    setSubmitting(true);
    setError(null);

    try {
      let draftId = "";

      if (uploadFile) {
        // Upload file via multipart/form-data
        const formData = new FormData();
        formData.append("file", uploadFile);
        formData.append("channel", channel);

        const res = await fetch("http://localhost:8000/drafts/upload", {
          method: "POST",
          body: formData,
        });
        if (!res.ok) {
          throw new Error("Failed to upload document");
        }
        const data = await res.json();
        draftId = data.id;
      } else {
        // Direct text creation with Intent Lock
        const draft = await createDraft({
          content,
          channel,
          intent_lock: {
            key_message: keyMessage,
            audience,
            call_to_action: cta,
          },
        });
        draftId = draft.id;
      }

      // Automatically trigger 4-layer review engine
      await reviewDraft(draftId);

      // Redirect to review & triage page
      router.push(`/drafts/${draftId}`);
    } catch (err: any) {
      setError(err.message || "Failed to create or audit draft.");
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="bg-white border border-gray-300 rounded-lg p-6 shadow-xs">
        <h1 className="text-2xl font-black text-gray-950 tracking-tight">New Draft & Pre-Publication Audit</h1>
        <p className="text-xs text-gray-600 mt-1">
          Submit copy to run through the 4-layer verification engine (Deterministic &rarr; Claim Ledger &rarr; Tone AI &rarr; Validator).
        </p>

        {error && (
          <div className="mt-4 p-3 bg-red-50 border border-red-200 text-red-700 text-xs rounded">
            {error}
          </div>
        )}

        {/* Quick Pre-fill Templates */}
        <div className="mt-4 pt-4 border-t border-gray-200 flex flex-wrap items-center gap-2 text-xs">
          <span className="text-gray-500 font-medium">Quick Test Templates:</span>
          <button
            type="button"
            onClick={() => setContent(sampleViolations)}
            className="px-2.5 py-1 bg-amber-50 hover:bg-amber-100 border border-amber-300 rounded text-amber-900 font-semibold"
          >
            ⚡ Load Draft with Planted Violations (Java, 500 stores, cures)
          </button>
          <button
            type="button"
            onClick={() => setContent(sampleCompliant)}
            className="px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 border border-emerald-300 rounded text-emerald-900 font-semibold"
          >
            ✅ Load Compliant Draft (127 stores)
          </button>
        </div>

        <form onSubmit={handleSubmit} className="mt-6 space-y-5 text-xs">
          {/* Channel */}
          <div>
            <label className="block font-bold text-gray-700 mb-1">Publishing Channel</label>
            <select
              value={channel}
              onChange={(e) => setChannel(e.target.value)}
              className="w-full sm:w-72 px-3 py-2 border border-gray-300 rounded bg-white text-xs"
            >
              <option value="instagram_post">Instagram / Social Post</option>
              <option value="press_release">Press Release</option>
              <option value="email_newsletter">Email Newsletter</option>
              <option value="blog_post">Blog Article</option>
              <option value="pitch_deck">Investor / Product Deck</option>
            </select>
          </div>

          {/* Text Area */}
          <div>
            <label className="block font-bold text-gray-700 mb-1">Draft Content (Paste Copy)</label>
            <textarea
              rows={6}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Paste your marketing copy or draft text here..."
              className="w-full p-3 border border-gray-300 rounded focus:outline-black text-xs font-mono"
            />
          </div>

          {/* Document Upload */}
          <div className="p-3 bg-gray-50 border border-gray-200 rounded space-y-1">
            <label className="block font-bold text-gray-700">Or Upload Document (.pdf, .docx, .txt)</label>
            <input
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
              className="text-xs text-gray-600"
            />
            {uploadFile && (
              <p className="text-[11px] text-emerald-700 font-medium">Selected: {uploadFile.name}</p>
            )}
          </div>

          {/* Intent Lock Section */}
          <div className="border border-gray-200 rounded-lg p-4 bg-gray-50 space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-gray-900 text-xs">🔒 Intent Lock Parameters</h4>
                <p className="text-[11px] text-gray-500">
                  ProofLine verifies that AI suggestions preserve your core message, audience tone, and CTA.
                </p>
              </div>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">Key Message to Protect</label>
                <input
                  type="text"
                  value={keyMessage}
                  onChange={(e) => setKeyMessage(e.target.value)}
                  placeholder="e.g. morning roast coffee"
                  className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">Target Audience</label>
                <input
                  type="text"
                  value={audience}
                  onChange={(e) => setAudience(e.target.value)}
                  placeholder="e.g. coffee enthusiasts"
                  className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-gray-600 mb-1">Call to Action (CTA)</label>
                <input
                  type="text"
                  value={cta}
                  onChange={(e) => setCta(e.target.value)}
                  placeholder="e.g. order roast online"
                  className="w-full p-2 border border-gray-300 rounded bg-white text-xs"
                />
              </div>
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={submitting}
            className="w-full bg-black text-white py-3 rounded-md font-bold text-sm hover:bg-gray-800 transition-colors disabled:opacity-50"
          >
            {submitting ? "Analyzing with Groq AI Review Engine..." : "🛡️ Save Draft & Run Pre-Publication Audit"}
          </button>
        </form>
      </div>
    </div>
  );
}
