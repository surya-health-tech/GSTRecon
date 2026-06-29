const API_BASE = "/api/v1";

const PF_SESSION_LOST = "pf-session-lost";

export type ApiFetchInit = RequestInit & {
  auth?: boolean;
  /** @internal retry once after access-token refresh */
  _authRetry?: boolean;
};

/** Extract a human-readable message from a JSON API body (or plain-text body). */
export function formatApiErrorBody(data: unknown, fallback: string): string {
  if (typeof data === "string" && data.trim()) return data.trim();
  if (typeof data === "object" && data !== null) {
    const o = data as Record<string, unknown>;
    if ("detail" in o) {
      const d = o.detail;
      if (typeof d === "string") return d;
      if (typeof d === "object" && d !== null && !Array.isArray(d)) {
        const block = d as Record<string, unknown>;
        if (typeof block.message === "string" && Array.isArray(block.tasks)) {
          const lines = block.tasks.map((item) => {
            if (typeof item !== "object" || item === null) return "";
            const t = item as Record<string, unknown>;
            const ref = typeof t.task_ref === "string" ? t.task_ref : "";
            const name = typeof t.name === "string" ? t.name : "Task";
            const statusLabel =
              typeof t.status_label === "string"
                ? t.status_label
                : typeof t.status === "string"
                  ? t.status
                  : "";
            const workTitle = typeof t.work_title === "string" ? t.work_title : "";
            return `• ${ref} ${name} (${statusLabel}) — ${workTitle}`.trim();
          });
          return [block.message, ...lines.filter(Boolean)].join("\n");
        }
        if (typeof block.message === "string") return block.message;
      }
      if (Array.isArray(d))
        return d
          .map((item) => {
            if (typeof item === "object" && item !== null && "msg" in item) {
              return String((item as { msg: unknown }).msg);
            }
            return JSON.stringify(item);
          })
          .join("; ");
    }
    // OAuth-style and some proxies (e.g. error="invalid_token")
    if (typeof o.error === "string") {
      const desc = typeof o.error_description === "string" ? o.error_description.trim() : "";
      const combined = desc ? `${o.error}: ${desc}` : o.error;
      if (combined.trim()) return combined.trim();
    }
  }
  return fallback;
}

/** Map cryptic or legacy API messages to clearer copy for end users. */
export function toUserFacingApiMessage(status: number, raw: string): string {
  const t = (raw || "").trim();
  const lower = t.toLowerCase();

  const looksLikeAuthTokenProblem =
    lower.includes("invalid token") ||
    lower.includes("invalid_token") ||
    lower.includes("invalid access token") ||
    lower.includes("invalid bearer") ||
    lower.includes("not authenticated") ||
    lower.includes("invalid refresh") ||
    lower.includes("invalid portal token") ||
    lower.includes("could not validate credentials") ||
    lower.includes("token has expired") ||
    lower.includes("token expired") ||
    lower.includes("jwt expired") ||
    lower.includes("signature has expired");

  const authishStatus = status === 401 || status === 403;

  if (authishStatus && looksLikeAuthTokenProblem) {
    if (lower.includes("portal") || lower.includes("client portal")) {
      return t;
    }
    return "Your session expired. Please sign in again to continue.";
  }

  if (status === 401) {
    if (lower.includes("sign in is required")) {
      return "Please sign in to continue.";
    }
    if (lower.includes("session has expired") || lower.includes("session expired")) {
      return t;
    }
    if (!t || lower === "unauthorized" || lower === "http 401" || lower === "401") {
      return "Your session expired. Please sign in again to continue.";
    }
  }
  return t || "Something went wrong. Please try again.";
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getAccessToken(): string | null {
  return localStorage.getItem("pf_access_token");
}

function getRefreshToken(): string | null {
  return localStorage.getItem("pf_refresh_token");
}

function clearFirmTokens(): void {
  localStorage.removeItem("pf_access_token");
  localStorage.removeItem("pf_refresh_token");
}

/** Clear firm tokens and broadcast so the app can return to the login screen. */
export function invalidateFirmSession(): void {
  clearFirmTokens();
  notifySessionLost();
}

/** Try to rotate firm access/refresh tokens using the stored refresh token. */
export async function refreshFirmTokens(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: rt }),
    });
    const text = await res.text();
    let data: unknown;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    if (!res.ok) return false;
    const d = data as { access_token?: string; refresh_token?: string };
    if (typeof d.access_token !== "string" || typeof d.refresh_token !== "string") return false;
    localStorage.setItem("pf_access_token", d.access_token);
    localStorage.setItem("pf_refresh_token", d.refresh_token);
    return true;
  } catch {
    return false;
  }
}

function notifySessionLost(): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(PF_SESSION_LOST));
}

export { PF_SESSION_LOST };

export async function apiFetch<T>(path: string, init: ApiFetchInit = {}): Promise<T> {
  const { auth = true, _authRetry = false, headers: hdrs, ...rest } = init;
  const headers = new Headers(hdrs);
  if (!headers.has("Content-Type") && rest.body && !(rest.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (auth) {
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const res = await fetch(`${API_BASE}${path}`, { ...rest, headers });
  const text = await res.text();
  let data: unknown = undefined;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }

  if (!res.ok) {
    const rawMsg = formatApiErrorBody(data, res.statusText);

    if (
      res.status === 401 &&
      auth &&
      !_authRetry &&
      path !== "/auth/login" &&
      path !== "/auth/refresh"
    ) {
      const refreshed = await refreshFirmTokens();
      if (refreshed) {
        return apiFetch<T>(path, { ...init, _authRetry: true });
      }
      invalidateFirmSession();
    }

    const msg = toUserFacingApiMessage(res.status, rawMsg);
    throw new ApiError(msg || "Request failed", res.status, data);
  }
  return data as T;
}

function filenameFromContentDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const match = header.match(/filename="([^"]+)"/i);
  return match?.[1] ?? fallback;
}

/** Download a file from an authenticated API route and trigger a browser save dialog. */
export async function downloadAuthenticatedFile(path: string, fallbackFilename: string): Promise<void> {
  const fetchWithAuth = async (retry: boolean) => {
    const headers = new Headers();
    const token = getAccessToken();
    if (token) headers.set("Authorization", `Bearer ${token}`);
    const res = await fetch(`${API_BASE}${path}`, { headers });
    if (res.status === 401 && !retry && path !== "/auth/login" && path !== "/auth/refresh") {
      const refreshed = await refreshFirmTokens();
      if (refreshed) return fetchWithAuth(true);
      invalidateFirmSession();
    }
    return res;
  };

  const res = await fetchWithAuth(false);
  if (!res.ok) {
    const text = await res.text();
    let data: unknown = text;
    if (text) {
      try {
        data = JSON.parse(text);
      } catch {
        data = text;
      }
    }
    const rawMsg = formatApiErrorBody(data, res.statusText);
    throw new ApiError(toUserFacingApiMessage(res.status, rawMsg) || "Download failed", res.status, data);
  }

  const blob = await res.blob();
  const filename = filenameFromContentDisposition(res.headers.get("Content-Disposition"), fallbackFilename);
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
