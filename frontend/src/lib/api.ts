import { lang } from "./i18n";
const KEY = "ecd_token";

export function getToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(KEY, t) : localStorage.removeItem(KEY); } catch { /* ignore */ }
}

export class ApiError extends Error {
  constructor(public status: number, msg: string) { super(msg); }
}

async function handle(r: Response) {
  if (r.status === 401) {
    setToken(null);
    if (!location.pathname.startsWith("/login")) location.href = "/login";
  }
  if (!r.ok) {
    let msg = r.statusText;
    try { const j = await r.json(); msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail); } catch { /* */ }
    throw new ApiError(r.status, msg);
  }
  const ct = r.headers.get("content-type") || "";
  return ct.includes("json") ? r.json() : r.blob();
}

function headers(extra: Record<string, string> = {}) {
  const t = getToken();
  return { ...(t ? { Authorization: `Bearer ${t}` } : {}), "X-Lang": lang, ...extra };
}

export const api = {
  get: (path: string, params?: Record<string, any>) => {
    const q = params ? "?" + new URLSearchParams(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== "").map(([k, v]) => [k, String(v)])) : "";
    return fetch(`/api${path}${q}`, { headers: headers() }).then(handle);
  },
  post: (path: string, body?: any) =>
    fetch(`/api${path}`, { method: "POST", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body ?? {}) }).then(handle),
  put: (path: string, body?: any) =>
    fetch(`/api${path}`, { method: "PUT", headers: headers({ "Content-Type": "application/json" }), body: JSON.stringify(body ?? {}) }).then(handle),
  del: (path: string) => fetch(`/api${path}`, { method: "DELETE", headers: headers() }).then(handle),
  form: (path: string, fd: FormData) => fetch(`/api${path}`, { method: "POST", headers: headers(), body: fd }).then(handle),
  download: async (path: string, filename: string) => {
    const b = await fetch(`/api${path}`, { headers: headers() }).then(handle);
    const url = URL.createObjectURL(b as Blob);
    const a = document.createElement("a");
    a.href = url; a.download = filename; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  },
  login: async (username: string, password: string) => {
    const fd = new URLSearchParams({ username, password });
    const r = await fetch("/api/auth/login", { method: "POST", body: fd });
    const j = await handle(r);
    setToken(j.access_token);
    return j;
  },
};
