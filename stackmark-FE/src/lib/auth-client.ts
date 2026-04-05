const STORAGE_ACCESS = "stackmark_access_token";
const STORAGE_REFRESH = "stackmark_refresh_token";

/** Thrown after redirecting to login so callers can abort without parsing the response. */
export class AuthRedirectError extends Error {
  constructor() {
    super("Auth required");
    this.name = "AuthRedirectError";
  }
}

export function getApiBase(): string {
  return import.meta.env.PUBLIC_API_BASE ?? "http://localhost:8000";
}

export function getAccessToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(STORAGE_ACCESS);
}

export function getRefreshToken(): string | null {
  if (typeof localStorage === "undefined") return null;
  return localStorage.getItem(STORAGE_REFRESH);
}

/** True if we have either token (refresh can renew access). */
export function isLoggedIn(): boolean {
  return !!(getRefreshToken() || getAccessToken());
}

export function storeTokens(access: string, refresh?: string | null): void {
  localStorage.setItem(STORAGE_ACCESS, access);
  if (refresh) localStorage.setItem(STORAGE_REFRESH, refresh);
}

export function clearTokens(): void {
  localStorage.removeItem(STORAGE_ACCESS);
  localStorage.removeItem(STORAGE_REFRESH);
}

export async function login(
  username: string,
  password: string
): Promise<{ ok: true } | { ok: false; error: string }> {
  const res = await fetch(`${getApiBase()}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  const data = (await res.json()) as {
    success?: boolean;
    error?: string;
    data?: { access_token?: string; refresh_token?: string };
  };
  if (data.success && data.data?.access_token) {
    storeTokens(data.data.access_token, data.data.refresh_token ?? null);
    return { ok: true };
  }
  return { ok: false, error: data.error ?? "Login failed" };
}

export function logout(): void {
  clearTokens();
}

export function redirectToLogin(): void {
  const path = window.location.pathname + window.location.search;
  const q =
    path && !path.startsWith("/login")
      ? `?redirect=${encodeURIComponent(path)}`
      : "";
  window.location.href = `/login${q}`;
}

async function refreshAccessToken(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const res = await fetch(`${getApiBase()}/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  const data = (await res.json()) as {
    success?: boolean;
    data?: { access_token?: string };
  };
  if (data.success && data.data?.access_token) {
    localStorage.setItem(STORAGE_ACCESS, data.data.access_token);
    return true;
  }
  clearTokens();
  return false;
}

function resolveUrl(path: string): string {
  if (path.startsWith("http://") || path.startsWith("https://")) return path;
  const base = getApiBase().replace(/\/$/, "");
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${base}${p}`;
}

/**
 * Authenticated fetch: Bearer access token, refresh on 401/403, redirect to login if still unauthorized.
 */
export async function fetchWithAuth(
  path: string,
  init: RequestInit = {}
): Promise<Response> {
  const url = resolveUrl(path);

  async function doFetch(token: string | null): Promise<Response> {
    const h = new Headers(init.headers);
    if (token) h.set("Authorization", `Bearer ${token}`);
    if (init.body && typeof init.body === "string" && !h.has("Content-Type")) {
      h.set("Content-Type", "application/json");
    }
    return fetch(url, { ...init, headers: h });
  }

  let access = getAccessToken();
  if (!access && getRefreshToken()) {
    await refreshAccessToken();
    access = getAccessToken();
  }

  let res = await doFetch(access);

  if (res.status === 401 || res.status === 403) {
    const ok = await refreshAccessToken();
    if (ok) {
      res = await doFetch(getAccessToken());
    }
  }

  if (res.status === 401 || res.status === 403) {
    clearTokens();
    redirectToLogin();
    throw new AuthRedirectError();
  }

  return res;
}
