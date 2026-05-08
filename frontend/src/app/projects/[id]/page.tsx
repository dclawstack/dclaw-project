"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { getProject, type ProjectDetail, type TaskStatus, type TaskPriority } from "@/lib/api";

const statusColors: Record<TaskStatus, string> = {
  todo: "bg-slate-100 text-slate-800",
  in_progress: "bg-blue-100 text-blue-800",
  review: "bg-amber-100 text-amber-800",
  done: "bg-green-100 text-green-800",
};

const priorityColors: Record<TaskPriority, string> = {
  low: "bg-slate-100 text-slate-600",
  medium: "bg-blue-100 text-blue-600",
  high: "bg-orange-100 text-orange-600",
  urgent: "bg-red-100 text-red-600",
};

export default function ProjectDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await getProject(id);
        setProject(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    if (id) load();
  }, [id]);

  if (loading) {
    return <div className="text-slate-500">Loading project...</div>;
  }

  if (!project) {
    return <div className="text-slate-500">Project not found.</div>;
  }

  const todoTasks = project.tasks.filter((t) => t.status === "todo");
  const inProgressTasks = project.tasks.filter((t) => t.status === "in_progress");
  const reviewTasks = project.tasks.filter((t) => t.status === "review");
  const doneTasks = project.tasks.filter((t) => t.status === "done");

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{project.name}</h1>
          <p className="text-slate-500">{project.description || "No description"}</p>
        </div>
        <Badge variant={project.status === "active" ? "default" : "secondary"}>
          {project.status}
        </Badge>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Owner</CardTitle>
          </CardHeader>
          <CardContent>{project.owner}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Start Date</CardTitle>
          </CardHeader>
          <CardContent>{project.start_date || "—"}</CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">End Date</CardTitle>
          </CardHeader>
          <CardContent>{project.end_date || "—"}</CardContent>
        </Card>
      </div>

      <Tabs defaultValue="board">
        <TabsList>
          <TabsTrigger value="board">Kanban Board</TabsTrigger>
          <TabsTrigger value="milestones">Milestones</TabsTrigger>
        </TabsList>

        <TabsContent value="board" className="space-y-4 pt-4">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
            <KanbanColumn title="To Do" tasks={todoTasks} />
            <KanbanColumn title="In Progress" tasks={inProgressTasks} />
            <KanbanColumn title="Review" tasks={reviewTasks} />
            <KanbanColumn title="Done" tasks={doneTasks} />
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
                  <p className="text-sm text-slate-500">{m.description || "No description"}</p>
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
  tasks,
}: {
  title: string;
  tasks: ProjectDetail["tasks"];
}) {
  return (
    <div className="rounded-lg border bg-slate-50 p-3">
      <h3 className="mb-3 text-sm font-semibold text-slate-600">{title}</h3>
      <div className="space-y-3">
        {tasks.map((task) => (
          <Card key={task.id} className="bg-white">
            <CardContent className="p-3 space-y-2">
              <Link href={`/tasks/${task.id}`} className="block font-medium hover:underline">
                {task.title}
              </Link>
              <div className="flex items-center gap-2">
                <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${priorityColors[task.priority]}`}>
                  {task.priority}
                </span>
                {task.assignee && (
                  <span className="text-xs text-slate-500">{task.assignee}</span>
                )}
              </div>
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
