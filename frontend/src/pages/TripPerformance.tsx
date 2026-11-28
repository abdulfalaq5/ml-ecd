import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ft, n, toLocalInput, wib } from "../lib/fmt";
import { AX, EChart, Err, Kpi, TIP, WellSelect } from "../components/ui";
import { t } from "../lib/i18n";

const DIR_COLOR: Record<string, string> = { TIH: "#2F6FD1", TOH: "#E07A10" };
const DIR_LABEL: Record<string, string> = { TIH: t("Trip in (TIH)"), TOH: t("Trip out (TOH)") };
const CREW_COLOR: Record<string, string> = { AM: "#5AA9E6", PM: "#1F3A93" };
const LOC_LABEL: Record<string, string> = { all: "Semua", cased: t("Cased hole"), open: t("Open hole") };
const TARGET_LINE = "#E4572E";
const UNIT_WORD: Record<string, string> = { stand: "stand", joint: "joint" };

// warna kotak selisih: lebih baik = hijau, lebih buruk ≤ 10% = kuning, lebih buruk > 10% = merah
function vsColor(pct: number | null | undefined, higherBetter: boolean) {
  if (pct == null) return { bg: t("var(--bg2, #F3F5F8)"), fg: "#3A4552" };
  const worse = higherBetter ? -pct : pct;
  if (worse <= 0) return { bg: "#DFF3E4", fg: "#1A7F37" };
  if (worse <= 10) return { bg: "#FFF4D6", fg: "#9A6700" };
  return { bg: "#FDE2E1", fg: "#C0362C" };
}

function histogram(vals: number[], bins = 20, cap?: number) {
  const v = vals.filter((x) => x != null && isFinite(x)).map((x) => (cap ? Math.min(x, cap) : x));
  if (!v.length) return { x: [] as string[], y: [] as number[] };
  const lo = Math.min(...v), hi = Math.max(...v);
  const w = (hi - lo) / bins || 1;
  const y = new Array(bins).fill(0);
  v.forEach((x) => { y[Math.min(bins - 1, Math.floor((x - lo) / w))]++; });
  return { x: y.map((_, i) => n(lo + (i + 0.5) * w, 1)), y };
}

function TargetBox({ title, med, target, manual, pct, unit, higherBetter, kind }: any) {
  const c = vsColor(pct, higherBetter);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 130 }}>
      <div style={{ border: "1px solid var(--line, #D8DEE6)", borderRadius: 6, padding: "6px 8px", textAlign: "center" }}>
        <div className="mono" style={{ fontSize: 18 }}>{target == null ? "—" : n(target)}</div>
        <div className="muted small">{manual ? t("Target {p0}", { p0: kind }) : t("{p0} data periode ini", { p0: kind })}</div>
      </div>
      <div style={{ textAlign: "center" }}>
        <div className="mono" style={{ fontSize: 26, fontWeight: 600 }}>{med == null ? "—" : n(med)}</div>
        <div className="muted small">{t("Median")}{" "}{title} ({unit})</div>
      </div>
      <div style={{ background: c.bg, color: c.fg, borderRadius: 6, padding: "6px 8px", textAlign: "center" }}>
        <div className="small">{t("vs")}{" "}{kind}</div>
        <div className="mono" style={{ fontSize: 22, fontWeight: 600 }}>{pct == null ? "—" : `${pct > 0 ? "+" : ""}${n(pct, 0)}%`}</div>
      </div>
    </div>
  );
}

function KpiRow({ title, unit, hist, chart, box }: any) {
  return (
    <div className="card" style={{ padding: 10 }}>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(180px, 1fr) minmax(320px, 3fr) auto", gap: 12, alignItems: "stretch" }}>
        <div><h3 style={{ margin: "0 0 4px" }}>{title}</h3>{hist}</div>
        <div><h3 style={{ margin: "0 0 4px" }}>{title}{" "}{t("vs measured depth")}{" "}<span className="muted small">({unit})</span></h3>{chart}</div>
        {box}
      </div>
    </div>
  );
}

function TargetEditor({ onSaved }: { onSaved: () => void }) {
  const { can } = useApp();
  const { data, err, reload } = useFetch<any>(() => api.get("/trip-targets"), []);
  const [v, setV] = useState<any>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (data) setV(JSON.parse(JSON.stringify(data.value))); }, [data]);
  if (!v) return <Err e={err} />;
  const set = (u: string, l: string, k: string, x: string) => setV({ ...v, [u]: { ...v[u], [l]: { ...v[u][l], [k]: x === "" ? null : x } } });
  const edit = can("threshold_propose");
  const save = async () => {
    try { await api.put("/trip-targets", { value: v }); setMsg(t("Target tersimpan.")); reload(); onSaved(); }
    catch (e: any) { setMsg(e.message || String(e)); }
  };
  const cell = (u: string, l: string, k: string) => (
    <td><input type="number" step="0.1" style={{ width: 80 }} disabled={!edit} value={v[u][l][k] ?? ""} placeholder={t("dari data")}
      onChange={(e) => set(u, l, k, e.target.value)} /></td>);
  return (
    <div>
      <table>
        <thead><tr><th>{t("Mode")}</th><th>{t("Lokasi")}</th><th>{t("Stand/joint per jam (P75)")}</th><th>{t("In-slip (mnt, P25)")}</th><th>{t("Moving time (mnt, P25)")}</th></tr></thead>
        <tbody>{["stand", "joint"].flatMap((u) => ["cased", "open"].map((l) => (
          <tr key={u + l}><td>{u === "stand" ? t("Stand DP/BHA") : t("Joint casing")}</td><td>{LOC_LABEL[l]}</td>{cell(u, l, "jph")}{cell(u, l, "in_min")}{cell(u, l, "move_min")}</tr>)))}
        </tbody>
      </table>
      <div className="row" style={{ gap: 12, marginTop: 8, alignItems: "flex-end", flexWrap: "wrap" }}>
        <label className="f">{t("Target gross trip speed (ft/jam)")}
          <input type="number" step="1" disabled={!edit} value={v.gross_ft_h ?? ""} onChange={(e) => setV({ ...v, gross_ft_h: e.target.value === "" ? null : e.target.value })} /></label>
        {edit && <button className="pri" onClick={save}>{t("Simpan target")}</button>}
        <span className="muted small">{t("Kosong = dibandingkan dengan P75 / P25 data periode yang dipilih.")}{" "}{data?.updated_by ? t("Terakhir diubah {p0}, {p1}.", { p0: data.updated_by, p1: wib(data.updated_at, true) }) : ""}</span>
      </div>
      {msg && <div className="muted small" style={{ marginTop: 6 }}>{msg}</div>}
    </div>
  );
}

const TRACK_H = 620;
const depthY = (lo: number, hi: number) => ({ type: "value", inverse: true, min: lo, max: hi, ...AX, name: t("MD (ft)"), nameLocation: "start",
  axisLabel: { ...(AX as any).axisLabel, formatter: (v: number) => ft(v) } });

/** Log vs depth format SLB hal. 5: kolom T&D | Bending moment | Deviation (DLS & inklinasi). Kedalaman ke bawah. */
function DepthLog({ wellId, stands, shoe, word }: { wellId: number; stands: any[]; shoe: number | null; word: string }) {
  const dev = useFetch<any>(() => api.get(`/wells/${wellId}/deviation`), [wellId]);
  const [whole, setWhole] = useState(false);
  const sv: any[] = dev.data?.survey || [];
  const mds = stands.map((s) => s.md);
  const tripLo = mds.length ? Math.min(...mds) : null, tripHi = mds.length ? Math.max(...mds) : null;
  const svHi = sv.length ? sv[sv.length - 1].md : 0;
  const useWhole = whole || tripLo == null;
  const pad = useWhole ? 0 : Math.max(100, ((tripHi as number) - (tripLo as number)) * 0.05);
  const lo = useWhole ? 0 : Math.max(0, Math.floor(((tripLo as number) - pad) / 100) * 100);
  const hi = useWhole ? Math.ceil(Math.max(svHi, tripHi ?? 0) / 100) * 100 || 1000 : Math.ceil(((tripHi as number) + pad) / 100) * 100;
  const shoeMark = shoe ? { symbol: "none", silent: true, data: [{ yAxis: shoe, lineStyle: { color: "#8A94A3", type: "dashed" }, label: { formatter: t("shoe {p0}", { p0: ft(shoe) }), position: "insideStartTop", color: "#5B6775", fontSize: 10 } }] } : undefined;
  const openArea = shoe ? { silent: true, itemStyle: { color: "rgba(224,122,16,0.06)" }, data: [[{ yAxis: shoe }, { yAxis: hi }]] } : undefined;
  const grid = { left: 58, right: 12, top: 56, bottom: 16 };
  const tip = (unit: string) => ({ ...TIP, trigger: "axis", axisPointer: { type: "line", axis: "y" },
    formatter: (ps: any[]) => t("{p0} ft<br/>", { p0: ft(ps[0]?.value?.[1]) }) + ps.filter((p) => p.value?.[0] != null).map((p) => t("{p0}{p1}: {p2} {p3}", { p0: p.marker, p1: p.seriesName, p2: n(p.value[0], 1), p3: unit })).join("<br/>") });

  const tnd = {
    animation: false, grid, tooltip: { ...TIP, trigger: "item", formatter: (p: any) => t("{p0}<br/>{p1} ft · {p2} klb", { p0: p.seriesName, p1: ft(p.value[1]), p2: n(p.value[0], 1) }) },
    legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 10 }, itemWidth: 10 },
    xAxis: { type: "value", position: "top", name: t("hookload (klb)"), nameLocation: "middle", nameGap: 22, scale: true, ...AX },
    yAxis: depthY(lo, hi),
    series: [
      ...["TIH", "TOH"].map((d) => ({ name: t("{p0} terukur", { p0: d }), type: "scatter", symbolSize: 4, itemStyle: { color: DIR_COLOR[d], opacity: 0.75 },
        data: stands.filter((x) => x.dir === d && x.hk != null).map((x) => [x.hk, x.md]) })),
      { name: "shoe", type: "line", data: [], markLine: shoeMark, markArea: openArea, silent: true, showInLegend: false },
    ],
  };
  const devOpt = {
    animation: false, grid: { ...grid, bottom: 44 }, tooltip: tip(""),
    legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 10 }, itemWidth: 12, data: [t("Inklinasi (°)"), t("DLS (°/100 ft)")] },
    xAxis: [
      { type: "value", position: "top", min: 0, max: 90, interval: 30, name: t("Inc (°)"), nameLocation: "middle", nameGap: 22, ...AX },
      { type: "value", position: "bottom", min: 0, max: (v: any) => Math.max(5, Math.ceil(v.max)), name: t("DLS (°/100 ft)"), nameLocation: "middle", nameGap: 22, ...AX,
        axisLine: { show: true, lineStyle: { color: "#C0362C" } }, axisLabel: { color: "#C0362C", fontSize: 11 }, nameTextStyle: { color: "#C0362C", fontSize: 11 }, splitLine: { show: false } },
    ],
    yAxis: depthY(lo, hi),
    series: [
      { name: t("Inklinasi (°)"), type: "line", xAxisIndex: 0, symbol: "circle", symbolSize: 3, lineStyle: { color: "#1F2933", width: 1.5 }, itemStyle: { color: "#1F2933" },
        data: sv.map((x) => [x.inc, x.md]), markLine: shoeMark, markArea: openArea },
      { name: t("DLS (°/100 ft)"), type: "line", xAxisIndex: 1, step: "end", symbol: "none", lineStyle: { color: "#C0362C", width: 1.5 }, itemStyle: { color: "#C0362C" },
        data: sv.map((x) => [x.dls, x.md]) },
    ],
  };
  const cell = (title: string, sub: string, body: any) => (
    <div style={{ border: "1px solid var(--line, #D8DEE6)", borderRadius: 6, padding: 6, minWidth: 0 }}>
      <div style={{ textAlign: "center", fontWeight: 600 }}>{title}</div>
      <div className="muted small" style={{ textAlign: "center", minHeight: 18 }}>{sub}</div>
      {body}
    </div>);
  return (
    <div className="card">
      <div className="row" style={{ alignItems: "center", flexWrap: "wrap", gap: 12 }}>
        <h3 style={{ margin: 0 }}>{t("Log vs depth")}</h3>
        <span className="muted small">{t("format laporan SLB hal. 5 · kedalaman ke bawah · area oranye = open hole (di bawah shoe)")}</span>
        <span className="sp" />
        <label className="small row" style={{ gap: 4 }}><input type="checkbox" checked={useWhole} disabled={tripLo == null} onChange={(e) => setWhole(e.target.checked)} />{" "}{t("seluruh sumur")}</label>
      </div>
      <Err e={dev.err} />
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: 8, marginTop: 8 }}>
        {cell("T&D", t("hookload per {p0} saat bergerak", { p0: word }), <>
          <EChart option={tnd} height={TRACK_H} />
          <div className="muted small">{t("Kurva model PU / SO / ROT (broomstick) menyusul setelah pipe tally masuk.")}</div></>)}
        {cell(t("Bending moment"), t("estimasi dari survey"), (
          <div className="muted small" style={{ height: TRACK_H, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 16, background: "#F7F9FB", borderRadius: 4 }}>
            {t("Menunggu pipe tally (OD / ID / berat / panjang joint dan batas bending sambungan).")}<br /><br />{t("Estimasi dari kelengkungan lubang, bukan sensor downhole.")}
          </div>))}
        {cell(t("Deviation data"), sv.length ? t("{p0} stasiun survey · Inc maks {p1}° · DLS maks {p2}°/100 ft{p3}", { p0: sv.length, p1: n(dev.data?.inc_max, 1), p2: n(dev.data?.dls_max, 1), p3: dev.data?.dls_computed ? " · DLS dihitung" : "" }) : "", sv.length
          ? <EChart option={devOpt} height={TRACK_H} />
          : <div className="muted small" style={{ height: TRACK_H, display: "flex", alignItems: "center", justifyContent: "center", textAlign: "center", padding: 16 }}>{t("Belum ada survey. Upload survey (Navita Rec 07 atau CSV / Excel MD, Inc, Azi) di Data & Upload.")}</div>)}
      </div>
      <div className="muted small" style={{ marginTop: 6 }}>{t("Deviation: inklinasi (hitam, sumbu 0–90°) dan DLS (merah, °/100 ft, berlaku per interval antar stasiun) dari survey. Default rentang = kedalaman trip di periode terpilih.")}</div>
    </div>
  );
}

export default function TripPerformance() {
  const { wellId } = useApp();
  const [t0, setT0] = useState(""); const [t1, setT1] = useState("");
  const [unit, setUnit] = useState("stand");
  const [applied, setApplied] = useState({ t0: "", t1: "", unit: "stand" });
  const [dir, setDir] = useState<"TIH" | "TOH">("TIH");
  const [loc, setLoc] = useState("all");
  const [showTargets, setShowTargets] = useState(false);
  const { data, err, loading, reload } = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/trips`, applied) : null), [wellId, applied]);
  useEffect(() => { setApplied({ t0: "", t1: "", unit }); setT0(""); setT1(""); }, [wellId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (data && !data.empty && !t0) { setT0(toLocalInput(data.t0)); setT1(toLocalInput(data.t1)); } }, [data, t0]);
  useEffect(() => { if (data?.kpi && !data.kpi[dir] && Object.keys(data.kpi).length) setDir(Object.keys(data.kpi)[0] as any); }, [data, dir]);

  const word = UNIT_WORD[data?.unit || "stand"];
  const k = data?.kpi?.[dir]?.[loc] ?? null;
  const locs = Object.keys(data?.kpi?.[dir] || {});
  const st = useMemo(() => (data?.stands || []).filter((s: any) => s.dir === dir && (loc === "all" || s.loc === loc)), [data, dir, loc]);

  const histOpt = (vals: number[], name: string, cap?: number) => {
    const h = histogram(vals, 20, cap);
    return { animation: false, grid: { left: 36, right: 6, top: 8, bottom: 34 }, tooltip: { ...TIP, trigger: "axis" },
      xAxis: { type: "category", data: h.x, ...AX, name, nameLocation: "middle", nameGap: 22 },
      yAxis: { type: "value", ...AX, name: "jumlah" }, series: [{ type: "bar", data: h.y, itemStyle: { color: DIR_COLOR[dir] }, barCategoryGap: "10%" }] };
  };
  const shoeLine = data?.shoe_md ? [{ xAxis: data.shoe_md, lineStyle: { color: "#8A94A3", type: "dashed" }, label: { formatter: "shoe", color: "#8A94A3" } }] : [];
  const depthOpt = (key: string, yname: string, target: number | null, cap: number) => ({
    animation: false, grid: { left: 44, right: 16, top: 26, bottom: 34 }, legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 11 } },
    tooltip: { ...TIP, trigger: "item", formatter: (p: any) => t("{p0}<br/>{p1} ft · {p2}{p3}", { p0: p.seriesName, p1: ft(p.value[0]), p2: n(p.value[1]), p3: p.value[2] ? `<br/>${wib(p.value[2], true)}` : "" }) },
    xAxis: { type: "value", ...AX, name: t("Measured depth (ft)"), nameLocation: "middle", nameGap: 22, scale: true },
    yAxis: { type: "value", ...AX, name: yname, max: (v: any) => Math.min(Math.ceil(v.max), cap) },
    series: [
      ...["AM", "PM"].map((c) => ({ name: t("{p0} crew", { p0: c }), type: "bar", barWidth: 2, itemStyle: { color: CREW_COLOR[c] },
        data: st.filter((s: any) => s.crew === c && s[key] != null).map((s: any) => [s.md, Math.min(s[key], cap), s.t]) })),
      { name: target == null ? t("P25 data") : "Target", type: "line", symbol: "none", data: [], markLine: { symbol: "none", silent: true,
        data: [...(target != null ? [{ yAxis: target, lineStyle: { color: TARGET_LINE, width: 2, type: "solid" }, label: { formatter: n(target) } }] : []), ...shoeLine] } },
    ],
  });
  const jphOpt = useMemo(() => {
    if (!st.length) return null;
    const tgt = k?.target?.jph ?? null;
    const sorted = [...st].sort((a: any, b: any) => a.md - b.md);
    return {
      animation: false, grid: { left: 44, right: 16, top: 26, bottom: 34 }, legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 11 } },
      tooltip: { ...TIP, trigger: "item", formatter: (p: any) => t("{p0}<br/>{p1} ft · {p2} {p3}/jam", { p0: p.seriesName, p1: ft(p.value[0]), p2: n(p.value[1], 1), p3: word }) },
      xAxis: { type: "value", ...AX, name: t("Measured depth (ft)"), nameLocation: "middle", nameGap: 22, scale: true },
      yAxis: { type: "value", ...AX, name: `${word}/jam`, min: 0, max: (v: any) => Math.min(Math.ceil(v.max), 40) },
      series: [
        { name: t("Per {p0}", { p0: word }), type: "scatter", symbolSize: 3, itemStyle: { color: DIR_COLOR[dir], opacity: 0.35 }, data: sorted.filter((s: any) => s.jph != null).map((s: any) => [s.md, s.jph]) },
        { name: t("Rolling 5 {p0}", { p0: word }), type: "line", symbol: "none", connectNulls: false, lineStyle: { color: DIR_COLOR[dir], width: 1.5 },
          data: sorted.map((s: any) => [s.md, s.jph_roll]) },
        { name: tgt == null ? t("P75 data") : "Target", type: "line", symbol: "none", data: [], markLine: { symbol: "none", silent: true,
          data: [...(tgt != null ? [{ yAxis: tgt, lineStyle: { color: TARGET_LINE, width: 2, type: "solid" }, label: { formatter: n(tgt, 1) } }] : []), ...shoeLine] } },
      ],
    };
  }, [st, k, dir, word]); // eslint-disable-line react-hooks/exhaustive-deps


  const has = data && !data.empty && Object.keys(data.kpi || {}).length > 0;
  return (
    <>
      <div className="top"><h1>{t("Trip Performance")}</h1><WellSelect /><span className="sp" /></div>
      <div className="card">
        <div className="row" style={{ flexWrap: "wrap", gap: 12, alignItems: "flex-end" }}>
          <label className="f">{t("Dari (WIB)")}<input type="datetime-local" value={t0} onChange={(e) => setT0(e.target.value)} /></label>
          <label className="f">{t("Sampai (WIB)")}<input type="datetime-local" value={t1} onChange={(e) => setT1(e.target.value)} /></label>
          <label className="f">{t("Rangkaian")}
            <select value={unit} onChange={(e) => setUnit(e.target.value)}>
              <option value="stand">{t("Stand DP / BHA (double ±62 ft)")}</option>
              <option value="joint">{t("Joint casing (single ±40 ft)")}</option>
            </select></label>
          <button className="pri" onClick={() => setApplied({ t0, t1, unit })} disabled={loading}>{loading ? t("Menghitung…") : t("Hitung")}</button>
          <button onClick={() => setShowTargets((x) => !x)}>{showTargets ? t("Tutup target") : t("Atur target")}</button>
          <span className="muted small">{t("Maks 14 hari. Default 7 hari terakhir data.")}{" "}{data && !data.empty ? t("Data sumur: {p0} → {p1}", { p0: wib(data.data_start, true), p1: wib(data.data_end, true) }) : ""}</span>
        </div>
        <details style={{ marginTop: 10 }}>
          <summary className="muted small">{t("Cara hitung")}</summary>
          <p className="note">
            {t("Slips dibaca dari hookload & bit depth (Navita tidak punya kanal slips), hanya saat bit ≥")}{" "}{data?.params?.off_bottom_ft ?? 100}{" "}{t("ft di atas dasar.")}
            <b>{" "}{t("In-slip")}</b>{" "}{t("= hookload ≈ berat block")}{" "}{data?.block_klb != null ? t("({p0} klb)", { p0: n(data.block_klb, 1) }) : ""} + {data?.params?.slip_margin_klb ?? 15}{" "}{t("klb")}
            {data?.threshold_klb != null ? t(" = {p0} klb", { p0: n(data.threshold_klb, 1) }) : ""}{t(": set slips, sambung/lepas, torque.")}{" "}<b>{t("Moving time")}</b>{" "}{t("= string tergantung, bit bergerak satu")}{" "}{word}
            ({data?.params?.stand_min_ft ?? 55}–{data?.params?.stand_max_ft ?? 105}{" "}{t("ft).")}{" "}<b>{t("Siklus")}</b>{" "}{t("= out-of-slip → out-of-slip berikutnya;")}{" "}{word}{t("/jam = 60 / siklus (menit), garis = rolling 5")}{" "}{word}. <b>{t("Gross speed")}</b>{" "}{t("= kedalaman ditempuh / waktu berlalu termasuk berhenti. In-slip >")}{" "}{Math.round((data?.params?.in_max_s ?? 900) / 60)}{" "}{t("menit (flow check, perbaikan, menunggu) = berhenti: tidak masuk median, tetap masuk gross speed. Crew AM = 06:00–18:00 WIB. Cased / open hole dari shoe")}{" "}{data?.shoe_md ? t("{p0} ft", { p0: ft(data.shoe_md) }) : t("(belum diisi)")}{t(". Target: P75")}{" "}{word}{t("/jam, P25 in-slip & moving (makin kecil makin baik); bila belum diisi, dibandingkan dengan P75/P25 data periode ini sendiri.")}
            {data?.step_s ? t(" Resolusi data ±{p0} detik.", { p0: n(data.step_s, 0) }) : ""}
          </p>
        </details>
        {(data?.warnings || []).map((w: string, i: number) => <div key={i} className="err">{w}</div>)}
      </div>
      {showTargets && <div className="card"><h3>{t("Target trip performance")}</h3><TargetEditor onSaved={reload} /></div>}
      <Err e={err} />
      {has && (<>
        <div className="card" style={{ padding: 10 }}>
          <div className="row" style={{ gap: 16, flexWrap: "wrap", alignItems: "center" }}>
            <div className="row" style={{ gap: 4 }}>{(["TIH", "TOH"] as const).map((d) => (
              <button key={d} className={dir === d ? "pri" : ""} disabled={!data.kpi[d]} onClick={() => setDir(d)}>{DIR_LABEL[d]}</button>))}</div>
            <div className="row" style={{ gap: 4 }}>{["all", "cased", "open"].map((l) => (
              <button key={l} className={loc === l ? "pri" : ""} disabled={!locs.includes(l)} onClick={() => setLoc(l)}>{LOC_LABEL[l]}</button>))}</div>
            <span className="muted small">{t("Lingkup:")}{" "}{data.well} · {DIR_LABEL[dir]} · {LOC_LABEL[loc]} · {k?.n ?? 0} {word}</span>
          </div>
        </div>
        {!k ? <div className="card muted">{t("Tidak ada")}{" "}{word} {DIR_LABEL[dir]}{" "}{t("di")}{" "}{LOC_LABEL[loc].toLowerCase()}{" "}{t("pada rentang ini.")}</div> : (<>
          <div className="kpis">
            <Kpi l={t("Gross trip speed")} v={`${ft(k.gross_ft_h)} ft/jam`} color={vsColor(k.vs.gross_ft_h, true).fg}
              s={k.target.gross_ft_h != null ? t("target {p0} ft/jam · {p1}{p2}%", { p0: ft(k.target.gross_ft_h), p1: k.vs.gross_ft_h > 0 ? "+" : "", p2: n(k.vs.gross_ft_h, 0) }) : t("belum ada target")} />
            <Kpi l={t("Median {p0}/jam", { p0: word })} v={n(k.jph_med, 1)} s={t("{p0} {p1} · {p2} ft dalam {p3} jam", { p0: k.n, p1: word, p2: ft(k.ft), p3: n(k.hours, 1) })} color={DIR_COLOR[dir]} />
            <Kpi l={t("Median in-slip")} v={`${n(k.in_med)} mnt`} s={t("P25 {p0} · P75 {p1} mnt", { p0: n(k.in_p25_data), p1: n(k.in_p75) })} />
            <Kpi l={t("Median moving time")} v={`${n(k.move_med)} mnt`} s={t("P25 {p0} · P75 {p1} mnt", { p0: n(k.move_p25_data), p1: n(k.move_p75) })} />
          </div>
          {k.notes.length > 0 && <div className="card" style={{ borderLeft: "4px solid #9A6700" }}>
            <h3 style={{ marginTop: 0 }}>{t("Interpretasi")}</h3>{k.notes.map((t: string, i: number) => <div key={i}>⚠ {t}</div>)}</div>}
          <KpiRow title={t("{p0} per jam", { p0: word[0].toUpperCase() + word.slice(1) })} unit={`${word}/jam`}
            hist={<EChart option={histOpt(st.map((s: any) => s.jph).filter((x: any) => x != null), `${word}/jam`, 40)} height={210} />}
            chart={jphOpt && <EChart option={jphOpt} height={210} />}
            box={<TargetBox title={`${word}/jam`} unit={`${word}/jam`} med={k.jph_med} target={k.target.jph} manual={k.target.manual.jph} pct={k.vs.jph} higherBetter kind="P75" />} />
          <KpiRow title={t("In-slip time")} unit={`menit per ${word}`}
            hist={<EChart option={histOpt(st.map((s: any) => s.in_min).filter((x: any) => x != null), "menit", 15)} height={210} />}
            chart={<EChart option={depthOpt("in_min", "menit", k.target.in_min, 15)} height={210} />}
            box={<TargetBox title="in-slip" unit="mnt" med={k.in_med} target={k.target.in_min} manual={k.target.manual.in_min} pct={k.vs.in_min} higherBetter={false} kind="P25" />} />
          <KpiRow title={t("Moving time")} unit={`menit per ${word}`}
            hist={<EChart option={histOpt(st.map((s: any) => s.out_min).filter((x: any) => x != null), "menit", 15)} height={210} />}
            chart={<EChart option={depthOpt("out_min", "menit", k.target.move_min, 15)} height={210} />}
            box={<TargetBox title="moving" unit="mnt" med={k.move_med} target={k.target.move_min} manual={k.target.manual.move_min} pct={k.vs.move_min} higherBetter={false} kind="P25" />} />
          <div className="muted small" style={{ margin: "0 0 12px" }}>
            {t("Kotak kanan: hijau = lebih baik dari target, kuning = lebih buruk ≤ 10%, merah = lebih buruk > 10%. Moving time naik → drag / restriction / surge; in-slip naik → crew / handling / make-up; gross turun tapi moving normal → connection; gross turun dan moving naik → kondisi lubang.")}
          </div>
        </>)}
        <DepthLog wellId={wellId!} stands={(data.stands || []).filter((x: any) => loc === "all" || x.loc === loc)} shoe={data.shoe_md} word={word} />
        <div className="card">
          <h3>{t("Daftar trip (")}{data.trips.length})</h3>
          <div style={{ overflowX: "auto" }}>
            <table><thead><tr><th>{t("Mulai (WIB)")}</th><th>{t("Arah")}</th><th>{t("Dari → ke (ft)")}</th><th>{t("Jam")}</th><th>{word[0].toUpperCase() + word.slice(1)}</th><th>{word}{t("/jam (median)")}</th><th>{t("Gross ft/jam")}</th><th>{t("ft/jam saat bergerak")}</th><th>{t("In-slip med")}</th><th>{t("Moving med")}</th><th>{t("Berhenti")}</th><th>{t("Pompa")}</th></tr></thead>
              <tbody>{data.trips.map((t: any, i: number) => (
                <tr key={i}><td className="mono">{wib(t.start, true)}</td><td style={{ color: DIR_COLOR[t.dir] }}>{t.dir}</td><td className="mono">{ft(t.md_from)} → {ft(t.md_to)}</td>
                  <td className="mono">{n(t.hours, 1)}</td><td className="mono">{t.stands}</td><td className="mono">{n(t.jph_med, 1)}</td><td className="mono">{ft(t.ft_per_h)}</td><td className="mono">{ft(t.ft_per_h_moving)}</td>
                  <td className="mono">{n(t.in_med)}</td><td className="mono">{n(t.out_med)}</td><td className="mono">{t.stops || "—"}</td><td className="mono">{t.pumping_pct ? `${t.pumping_pct}%` : "—"}</td></tr>))}</tbody></table>
          </div>
          <div className="muted small">{t("Berhenti = in-slip > 15 menit. Pompa = %")}{" "}{word}{" "}{t("yang dipindahkan sambil memompa (pump out / pump in).")}</div>
        </div>
      </>)}
      {data && !data.empty && !has && !(data.warnings || []).length && <div className="card muted">{t("Tidak ada trip di rentang ini.")}</div>}
    </>
  );
}
