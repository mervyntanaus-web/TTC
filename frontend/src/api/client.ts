const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

function getToken(): string | null {
  return localStorage.getItem("ttc_token");
}

export function setToken(token: string | null) {
  if (token) localStorage.setItem("ttc_token", token);
  else localStorage.removeItem("ttc_token");
}

async function handle<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    let detail = resp.statusText;
    try {
      const body = await resp.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* ignore parse errors, fall back to statusText */
    }
    throw new ApiError(resp.status, detail);
  }
  if (resp.status === 204) return undefined as T;
  const contentType = resp.headers.get("content-type") || "";
  if (contentType.includes("application/json")) return (await resp.json()) as T;
  return undefined as T;
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = getToken();
  return {
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(extra || {}),
  };
}

export async function apiGet<T>(path: string, params?: Record<string, string | number | undefined>): Promise<T> {
  const qs = params
    ? "?" +
      Object.entries(params)
        .filter(([, v]) => v !== undefined && v !== "")
        .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`)
        .join("&")
    : "";
  const resp = await fetch(`${API_BASE}${path}${qs}`, { headers: authHeaders() });
  return handle<T>(resp);
}

export async function apiPost<T>(path: string, body?: unknown, params?: Record<string, string | number>): Promise<T> {
  const qs = params
    ? "?" + Object.entries(params).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join("&")
    : "";
  const resp = await fetch(`${API_BASE}${path}${qs}`, {
    method: "POST",
    headers: authHeaders(body !== undefined ? { "Content-Type": "application/json" } : {}),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  return handle<T>(resp);
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "PATCH",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<T>(resp);
}

export async function apiPut<T>(path: string, body: unknown): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "PUT",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(body),
  });
  return handle<T>(resp);
}

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const resp = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  return handle<T>(resp);
}

export function apiStreamUrl(path: string, params?: Record<string, string>): string {
  const qs = params ? "?" + new URLSearchParams(params).toString() : "";
  return `${API_BASE}${path}${qs}`;
}

export function authFetchInit(): RequestInit {
  return { headers: authHeaders() };
}

export { API_BASE };
