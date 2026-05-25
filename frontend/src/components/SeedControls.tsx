// ─── SEED CONTROLS ────────────────────────────────────────────────────────────
// Demo utility — remove this file and the <SeedControls /> block in
// app/page.tsx (and the seed router in the backend) when no longer needed.
// ──────────────────────────────────────────────────────────────────────────────
"use client";

import { useState } from "react";
import Link from "next/link";
import { seedDemoData, clearDemoData, setAuthToken, type SeedResult } from "@/lib/api";

type Status = "idle" | "loading" | "success" | "error";

export function SeedControls() {
  const [fillStatus, setFillStatus] = useState<Status>("idle");
  const [clearStatus, setClearStatus] = useState<Status>("idle");
  const [result, setResult] = useState<SeedResult | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [isError, setIsError] = useState(false);

  async function handleFill() {
    setFillStatus("loading");
    setMessage(null);
    setIsError(false);
    try {
      const res = await seedDemoData();
      // Drop the visitor straight into the populated demo workspace.
      setAuthToken(res.access_token);
      setResult(res);
      setMessage(
        `Seeded ${res.projects} projects · ${res.tasks} tasks · ${res.milestones} milestones · ${res.comments} comments. You're signed in as the demo user.`
      );
      setFillStatus("success");
    } catch (e) {
      setIsError(true);
      setMessage(e instanceof Error ? e.message : "Seed failed");
      setFillStatus("error");
    }
  }

  async function handleClear() {
    setClearStatus("loading");
    setMessage(null);
    setIsError(false);
    try {
      await clearDemoData();
      setAuthToken(null);
      setResult(null);
      setMessage("All data cleared. App is back to a fresh, empty state.");
      setClearStatus("success");
      setFillStatus("idle");
    } catch (e) {
      setIsError(true);
      setMessage(e instanceof Error ? e.message : "Clear failed");
      setClearStatus("error");
    }
  }

  const busy = fillStatus === "loading" || clearStatus === "loading";
  const fillLabel =
    fillStatus === "loading" ? "Seeding…" : fillStatus === "success" ? "Seeded ✓" : "Fill Seed Data";
  const clearLabel =
    clearStatus === "loading" ? "Clearing…" : clearStatus === "success" ? "Cleared ✓" : "Clear Data";

  return (
    <div className="rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/60 p-6 text-center">
      <p className="font-mono text-xs uppercase tracking-widest text-indigo-500">Demo Controls</p>
      <p className="mt-1 text-sm text-slate-600">
        Populate the app with a realistic demo workspace, or wipe it to start fresh.
      </p>

      <div className="mt-4 flex flex-col justify-center gap-3 sm:flex-row">
        <button
          onClick={handleFill}
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-500 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {fillLabel}
        </button>
        <button
          onClick={handleClear}
          disabled={busy}
          className="rounded-lg border border-slate-300 px-6 py-2.5 text-sm font-semibold text-slate-700 transition-colors hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {clearLabel}
        </button>
      </div>

      {message && (
        <p className={`mt-4 text-xs ${isError ? "text-red-600" : "text-emerald-600"}`}>{message}</p>
      )}

      {result && fillStatus === "success" && (
        <div className="mt-4 space-y-3">
          <Link
            href="/dashboard"
            className="inline-block rounded-lg bg-slate-900 px-6 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-slate-700"
          >
            Open the demo dashboard →
          </Link>
          <p className="font-mono text-xs text-slate-500">
            Demo login · {result.demo_email} / {result.demo_password}
          </p>
        </div>
      )}
    </div>
  );
}
