"use client";

import { useState } from "react";
import { usePathname } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { copilotChat, type CopilotMessage } from "@/lib/ai";

interface Props {
  projectId?: string;
}

type Turn = CopilotMessage & { provider?: string };

function projectIdFromPath(pathname: string | null): string | undefined {
  if (!pathname) return undefined;
  const m = pathname.match(/^\/projects\/([0-9a-fA-F-]{36})/);
  return m ? m[1] : undefined;
}

export function CopilotWidget({ projectId }: Props) {
  const pathname = usePathname();
  const inferredProjectId = projectId ?? projectIdFromPath(pathname);
  const [open, setOpen] = useState(false);
  const [turns, setTurns] = useState<Turn[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm DClaw Copilot. Ask me to plan a project, summarize risks, or suggest next actions.",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  async function send() {
    const text = draft.trim();
    if (!text || busy) return;
    setDraft("");
    setBusy(true);
    const userTurn: Turn = { role: "user", content: text };
    const history = [...turns, userTurn];
    setTurns(history);
    try {
      const llmMessages: CopilotMessage[] = history.map((t) => ({
        role: t.role,
        content: t.content,
      }));
      const resp = await copilotChat(llmMessages, inferredProjectId);
      setTurns((prev) => [
        ...prev,
        { role: "assistant", content: resp.text, provider: resp.provider },
      ]);
    } catch (err) {
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `Sorry — Copilot is unavailable right now. (${(err as Error).message})`,
        },
      ]);
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 z-40 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg hover:bg-blue-700"
        aria-label="Open AI Copilot"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={2}
          stroke="currentColor"
          className="h-6 w-6"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9.813 15.904 9 18.75l-.813-2.846a4.5 4.5 0 0 0-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 0 0 3.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 0 0 3.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 0 0-3.09 3.09zM18.259 8.715 18 9.75l-.259-1.035a3.375 3.375 0 0 0-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 0 0 2.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 0 0 2.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 0 0-2.456 2.456zM16.894 20.567 16.5 21.75l-.394-1.183a2.25 2.25 0 0 0-1.423-1.423L13.5 18.75l1.183-.394a2.25 2.25 0 0 0 1.423-1.423l.394-1.183.394 1.183a2.25 2.25 0 0 0 1.423 1.423l1.183.394-1.183.394a2.25 2.25 0 0 0-1.423 1.423z"
          />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-40 flex h-[32rem] w-96 max-w-[calc(100vw-3rem)] flex-col rounded-xl border border-slate-200 bg-white shadow-2xl">
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-slate-800">DClaw Copilot</span>
          {inferredProjectId && (
            <Badge variant="outline" className="text-[10px]">
              Project context
            </Badge>
          )}
        </div>
        <button
          onClick={() => setOpen(false)}
          aria-label="Close Copilot"
          className="text-slate-500 hover:text-slate-800"
        >
          ✕
        </button>
      </div>
      <div className="flex-1 space-y-3 overflow-y-auto px-4 py-3 text-sm">
        {turns.map((t, idx) => (
          <div
            key={idx}
            className={
              t.role === "user"
                ? "ml-auto max-w-[85%] rounded-lg bg-blue-600 px-3 py-2 text-white"
                : "max-w-[85%] rounded-lg bg-slate-100 px-3 py-2 text-slate-800"
            }
          >
            <div className="whitespace-pre-wrap">{t.content}</div>
            {t.role === "assistant" && t.provider && (
              <div className="mt-1 text-[10px] uppercase tracking-wide text-slate-400">
                {t.provider}
              </div>
            )}
          </div>
        ))}
        {busy && (
          <div className="max-w-[85%] rounded-lg bg-slate-100 px-3 py-2 text-slate-500">
            thinking…
          </div>
        )}
      </div>
      <div className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <Input
            placeholder="Ask Copilot…"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
          />
          <Button onClick={send} disabled={!draft.trim() || busy}>
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
