import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ago, C, ft, n, RATHOLE, STATE_LABEL, wib, toLocalInput } from "../lib/fmt";
import { EChart, Err, Evidence, Kpi, Level, WellSelect, ZoneTag } from "../components/ui";
import { buildTracks, CHANNELS, PRESETS } from "../components/tracks";
import { t } from "../lib/i18n";

const WINDOWS = [["30 mnt", 30], ["1 jam", 60], ["3 jam", 180], ["6 jam", 360], ["12 jam", 720]] as const;

export default function LiveMonitor() {
  const { wellId } = useApp();
  const [mode, setMode] = useState<"rt" | "pick">("rt");
  const [win, setWin] = useState(60);
  const [t0, setT0] = useState(""); const [t1, setT1] = useState("");
  const [view, setView] = useState<"h" | "v">("h");
  const [preset, setPreset] = useState("Navita default");
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const [ack, setAck] = useState<Record<string, boolean>>({});

  const { data, err, loading } = useFetch<any>(() => {
    if (!wellId) return null;
    if (mode === "pick" && t0 && t1) return api.get(`/wells/${wellId}/monitor`, { t0, t1 });
    return api.get(`/wells/${wellId}/monitor`, { minutes: win });
  }, [wellId, mode, t0, t1, win], mode === "rt" ? 30000 : undefined);

  const tracks = useMemo(() => PRESETS[preset].map((keys) => ({ title: keys.map((k) => CHANNELS[k].name).join(" · "), ch: keys.map((k) => CHANNELS[k]) })), [preset]);
  const sn = data?.snapshot; const meta = data?.meta;
  const ppgRange = useMemo<[number, number]>(() => {
    if (!data?.series) return [8, 16];
    const vals = ["ecd", "ecd_pred", "fg_bit", "lower_bit", "mw"].flatMap((k) => (data.series[k] || []).filter((x: any) => x != null));
    if (!vals.length) return [8, 16];
    return [Math.floor(Math.min(...vals) - 0.5), Math.ceil(Math.max(...vals) + 0.5)];
  }, [data]);
  const marks = (data?.detections || []).map((d: any) => ({ t0: d.start, t1: d.end, label: d.label, level: d.level }));
  const option = useMemo(() => data?.series ? buildTracks(data.series, tracks, { vertical: view === "v", hidden, marks, ppgRange }) : null, [data, tracks, view, hidden, ppgRange]);
  const allKeys = Array.from(new Set(PRESETS[preset].flat()));
  const ecdLabel = sn?.ecd_kind === "m" ? t("ECD terukur (PWD @ bit − {p0} ft)", { p0: sn?.pwd_offset_ft ?? 40 }) : t("ECD ⓥ prediksi (tanpa PWD)");

  return (
    <>
      <div className="top">
        <h1>{t("Live Monitor")}</h1>
        <WellSelect />
        <span className="chip">{t("Section")}{" "}{meta?.section || "—"}</span>
        <Link to="/ramalan" className="chip guide-go" title={t("Ramalan ECD beberapa jam ke depan dari rencana operasi")}>{t("Ramal ke depan →")}</Link>
        <span className="sp" />
        {meta && <span className="muted small">{wib(meta.data_end, true)}{" "}{t("· data")}{" "}{ago(meta.fresh_min)}</span>}
        {meta && <span className="chip" style={{ color: (meta.fresh_min ?? 99) <= 10 ? "#1E9E5A" : "#5B6775" }}>{(meta.fresh_min ?? 99) <= 10 ? "LIVE" : t("OFFLINE / UPLOAD")}{meta.model ? t(" · {p0} mode", { p0: meta.model.status }) : ""}</span>}
      </div>
      <Err e={err} />
      {!wellId && <div className="card empty">{t("Pilih atau buat sumur dulu di halaman Data & Upload.")}</div>}
      {data?.empty && <div className="card empty">{t("Belum ada data time-based untuk sumur ini.")}</div>}
      {sn && meta && (
        <>
          <div className="row small" style={{ marginBottom: 10, gap: 8 }}>
            <span className="chip">{t("State:")}{" "}<b>{STATE_LABEL[sn.state] || sn.state || "—"}</b></span>
            <span className="chip">{t("Bucket:")}{" "}{meta.bucket_s}{" "}{t("dtk")}</span>
            <span className="chip">{t("Model:")}{" "}{meta.model ? `${meta.model.name} (${meta.model.status})` : t("belum ada model")}</span>
            <span className="chip" style={{ color: meta.missing.length ? "#E07A10" : undefined }}>{t("Fitur valid:")}{" "}{meta.valid_features}/{meta.total_features}{meta.missing.length ? ` · ${meta.missing.join(", ")} ⚠` : ""}</span>
            <span className="chip" style={{ color: meta.ppfg ? undefined : "#E07A10" }}>{t("PPFG:")}{" "}{meta.ppfg ? t("Rec 03 v{p0} · {p1}{p2}", { p0: meta.ppfg.version, p1: meta.ppfg.status, p2: meta.ppfg.approved_by ? " " + meta.ppfg.approved_by : "" }) : t("belum ada approved")}</span>
            <span className="chip">{t("MW: Rec 04 · effective-from hole depth")}</span>
            {meta.rathole && <Link to="/rathole" className="chip" style={{ color: sn.zone === "rathole" ? "#8A4B00" : undefined, borderColor: sn.zone === "rathole" ? RATHOLE : undefined, background: sn.zone === "rathole" ? RATHOLE + "1A" : undefined }}>
              {sn.zone === "rathole" ? t("⚠ Bit di zona rathole") : t("Zona rathole")} {ft(meta.rathole.top_md)}–{ft(meta.rathole.base_md)}{" "}{t("ft")}</Link>}
            {sn.low_conf && <span className="chip" style={{ color: "#B98900" }}>{t("Low confidence")}{sn.ood ? t(" · di luar rentang training") : ""}</span>}
          </div>
          <div className="kpis">
            <Kpi l={ecdLabel} v={n(sn.ecd)} color={C.ecd} s={(sn.ecd_lo != null ? t("interval {p0}–{p1} ppg", { p0: n(sn.ecd_lo), p1: n(sn.ecd_hi) }) : sn.ecd_kind === "m" ? t("terukur PWD") : "—") + (sn.ecd_kind === "v" && sn.cal_offset != null && Math.abs(sn.cal_offset) >= 0.01 ? t(" · terkalibrasi PWD {p0}{p1} ({p2} j lalu)", { p0: sn.cal_offset > 0 ? "+" : "", p1: n(sn.cal_offset), p2: n(sn.cal_age_h, 1) }) : "")} />
            <Kpi l={t("FG_min bit / open hole")} v={`${n(sn.fg_bit, 1)} / ${n(sn.fg_oh, 1)}`} color={C.fg} s={sn.fg_oh_md ? t("titik terlemah OH @{p0} ft", { p0: ft(sn.fg_oh_md) }) : t("shoe belum diisi / PPFG kosong")} />
            <Kpi l={t("Margin atas bit · OH")} v={`${n(sn.margin_up_bit, 1)} · ${n(sn.margin_up_oh, 1)}`} s={sn.interval_half ? t("±{p0} dari interval", { p0: n(sn.interval_half) }) : ""} />
            <Kpi l={t("Margin bawah (ECD − max(PP,SFG))")} v={n(sn.margin_low, 1)} s={t("batas bawah {p0}", { p0: n(sn.lower_bit, 1) })} color={sn.margin_low != null && sn.margin_low < 0.25 ? "#E07A10" : undefined} />
            <Kpi l={t("Margin statis (pumps off)")} v={n(sn.margin_static, 1)} s={t("MW {p0} vs batas bawah OH {p1}", { p0: n(sn.mw, 1), p1: n(sn.lower_oh, 1) })} color={sn.margin_static != null && sn.margin_static < 0 ? "#D63A40" : undefined} />
            <Kpi l={t("Tingkat alert")} v={<Level v={sn.level} big />} s={sn.reason || t("tidak ada anomali terdeteksi")} />
          </div>
        </>
      )}
      {data?.series && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0,1fr) 320px", alignItems: "start" }}>
          <div className="card">
            <div className="row" style={{ marginBottom: 8 }}>
              <div className="segs"><button className={"seg" + (view === "h" ? " on" : "")} onClick={() => setView("h")}>{t("Horizontal")}</button><button className={"seg" + (view === "v" ? " on" : "")} onClick={() => setView("v")}>{t("Log format (waktu ↓)")}</button></div>
              <label className="row small muted">{t("Preset")}<select value={preset} onChange={(e) => setPreset(e.target.value)}>{Object.keys(PRESETS).map((p) => <option key={p}>{p}</option>)}</select></label>
              <span className="sp" />
              <div className="segs"><button className={"seg" + (mode === "rt" ? " on" : "")} onClick={() => setMode("rt")}>{t("Realtime")}</button><button className={"seg" + (mode === "pick" ? " on" : "")} onClick={() => { setMode("pick"); setT0(toLocalInput(meta.t0)); setT1(toLocalInput(meta.t1)); }}>{t("Picker")}</button></div>
              {mode === "rt" ? (
                <select value={win} onChange={(e) => setWin(Number(e.target.value))}>{WINDOWS.map(([l, m]) => <option key={m} value={m}>{l}{" "}{t("terakhir")}</option>)}</select>
              ) : (
                <><input type="datetime-local" value={t0} onChange={(e) => setT0(e.target.value)} /><input type="datetime-local" value={t1} onChange={(e) => setT1(e.target.value)} /></>
              )}
              {loading && <span className="muted small">{t("memuat…")}</span>}
            </div>
            <div className="row small" style={{ marginBottom: 6, gap: 6 }}>
              {allKeys.map((k) => (
                <label key={k} className="chip" style={{ cursor: "pointer", opacity: hidden[k] ? 0.45 : 1 }}>
                  <input type="checkbox" checked={!hidden[k]} onChange={() => setHidden({ ...hidden, [k]: !hidden[k] })} style={{ margin: 0 }} />
                  <i style={{ width: 10, height: 3, background: CHANNELS[k].color, display: "inline-block" }} />{CHANNELS[k].name} <span className="dim">{CHANNELS[k].unit}</span>
                </label>
              ))}
              <span className="muted">{t("Skala ppg terkunci bersama (ECD · FG · SFG · MW)")}</span>
            </div>
            {option && <EChart option={option} height={view === "v" ? 720 : 560} />}
          </div>
          <div className="grid">
            <PressureWindow sn={sn} meta={meta} />
            <div className="card">
              <div className="row"><h3 style={{ margin: 0 }}>{t("Alert terbaru")}</h3><span className="sp" /><Link to="/event" className="small">{t("Riwayat Event")}</Link></div>
              {data.detections.length === 0 && <div className="muted small" style={{ marginTop: 8 }}>{t("Tidak ada indikasi pada jendela ini.")}</div>}
              {data.detections.slice(0, 12).map((d: any, i: number) => {
                const k = d.detector + d.start;
                return (
                  <div key={i} style={{ borderTop: "1px solid #E3E8EE", padding: "8px 0", opacity: ack[k] ? 0.5 : 1 }}>
                    <div className="row"><Level v={d.level} /><ZoneTag z={d.zone} /><span className="small mono">{wib(d.start)}</span><span className="sp" /><button style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => setAck({ ...ack, [k]: true })}>{t("Ack")}</button></div>
                    <div className="small" style={{ marginTop: 4 }}><b>{t(d.label)}</b>{d.md ? t(" @{p0} ft", { p0: ft(d.md) }) : ""}</div>
                    <Evidence d={d} />
                  </div>
                );
              })}
              <Link to="/anomali" className="small">{t("Buka Analisis Anomali →")}</Link>
            </div>
          </div>
        </div>
      )}
      <p className="note" style={{ marginTop: 14 }}>{t("Normal berarti \"tidak ada anomali terdeteksi pada data yang tersedia\", bukan izin melanjutkan operasi. Sistem tidak memberi perintah perubahan flow / MW. ECD ⓥ = estimasi model dari parameter permukaan.")}</p>
    </>
  );
}

function PressureWindow({ sn, meta }: { sn: any; meta: any }) {
  if (!sn) return null;
  const items = [["MW", sn.mw, C.mw], ["max(PP,SFG)", sn.lower_bit, C.sfg], [sn.ecd_kind === "m" ? "ECD" : t("ECD ⓥ"), sn.ecd, C.ecd], [t("FG OH"), sn.fg_oh, C.fg], [t("FG bit"), sn.fg_bit, "#B42318"]]
    .filter((x) => x[1] != null) as [string, number, string][];
  const vals = items.map((x) => x[1]);
  const lo = vals.length ? Math.floor(Math.min(...vals) - 0.5) : 8, hi = vals.length ? Math.ceil(Math.max(...vals) + 0.5) : 14;
  const option = {
    animation: false, grid: { left: 90, right: 16, top: 6, bottom: 24 },
    xAxis: { type: "value", min: lo, max: hi, axisLabel: { color: "#5B6775", fontSize: 10 }, splitLine: { lineStyle: { color: "#EEF1F5" } } },
    yAxis: { type: "category", data: items.map((x) => x[0]), axisLabel: { color: "#3A4552", fontSize: 11 }, axisLine: { lineStyle: { color: "#D5DCE4" } } },
    series: [{ type: "scatter", symbolSize: 12, data: items.map((x) => ({ value: [x[1], x[0]], itemStyle: { color: x[2] } })),
      label: { show: true, position: "right", color: "#1B2430", formatter: (p: any) => p.value[0].toFixed(2) } },
      ...(sn.ecd_lo != null ? [{ type: "line", data: [[sn.ecd_lo, items.find((x) => x[0].startsWith("ECD"))?.[0]], [sn.ecd_hi, items.find((x) => x[0].startsWith("ECD"))?.[0]]], lineStyle: { color: C.ecd, width: 6, opacity: 0.35 }, symbol: "none" }] : [])],
  };
  return (
    <div className="card">
      <h3>{t("Pressure window")}</h3>
      <div className="muted small">{meta?.ppfg ? t("PPFG v{p0} {p1}", { p0: meta.ppfg.version, p1: meta.ppfg.status }) : t("PPFG belum approved")}{" "}{t("· bit")}{" "}{ft(sn.bit_depth)}{" "}{t("ft · shoe")}{" "}{ft(meta?.shoe_md)}{" "}{t("ft")}</div>
      <EChart option={option} height={170} />
      <div className="small mono" style={{ display: "grid", gap: 2 }}>
        <span>{t("Margin atas bit:")}{" "}{n(sn.margin_up_bit)}</span><span>{t("Margin atas OH:")}{" "}{n(sn.margin_up_oh)}</span>
        <span>{t("Margin bawah:")}{" "}{n(sn.margin_low)}</span><span>{t("Margin statis:")}{" "}{n(sn.margin_static)}</span>
      </div>
      <p className="note">{t("Uncertainty FG tidak tersedia di Rec 03. Saat pumps off, ECD dinamis disuppress; yang dibandingkan MW vs batas bawah.")}</p>
    </div>
  );
}
