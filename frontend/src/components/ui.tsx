import { useEffect, useRef, type ReactNode } from "react";
import * as echarts from "echarts";
import { NavLink } from "react-router-dom";
import { useApp } from "../lib/ctx";
import { LEVEL_COLOR, RATHOLE, ZONE_LABEL } from "../lib/fmt";
import { RigIcon } from "./DrillingScene";

const CORE = [["1", "Live Monitor", "/monitor"], ["2", "Profil Depth", "/profil"], ["3", "Riwayat Event", "/event"],
  ["4", "Data & Upload", "/data"], ["5", "Formasi & FG", "/formasi"], ["6", "Model ML", "/model"]];
const SUP = [["0", "Overview", "/"], ["A", "Analisis Anomali", "/anomali"], ["K", "Studi Kasus Rathole", "/rathole"], ["R", "Laporan", "/laporan"], ["S", "Pengaturan", "/pengaturan"], ["?", "Panduan", "/panduan"]];

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useApp();
  const item = ([k, l, h]: string[]) => (
    <NavLink key={k} to={h} end={h === "/"} className={({ isActive }) => "it" + (isActive ? " on" : "")}>
      <span className="k">{k}</span>{l}
    </NavLink>
  );
  return (
    <div className="app">
      <nav className="nav" aria-label="Navigasi utama">
        <div className="brand">
          <RigIcon size={30} />
          <div><b>ECD Monitor</b><small>PHR Drilling · RTO</small></div>
        </div>
        <span className="sec">DASHBOARD INTI</span>
        {CORE.map(item)}
        <span className="sec">PENDUKUNG</span>
        {SUP.map(item)}
        <div className="me">
          <span>{user?.username}</span>
          <span className="muted small">Peran: {user?.role_label} · akun lokal</span>
          <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}>Keluar</a>
        </div>
      </nav>
      <main className="main">{children}</main>
    </div>
  );
}

export function Level({ v, big }: { v?: string | null; big?: boolean }) {
  const c = LEVEL_COLOR[v || "UNAVAILABLE"] || "#7A8694";
  return <span className="lvl" style={{ background: c + "22", color: c, border: `1px solid ${c}55`, fontSize: big ? 16 : undefined, padding: big ? "4px 12px" : undefined }}>{v || "UNAVAILABLE"}</span>;
}

/** Penanda zona kedalaman sebuah indikasi (hanya muncul bila sumur punya zona rathole). */
export function ZoneTag({ z }: { z?: string | null }) {
  if (!z) return null;
  const hot = z === "rathole";
  return <span className="lvl" style={{ background: hot ? RATHOLE + "22" : "#EEF1F5", color: hot ? "#8A4B00" : "#5B6775", border: `1px solid ${hot ? RATHOLE + "66" : "#D5DCE4"}` }}>{ZONE_LABEL[z] || z}</span>;
}

export function WellSelect({ label = "Room" }: { label?: string }) {
  const { wells, wellId, setWellId } = useApp();
  return (
    <label className="row small muted">{label}
      <select value={wellId ?? ""} onChange={(e) => setWellId(Number(e.target.value))}>
        {wells.length === 0 && <option value="">(belum ada sumur)</option>}
        {wells.map((w) => <option key={w.id} value={w.id}>{w.name}{w.role !== "train" ? ` · ${w.role}` : ""}</option>)}
      </select>
    </label>
  );
}

export function Kpi({ l, v, s, color }: { l: ReactNode; v: ReactNode; s?: ReactNode; color?: string }) {
  return <div className="kpi"><div className="l">{l}</div><div className="v" style={{ color }}>{v}</div>{s && <div className="s">{s}</div>}</div>;
}

export function Err({ e }: { e?: string | null }) { return e ? <div className="err">{e}</div> : null; }

export function EChart({ option, height = 300, onReady, notMerge = true }: { option: any; height?: number | string; onReady?: (c: echarts.ECharts) => void; notMerge?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const inst = useRef<echarts.ECharts | null>(null);
  useEffect(() => {
    if (!ref.current) return;
    inst.current = echarts.init(ref.current, undefined, { renderer: "canvas" });
    onReady?.(inst.current);
    const ro = new ResizeObserver(() => inst.current?.resize());
    ro.observe(ref.current);
    return () => { ro.disconnect(); inst.current?.dispose(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => { inst.current?.setOption(option, { notMerge }); }, [option, notMerge]);
  return <div ref={ref} style={{ width: "100%", height }} />;
}

export const AX = {
  axisLine: { lineStyle: { color: "#D5DCE4" } }, axisTick: { lineStyle: { color: "#D5DCE4" } },
  axisLabel: { color: "#5B6775", fontSize: 11 }, splitLine: { lineStyle: { color: "#EEF1F5" } },
  nameTextStyle: { color: "#5B6775", fontSize: 11 },
};
export const TIP = { trigger: "axis", backgroundColor: "#FFFFFF", borderColor: "#D5DCE4", textStyle: { color: "#1B2430", fontSize: 12 }, axisPointer: { type: "cross", lineStyle: { color: "#9AA5B1" } } };
