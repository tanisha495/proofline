"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { login } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/drafts");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  const quickLogin = async (role: string) => {
    setLoading(true);
    setError(null);
    try {
      await login(`${role}@proofline.ai`, `${role}12345`);
      router.push("/drafts");
    } catch (err: any) {
      setError(err.message || "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-md mx-auto my-12 bg-white border border-gray-300 rounded-lg p-8 shadow-xs">
      <h1 className="text-2xl font-black text-gray-900 tracking-tight">Sign In to ProofLine</h1>
      <p className="text-xs text-gray-500 mt-1">Select a role to test role-based permissions.</p>

      {error && (
        <div className="mt-4 p-2.5 bg-red-50 border border-red-200 rounded text-red-700 text-xs">
          {error}
        </div>
      )}

      {/* One-Click Role Testers */}
      <div className="mt-6 pt-4 border-t border-gray-200 space-y-2">
        <label className="text-xs font-bold text-gray-600 uppercase tracking-wider block">
          One-Click Demo Roles
        </label>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <button
            type="button"
            onClick={() => quickLogin("creator")}
            disabled={loading}
            className="p-2 border border-gray-300 rounded hover:bg-gray-100 font-medium text-left"
          >
            ✏️ <strong>Creator</strong>
            <span className="block text-[10px] text-gray-500">Drafts & triage</span>
          </button>
          <button
            type="button"
            onClick={() => quickLogin("reviewer")}
            disabled={loading}
            className="p-2 border border-gray-300 rounded hover:bg-gray-100 font-medium text-left"
          >
            ⚖️ <strong>Reviewer</strong>
            <span className="block text-[10px] text-gray-500">Legal/compliance sign-off</span>
          </button>
          <button
            type="button"
            onClick={() => quickLogin("manager")}
            disabled={loading}
            className="p-2 border border-gray-300 rounded hover:bg-gray-100 font-medium text-left"
          >
            👔 <strong>Manager</strong>
            <span className="block text-[10px] text-gray-500">Department approvals</span>
          </button>
          <button
            type="button"
            onClick={() => quickLogin("admin")}
            disabled={loading}
            className="p-2 border border-gray-300 rounded hover:bg-gray-100 font-medium text-left"
          >
            🛠️ <strong>Admin</strong>
            <span className="block text-[10px] text-gray-500">Manage sources & rules</span>
          </button>
        </div>
      </div>

      <div className="relative my-6 text-center text-xs text-gray-400">
        <span className="bg-white px-2 relative z-10">or manual credentials</span>
        <div className="absolute inset-0 flex items-center">
          <div className="w-full border-t border-gray-200"></div>
        </div>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4 text-xs">
        <div>
          <label className="block font-medium text-gray-700 mb-1">Email</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            placeholder="creator@proofline.ai"
            className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-black"
          />
        </div>
        <div>
          <label className="block font-medium text-gray-700 mb-1">Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            placeholder="creator12345"
            className="w-full px-3 py-2 border border-gray-300 rounded focus:outline-black"
          />
        </div>
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-black text-white py-2 rounded font-semibold hover:bg-gray-800 disabled:opacity-50"
        >
          {loading ? "Authenticating..." : "Sign In"}
        </button>
      </form>
    </div>
  );
}
