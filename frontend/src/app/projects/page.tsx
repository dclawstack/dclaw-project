"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from "@/components/ui/select";
import { listProjects, type Project, type ProjectStatus } from "@/lib/api";

const statusOptions: ProjectStatus[] = [
  "planning",
  "active",
  "on_hold",
  "completed",
  "cancelled",
];

const statusLabel: Record<ProjectStatus, string> = {
  planning: "Planning",
  active: "Active",
  on_hold: "On Hold",
  completed: "Completed",
  cancelled: "Cancelled",
};

export default function ProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [filter, setFilter] = useState<ProjectStatus | "all">("all");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await listProjects();
        setProjects(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const filtered =
    filter === "all" ? projects : projects.filter((p) => p.status === filter);

  if (loading) {
    return <div className="text-slate-500">Loading projects...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Projects</h1>
        <Select value={filter} onValueChange={(v) => setFilter(v as ProjectStatus | "all")}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Filter by status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
            {statusOptions.map((s) => (
              <SelectItem key={s} value={s}>
                {statusLabel[s]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {filtered.map((project) => (
          <Card key={project.id} className="hover:shadow-md transition-shadow">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg">{project.name}</CardTitle>
                <Badge variant={project.status === "active" ? "default" : "secondary"}>
                  {statusLabel[project.status]}
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <p className="text-sm text-slate-500 line-clamp-2">
                {project.description || "No description"}
              </p>
              <div className="flex items-center justify-between text-sm text-slate-500">
                <span>Owner: {project.owner}</span>
              </div>
              <Link href={`/projects/${project.id}`}>
                <Button variant="outline" size="sm" className="w-full">
                  View Details
                </Button>
              </Link>
            </CardContent>
          </Card>
        ))}
      </div>

      {filtered.length === 0 && (
        <p className="text-center text-slate-500">No projects found.</p>
      )}
    </div>
  );
}
