"use client";

import { useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { generateWBS, type GenerateWBSResponse } from "@/lib/ai";

const priorityColors: Record<string, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-orange-100 text-orange-600",
  urgent: "bg-red-100 text-red-600",
};

export default function PlanPage() {
  const [form, setForm] = useState({
    goal: "",
    deadline_days: 30,
    team_size: 3,
    project_name: "",
    owner: "",
  });
  const [result, setResult] = useState<GenerateWBSResponse | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate() {
    if (!form.goal || !form.project_name || !form.owner) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await generateWBS(form);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">AI Planner</h1>
        <p className="mt-1 text-sm text-slate-500">
          Describe a goal and DClaw Copilot will produce a full project plan in seconds.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Generate a plan</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="goal">Project goal</Label>
            <Input
              id="goal"
              value={form.goal}
              onChange={(e) => setForm({ ...form, goal: e.target.value })}
              placeholder="e.g. Launch a mobile time-tracking app in 3 weeks"
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label htmlFor="project_name">New project name</Label>
              <Input
                id="project_name"
                value={form.project_name}
                onChange={(e) => setForm({ ...form, project_name: e.target.value })}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="owner">Owner</Label>
              <Input
                id="owner"
                value={form.owner}
                onChange={(e) => setForm({ ...form, owner: e.target.value })}
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label htmlFor="deadline_days">Deadline (days)</Label>
              <Input
                id="deadline_days"
                type="number"
                min={1}
                max={365}
                value={form.deadline_days}
                onChange={(e) =>
                  setForm({ ...form, deadline_days: Number(e.target.value) || 1 })
                }
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="team_size">Team size</Label>
              <Input
                id="team_size"
                type="number"
                min={1}
                max={100}
                value={form.team_size}
                onChange={(e) =>
                  setForm({ ...form, team_size: Number(e.target.value) || 1 })
                }
              />
            </div>
          </div>
          <Button
            onClick={handleGenerate}
            disabled={busy || !form.goal || !form.project_name || !form.owner}
          >
            {busy ? "Generating…" : "Generate plan ✨"}
          </Button>
          {error && <p className="text-sm text-red-600">{error}</p>}
        </CardContent>
      </Card>

      {result && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Generated plan</CardTitle>
              <div className="flex items-center gap-2">
                <Badge variant="outline">via {result.provider}</Badge>
                <Link href={`/projects/${result.project_id}`}>
                  <Button size="sm">Open project</Button>
                </Link>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-600">
                Tasks ({result.tasks.length})
              </h3>
              <div className="space-y-2">
                {result.tasks.map((t, idx) => (
                  <div
                    key={idx}
                    className="rounded-md border border-slate-200 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{t.title}</span>
                      <span
                        className={`rounded-full px-2 py-0.5 text-xs font-semibold ${priorityColors[t.priority] || ""}`}
                      >
                        {t.priority}
                      </span>
                    </div>
                    {t.description && (
                      <p className="mt-1 text-slate-500">{t.description}</p>
                    )}
                    <div className="mt-1 flex items-center gap-3 text-xs text-slate-400">
                      <span>{t.estimated_hours}h</span>
                      {t.depends_on.length > 0 && (
                        <span>depends on #{t.depends_on.join(", #")}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <h3 className="mb-2 text-sm font-semibold text-slate-600">
                Milestones ({result.milestones.length})
              </h3>
              <div className="space-y-2">
                {result.milestones.map((m, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-md border border-slate-200 p-3 text-sm"
                  >
                    <span className="font-medium">{m.name}</span>
                    <span className="text-xs text-slate-500">
                      day {m.target_offset_days} · {m.target_date}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
