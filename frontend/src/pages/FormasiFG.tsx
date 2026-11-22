import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { C, dateOnly, ft, n } from "../lib/fmt";
import { AX, EChart, Err, TIP, WellSelect } from "../components/ui";

const ST: Record<string, string> = { approved: "#1E9E5A", draft: "#B98900", superseded: "#7A8694" };

export default function FormasiFG() {
  const { wellId, can } = useApp();
  const vers = useFetch<any[]>(() => (wellId ? api.get(`/wells/${wellId}/ppfg`) : null), [wellId]);
  const [vid, setVid] = useState<number | null>(null);
  const [step, setStep] = useState(250);
  const [msg, setMsg] = useState<string | null>(null);
  const [ed, setEd] = useState({ md_from: "", md_to: "", field: "fg_min", value: "" });
  useEffect(() => { const v = vers.data; if (v?.length) setVid((cur) => (cur && v.some((x) => x.id === cur) ? cur : (v.find((x) => x.status === "approved") || v[v.length - 1]).id)); else setVid(null); }, [vers.data]);
  const rows = useFetch<any[]>(() => (vid ? api.get(`/ppfg/${vid}/intervals`, { step }) : null), [vid, step]);
  const mwRule = useFetch<any>(() => api.get("/settings/mw_rule"), []);
  const cur = vers.data?.find((v) => v.id === vid);
  const act = async (fn: () => Promise<any>) => { setMsg(null); try { await fn(); vers.reload(); rows.reload(); } catch (e: any) { setMsg(e.message); } };

  const option = useMemo(() => {
    const r = rows.data || [];
    if (!r.length) return null;
    const mid = r.map((x) => (x.a + x.b) / 2);
    const L = (name: string, k: string, color: string, dash = false) => ({ type: "line", name, step: "middle", data: r.map((x, i) => [x[k], mid[i]]), showSymbol: false, lineStyle: { color, type: dash ? "dashed" : "solid", width: 1.6 }, itemStyle: { color } });
    return { backgroundColor: "transparent", animation: false, legend: { textStyle: { color: "#3A4552" } }, tooltip: { ...TIP, trigger: "item" }, grid: { left: 64, right: 20, top: 40, bottom: 30 },
      xAxis: { type: "value", scale: true, name: "ppg", position: "top", ...AX }, yAxis: { type: "value", inverse: true, name: "MD ft", ...AX },
      series: [L("PP", "pp", C.pp), L("SFG", "sfg", C.sfg, true), L("FG_min", "fg_min", C.fg), L("FG_max", "fg_max", "#B42318", true)] };
  }, [rows.data]);

  return (
    <>
      <div className="top"><h1>Formasi &amp; FG</h1><WellSelect /><span className="sp" />
        <span className="chip">Aturan MW: {mwRule.data?.rule === "mud_report" ? "per laporan lumpur" : "effective-from saat bit melewati depth"}{mwRule.data?.approved_by ? ` · ${mwRule.data.approved_by}` : " · default"}</span>
        {can("mw_rule") && <select value={mwRule.data?.rule || "bit_passes"} onChange={(e) => act(() => api.post("/settings/mw_rule", { rule: e.target.value }).then(mwRule.reload))}><option value="bit_passes">effective-from bit</option><option value="mud_report">laporan lumpur</option></select>}
      </div>
      <Err e={msg || vers.err} />
      <div className="card" style={{ marginBottom: 12 }}>
        <h3>Versi PPFG (Rec 03)</h3>
        <table>
          <thead><tr><th>Versi</th><th>Status</th><th>TVD datum</th><th>Efektif</th><th>Approved</th><th>Dibuat</th><th>Catatan</th><th></th></tr></thead>
          <tbody>
            {vers.data?.length === 0 && <tr><td colSpan={8} className="muted">Belum ada PPFG. Upload file Rec 03 di Data &amp; Upload — tiap upload jadi versi draft baru.</td></tr>}
            {vers.data?.map((v) => (
              <tr key={v.id} className="click" onClick={() => setVid(v.id)} style={{ background: v.id === vid ? "#EAF1FA" : undefined }}>
                <td className="mono">v{v.version}</td><td style={{ color: ST[v.status] }}>{v.status}</td><td>{v.tvd_datum}</td><td>{dateOnly(v.effective_date)}</td>
                <td className="small">{v.approved_by ? `${v.approved_by} · ${dateOnly(v.approved_at)}` : "—"}</td><td className="small muted">{v.created_by}</td><td className="small">{v.notes}</td>
                <td className="row" onClick={(e) => e.stopPropagation()}>
                  {v.status === "draft" && can("ppfg_approve") && <button className="pri" onClick={() => act(() => api.post(`/ppfg/${v.id}/approve`, { tvd_datum: v.tvd_datum || "RKB" }))}>Approve</button>}
                  {can("ppfg_edit") && <button onClick={() => act(() => api.post(`/ppfg/${v.id}/draft`))}>Salin → draft</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note">Hanya versi <b>approved</b> (Geomechanics) yang dipakai untuk margin & alert. Koreksi dilakukan di salinan draft; versi lama tetap tersimpan untuk audit.</p>
      </div>
      {cur && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 0.9fr) minmax(0, 1.1fr)", alignItems: "start" }}>
          <div className="card">{option && <EChart option={option} height={640} />}</div>
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>Ringkasan v{cur.version} per interval</h3><span className="sp" />
              <select value={step} onChange={(e) => setStep(Number(e.target.value))}>{[100, 250, 500, 1000].map((s) => <option key={s} value={s}>{s} ft</option>)}</select></div>
            {cur.status === "draft" && can("ppfg_edit") && (
              <div className="row" style={{ margin: "10px 0" }}>
                <span className="small muted">Koreksi draft:</span>
                <input style={{ width: 90 }} placeholder="MD dari" value={ed.md_from} onChange={(e) => setEd({ ...ed, md_from: e.target.value })} />
                <input style={{ width: 90 }} placeholder="MD ke" value={ed.md_to} onChange={(e) => setEd({ ...ed, md_to: e.target.value })} />
                <select value={ed.field} onChange={(e) => setEd({ ...ed, field: e.target.value })}>{["pp", "sfg", "fg_min", "fg_max"].map((f) => <option key={f}>{f}</option>)}</select>
                <input style={{ width: 80 }} placeholder="ppg" value={ed.value} onChange={(e) => setEd({ ...ed, value: e.target.value })} />
                <button onClick={() => act(() => api.post(`/ppfg/${cur.id}/edit`, { md_from: Number(ed.md_from), md_to: Number(ed.md_to), field: ed.field, value: ed.value === "" ? null : Number(ed.value) }))}>Terapkan</button>
              </div>
            )}
            <table>
              <thead><tr><th>MD (ft)</th><th>TVD</th><th>Formasi</th><th>PP</th><th>SFG</th><th>FG_min</th><th>FG_max</th><th>max(PP,SFG)</th></tr></thead>
              <tbody>{rows.data?.map((r, i) => (
                <tr key={i}><td className="mono">{ft(r.a)}–{ft(r.b)}</td><td className="mono">{ft(r.tvd)}</td><td className="small">{r.formation || "—"}</td>
                  <td className="mono">{n(r.pp)}</td><td className="mono">{n(r.sfg)}</td><td className="mono" style={{ color: C.fg }}>{n(r.fg_min)}</td><td className="mono">{n(r.fg_max)}</td>
                  <td className="mono" style={{ color: C.sfg }}>{n(Math.max(r.pp ?? -1, r.sfg ?? -1) < 0 ? null : Math.max(r.pp ?? -1, r.sfg ?? -1))}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
