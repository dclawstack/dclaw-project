import Link from "next/link";
import { SeedControls } from "@/components/SeedControls";

/* ─── Inline SVG icons (zero dependencies) ─── */

function IconBoard() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <rect x="3" y="4" width="18" height="16" rx="2" />
      <path d="M9 4v16M15 4v16" strokeLinecap="round" />
    </svg>
  );
}
function IconTree() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <rect x="3" y="3" width="7" height="5" rx="1" />
      <rect x="14" y="9" width="7" height="5" rx="1" />
      <rect x="14" y="16" width="7" height="5" rx="1" />
      <path d="M6.5 8v8.5h7.5M6.5 11.5h7.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconFlag() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <path d="M5 21V4m0 0 9 2-2 5 8 1.5L5 16" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconChat() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconSparkle() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M18 6l-2.5 2.5M8.5 15.5 6 18" strokeLinecap="round" />
    </svg>
  );
}
function IconShield() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <path d="M12 2 3 7v5c0 5.25 3.75 10.15 9 11.25C17.25 22.15 21 17.25 21 12V7L12 2Z" strokeLinecap="round" strokeLinejoin="round" />
      <path d="m9 12 2 2 4-4" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconScale() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <path d="M12 3v18M5 7h14M5 7 2 14h6L5 7Zm14 0-3 7h6l-3-7Z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconClock() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-7 w-7">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
function IconArrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} className="ml-1 inline h-4 w-4">
      <path d="M5 12h14M13 6l6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/* ─── Content ─── */

const features = [
  {
    icon: <IconBoard />,
    title: "Projects & Workspaces",
    desc: "Organize work into projects inside multi-tenant workspaces, each with status, owner, timeline, and tags. Your team's data stays cleanly isolated.",
    tag: "Core",
  },
  {
    icon: <IconTree />,
    title: "Tasks, Subtasks & Dependencies",
    desc: "Break work down into nested subtasks, set priorities and assignees, and link dependencies. Cycles are rejected automatically.",
    tag: "Core",
  },
  {
    icon: <IconFlag />,
    title: "Milestones & Critical Path",
    desc: "Track milestones against target dates and compute the critical path across your dependency graph to see what really drives the deadline.",
    tag: "Planning",
  },
  {
    icon: <IconChat />,
    title: "AI Project Copilot",
    desc: "Chat with your projects in plain English. Ask what's overdue, what's at risk, or what to do next — answered from live task and milestone data.",
    tag: "AI",
  },
  {
    icon: <IconSparkle />,
    title: "AI Work-Breakdown Generation",
    desc: "Describe a goal and the planner drafts a structured work breakdown — phases, tasks, and estimates — ready to drop into a project.",
    tag: "AI",
  },
  {
    icon: <IconShield />,
    title: "Risk Prediction & Health",
    desc: "A rolling project-health model flags scope, schedule, and overdue risk before a deadline slips, so you can intervene early.",
    tag: "AI",
  },
  {
    icon: <IconScale />,
    title: "Resource Leveling",
    desc: "Spot over-allocated assignees and let the optimizer suggest a smoother distribution of work across the team.",
    tag: "AI",
  },
  {
    icon: <IconClock />,
    title: "Time Tracking & Burndown",
    desc: "Log billable time against tasks and watch burndown charts track remaining work versus the ideal line throughout the sprint.",
    tag: "Analytics",
  },
];

const tagColor: Record<string, string> = {
  AI: "bg-violet-100 text-violet-700 border border-violet-200",
  Core: "bg-amber-100 text-amber-700 border border-amber-200",
  Planning: "bg-blue-100 text-blue-700 border border-blue-200",
  Analytics: "bg-emerald-100 text-emerald-700 border border-emerald-200",
};

const steps = [
  {
    n: "01",
    title: "Create a workspace",
    desc: "Sign up and your first workspace is ready instantly. Invite teammates or explore solo — everything is scoped to your workspace.",
  },
  {
    n: "02",
    title: "Plan with AI",
    desc: "Describe what you're building. The copilot drafts a work breakdown, suggests milestones, and lays out task dependencies for you.",
  },
  {
    n: "03",
    title: "Ship with confidence",
    desc: "Track progress on the dashboard while the risk model watches the schedule and warns you before a deadline is in danger.",
  },
];

const stats = [
  { value: "Multi-tenant", label: "workspace isolation" },
  { value: "Critical path", label: "dependency-aware scheduling" },
  { value: "AI copilot", label: "grounded in live data" },
  { value: "Real-time", label: "notifications over SSE" },
];

/* ─── Page ─── */

export default function LandingPage() {
  return (
    <div className="min-h-screen bg-white text-slate-900">
      {/* ── Nav ── */}
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/80 backdrop-blur-md">
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold tracking-tight text-indigo-600">DClaw Project</span>
            <span className="ml-1 rounded-full border border-indigo-200 bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-600">
              v1.2
            </span>
          </div>
          <nav className="hidden items-center gap-6 text-sm text-slate-500 md:flex">
            <a href="#features" className="transition-colors hover:text-slate-900">Features</a>
            <a href="#how-it-works" className="transition-colors hover:text-slate-900">How it works</a>
            <a href="#ai" className="transition-colors hover:text-slate-900">AI Copilot</a>
          </nav>
          <div className="flex items-center gap-3">
            <Link href="/login" className="text-sm font-medium text-slate-600 transition-colors hover:text-slate-900">
              Sign in
            </Link>
            <Link
              href="/register"
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-500"
            >
              Get started
            </Link>
          </div>
        </div>
      </header>

      {/* ── Hero ── */}
      <section className="relative overflow-hidden px-6 pb-28 pt-24">
        <div className="pointer-events-none absolute inset-0">
          <div className="absolute left-1/2 top-0 h-[480px] w-[900px] -translate-x-1/2 rounded-full bg-indigo-100/60 blur-3xl" />
          <div className="absolute left-1/4 top-24 h-[300px] w-[400px] rounded-full bg-violet-100/50 blur-3xl" />
        </div>

        <div className="relative mx-auto max-w-5xl space-y-8 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-indigo-200 bg-indigo-50 px-4 py-1.5 text-sm font-medium text-indigo-600">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" />
            The autonomous AI project manager
          </div>

          <h1 className="text-5xl font-extrabold leading-[1.08] tracking-tight text-slate-900 md:text-7xl">
            Plan, track, and{" "}
            <span className="bg-gradient-to-r from-indigo-600 to-violet-500 bg-clip-text text-transparent">
              de-risk
            </span>{" "}
            <br className="hidden md:block" />
            every project
          </h1>

          <p className="mx-auto max-w-3xl text-xl leading-relaxed text-slate-500 md:text-2xl">
            DClaw Project pairs a clean task tracker with an AI copilot that drafts work breakdowns,
            maps dependencies, predicts risk, and keeps your team ahead of the deadline.
          </p>

          <div className="flex flex-col justify-center gap-4 pt-2 sm:flex-row">
            <Link
              href="/register"
              className="rounded-xl bg-indigo-600 px-8 py-4 text-lg font-bold text-white shadow-lg shadow-indigo-500/20 transition-all hover:scale-105 hover:bg-indigo-500"
            >
              Get started free <IconArrow />
            </Link>
            <a
              href="#features"
              className="rounded-xl border border-slate-300 px-8 py-4 text-lg font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:text-slate-900"
            >
              Explore features
            </a>
          </div>
        </div>

        {/* Hero dashboard mockup */}
        <div className="relative mx-auto mt-20 max-w-4xl">
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-300/50">
            <div className="flex items-center gap-2 border-b border-slate-200 bg-slate-50 px-4 py-3">
              <span className="h-3 w-3 rounded-full bg-red-400" />
              <span className="h-3 w-3 rounded-full bg-yellow-400" />
              <span className="h-3 w-3 rounded-full bg-green-400" />
              <span className="ml-3 text-xs text-slate-400">DClaw Project · Dashboard</span>
            </div>
            <div className="space-y-4 p-6">
              <div className="grid grid-cols-4 gap-3">
                {[
                  { label: "Active Projects", value: "3" },
                  { label: "Due Today", value: "2" },
                  { label: "Completed", value: "5" },
                  { label: "Overdue", value: "2", danger: true },
                ].map((s) => (
                  <div key={s.label} className="rounded-lg border border-slate-200 bg-slate-50/70 p-3">
                    <div className="mb-1 text-xs text-slate-400">{s.label}</div>
                    <div className={`text-2xl font-bold ${s.danger ? "text-red-600" : "text-slate-900"}`}>
                      {s.value}
                    </div>
                  </div>
                ))}
              </div>
              <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50/40 p-3">
                <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                  Mobile App Launch
                </div>
                {[
                  { t: "Build onboarding flow", s: "done", c: "bg-emerald-100 text-emerald-700" },
                  { t: "Fix crash on cold start", s: "urgent", c: "bg-red-100 text-red-700" },
                  { t: "Push notification service", s: "in progress", c: "bg-blue-100 text-blue-700" },
                  { t: "App Store screenshots", s: "todo", c: "bg-slate-200 text-slate-600" },
                ].map((row) => (
                  <div key={row.t} className="flex items-center justify-between text-sm">
                    <span className="text-slate-700">{row.t}</span>
                    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${row.c}`}>{row.s}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="absolute -bottom-8 left-1/2 h-16 w-2/3 -translate-x-1/2 rounded-full bg-indigo-200/40 blur-2xl" />
        </div>
      </section>

      {/* ── Stats bar ── */}
      <section className="border-y border-slate-200 bg-slate-50 px-6 py-10">
        <div className="mx-auto grid max-w-4xl grid-cols-2 gap-8 text-center md:grid-cols-4">
          {stats.map((s) => (
            <div key={s.label}>
              <div className="text-2xl font-extrabold text-indigo-600">{s.value}</div>
              <div className="mt-1 text-sm text-slate-500">{s.label}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Features ── */}
      <section id="features" className="px-6 py-28">
        <div className="mx-auto max-w-7xl">
          <div className="mb-16 space-y-3 text-center">
            <div className="text-sm font-semibold uppercase tracking-widest text-indigo-600">
              Everything your team needs
            </div>
            <h2 className="text-4xl font-bold text-slate-900 md:text-5xl">
              Built for ambitious project teams
            </h2>
            <p className="mx-auto max-w-2xl text-lg text-slate-500">
              From day-to-day task tracking to AI-assisted planning and risk prediction — one workspace
              covers the whole delivery lifecycle.
            </p>
          </div>

          <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
            {features.map((f) => (
              <div
                key={f.title}
                className="group rounded-2xl border border-slate-200 bg-white p-6 transition-all duration-200 hover:border-indigo-300 hover:shadow-lg hover:shadow-indigo-100"
              >
                <div className="mb-4 flex items-start justify-between">
                  <div className="text-indigo-600">{f.icon}</div>
                  <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${tagColor[f.tag]}`}>
                    {f.tag}
                  </span>
                </div>
                <h3 className="mb-2 text-base font-semibold leading-snug text-slate-900">{f.title}</h3>
                <p className="text-sm leading-relaxed text-slate-500">{f.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── How it works ── */}
      <section id="how-it-works" className="bg-slate-50 px-6 py-28">
        <div className="mx-auto max-w-5xl">
          <div className="mb-16 space-y-3 text-center">
            <div className="text-sm font-semibold uppercase tracking-widest text-indigo-600">
              Simple by design
            </div>
            <h2 className="text-4xl font-bold text-slate-900 md:text-5xl">From idea to delivery</h2>
            <p className="mx-auto max-w-xl text-lg text-slate-500">
              No setup overhead. Create a workspace, let the AI help you plan, and start shipping.
            </p>
          </div>

          <div className="relative">
            <div className="absolute left-[calc(16.7%-1px)] right-[calc(16.7%-1px)] top-12 hidden h-px bg-gradient-to-r from-transparent via-indigo-300 to-transparent md:block" />
            <div className="grid gap-10 md:grid-cols-3">
              {steps.map((step) => (
                <div key={step.n} className="space-y-4 text-center">
                  <div className="relative mx-auto inline-flex h-24 w-24 items-center justify-center rounded-2xl border border-slate-200 bg-white shadow-sm">
                    <span className="text-3xl font-extrabold text-indigo-600">{step.n}</span>
                  </div>
                  <h3 className="text-xl font-bold text-slate-900">{step.title}</h3>
                  <p className="leading-relaxed text-slate-500">{step.desc}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── AI Copilot spotlight ── */}
      <section id="ai" className="px-6 py-28">
        <div className="mx-auto grid max-w-6xl items-center gap-16 md:grid-cols-2">
          <div className="space-y-6">
            <div className="text-sm font-semibold uppercase tracking-widest text-indigo-600">AI Copilot</div>
            <h2 className="text-4xl font-bold leading-tight text-slate-900 md:text-5xl">
              Ask your projects anything
            </h2>
            <p className="text-lg leading-relaxed text-slate-500">
              The copilot is grounded in your live tasks, milestones, and dependencies. It answers in
              plain English, drafts work breakdowns, and flags what's at risk — no query language required.
            </p>
            <ul className="space-y-3">
              {[
                "What's overdue across all active projects?",
                "Draft a work breakdown for a mobile app launch",
                "Which milestones are at risk of slipping?",
                "Who is over-allocated this sprint?",
              ].map((q) => (
                <li key={q} className="flex items-start gap-3 text-sm text-slate-600">
                  <span className="mt-0.5 text-indigo-500">→</span>
                  <span className="italic">&ldquo;{q}&rdquo;</span>
                </li>
              ))}
            </ul>
            <Link
              href="/plan"
              className="inline-flex items-center gap-1 text-sm font-semibold text-indigo-600 transition-colors hover:text-indigo-500"
            >
              Try the AI Planner <IconArrow />
            </Link>
          </div>

          {/* Chat mockup */}
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl shadow-slate-300/40">
            <div className="flex items-center gap-2 border-b border-slate-200 px-4 py-3">
              <div className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" />
              <span className="text-xs font-medium text-slate-500">AI Project Copilot</span>
            </div>
            <div className="space-y-4 p-5 text-sm">
              <div className="flex justify-end">
                <div className="max-w-xs rounded-2xl rounded-tr-sm border border-indigo-200 bg-indigo-50 px-4 py-2.5 text-indigo-900">
                  What&apos;s at risk this week?
                </div>
              </div>
              <div className="flex gap-3">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-violet-200 bg-violet-100 text-xs font-bold text-violet-600">
                  AI
                </div>
                <div className="flex-1 space-y-2 rounded-2xl rounded-tl-sm border border-slate-200 bg-slate-50 px-4 py-3 leading-relaxed text-slate-700">
                  <p>
                    <strong className="text-slate-900">2 items</strong> need attention:
                  </p>
                  <div className="space-y-1.5 rounded-lg bg-white p-2.5 font-mono text-xs">
                    <div className="flex justify-between">
                      <span className="text-indigo-600">Fix crash on cold start</span>
                      <span className="text-red-600">overdue · urgent</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-indigo-600">App Store submission</span>
                      <span className="text-amber-600">milestone in 10d</span>
                    </div>
                  </div>
                  <p className="text-xs text-slate-400">
                    The crash blocks the App Store milestone — I&apos;d prioritize it today.
                  </p>
                </div>
              </div>
            </div>
            <div className="px-4 pb-4">
              <div className="flex items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5">
                <span className="flex-1 text-sm text-slate-400">Ask anything about your projects…</span>
                <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-indigo-600">
                  <IconArrow />
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="px-6 py-28">
        <div className="mx-auto max-w-2xl space-y-8 text-center">
          <h2 className="text-4xl font-bold text-slate-900 md:text-5xl">Ready to run a tighter ship?</h2>
          <p className="text-lg text-slate-500">
            Create your workspace and let the AI copilot draft your first plan in minutes.
          </p>
          <div className="flex flex-col justify-center gap-4 sm:flex-row">
            <Link
              href="/register"
              className="rounded-xl bg-indigo-600 px-8 py-4 text-lg font-bold text-white shadow-lg shadow-indigo-500/20 transition-all hover:scale-105 hover:bg-indigo-500"
            >
              Get started free <IconArrow />
            </Link>
            <Link
              href="/login"
              className="rounded-xl border border-slate-300 px-8 py-4 text-lg font-semibold text-slate-700 transition-colors hover:border-slate-400 hover:text-slate-900"
            >
              Sign in
            </Link>
          </div>
        </div>
      </section>

      {/* ── SEED CONTROLS — remove this block (and the SeedControls import) to hide ── */}
      <section className="border-t border-slate-200 px-6 py-12">
        <div className="mx-auto max-w-lg">
          <SeedControls />
        </div>
      </section>
      {/* ── END SEED CONTROLS ── */}

      {/* ── Footer ── */}
      <footer className="border-t border-slate-200 px-6 py-10">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-6 md:flex-row">
          <div className="flex items-center gap-3">
            <span className="text-lg font-bold text-indigo-600">DClaw Project</span>
            <span className="text-slate-300">·</span>
            <span className="text-sm text-slate-400">v1.2 · dclaw_project</span>
          </div>
          <nav className="flex items-center gap-6 text-sm text-slate-500">
            <Link href="/dashboard" className="transition-colors hover:text-slate-900">Dashboard</Link>
            <Link href="/projects" className="transition-colors hover:text-slate-900">Projects</Link>
            <Link href="/plan" className="transition-colors hover:text-slate-900">AI Planner</Link>
            <Link href="/search" className="transition-colors hover:text-slate-900">Search</Link>
          </nav>
          <div className="text-sm text-slate-400">Built with FastAPI · Next.js · PostgreSQL</div>
        </div>
      </footer>
    </div>
  );
}
