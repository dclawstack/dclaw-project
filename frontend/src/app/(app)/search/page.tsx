"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { getAuthToken } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

interface Hit {
  entity_type: string;
  entity_id: string;
  content: string;
  score: number;
}

interface AskResponse {
  answer: string;
  citations: { entity_type: string; entity_id: string; score: number }[];
  provider: string;
}

async function authFetch(path: string, init?: RequestInit) {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const resp = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
  return resp.json();
}

export default function SearchPage() {
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"search" | "ask">("search");
  const [hits, setHits] = useState<Hit[]>([]);
  const [answer, setAnswer] = useState<AskResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [indexed, setIndexed] = useState<number | null>(null);

  async function reindex() {
    const r = await authFetch("/api/v1/ai/reindex", { method: "POST" });
    setIndexed(r.chunks);
  }

  async function run() {
    if (!q) return;
    setBusy(true);
    setHits([]);
    setAnswer(null);
    try {
      if (mode === "search") {
        const r = await authFetch(`/api/v1/ai/search?q=${encodeURIComponent(q)}`);
        setHits(r.hits);
      } else {
        const r = await authFetch("/api/v1/ai/ask", {
          method: "POST",
          body: JSON.stringify({ question: q }),
        });
        setAnswer(r);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Project knowledge search</h1>
        <Button variant="outline" onClick={reindex}>
          Rebuild index{indexed !== null ? ` (${indexed} chunks)` : ""}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>
            {mode === "search" ? "Semantic search" : "Grounded Q&A"}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex gap-2">
            <Button
              variant={mode === "search" ? "default" : "outline"}
              onClick={() => setMode("search")}
              size="sm"
            >
              Search
            </Button>
            <Button
              variant={mode === "ask" ? "default" : "outline"}
              onClick={() => setMode("ask")}
              size="sm"
            >
              Ask
            </Button>
          </div>
          <div className="flex gap-2">
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") run();
              }}
              placeholder={
                mode === "search"
                  ? "Find tasks or comments matching..."
                  : "Ask a question grounded in workspace content"
              }
            />
            <Button onClick={run} disabled={!q || busy}>
              {busy ? "..." : "Go"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {mode === "search" && hits.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{hits.length} results</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {hits.map((h) => (
              <div
                key={h.entity_id}
                className="rounded-md border border-slate-200 p-3 text-sm"
              >
                <div className="mb-1 flex items-center gap-2">
                  <Badge variant="outline">{h.entity_type}</Badge>
                  <span className="text-xs text-slate-400">
                    score {h.score.toFixed(3)}
                  </span>
                </div>
                <p className="whitespace-pre-wrap text-slate-700">{h.content}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {mode === "ask" && answer && (
        <Card>
          <CardHeader>
            <CardTitle>Answer</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="whitespace-pre-wrap text-slate-800">{answer.answer}</p>
            {answer.citations.length > 0 && (
              <div className="text-xs text-slate-500">
                Citations:{" "}
                {answer.citations.map((c) => (
                  <Badge key={c.entity_id} variant="outline" className="mr-1">
                    {c.entity_type}
                  </Badge>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-400">via {answer.provider}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
