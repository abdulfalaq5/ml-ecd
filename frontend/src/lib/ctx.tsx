import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";

export type User = { id: number; username: string; full_name: string; role: string; role_label: string; perms: string[] };
export type Well = { id: number; name: string; section: string; role: string; status: string; shoe_md: number | null;
  data_start: string | null; data_end: string | null; fresh_min: number | null; ecd_points: number; field: string; aliases: string[]; notes: string };

type Ctx = {
  user: User | null; wells: Well[]; wellId: number | null; well: Well | null;
  setWellId: (id: number) => void; reloadWells: () => Promise<void>; logout: () => void; setUser: (u: User | null) => void;
  can: (perm: string) => boolean;
};
const C = createContext<Ctx>(null as any);
export const useApp = () => useContext(C);

function readWell(): number | null {
  try { const v = localStorage.getItem("ecd_well"); return v ? Number(v) : null; } catch { return null; }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(!getToken());
  const [wells, setWells] = useState<Well[]>([]);
  const [wellId, _setWellId] = useState<number | null>(readWell());

  const reloadWells = useCallback(async () => {
    const ws: Well[] = await api.get("/wells");
    setWells(ws);
    _setWellId((cur) => (cur && ws.some((w) => w.id === cur) ? cur : ws[0]?.id ?? null));
  }, []);

  useEffect(() => {
    if (!getToken()) return;
    api.get("/auth/me").then((u) => { setUser(u); return reloadWells(); }).catch(() => setToken(null)).finally(() => setReady(true));
  }, [reloadWells]);

  const setWellId = (id: number) => {
    _setWellId(id);
    try { localStorage.setItem("ecd_well", String(id)); } catch { /* */ }
  };
  const logout = () => { setToken(null); setUser(null); location.href = "/login"; };
  const can = (p: string) => !!user && (user.perms || []).includes(p);
  const well = wells.find((w) => w.id === wellId) || null;
  if (!ready) return <div className="empty">Memuat…</div>;
  return <C.Provider value={{ user, wells, wellId, well, setWellId, reloadWells, logout, setUser, can }}>{children}</C.Provider>;
}

/** Ambil data; `deps` memicu ulang; `every` (ms) auto-refresh. */
export function useFetch<T = any>(fn: () => Promise<T> | null, deps: any[], every?: number) {
  const [data, setData] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    const p = fn();
    if (!p) { setData(null); return; }
    setLoading(true);
    p.then((d) => { if (alive) { setData(d); setErr(null); } })
      .catch((e) => { if (alive) setErr(e.message || String(e)); })
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  useEffect(() => {
    if (!every) return;
    const h = setInterval(() => setTick((x) => x + 1), every);
    return () => clearInterval(h);
  }, [every]);
  return { data, err, loading, reload: () => setTick((x) => x + 1), setData };
}
