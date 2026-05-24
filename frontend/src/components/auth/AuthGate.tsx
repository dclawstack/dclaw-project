"use client";

import { useEffect, useRef, useState } from "react";
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

  // Capture router in a ref so the effect doesn't re-run when Next
  // hands us a fresh router object on rerender (which would otherwise
  // re-fire fetchMe + replace('/login') on every render — a fetch loop
  // on token-missing).
  const routerRef = useRef(router);
  routerRef.current = router;

  useEffect(() => {
    let cancelled = false;
    async function check() {
      if (isPublic) {
        setChecking(false);
        return;
      }
      const token = getAuthToken();
      if (!token) {
        if (!cancelled) {
          // Always clear `checking` so the gate doesn't render an
          // infinite "Loading…" if router.replace silently fails (fast-
          // refresh, stale router, etc.). The render path below shows
          // a recovery link instead.
          setChecking(false);
          routerRef.current.replace("/login");
        }
        return;
      }
      try {
        const data = await fetchMe();
        if (!cancelled) {
          setMe({ user: data.user, workspace: data.active_workspace });
          setChecking(false);
        }
      } catch {
        if (!cancelled) {
          setChecking(false);
          routerRef.current.replace("/login");
        }
      }
    }
    check();
    return () => {
      cancelled = true;
    };
  }, [pathname, isPublic]);

  if (isPublic) return <>{children}</>;
  if (checking) {
    return <div className="p-8 text-slate-500">Loading…</div>;
  }
  if (!me) {
    // checking has finished, fetchMe failed, router.replace hasn't taken
    // us anywhere. Give the user an affordance instead of a white screen.
    return (
      <div className="space-y-2 p-8 text-slate-600">
        <p>You&apos;re not signed in.</p>
        <a href="/login" className="text-blue-600 hover:underline">
          Go to sign in
        </a>
      </div>
    );
  }

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
