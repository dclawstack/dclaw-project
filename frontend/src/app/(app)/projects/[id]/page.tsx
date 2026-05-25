"use client";

import { useCallback, useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectTrigger,
  SelectValue,
  SelectContent,
  SelectItem,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  getProject,
  createTask,
  projectStats,
  updateTask,
  type ProjectDetail,
  type ProjectStats,
  type Task,
  type TaskStatus,
  type TaskPriority,
} from "@/lib/api";
import { projectHealth, type ProjectHealthResponse } from "@/lib/ai";

const priorityColors: Record<TaskPriority, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-orange-100 text-orange-600",
  urgent: "bg-red-100 text-red-600",
};

const PRIORITY_OPTIONS: TaskPriority[] = ["low", "medium", "high", "urgent"];
const STATUS_OPTIONS: TaskStatus[] = ["todo", "in_progress", "review", "done"];

export default function ProjectDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [stats, setStats] = useState<ProjectStats | null>(null);
  const [health, setHealth] = useState<ProjectHealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [taskDialogOpen, setTaskDialogOpen] = useState(false);
  const [taskForm, setTaskForm] = useState({
    title: "",
    description: "",
    assignee: "",
    priority: "medium" as TaskPriority,
    status: "todo" as TaskStatus,
    due_date: "",
  });

  const load = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    try {
      const [proj, st, hp] = await Promise.all([
        getProject(id),
        projectStats(id),
        projectHealth(id).catch(() => null),
      ]);
      setProject(proj);
      setStats(st);
      setHealth(hp);
    } catch {
      setProject(null);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function handleMove(taskId: string, newStatus: TaskStatus) {
    if (!project) return;
    const existing = project.tasks.find((t) => t.id === taskId);
    if (!existing || existing.status === newStatus) return;
    // Optimistic update: swap status in local state, roll back on failure.
    const previousStatus = existing.status;
    setProject({
      ...project,
      tasks: project.tasks.map((t) =>
        t.id === taskId ? { ...t, status: newStatus } : t,
      ),
    });
    try {
      await updateTask(taskId, { status: newStatus });
    } catch {
      setProject({
        ...project,
        tasks: project.tasks.map((t) =>
          t.id === taskId ? { ...t, status: previousStatus } : t,
        ),
      });
    }
  }

  async function handleCreateTask() {
    if (!taskForm.title) return;
    await createTask({
      project_id: id,
      title: taskForm.title,
      description: taskForm.description || null,
      assignee: taskForm.assignee || null,
      priority: taskForm.priority,
      status: taskForm.status,
      due_date: taskForm.due_date || null,
    });
    setTaskForm({
      title: "",
      description: "",
      assignee: "",
      priority: "medium",
      status: "todo",
      due_date: "",
    });
    setTaskDialogOpen(false);
    await load();
  }

  if (loading) {
    return <div className="text-slate-500">Loading project...</div>;
  }
  if (!project) {
    return <div className="text-slate-500">Project not found.</div>;
  }

  const grouped: Record<TaskStatus, ProjectDetail["tasks"]> = {
    todo: [],
    in_progress: [],
    review: [],
    done: [],
  };
  project.tasks.forEach((t) => grouped[t.status].push(t));

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{project.name}</h1>
          <p className="text-slate-500">{project.description || "No description"}</p>
          {project.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {project.tags.map((t) => (
                <Badge
                  key={t.id}
                  variant="outline"
                  style={{ borderColor: t.color, color: t.color }}
                >
                  {t.name}
                </Badge>
              ))}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={project.status === "active" ? "default" : "secondary"}>
            {project.status}
          </Badge>
          <Button onClick={() => setTaskDialogOpen(true)}>New Task</Button>
          <Dialog open={taskDialogOpen} onOpenChange={setTaskDialogOpen}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create task</DialogTitle>
              </DialogHeader>
              <div className="space-y-3">
                <div className="space-y-1">
                  <Label htmlFor="title">Title</Label>
                  <Input
                    id="title"
                    value={taskForm.title}
                    onChange={(e) =>
                      setTaskForm({ ...taskForm, title: e.target.value })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="description">Description</Label>
                  <Input
                    id="description"
                    value={taskForm.description}
                    onChange={(e) =>
                      setTaskForm({ ...taskForm, description: e.target.value })
                    }
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label htmlFor="assignee">Assignee</Label>
                    <Input
                      id="assignee"
                      value={taskForm.assignee}
                      onChange={(e) =>
                        setTaskForm({ ...taskForm, assignee: e.target.value })
                      }
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="due_date">Due date</Label>
                    <Input
                      id="due_date"
                      type="date"
                      value={taskForm.due_date}
                      onChange={(e) =>
                        setTaskForm({ ...taskForm, due_date: e.target.value })
                      }
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div className="space-y-1">
                    <Label>Status</Label>
                    <Select
                      value={taskForm.status}
                      onValueChange={(v) =>
                        setTaskForm({ ...taskForm, status: v as TaskStatus })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {STATUS_OPTIONS.map((s) => (
                          <SelectItem key={s} value={s}>
                            {s}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-1">
                    <Label>Priority</Label>
                    <Select
                      value={taskForm.priority}
                      onValueChange={(v) =>
                        setTaskForm({ ...taskForm, priority: v as TaskPriority })
                      }
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {PRIORITY_OPTIONS.map((p) => (
                          <SelectItem key={p} value={p}>
                            {p}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <Button
                  onClick={handleCreateTask}
                  disabled={!taskForm.title}
                  className="w-full"
                >
                  Create task
                </Button>
              </div>
            </DialogContent>
          </Dialog>
        </div>
      </div>

      {health && (
        <Card
          className={
            health.status === "green"
              ? "border-emerald-200 bg-emerald-50"
              : health.status === "yellow"
              ? "border-amber-200 bg-amber-50"
              : "border-red-200 bg-red-50"
          }
        >
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm font-medium text-slate-600">
                AI Health Score
              </CardTitle>
              <Badge
                variant={health.status === "green" ? "default" : "destructive"}
                className={
                  health.status === "green"
                    ? "bg-emerald-600"
                    : health.status === "yellow"
                    ? "bg-amber-600"
                    : "bg-red-600"
                }
              >
                {health.status.toUpperCase()} · {health.score}/100
              </Badge>
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <p className="text-sm text-slate-700">{health.narrative}</p>
            {health.top_risks.length > 0 && (
              <ul className="list-disc pl-5 text-sm text-slate-600">
                {health.top_risks.map((r, idx) => (
                  <li key={idx}>{r}</li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.total_tasks ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Completion</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{(stats?.completion_pct ?? 0).toFixed(0)}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Overdue</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-red-600">{stats?.overdue ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Due in 7 days</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{stats?.due_soon ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <Tabs defaultValue="board">
        <TabsList>
          <TabsTrigger value="board">Kanban Board</TabsTrigger>
          <TabsTrigger value="milestones">Milestones</TabsTrigger>
        </TabsList>

        <TabsContent value="board" className="space-y-4 pt-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <KanbanColumn title="To Do" status="todo" tasks={grouped.todo} onMove={handleMove} />
            <KanbanColumn title="In Progress" status="in_progress" tasks={grouped.in_progress} onMove={handleMove} />
            <KanbanColumn title="Review" status="review" tasks={grouped.review} onMove={handleMove} />
            <KanbanColumn title="Done" status="done" tasks={grouped.done} onMove={handleMove} />
          </div>
        </TabsContent>

        <TabsContent value="milestones" className="space-y-4 pt-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {project.milestones.map((m) => (
              <Card key={m.id}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base">{m.name}</CardTitle>
                    {m.completed ? (
                      <Badge variant="default">Done</Badge>
                    ) : (
                      <Badge variant="secondary">Open</Badge>
                    )}
                  </div>
                </CardHeader>
                <CardContent className="space-y-2">
                  <p className="text-sm text-slate-500">
                    {m.description || "No description"}
                  </p>
                  <p className="text-sm text-slate-500">Target: {m.target_date}</p>
                </CardContent>
              </Card>
            ))}
            {project.milestones.length === 0 && (
              <p className="text-slate-500">No milestones yet.</p>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <Link href="/projects">
        <Button variant="outline">Back to Projects</Button>
      </Link>
    </div>
  );
}

function KanbanColumn({
  title,
  status,
  tasks,
  onMove,
}: {
  title: string;
  status: TaskStatus;
  tasks: ProjectDetail["tasks"];
  onMove: (taskId: string, newStatus: TaskStatus) => void;
}) {
  return (
    <div
      className="rounded-lg border bg-slate-50 p-3 transition-colors"
      onDragOver={(e) => {
        e.preventDefault();
        (e.currentTarget as HTMLDivElement).classList.add("bg-blue-50", "ring-2", "ring-blue-300");
      }}
      onDragLeave={(e) => {
        (e.currentTarget as HTMLDivElement).classList.remove("bg-blue-50", "ring-2", "ring-blue-300");
      }}
      onDrop={(e) => {
        e.preventDefault();
        (e.currentTarget as HTMLDivElement).classList.remove("bg-blue-50", "ring-2", "ring-blue-300");
        const taskId = e.dataTransfer.getData("text/plain");
        if (taskId) onMove(taskId, status);
      }}
    >
      <h3 className="mb-3 text-sm font-semibold text-slate-600">
        {title} <span className="text-slate-400">({tasks.length})</span>
      </h3>
      <div className="space-y-3">
        {tasks.map((task) => (
          <Card
            key={task.id}
            className="cursor-grab bg-white active:cursor-grabbing"
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("text/plain", task.id);
              e.dataTransfer.effectAllowed = "move";
            }}
          >
            <CardContent className="space-y-2 p-3">
              <Link
                href={`/tasks/${task.id}`}
                className="block font-medium hover:underline"
              >
                {task.title}
              </Link>
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${priorityColors[task.priority]}`}
                >
                  {task.priority}
                </span>
                {task.assignee && (
                  <span className="text-xs text-slate-500">{task.assignee}</span>
                )}
                {task.due_date && (
                  <span className="text-xs text-slate-400">due {task.due_date}</span>
                )}
              </div>
              {task.tags.length > 0 && (
                <div className="flex flex-wrap gap-1">
                  {task.tags.map((t) => (
                    <Badge
                      key={t.id}
                      variant="outline"
                      className="text-[10px]"
                      style={{ borderColor: t.color, color: t.color }}
                    >
                      {t.name}
                    </Badge>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        ))}
        {tasks.length === 0 && (
          <p className="text-xs text-slate-400">No tasks</p>
        )}
      </div>
    </div>
  );
}
