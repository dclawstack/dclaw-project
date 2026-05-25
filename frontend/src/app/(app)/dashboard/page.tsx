"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  listProjects,
  tasksDueToday,
  tasksOverdue,
  completedTasksCount,
  type Project,
  type Task,
} from "@/lib/api";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [dueToday, setDueToday] = useState<Task[]>([]);
  const [overdue, setOverdue] = useState<Task[]>([]);
  const [completed, setCompleted] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [projResp, due, over, comp] = await Promise.all([
          listProjects({ status: "active", limit: 50 }),
          tasksDueToday(),
          tasksOverdue(),
          completedTasksCount(),
        ]);
        setProjects(projResp.items);
        setDueToday(due);
        setOverdue(over);
        setCompleted(comp.count);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return <div className="text-slate-500">Loading dashboard...</div>;
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="mt-1 text-sm text-slate-500">
          The autonomous project manager — at a glance.
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Active Projects</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{projects.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Tasks Due Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{dueToday.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Completed Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold">{completed}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-slate-500">Overdue Tasks</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-bold text-red-600">{overdue.length}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Active Projects</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {projects.length === 0 && (
              <p className="text-sm text-slate-500">No active projects.</p>
            )}
            {projects.map((p) => (
              <div key={p.id} className="flex items-center justify-between">
                <Link href={`/projects/${p.id}`} className="font-medium hover:underline">
                  {p.name}
                </Link>
                <Badge variant="secondary">{p.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Tasks Due Today</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {dueToday.length === 0 && (
              <p className="text-sm text-slate-500">No tasks due today.</p>
            )}
            {dueToday.map((t) => (
              <div key={t.id} className="flex items-center justify-between">
                <Link href={`/tasks/${t.id}`} className="font-medium hover:underline">
                  {t.title}
                </Link>
                <Badge variant="outline">{t.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Overdue Tasks</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {overdue.length === 0 && (
              <p className="text-sm text-slate-500">No overdue tasks.</p>
            )}
            {overdue.map((t) => (
              <div key={t.id} className="flex items-center justify-between">
                <Link href={`/tasks/${t.id}`} className="font-medium hover:underline">
                  {t.title}
                </Link>
                <Badge variant="destructive">{t.status}</Badge>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-4">
        <Link href="/projects">
          <Button>View All Projects</Button>
        </Link>
      </div>
    </div>
  );
}
