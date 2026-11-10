"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { clearToken, getCurrentUser, login } from "@/lib/api";

const navLinks = [
  { href: "/drafts/new", label: "New Draft & Audit" },
  { href: "/drafts", label: "All Drafts" },
  { href: "/review-queue", label: "Review Queue" },
  { href: "/sources", label: "Brand Sources" },
  { href: "/insights", label: "Guideline Health" },
];

export default function Navbar() {
  const [user, setUser] = useState<any>(null);
  const [switching, setSwitching] = useState(false);

  useEffect(() => {
    setUser(getCurrentUser());
  }, []);

  const handleQuickSwitch = async (role: string) => {
    setSwitching(true);
    try {
      const email = `${role}@proofline.ai`;
      const pass = `${role}12345`;
      const me = await login(email, pass);
      setUser(me);
      window.location.reload();
    } catch (e: any) {
      alert("Failed to switch role: " + e.message);
    } finally {
      setSwitching(false);
    }
  };

  const handleLogout = () => {
    clearToken();
    setUser(null);
    window.location.href = "/login";
  };

  return (
    <header className="bg-white border-b border-gray-300 px-6 py-3 sticky top-0 z-50 shadow-xs">
      <div className="max-w-7xl mx-auto flex flex-wrap items-center justify-between gap-4">
        {/* Brand */}
        <div className="flex items-center gap-3">
          <Link href="/" className="flex items-center gap-2">
            <span className="text-xl font-black tracking-tight text-gray-900 border-2 border-black px-2 py-0.5 rounded">
              ProofLine
            </span>
          </Link>
          <span className="text-xs bg-gray-100 text-gray-700 font-medium px-2 py-0.5 rounded border border-gray-200">
            Pre-Publication Governance
          </span>
        </div>

        {/* Links */}
        <nav className="flex items-center gap-1 sm:gap-2 text-sm font-medium">
          {navLinks.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="px-3 py-1.5 rounded text-gray-700 hover:text-black hover:bg-gray-100 transition-colors"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        {/* Role & Auth */}
        <div className="flex items-center gap-2 text-xs">
          {user ? (
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded px-2.5 py-1">
              <span className="text-gray-500">Active:</span>
              <span className="font-semibold text-gray-900">{user.email}</span>
              <span className="uppercase font-bold bg-black text-white px-1.5 py-0.5 rounded text-[10px]">
                {user.role}
              </span>
              <button
                onClick={handleLogout}
                className="text-gray-400 hover:text-red-600 ml-1 font-medium underline"
              >
                Logout
              </button>
            </div>
          ) : (
            <Link
              href="/login"
              className="px-3 py-1 bg-black text-white rounded font-medium hover:bg-gray-800"
            >
              Sign In
            </Link>
          )}

          {/* Quick role switcher for testing */}
          <div className="hidden lg:flex items-center gap-1 pl-2 border-l border-gray-300">
            <span className="text-gray-400">Quick Test:</span>
            <button
              onClick={() => handleQuickSwitch("creator")}
              disabled={switching}
              className="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded font-mono text-[11px]"
            >
              Creator
            </button>
            <button
              onClick={() => handleQuickSwitch("reviewer")}
              disabled={switching}
              className="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded font-mono text-[11px]"
            >
              Reviewer
            </button>
            <button
              onClick={() => handleQuickSwitch("admin")}
              disabled={switching}
              className="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded font-mono text-[11px]"
            >
              Admin
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
