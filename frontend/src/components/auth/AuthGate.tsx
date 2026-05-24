"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import Link from "next/link";
import { fetchMe, logout, type AuthUser, type AuthWorkspace } from "@/lib/auth";
import { getAuthToken } from "@/lib/api";

const PUBLIC_PATHS = ["/login", "/register"];

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [me, setMe] = useState<{ user: AuthUser; workspace: AuthWorkspace } | null>(null);
  const [checking, setChecking] = useState(true);

  const isPublic = pathname ? PUBLIC_PATHS.includes(pathname) : false;

  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (isPublic) {
        setChecking(false);
        return;
      }
      const token = getAuthToken();
      if (!token) {
        if (!cancelled) router.replace("/login");
        return;
      }
      try {
        const data = await fetchMe();
        if (!cancelled) {
          setMe({ user: data.user, workspace: data.active_workspace });
          setChecking(false);
        }
      } catch {
        if (!cancelled) router.replace("/login");
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, [pathname, isPublic, router]);

  if (isPublic) return <>{children}</>;
  if (checking) {
    return <div className="p-8 text-slate-500">Loading…</div>;
  }
  if (!me) return null;

  return (
    <>
      <div className="border-b border-slate-100 bg-slate-50">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-2 text-xs text-slate-500">
          <span>
            <strong>{me.user.email}</strong> · workspace: {me.workspace.name}
          </span>
          <button onClick={logout} className="text-blue-600 hover:underline">
            Sign out
          </button>
        </div>
      </div>
      {children}
    </>
  );
}
