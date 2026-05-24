import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { CopilotWidget } from "@/components/copilot/CopilotWidget";
import { AuthGate } from "@/components/auth/AuthGate";

export const metadata: Metadata = {
  title: "DClaw Project",
  description: "DClaw Project — The autonomous AI project manager",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-white text-slate-900">
        <nav className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
            <Link href="/" className="text-xl font-bold text-slate-900">
              DClaw Project
            </Link>
            <div className="flex gap-6">
              <Link
                href="/"
                className="text-sm font-medium text-slate-600 hover:text-slate-900"
              >
                Dashboard
              </Link>
              <Link
                href="/projects"
                className="text-sm font-medium text-slate-600 hover:text-slate-900"
              >
                Projects
              </Link>
              <Link
                href="/plan"
                className="text-sm font-medium text-slate-600 hover:text-slate-900"
              >
                AI Planner
              </Link>
              <Link
                href="/search"
                className="text-sm font-medium text-slate-600 hover:text-slate-900"
              >
                Search
              </Link>
            </div>
          </div>
        </nav>
        <AuthGate>
          <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
          <CopilotWidget />
        </AuthGate>
      </body>
    </html>
  );
}
