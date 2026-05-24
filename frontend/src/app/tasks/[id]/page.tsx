"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  getTask,
  updateTask,
  listTaskComments,
  createTaskComment,
  deleteComment,
  type Task,
  type Comment,
  type TaskStatus,
  type TaskPriority,
} from "@/lib/api";

const statuses: TaskStatus[] = ["todo", "in_progress", "review", "done"];
const priorities: TaskPriority[] = ["low", "medium", "high", "urgent"];

export default function TaskDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [task, setTask] = useState<Task | null>(null);
  const [comments, setComments] = useState<Comment[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newComment, setNewComment] = useState({ author: "", body: "" });

  const loadComments = useCallback(async () => {
    if (!id) return;
    const data = await listTaskComments(id);
    setComments(data);
  }, [id]);

  useEffect(() => {
    async function load() {
      if (!id) return;
      try {
        const [t, c] = await Promise.all([getTask(id), listTaskComments(id)]);
        setTask(t);
        setComments(c);
      } catch {
        setTask(null);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  async function handleUpdate(updates: Partial<Task>) {
    if (!task) return;
    setSaving(true);
    try {
      const updated = await updateTask(task.id, updates);
      setTask(updated);
    } finally {
      setSaving(false);
    }
  }

  async function handleAddComment() {
    if (!newComment.author || !newComment.body || !task) return;
    await createTaskComment(task.id, newComment);
    setNewComment({ author: newComment.author, body: "" });
    await loadComments();
  }

  async function handleDeleteComment(commentId: string) {
    await deleteComment(commentId);
    await loadComments();
  }

  if (loading) {
    return <div className="text-slate-500">Loading task...</div>;
  }
  if (!task) {
    return <div className="text-slate-500">Task not found.</div>;
  }

  return (
    <div className="max-w-3xl space-y-6">
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
              onChange={(e) => setTask({ ...task, assignee: e.target.value })}
              onBlur={(e) => handleUpdate({ assignee: e.target.value || null })}
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
            {task.completed_at && (
              <span className="text-xs text-emerald-600">
                completed {task.completed_at}
              </span>
            )}
          </div>

          {saving && <p className="text-xs text-slate-500">Saving...</p>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Activity</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-3">
            {comments.map((c) => (
              <div
                key={c.id}
                className="rounded-md border border-slate-200 bg-slate-50 p-3"
              >
                <div className="mb-1 flex items-center justify-between text-xs text-slate-500">
                  <span>
                    <strong>{c.author}</strong> · {new Date(c.created_at).toLocaleString()}
                  </span>
                  <button
                    onClick={() => handleDeleteComment(c.id)}
                    className="text-xs text-red-600 hover:underline"
                  >
                    delete
                  </button>
                </div>
                <p className="whitespace-pre-wrap text-sm text-slate-800">{c.body}</p>
              </div>
            ))}
            {comments.length === 0 && (
              <p className="text-xs text-slate-400">No activity yet.</p>
            )}
          </div>
          <div className="space-y-2 border-t border-slate-100 pt-4">
            <div className="grid grid-cols-3 gap-2">
              <Input
                placeholder="Your name"
                value={newComment.author}
                onChange={(e) => setNewComment({ ...newComment, author: e.target.value })}
              />
              <Input
                className="col-span-2"
                placeholder="Add a comment..."
                value={newComment.body}
                onChange={(e) => setNewComment({ ...newComment, body: e.target.value })}
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleAddComment();
                }}
              />
            </div>
            <Button
              onClick={handleAddComment}
              disabled={!newComment.author || !newComment.body}
              size="sm"
            >
              Post comment
            </Button>
          </div>
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
