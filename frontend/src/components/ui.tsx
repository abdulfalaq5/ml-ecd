import { useEffect, useRef, type ReactNode } from "react";
import * as echarts from "echarts";
import { NavLink } from "react-router-dom";
import { useApp } from "../lib/ctx";
import { LEVEL_COLOR, RATHOLE, ZONE_LABEL } from "../lib/fmt";
import { RigIcon } from "./DrillingScene";
import { lang, setLang, t } from "../lib/i18n";

const CORE = [["1", t("Live Monitor"), "/monitor"], ["2", t("Profil Depth"), "/profil"], ["3", t("Riwayat Event"), "/event"],
  ["4", t("Data & Upload"), "/data"], ["5", t("Formasi & FG"), "/formasi"], ["6", t("Model ML"), "/model"], ["7", t("Ramalan ECD"), "/ramalan"], ["8", t("Trip Performance"), "/trip"]];
const SUP = [["0", "Overview", "/"], ["A", t("Analisis Anomali"), "/anomali"], ["K", t("Studi Kasus Rathole"), "/rathole"], ["R", t("Laporan"), "/laporan"], ["S", t("Pengaturan"), "/pengaturan"], ["?", t("Panduan"), "/panduan"]];

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useApp();
  const item = ([k, l, h]: string[]) => (
    <NavLink key={k} to={h} end={h === "/"} className={({ isActive }) => "it" + (isActive ? " on" : "")}>
      <span className="k">{k}</span>{l}
    </NavLink>
  );
  return (
    <div className="app">
      <nav className="nav" aria-label={t("Navigasi utama")}>
        <div className="brand">
          <RigIcon size={30} />
          <div><b>{t("Paningal Sense")}</b><small>{t("ECD & Hole Condition · PHR")}</small></div>
        </div>
        <span className="sec">{t("DASHBOARD INTI")}</span>
        {CORE.map(item)}
        <span className="sec">{t("PENDUKUNG")}</span>
        {SUP.map(item)}
        <div className="me">
          <span>{user?.username}</span>
          <span className="muted small">{t("Peran:")}{" "}{user?.role_label}{" "}{t("· akun lokal")}</span>
          <span className="row small" title={t("Bahasa tampilan")}>
            {(["en", "id"] as const).map((l) => <button key={l} className={lang === l ? "pri" : ""} style={{ padding: "1px 8px" }} onClick={() => lang !== l && setLang(l)}>{l.toUpperCase()}</button>)}
          </span>
          <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}>{t("Keluar")}</a>
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

/** Tipe sumur dihitung dari survey (backend core/welltype.py); urutan grup di pemilih Room. */
const WELL_TYPES: [string | null, string][] = [["Horizontal", "Horizontal"], ["J", "J-type"], ["S", "S-type"], ["Vertical", "Vertical"], [null, t("Belum ada survey")]];

export function WellSelect({ label = "Room" }: { label?: string }) {
  const { wells, wellId, setWellId } = useApp();
  return (
    <label className="row small muted">{label}
      <select value={wellId ?? ""} onChange={(e) => setWellId(Number(e.target.value))}>
        {wells.length === 0 && <option value="">{t("(belum ada sumur)")}</option>}
        {WELL_TYPES.map(([k, l]) => { const ws = wells.filter((w) => (w.well_type ?? null) === k); return ws.length ? (
          <optgroup key={String(k)} label={l}>{ws.map((w) => <option key={w.id} value={w.id}>{w.name}{w.role !== "train" ? ` · ${w.role}` : ""}</option>)}</optgroup>) : null; })}
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
