import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { C, RATHOLE, ZONE_LABEL, ft, n, wib } from "../lib/fmt";
import { AX, EChart, Err, Kpi, Level, TIP, WellSelect } from "../components/ui";
import { t } from "../lib/i18n";

const tShort = (v: number) => new Date(v).toLocaleString("id-ID", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Jakarta" }).replace(".", ":");
const dayLabel = (d: string) => new Date(d + "T00:00:00+07:00").toLocaleDateString("id-ID", { day: "2-digit", month: "short", timeZone: "Asia/Jakarta" });

export default function StudiRathole() {
  const { wellId, can } = useApp();
  const { data: a, err, loading } = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/rathole`) : null), [wellId]);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const rh = a?.rathole;
  const p1 = a?.phase1, p2 = a?.phase2;

  const opt1 = useMemo(() => {
    if (!p1?.series?.t) return null;
    const s = p1.series, pts = (k: string) => s.t.map((t: string, i: number) => [t, s[k][i]]);
    return {
      animation: false, grid: { left: 52, right: 16, top: 34, bottom: 28 },
      legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 11 }, data: [t("Interval ECD ⓥ"), t("ECD terukur (APWD)"), t("ECD ⓥ"), "MW"] },
      tooltip: { ...TIP, axisPointer: { type: "line" }, valueFormatter: (v: any) => (v == null ? "—" : Number(v).toFixed(2)) },
      xAxis: { type: "time", ...AX, axisLabel: { ...AX.axisLabel, formatter: (v: number) => dayLabel(new Date(v + 7 * 3600e3).toISOString().slice(0, 10)), hideOverlap: true } },
      yAxis: { type: "value", name: "ppg", scale: true, ...AX },
      series: [
        { name: t("Interval ECD ⓥ (bawah)"), type: "line", data: pts("ecd_lo"), showSymbol: false, lineStyle: { opacity: 0 }, stack: "iv", tooltip: { show: false } },
        { name: t("Interval ECD ⓥ"), type: "line", data: s.t.map((t: string, i: number) => [t, s.ecd_hi[i] != null && s.ecd_lo[i] != null ? s.ecd_hi[i] - s.ecd_lo[i] : null]), showSymbol: false, lineStyle: { opacity: 0 }, areaStyle: { color: C.ecd, opacity: 0.14 }, stack: "iv", tooltip: { show: false } },
        { name: t("ECD terukur (APWD)"), type: "scatter", data: pts("ecd"), symbolSize: 3, itemStyle: { color: "#1B2430" } },
        { name: t("ECD ⓥ"), type: "scatter", data: pts("ecd_pred"), symbolSize: 3, itemStyle: { color: C.ecd } },
        { name: "MW", type: "line", step: "end", data: pts("mw"), showSymbol: false, lineStyle: { color: C.mw, width: 1.5 }, itemStyle: { color: C.mw } },
      ],
    };
  }, [p1]);

  const optDaily = useMemo(() => {
    if (!p2?.daily?.length) return null;
    const d = p2.daily;
    return {
      animation: false, grid: { left: 48, right: 56, top: 34, bottom: 28 }, tooltip: { ...TIP, axisPointer: { type: "shadow" } },
      legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 11 } },
      xAxis: { type: "category", data: d.map((x: any) => dayLabel(x.date)), ...AX },
      yAxis: [{ type: "value", name: "indikasi", ...AX, minInterval: 1 }, { type: "value", name: t("psi/100 gpm"), ...AX, splitLine: { show: false } }],
      series: [
        { name: t("Indikasi di rathole"), type: "bar", stack: "z", data: d.map((x: any) => x.ind_rathole), itemStyle: { color: RATHOLE } },
        { name: t("Indikasi di atas shoe"), type: "bar", stack: "z", data: d.map((x: any) => x.ind_atas_shoe), itemStyle: { color: "#AEB9C6" } },
        { name: t("SPP per 100 gpm (median)"), type: "line", yAxisIndex: 1, data: d.map((x: any) => x.spp_per_100gpm), connectNulls: false, symbolSize: 6, lineStyle: { color: "#7C4DD8", width: 2 }, itemStyle: { color: "#7C4DD8" } },
      ],
    };
  }, [p2]);

  const opt2 = useMemo(() => {
    if (!p2?.series?.t || !rh) return null;
    const s = p2.series, pts = (k: string) => s.t.map((t: string, i: number) => [t, s[k][i]]);
    const tAx = (gi: number, show: boolean) => ({ type: "time", gridIndex: gi, ...AX, axisLabel: { ...AX.axisLabel, show, formatter: (v: number) => tShort(v), hideOverlap: true } });
    return {
      animation: false, tooltip: TIP, axisPointer: { link: [{ xAxisIndex: "all" }] },
      legend: { top: 0, textStyle: { color: "#3A4552", fontSize: 11 } },
      grid: [{ left: 60, right: 60, top: 34, height: "38%" }, { left: 60, right: 60, top: "58%", bottom: 28 }],
      xAxis: [tAx(0, false), tAx(1, true)],
      yAxis: [
        // skala dikunci di sekitar zona rathole: glitch depth (mis. 9.909 ft) tidak merusak tampilan
        { type: "value", gridIndex: 0, name: t("Bit MD (ft)"), inverse: true, min: Math.max(0, Math.floor((rh.top_md - 1500) / 500) * 500), max: Math.ceil((rh.base_md + 200) / 100) * 100, ...AX },
        { type: "value", gridIndex: 1, name: t("SPP (psi)"), ...AX },
        { type: "value", gridIndex: 1, name: "ppg", scale: true, ...AX, splitLine: { show: false } },
      ],
      dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
      series: [
        { name: t("Bit depth"), type: "line", xAxisIndex: 0, yAxisIndex: 0, data: pts("bit_depth"), showSymbol: false, lineStyle: { color: C.depth, width: 1.2 }, itemStyle: { color: C.depth },
          markArea: { silent: true, itemStyle: { color: RATHOLE + "2E" }, label: { color: "#8A4B00", fontSize: 11, position: "insideLeft" }, data: [[{ yAxis: rh.top_md, name: t("rathole {p0}–{p1} ft", { p0: ft(rh.top_md), p1: ft(rh.base_md) }) }, { yAxis: rh.base_md }]] } },
        { name: "SPP", type: "line", xAxisIndex: 1, yAxisIndex: 1, data: pts("spp"), showSymbol: false, lineStyle: { color: "#7C4DD8", width: 1 }, itemStyle: { color: "#7C4DD8" } },
        { name: t("ECD ⓥ"), type: "line", xAxisIndex: 1, yAxisIndex: 2, data: pts("ecd_pred"), showSymbol: false, lineStyle: { color: C.ecd, width: 1.6 }, itemStyle: { color: C.ecd } },
        { name: "MW", type: "line", step: "end", xAxisIndex: 1, yAxisIndex: 2, data: pts("mw"), showSymbol: false, lineStyle: { color: C.mw, width: 1.2 }, itemStyle: { color: C.mw } },
      ],
    };
  }, [p2, rh]);

  const makeReport = async () => {
    setBusy(true); setMsg(null);
    try {
      const r = await api.post("/reports", { kind: "rathole", well_id: wellId });
      await api.download(`/reports/${r.id}/xlsx`, `studi_kasus_rathole_${a.well}_${r.id}.xlsx`);
      setMsg(t("Laporan #{p0} dibuat dan diunduh. Arsip & narasi ada di menu Laporan.", { p0: r.id }));
    } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };

  return (
    <>
      <div className="top"><h1>{t("Studi Kasus Rathole")}</h1><WellSelect /><span className="muted small">{t("H1–H3 · validasi ECD ⓥ saat ECD terukur ada → pantau zona rathole sesudahnya")}</span><span className="sp" />
        {a?.enabled && can("report") && <button className="pri" onClick={makeReport} disabled={busy}>{busy ? t("Membuat…") : t("Buat laporan (Excel)")}</button>}
      </div>
      <Err e={err || msg} />
      {loading && !a && <div className="card empty">{t("Menghitung… (fase 1 memakai data resolusi penuh, bisa beberapa detik)")}</div>}
      {a && !a.enabled && (
        <div className="card empty">{a.message}<div style={{ marginTop: 10 }}><Link to="/data">{t("Buka Data & Upload →")}</Link></div></div>
      )}
      {a?.enabled && (<>
        <div className="card" style={{ marginBottom: 12, borderLeft: `4px solid ${RATHOLE}` }}>
          <div className="row" style={{ gap: 18 }}>
            <div><div className="muted small">{t("Zona rathole")}</div><b style={{ fontSize: 18 }}>{ft(rh.top_md)}–{ft(rh.base_md)}{" "}{t("ftMD")}</b> <span className="muted">({n(rh.length_ft, 0)}{" "}{t("ft open hole)")}</span></div>
            <div><div className="muted small">{t("Berlaku sejak")}</div><b>{wib(rh.since, true)}</b></div>
            <div><div className="muted small">{t("Section / shoe")}</div><b>{a.section || "—"}</b>{" "}{t("· shoe")}{" "}{ft(a.shoe_md)}{" "}{t("ft")}</div>
            <div><div className="muted small">{t("Model")}</div><b>{a.model?.name || "—"}</b> <span className="chip">{t("sumur ini:")}{" "}{a.model?.well_role_in_model || "—"}</span></div>
          </div>
          {rh.note && <div className="small muted" style={{ marginTop: 8 }}>{rh.note}</div>}
        </div>

        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1.35fr) minmax(0, 1fr)", alignItems: "start", marginBottom: 12 }}>
          <div className="card">
            <h3>{t("Fase 1 · Validasi ECD ⓥ vs ECD terukur")}{" "}{p1 && <span className="muted small" style={{ fontWeight: 400 }}>{wib(p1.t0, true)} → {wib(p1.t1, true)}</span>}</h3>
            {!p1 ? <div className="muted small">{t("Tidak ada ECD terukur sebelum zona rathole berlaku.")}</div> : (<>
              <div className="kpis">
                <Kpi l={t("MAE ECD ⓥ")} v={n(p1.mae, 3)} s={t("ppg · n={p0} titik", { p0: p1.n })} />
                <Kpi l={t("Bias (ⓥ − terukur)")} v={n(p1.bias, 3)} s={p1.bias < 0 ? t("ECD ⓥ cenderung di bawah") : t("ECD ⓥ cenderung di atas")} />
                <Kpi l={t("Masuk interval")} v={`${n(p1.coverage_pct, 0)}%`} s={t("target 90%")} color={p1.coverage_pct < 80 ? "#E07A10" : undefined} />
                <Kpi l={t("Bit di kedalaman rathole")} v={n(p1.in_rathole_depth?.mae, 3)} s={p1.in_rathole_depth ? t("bias {p0} · ECD−MW {p1}", { p0: n(p1.in_rathole_depth.bias, 3), p1: n(p1.in_rathole_depth.ecd_minus_mw_med) }) : t("tidak ada titik")} color={RATHOLE} />
              </div>
              {opt1 && <EChart option={opt1} height={260} />}
              <table style={{ marginTop: 8 }}><thead><tr><th>{t("Tanggal")}</th><th>{t("Titik")}</th><th>{t("ECD terukur")}</th><th>{t("ECD ⓥ")}</th><th>{t("MW")}</th><th>{t("MAE")}</th><th>{t("Bit maks (ft)")}</th></tr></thead>
                <tbody>{p1.daily.map((d: any) => <tr key={d.date}><td>{dayLabel(d.date)}</td><td className="mono">{d.n}</td><td className="mono">{n(d.ecd)}</td><td className="mono">{n(d.ecd_pred)}</td><td className="mono">{n(d.mw)}</td><td className="mono">{n(d.mae, 3)}</td><td className="mono">{ft(d.bit_max)}</td></tr>)}</tbody></table>
            </>)}
          </div>
          <div className="grid">
            <div className="card">
              <h3>{t("Timeline kejadian")}</h3>
              {!a.events?.length && <div className="muted small">{t("Belum ada event. Tambah di Riwayat Event.")}</div>}
              {a.events?.map((e: any, i: number) => (
                <div key={i} className="small" style={{ borderTop: i ? "1px solid #E3E8EE" : undefined, padding: "7px 0" }}>
                  <div className="row"><Level v={e.level} /><span className="mono">{wib(e.onset, true)}</span>{e.md ? <span className="muted">@{ft(e.md)}{" "}{t("ft")}</span> : null}<span className="sp" /><span className="chip">{e.review}</span></div>
                  <div style={{ marginTop: 3 }}><b>{e.category}</b> — {e.detail}</div>
                  <div className="muted">{t("Sumber:")}{" "}{e.source}</div>
                </div>
              ))}
            </div>
            <div className="card">
              <h3>{t("Catatan interpretasi")}</h3>
              <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>{a.caveats.map((c: string, i: number) => <li key={i} style={{ marginBottom: 4 }}>{c}</li>)}</ul>
            </div>
          </div>
        </div>

        <div className="card" style={{ marginBottom: 12 }}>
          <h3>{t("Fase 2 · Zona rathole tanpa ECD terukur")}{" "}{p2 && <span className="muted small" style={{ fontWeight: 400 }}>{wib(p2.t0, true)} → {wib(p2.t1, true)}</span>}</h3>
          {!p2 ? <div className="muted small">{t("Belum ada data setelah zona rathole berlaku.")}</div> : (<>
            <div className="kpis">
              <Kpi l={t("Jam pompa di zona rathole")} v={n(p2.rathole_pump_minutes / 60, 1)} s={t("dari {p0} jam pompa hidup", { p0: n(p2.pump_minutes / 60, 1) })} color={RATHOLE} />
              <Kpi l={t("ECD ⓥ median")} v={n(p2.ecd_pred_med)} s={t("maks {p0} ppg", { p0: n(p2.ecd_pred_max) })} color={C.ecd} />
              <Kpi l={t("Di luar rentang training")} v={`${n(p2.ood_pct, 0)}%`} s={t("titik pompa hidup (OOD)")} />
              <Kpi l={t("Indikasi di rathole")} v={(a.zone_table || []).reduce((s: number, z: any) => s + z.rathole, 0)} s={t("vs {p0} di atas shoe", { p0: (a.zone_table || []).reduce((s: number, z: any) => s + z.atas_shoe, 0) })} />
            </div>
            <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)" }}>
              <div>{optDaily && <EChart option={optDaily} height={280} />}</div>
              <div>
                <table><thead><tr><th>{t("Indikasi")}</th><th style={{ color: "#8A4B00" }}>{ZONE_LABEL.rathole}</th><th>{ZONE_LABEL.atas_shoe}</th><th>{ZONE_LABEL.bawah_rathole}</th></tr></thead>
                  <tbody>{(a.zone_table || []).map((z: any) => <tr key={z.label}><td>{z.label}</td><td className="mono"><b>{z.rathole}</b></td><td className="mono">{z.atas_shoe}</td><td className="mono">{z.bawah_rathole}</td></tr>)}</tbody></table>
                <div className="note" style={{ marginTop: 8 }}>{t("Zona ditentukan dari MD bit saat indikasi terdeteksi. Ambang detektor belum dikalibrasi; angka bersifat indikatif.")}</div>
              </div>
            </div>
            {opt2 && <EChart option={opt2} height={420} />}
            <div style={{ overflowX: "auto" }}>
              <table style={{ marginTop: 8 }}><thead><tr><th>{t("Tanggal")}</th><th>{t("Pompa (jam)")}</th><th>{t("di rathole (jam)")}</th><th>{t("Bit (ft)")}</th><th>{t("Flow")}</th><th>{t("SPP")}</th><th>{t("SPP di rathole")}</th><th>{t("SPP/100 gpm")}</th><th>{t("Torque")}</th><th>{t("Hookload")}</th><th>{t("ECD ⓥ")}</th><th>{t("MW")}</th><th>{t("Indikasi rathole")}</th></tr></thead>
                <tbody>{p2.daily.map((d: any) => <tr key={d.date}><td>{dayLabel(d.date)}</td><td className="mono">{n(d.pump_minutes / 60, 1)}</td><td className="mono" style={{ color: d.rathole_pump_minutes ? "#8A4B00" : undefined }}>{n(d.rathole_pump_minutes / 60, 1)}</td>
                  <td className="mono">{ft(d.bit_min)}–{ft(d.bit_max)}</td><td className="mono">{ft(d.flow_med)}</td><td className="mono">{ft(d.spp_med)}</td><td className="mono">{ft(d.spp_rathole_med)}</td><td className="mono"><b>{ft(d.spp_per_100gpm)}</b></td>
                  <td className="mono">{n(d.torque_med)}</td><td className="mono">{n(d.hookload_med, 1)}</td><td className="mono">{n(d.ecd_pred_med)}</td><td className="mono">{n(d.mw)}</td><td className="mono"><b>{d.ind_rathole}</b></td></tr>)}</tbody></table>
            </div>
          </>)}
        </div>
      </>)}
    </>
  );
}
