"use client";

import { useEffect, useState, FormEvent } from "react";
import { useRouter } from "next/navigation";
import api, {
  ApiError,
  Client,
  CurrentUser,
  tokenStorage,
} from "@/lib/api";

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Create-client form state
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newIndustry, setNewIndustry] = useState("");
  const [newEmail, setNewEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // ---- Load user + clients on mount ----
  useEffect(() => {
    let mounted = true;

    async function load() {
      if (!tokenStorage.isAuthenticated()) {
        router.replace("/login");
        return;
      }
      try {
        const [me, clientList] = await Promise.all([
          api.me(),
          api.listClients(),
        ]);
        if (!mounted) return;
        setUser(me);
        setClients(clientList);
      } catch (err) {
        if (!mounted) return;
        if (err instanceof ApiError && err.status === 401) {
          // api.ts already handles redirect on 401
          return;
        }
        setError(
          err instanceof ApiError ? err.detail : "Failed to load dashboard."
        );
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();
    return () => {
      mounted = false;
    };
  }, [router]);

  async function handleCreateClient(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      const created = await api.createClient({
        name: newName.trim(),
        industry: newIndustry.trim() || undefined,
        primary_contact_email: newEmail.trim() || undefined,
      });
      setClients((prev) => [created, ...prev]);
      setNewName("");
      setNewIndustry("");
      setNewEmail("");
      setShowForm(false);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.detail : "Could not create client."
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(id: string, name: string) {
    if (!confirm(`Delete ${name}? This also deletes all platform connections, metrics, and reports for this client.`)) {
      return;
    }
    try {
      await api.deleteClient(id);
      setClients((prev) => prev.filter((c) => c.id !== id));
    } catch (err) {
      alert(
        err instanceof ApiError ? err.detail : "Failed to delete client."
      );
    }
  }

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="w-12 h-12 border-4 border-brand-blue border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* ---- Top nav ---- */}
      <header className="bg-brand-blue text-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex justify-between items-center">
          <div>
            <h1 className="text-lg font-semibold">Online Smart Pick</h1>
            {user?.agency_name && (
              <p className="text-xs text-brand-blue-100 opacity-90">
                {user.agency_name}
              </p>
            )}
          </div>
          <div className="flex items-center gap-4">
            {user && (
              <div className="text-right hidden sm:block">
                <p className="text-sm font-medium">{user.full_name}</p>
                <p className="text-xs text-brand-blue-100 opacity-75 capitalize">
                  {user.role}
                </p>
              </div>
            )}
            <button
              onClick={() => api.logout()}
              className="text-sm bg-brand-blue-600 hover:bg-brand-blue-700 px-3 py-1.5 rounded-md transition-colors"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>

      {/* ---- Main content ---- */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="error-banner mb-6" role="alert">
            {error}
          </div>
        )}

        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold text-slate-900">Clients</h2>
            <p className="text-sm text-slate-500 mt-1">
              {clients.length} {clients.length === 1 ? "client" : "clients"}
            </p>
          </div>
          {!showForm && (
            <button
              onClick={() => setShowForm(true)}
              className="btn-success"
            >
              + Add client
            </button>
          )}
        </div>

        {/* ---- Create form ---- */}
        {showForm && (
          <div className="card p-6 mb-6">
            <h3 className="text-lg font-semibold text-slate-900 mb-4">
              New client
            </h3>
            {formError && (
              <div className="error-banner mb-4" role="alert">
                {formError}
              </div>
            )}
            <form onSubmit={handleCreateClient} className="space-y-4">
              <div>
                <label htmlFor="new_name" className="label">
                  Client name <span className="text-red-500">*</span>
                </label>
                <input
                  id="new_name"
                  type="text"
                  className="input"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  required
                  minLength={2}
                  maxLength={255}
                  disabled={submitting}
                  placeholder="Sarah's Boutique"
                />
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label htmlFor="new_industry" className="label">
                    Industry
                  </label>
                  <input
                    id="new_industry"
                    type="text"
                    className="input"
                    value={newIndustry}
                    onChange={(e) => setNewIndustry(e.target.value)}
                    maxLength={100}
                    disabled={submitting}
                    placeholder="E-commerce"
                  />
                </div>
                <div>
                  <label htmlFor="new_email" className="label">
                    Primary contact email
                  </label>
                  <input
                    id="new_email"
                    type="email"
                    className="input"
                    value={newEmail}
                    onChange={(e) => setNewEmail(e.target.value)}
                    disabled={submitting}
                    placeholder="contact@client.com"
                  />
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button
                  type="submit"
                  className="btn-success"
                  disabled={submitting}
                >
                  {submitting ? "Creating…" : "Create client"}
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  onClick={() => {
                    setShowForm(false);
                    setFormError(null);
                    setNewName("");
                    setNewIndustry("");
                    setNewEmail("");
                  }}
                  disabled={submitting}
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {/* ---- Clients list ---- */}
        {clients.length === 0 ? (
          <div className="card p-12 text-center">
            <p className="text-slate-500 mb-4">
              You don't have any clients yet.
            </p>
            {!showForm && (
              <button
                onClick={() => setShowForm(true)}
                className="btn-success"
              >
                Add your first client
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {clients.map((client) => (
              <div
                key={client.id}
                className="card p-5 hover:shadow-md transition-shadow"
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-semibold text-slate-900 truncate">
                    {client.name}
                  </h3>
                  {client.is_active ? (
                    <span className="text-xs bg-brand-green-50 text-brand-green-700 px-2 py-0.5 rounded-full font-medium">
                      Active
                    </span>
                  ) : (
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">
                      Inactive
                    </span>
                  )}
                </div>
                {client.industry && (
                  <p className="text-sm text-slate-500 mb-1">
                    {client.industry}
                  </p>
                )}
                {client.primary_contact_email && (
                  <p className="text-xs text-slate-400 mb-3 truncate">
                    {client.primary_contact_email}
                  </p>
                )}
                <p className="text-xs text-slate-400 mb-4">
                  Added {new Date(client.created_at).toLocaleDateString()}
                </p>
                <div className="flex gap-2">
                  <button
                    className="text-xs text-slate-400 hover:text-red-600 transition-colors"
                    onClick={() => handleDelete(client.id, client.name)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ---- Roadmap footer ---- */}
        <div className="mt-12 card p-6 bg-brand-blue-50 border-brand-blue-100">
          <h3 className="text-sm font-semibold text-brand-blue mb-2">
            Coming in the next phases
          </h3>
          <ul className="text-sm text-slate-700 space-y-1 list-disc list-inside">
            <li>Phase 2 — Platform connection UI (OAuth flows for Meta, Google, etc.)</li>
            <li>Phase 3 — Nightly data sync + unified metrics dashboard</li>
            <li>Phase 4 — Claude AI Smart Picks + natural language queries</li>
            <li>Phase 5 — Automated PPTX / PDF / HTML report generation</li>
            <li>Phase 6 — Deployment to Railway + Vercel</li>
          </ul>
        </div>
      </main>
    </div>
  );
}
