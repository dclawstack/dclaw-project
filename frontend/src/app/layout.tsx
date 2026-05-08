import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "DClaw Project",
  description: "DClaw Project Management",
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
              <Link href="/" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                Dashboard
              </Link>
              <Link href="/projects" className="text-sm font-medium text-slate-600 hover:text-slate-900">
                Projects
              </Link>
            </div>
          </div>
        </nav>
        <main className="mx-auto max-w-7xl px-4 py-8">{children}</main>
      </body>
    </html>
  );
}
