/**
 * Typed API client for the Online Smart Pick Ecosystem backend.
 *
 * Features:
 *  - JWT access + refresh tokens stored in localStorage
 *  - Automatic access-token refresh on 401 responses
 *  - Typed request/response shapes
 *  - Works in the browser only (SSR-safe guards)
 *
 * Phase 2 additions:
 *  - Email verification (verifyEmail, resendVerification)
 *  - Password reset (requestPasswordReset, confirmPasswordReset)
 *  - Metrics endpoints (listMetrics, metricTimeseries, metricSummary)
 *  - Sync trigger (triggerSync)
 */

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

// ============================================================
// Types — mirror the backend Pydantic schemas
// ============================================================

export type UserRole = "owner" | "admin" | "manager" | "viewer";

export type PlatformType =
  | "google_analytics"
  | "google_ads"
  | "google_search_console"
  | "meta_ads"
  | "meta_organic"
  | "x_ads"
  | "instagram"
  | "tiktok_ads"
  | "pinterest_ads"
  | "linkedin_ads"
  | "email_marketing";

export type ConnectionStatus =
  | "pending"
  | "active"
  | "error"
  | "disconnected";

export interface CurrentUser {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  agency_id: string;
  agency_name: string | null;
  is_active: boolean;
  is_email_verified: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in_minutes: number;
  user: CurrentUser;
}

export interface RefreshTokenResponse {
  access_token: string;
  token_type: string;
  expires_in_minutes: number;
}

export interface SignupRequest {
  agency_name: string;
  full_name: string;
  email: string;
  password: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface Client {
  id: string;
  agency_id: string;
  name: string;
  slug: string;
  industry: string | null;
  logo_url: string | null;
  primary_contact_email: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ClientCreateRequest {
  name: string;
  industry?: string;
  logo_url?: string;
  primary_contact_email?: string;
}

export interface SimpleMessageResponse {
  message: string;
}

export interface VerifyEmailRequest {
  token: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirmRequest {
  token: string;
  new_password: string;
}

// -------- Phase 2: Metrics ----------

export interface MetricRow {
  id: string;
  client_id: string;
  platform_type: PlatformType;
  metric_name: string;
  metric_value: number;
  metric_date: string;
  campaign_id: string | null;
  campaign_name: string | null;
  fetched_at: string;
}

export interface MetricTimeseriesPoint {
  date: string | null;
  platform: string | null;
  value: number;
}

export interface MetricSummary {
  row_count: number;
  platforms: string[];
  metrics: string[];
  date_range: {
    min: string | null;
    max: string | null;
  };
}

export interface MetricsListQuery {
  platform?: PlatformType;
  metric_name?: string;
  start_date?: string; // YYYY-MM-DD
  end_date?: string; // YYYY-MM-DD
  limit?: number;
}

export interface MetricTimeseriesQuery {
  metric_name: string;
  platform?: PlatformType;
  start_date?: string;
  end_date?: string;
}

export interface SyncTriggerResponse {
  client_id: string;
  task_id: string;
  message: string;
  status: string;
}

// ============================================================
// Token storage
// ============================================================

const ACCESS_KEY = "smartpick_access_token";
const REFRESH_KEY = "smartpick_refresh_token";
const USER_KEY = "smartpick_user";

const isBrowser = () => typeof window !== "undefined";

export const tokenStorage = {
  getAccess: (): string | null =>
    isBrowser() ? localStorage.getItem(ACCESS_KEY) : null,
  getRefresh: (): string | null =>
    isBrowser() ? localStorage.getItem(REFRESH_KEY) : null,
  getUser: (): CurrentUser | null => {
    if (!isBrowser()) return null;
    const raw = localStorage.getItem(USER_KEY);
    if (!raw) return null;
    try {
      return JSON.parse(raw) as CurrentUser;
    } catch {
      return null;
    }
  },
  setTokens: (access: string, refresh: string) => {
    if (!isBrowser()) return;
    localStorage.setItem(ACCESS_KEY, access);
    localStorage.setItem(REFRESH_KEY, refresh);
  },
  setAccess: (access: string) => {
    if (!isBrowser()) return;
    localStorage.setItem(ACCESS_KEY, access);
  },
  setUser: (user: CurrentUser) => {
    if (!isBrowser()) return;
    localStorage.setItem(USER_KEY, JSON.stringify(user));
  },
  clear: () => {
    if (!isBrowser()) return;
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
  isAuthenticated: (): boolean =>
    isBrowser() && !!localStorage.getItem(ACCESS_KEY),
};

// ============================================================
// API error
// ============================================================

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
    this.detail = detail;
    this.name = "ApiError";
  }
}

// ============================================================
// Core fetch wrapper
// ============================================================

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  auth?: boolean; // default true
  // Internal flag to prevent infinite refresh loops
  _isRetry?: boolean;
}

/**
 * Low-level request helper. Handles:
 *  - JSON serialization
 *  - Authorization header injection
 *  - Automatic token refresh on 401 (one retry, then gives up)
 */
async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = true, _isRetry = false } = options;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    Accept: "application/json",
  };

  if (auth) {
    const token = tokenStorage.getAccess();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const init: RequestInit = {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  };

  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, init);
  } catch (networkError) {
    throw new ApiError(
      0,
      "Cannot reach the backend. Is it running on " + API_URL + "?"
    );
  }

  // Handle 401 — try refresh once
  if (response.status === 401 && auth && !_isRetry) {
    const refreshed = await tryRefreshAccessToken();
    if (refreshed) {
      return request<T>(path, { ...options, _isRetry: true });
    } else {
      tokenStorage.clear();
      if (isBrowser() && !window.location.pathname.startsWith("/login")) {
        window.location.href = "/login";
      }
      throw new ApiError(401, "Session expired. Please log in again.");
    }
  }

  // 204 No Content — nothing to parse
  if (response.status === 204) {
    return undefined as T;
  }

  // Parse JSON body (error or success)
  let data: any;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    const detail =
      (data && (data.detail || data.message)) ||
      `Request failed with status ${response.status}`;
    throw new ApiError(response.status, detail);
  }

  return data as T;
}

/**
 * Try to exchange the refresh token for a new access token.
 * Returns true on success, false otherwise.
 */
async function tryRefreshAccessToken(): Promise<boolean> {
  const refreshToken = tokenStorage.getRefresh();
  if (!refreshToken) return false;
  try {
    const resp = await fetch(`${API_URL}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!resp.ok) return false;
    const data: RefreshTokenResponse = await resp.json();
    tokenStorage.setAccess(data.access_token);
    return true;
  } catch {
    return false;
  }
}

/**
 * Small helper to build querystrings from objects with undefined-safe keys.
 */
function buildQuery(params: Record<string, unknown>): string {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`);
  }
  return parts.length ? `?${parts.join("&")}` : "";
}

// ============================================================
// Public API methods
// ============================================================

export const api = {
  // ---- Auth ----
  async signup(data: SignupRequest): Promise<TokenResponse> {
    const resp = await request<TokenResponse>("/auth/signup", {
      method: "POST",
      body: data,
      auth: false,
    });
    tokenStorage.setTokens(resp.access_token, resp.refresh_token);
    tokenStorage.setUser(resp.user);
    return resp;
  },

  async login(data: LoginRequest): Promise<TokenResponse> {
    const resp = await request<TokenResponse>("/auth/login", {
      method: "POST",
      body: data,
      auth: false,
    });
    tokenStorage.setTokens(resp.access_token, resp.refresh_token);
    tokenStorage.setUser(resp.user);
    return resp;
  },

  async me(): Promise<CurrentUser> {
    const user = await request<CurrentUser>("/auth/me");
    tokenStorage.setUser(user);
    return user;
  },

  logout(): void {
    tokenStorage.clear();
    if (isBrowser()) window.location.href = "/login";
  },

  // ---- Email verification (Phase 2) ----
  async verifyEmail(token: string): Promise<SimpleMessageResponse> {
    return request<SimpleMessageResponse>("/auth/verify-email", {
      method: "POST",
      body: { token } as VerifyEmailRequest,
      auth: false,
    });
  },

  async resendVerification(): Promise<SimpleMessageResponse> {
    return request<SimpleMessageResponse>("/auth/resend-verification", {
      method: "POST",
    });
  },

  // ---- Password reset (Phase 2) ----
  async requestPasswordReset(email: string): Promise<SimpleMessageResponse> {
    return request<SimpleMessageResponse>("/auth/password-reset/request", {
      method: "POST",
      body: { email } as PasswordResetRequest,
      auth: false,
    });
  },

  async confirmPasswordReset(
    token: string,
    newPassword: string
  ): Promise<SimpleMessageResponse> {
    return request<SimpleMessageResponse>("/auth/password-reset/confirm", {
      method: "POST",
      body: { token, new_password: newPassword } as PasswordResetConfirmRequest,
      auth: false,
    });
  },

  // ---- Clients ----
  async listClients(): Promise<Client[]> {
    return request<Client[]>("/clients");
  },

  async createClient(data: ClientCreateRequest): Promise<Client> {
    return request<Client>("/clients", { method: "POST", body: data });
  },

  async getClient(id: string): Promise<Client> {
    return request<Client>(`/clients/${id}`);
  },

  async deleteClient(id: string): Promise<void> {
    return request<void>(`/clients/${id}`, { method: "DELETE" });
  },

  // ---- Metrics (Phase 2) ----
  async listMetrics(
    clientId: string,
    query: MetricsListQuery = {}
  ): Promise<MetricRow[]> {
    const qs = buildQuery(query as Record<string, unknown>);
    return request<MetricRow[]>(`/clients/${clientId}/metrics${qs}`);
  },

  async metricTimeseries(
    clientId: string,
    query: MetricTimeseriesQuery
  ): Promise<MetricTimeseriesPoint[]> {
    const qs = buildQuery(query as Record<string, unknown>);
    return request<MetricTimeseriesPoint[]>(
      `/clients/${clientId}/metrics/timeseries${qs}`
    );
  },

  async metricSummary(
    clientId: string,
    query: { start_date?: string; end_date?: string } = {}
  ): Promise<MetricSummary> {
    const qs = buildQuery(query as Record<string, unknown>);
    return request<MetricSummary>(`/clients/${clientId}/metrics/summary${qs}`);
  },

  // ---- Sync (Phase 2) ----
  async triggerSync(clientId: string): Promise<SyncTriggerResponse> {
    return request<SyncTriggerResponse>(`/data/sync/${clientId}`, {
      method: "POST",
    });
  },

  // ---- Health ----
  async health(): Promise<{ status: string; app: string; env: string }> {
    return request("/health", { auth: false });
  },
};

export default api;
