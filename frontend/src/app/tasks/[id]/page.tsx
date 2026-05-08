"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getTask, updateTask, type Task, type TaskStatus, type TaskPriority } from "@/lib/api";

const statuses: TaskStatus[] = ["todo", "in_progress", "review", "done"];
const priorities: TaskPriority[] = ["low", "medium", "high", "urgent"];

export default function TaskDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        const data = await getTask(id);
        setTask(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    if (id) load();
  }, [id]);

  async function handleUpdate(updates: Partial<Omit<Task, "id">>) {
    if (!task) return;
    setSaving(true);
    try {
      const updated = await updateTask(task.id, updates);
      setTask(updated);
    } catch {
      // ignore
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <div className="text-slate-500">Loading task...</div>;
  }

  if (!task) {
    return <div className="text-slate-500">Task not found.</div>;
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <h1 className="text-3xl font-bold">{task.title}</h1>

      <Card>
        <CardHeader>
          <CardTitle>Task Details</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Status</Label>
              <Select
                value={task.status}
                onValueChange={(v) => handleUpdate({ status: v as TaskStatus })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {statuses.map((s) => (
                    <SelectItem key={s} value={s}>
                      {s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Priority</Label>
              <Select
                value={task.priority}
                onValueChange={(v) => handleUpdate({ priority: v as TaskPriority })}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {priorities.map((p) => (
                    <SelectItem key={p} value={p}>
                      {p}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Assignee</Label>
            <Input
              value={task.assignee || ""}
              onChange={(e) => handleUpdate({ assignee: e.target.value || null })}
              placeholder="Unassigned"
            />
          </div>

          <div className="space-y-2">
            <Label>Due Date</Label>
            <Input
              type="date"
              value={task.due_date || ""}
              onChange={(e) => handleUpdate({ due_date: e.target.value || null })}
            />
          </div>

          <div className="space-y-2">
            <Label>Description</Label>
            <p className="text-sm text-slate-600">{task.description || "No description"}</p>
          </div>

          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Badge variant="outline">{task.status}</Badge>
            <Badge variant="secondary">{task.priority}</Badge>
          </div>

          {saving && <p className="text-xs text-slate-500">Saving...</p>}
        </CardContent>
      </Card>

      <div className="flex gap-4">
        <Link href={`/projects/${task.project_id}`}>
          <Button variant="outline">Back to Project</Button>
        </Link>
        <Link href="/projects">
          <Button variant="outline">All Projects</Button>
        </Link>
      </div>
    </div>
  );
}
