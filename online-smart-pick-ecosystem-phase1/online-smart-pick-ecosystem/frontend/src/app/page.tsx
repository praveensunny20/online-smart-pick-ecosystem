"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { tokenStorage } from "@/lib/api";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    // On mount, check if a token exists and route accordingly.
    // This runs in the browser only (useEffect is client-side).
    if (tokenStorage.isAuthenticated()) {
      router.replace("/dashboard");
    } else {
      router.replace("/login");
    }
  }, [router]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="text-center">
        <div className="w-12 h-12 border-4 border-brand-blue border-t-transparent rounded-full animate-spin mx-auto mb-4" />
        <p className="text-slate-600 text-sm">Loading Online Smart Pick…</p>
      </div>
    </div>
  );
}
