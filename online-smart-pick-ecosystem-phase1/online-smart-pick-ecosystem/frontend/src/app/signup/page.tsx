"use client";

import { useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import api, { ApiError } from "@/lib/api";

export default function SignupPage() {
  const router = useRouter();
  const [agencyName, setAgencyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    // Basic client-side validation (backend enforces more)
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (!/[A-Z]/.test(password) || !/[a-z]/.test(password) || !/[0-9]/.test(password)) {
      setError("Password must contain uppercase, lowercase, and a digit.");
      return;
    }

    setSubmitting(true);
    try {
      await api.signup({
        agency_name: agencyName.trim(),
        full_name: fullName.trim(),
        email: email.trim(),
        password,
      });
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
    <div className="min-h-screen flex flex-col items-center justify-center bg-slate-50 px-4 py-10">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold text-brand-blue">
            Online Smart Pick
          </h1>
          <p className="text-slate-500 mt-1 text-sm">
            Start managing your clients in minutes.
          </p>
        </div>

        <div className="card p-8">
          <h2 className="text-xl font-semibold text-slate-900 mb-1">
            Create your agency account
          </h2>
          <p className="text-sm text-slate-500 mb-6">
            You'll be the owner of this agency.
          </p>

          {error && (
            <div className="error-banner mb-4" role="alert">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label htmlFor="agency_name" className="label">
                Agency name
              </label>
              <input
                id="agency_name"
                type="text"
                className="input"
                value={agencyName}
                onChange={(e) => setAgencyName(e.target.value)}
                required
                minLength={2}
                maxLength={255}
                disabled={submitting}
                placeholder="Acme Marketing"
              />
            </div>

            <div>
              <label htmlFor="full_name" className="label">
                Your name
              </label>
              <input
                id="full_name"
                type="text"
                className="input"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                required
                minLength={2}
                maxLength={255}
                disabled={submitting}
                autoComplete="name"
                placeholder="Jane Smith"
              />
            </div>

            <div>
              <label htmlFor="email" className="label">
                Work email
              </label>
              <input
                id="email"
                type="email"
                className="input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
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
                required
                minLength={8}
                maxLength={72}
                autoComplete="new-password"
                disabled={submitting}
              />
              <p className="text-xs text-slate-500 mt-1">
                At least 8 characters, with uppercase, lowercase, and a digit.
              </p>
            </div>

            <button
              type="submit"
              className="btn-success w-full"
              disabled={submitting}
            >
              {submitting ? "Creating account…" : "Create agency account"}
            </button>
          </form>

          <p className="text-sm text-slate-600 text-center mt-6">
            Already have an account?{" "}
            <Link
              href="/login"
              className="text-brand-blue font-medium hover:underline"
            >
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
