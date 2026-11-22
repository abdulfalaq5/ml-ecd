import { useMemo } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { C, ft, n } from "../lib/fmt";
import { AX, EChart, Err, TIP, WellSelect } from "../components/ui";

export default function ProfilDepth() {
  const { wellId } = useApp();
  const { data, err } = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/profile`) : null), [wellId]);
  const option = useMemo(() => {
    if (!data) return null;
    const pp = data.pp || {};
    const line = (name: string, xs: any[], ys: any[], color: string, dash = false, w = 1.6) => ({ type: "line", name, data: (xs || []).map((x: any, i: number) => [x, ys[i]]), showSymbol: false, lineStyle: { color, width: w, type: dash ? "dashed" : "solid" }, itemStyle: { color } });
    const series: any[] = [];
    if (pp.md) {
      series.push(line("PP", pp.pp, pp.md, C.pp), line("SFG", pp.sfg, pp.md, C.sfg, true), line("FG_min", pp.fg_min, pp.md, C.fg), line("FG_max", pp.fg_max, pp.md, "#B42318", true, 1));
    }
    if (data.mw?.md) series.push({ ...line("MW", data.mw.mw, data.mw.md, C.mw, false, 2), step: "end" });
    if (data.ecd_measured?.md) series.push({ type: "scatter", name: "ECD terukur", data: data.ecd_measured.md.map((m: number, i: number) => [data.ecd_measured.ecd[i], m]), symbolSize: 3, itemStyle: { color: C.ecd } });
    if (data.shoe_md) series.push({ type: "line", name: "Shoe", data: [], markLine: { symbol: "none", data: [{ yAxis: data.shoe_md }], lineStyle: { color: "#5B6775", type: "dotted" }, label: { formatter: `shoe ${ft(data.shoe_md)} ft`, color: "#5B6775" } } });
    return {
      backgroundColor: "transparent", animation: false, legend: { textStyle: { color: "#3A4552" }, top: 0 },
      grid: { left: 70, right: 30, top: 40, bottom: 40 }, tooltip: { ...TIP, trigger: "item" },
      xAxis: { type: "value", name: "ppg", nameLocation: "middle", nameGap: 26, scale: true, ...AX, position: "top" },
      yAxis: { type: "value", name: "MD (ft)", inverse: true, ...AX, nameLocation: "middle", nameGap: 50 },
      dataZoom: [{ type: "inside", yAxisIndex: 0 }, { type: "slider", yAxisIndex: 0, right: 0, width: 14, textStyle: { color: "#5B6775" } }],
      series,
    };
  }, [data]);
  return (
    <>
      <div className="top"><h1>Profil Depth</h1><WellSelect /><span className="sp" />
        {data?.ppfg ? <span className="chip">PPFG Rec 03 v{data.ppfg.version} · {data.ppfg.status}</span> : data && <span className="chip" style={{ color: "#E07A10" }}>Belum ada PPFG approved — approve di Formasi &amp; FG</span>}
      </div>
      <Err e={err} />
      {data && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.1fr)", alignItems: "start" }}>
          <div className="card">{option && <EChart option={option} height={720} />}</div>
          <div className="grid">
            {data.mw_below?.length > 0 && (
              <div className="err">MW di bawah batas bawah max(PP,SFG) pada {data.mw_below.length} interval: {data.mw_below.map((r: any) => `${ft(r.a)}–${ft(r.b)} ft (${n(r.low_margin)} ppg)`).join(", ")}. Rekomendasi verifikasi dengan Mud Eng / Geomechanics.</div>
            )}
            <div className="card">
              <h3>Tabel interval (500 ft)</h3>
              <table>
                <thead><tr><th>Interval MD (ft)</th><th>PP</th><th>SFG</th><th>MW</th><th>ECD terukur (med)</th><th>FG_min</th><th>Margin bawah statis</th><th>Margin atas</th><th>Status</th></tr></thead>
                <tbody>
                  {data.intervals.length === 0 && <tr><td colSpan={9} className="muted">Butuh Rec 03 (PPFG) dan Rec 04 (MW).</td></tr>}
                  {data.intervals.map((r: any, i: number) => (
                    <tr key={i}><td className="mono">{ft(r.a)}–{ft(r.b)}</td><td className="mono">{n(r.pp)}</td><td className="mono">{n(r.sfg)}</td><td className="mono">{n(r.mw)}</td>
                      <td className="mono">{n(r.ecd)}</td><td className="mono">{n(r.fg_min)}</td>
                      <td className="mono" style={{ color: r.low_margin < 0 ? "#D63A40" : undefined }}>{n(r.low_margin)}</td><td className="mono">{n(r.up_margin)}</td>
                      <td className="small" style={{ color: r.low_margin < 0 ? "#D63A40" : "#5B6775" }}>{r.flag}</td></tr>
                  ))}
                </tbody>
              </table>
              <p className="note">Margin bawah statis = MW − max(PP,SFG). Margin atas = FG_min − ECD terukur (median interval). Semua nilai ppg EMW pada TVD datum PPFG.</p>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
