"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api, { ApiError } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await api.login({ email: email.trim(), password });
      router.replace("/dashboard");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-blue">
            Online Smart Pick
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Marketing intelligence, unified.
          </p>
        </div>

        <div className="card p-8">
          <h2 className="text-xl font-semibold text-slate-900 mb-1">
            Sign in to your account
          </h2>
          <p className="text-sm text-slate-500 mb-6">
            Enter your agency credentials to continue.
          </p>

          {error && (
            <div className="error-banner mb-4" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="email" className="label">
                Email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
                disabled={submitting}
                placeholder="you@agency.com"
              />
            </div>

            <div>
              <label htmlFor="password" className="label">
                Password
              </label>
              <input
                id="password"
                type="password"
                className="input"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
                disabled={submitting}
              />
            </div>

            <button
              type="submit"
              className="btn-primary w-full"
              disabled={submitting}
            >
              {submitting ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="text-sm text-slate-600 text-center mt-6">
            New agency?{" "}
            <Link
              href="/signup"
              className="text-brand-blue font-medium hover:underline"
            >
              Create an account
            </Link>
          </p>
        </div>

        <p className="text-xs text-slate-400 text-center mt-6">
          © {new Date().getFullYear()} Online Smart Pick Ecosystem
        </p>
      </div>
    </div>
  );
}
