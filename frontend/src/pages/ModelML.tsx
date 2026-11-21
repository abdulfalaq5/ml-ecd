import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { dateOnly, n, wib } from "../lib/fmt";
import { EChart, Err, Kpi } from "../components/ui";

const ST: Record<string, string> = { production: "#4CC38A", shadow: "#7DB4FF", candidate: "#E8C547", training: "#FF9F43", archived: "#8A96A3", failed: "#F2555A" };
const M = (m: any, k: string, d = 3) => (m && m[k] != null ? n(m[k], d) : "—");

export default function ModelML() {
  const { can, wells } = useApp();
  const list = useFetch<any[]>(() => api.get("/models"), [], 10000);
  const ds = useFetch<any[]>(() => api.get("/models/dataset"), []);
  const [sel, setSel] = useState<number | null>(null);
  const det = useFetch<any>(() => (sel ? api.get(`/models/${sel}`) : null), [sel, list.data?.find((m) => m.id === sel)?.status]);
  const [algo, setAlgo] = useState("all"); const [lowo, setLowo] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (!sel && list.data?.length) setSel(list.data[0].id); }, [list.data, sel]);
  const act = async (fn: () => Promise<any>) => { setMsg(null); try { await fn(); list.reload(); det.reload(); } catch (e: any) { setMsg(e.message); } };
  const train = wells.filter((w) => w.role === "train").map((w) => w.name), blind = wells.filter((w) => w.role === "blind").map((w) => w.name);
  const m = det.data; const res = m?.metrics; const chosen = res?.chosen; const ex = res?.experiments || {};
  const best = chosen ? ex[chosen] : null;
  const ref = Object.values(ex).some((e: any) => e.blind) ? " blind" : " LOWO";
  const imp = m?.importance ? Object.entries(m.importance as Record<string, number>).slice(0, 14) : [];

  return (
    <>
      <div className="top"><h1>Model ML</h1><span className="muted small">Nowcast ECD dari parameter permukaan · validasi grouped-by-well (LOWO + blind tetap)</span></div>
      <Err e={msg || list.err} />
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", alignItems: "start" }}>
        <div className="card">
          <h3>Dataset per sumur</h3>
          <table>
            <thead><tr><th>Sumur</th><th>Peran</th><th>Titik ECD terukur</th><th>Titik rig (Rec 01)</th><th>Rentang</th></tr></thead>
            <tbody>{ds.data?.map((w) => (
              <tr key={w.id}><td>{w.name}</td><td>{w.role}</td><td className="mono">{w.ecd_points.toLocaleString()}</td><td className="mono">{w.rig_points.toLocaleString()}</td><td className="small">{dateOnly(w.t0)} → {dateOnly(w.t1)}</td></tr>
            ))}</tbody>
          </table>
          <p className="note">Atur peran sumur di Data &amp; Upload. Sumur <b>blind</b> tidak pernah ikut training; <b>case</b> (mis. PDSI 53.2) dan <b>shadow</b> hanya inferensi.</p>
        </div>
        <div className="card">
          <h3>Training baru</h3>
          <div className="small">Train: {train.join(", ") || <span style={{ color: "#F59E4B" }}>belum ada sumur peran train</span>}</div>
          <div className="small" style={{ marginBottom: 8 }}>Blind: {blind.join(", ") || <span className="muted">tidak ada (hanya LOWO)</span>}</div>
          <div className="row">
            <select value={algo} onChange={(e) => setAlgo(e.target.value)}>
              <option value="all">Semua (A–D, pilih terbaik di LOWO)</option><option value="mw_only">A · Baseline MW-only</option><option value="rf">B · Random Forest</option><option value="xgb">C · XGBoost</option><option value="lgbm">D · LightGBM</option>
            </select>
            <label className="row small"><input type="checkbox" checked={lowo} onChange={(e) => setLowo(e.target.checked)} />Leave-one-well-out</label>
            <button className="pri" disabled={!can("model_train") || !train.length} onClick={() => act(() => api.post("/models/train", { algo, lowo }))}>Mulai training</button>
          </div>
          <p className="note">E (LSTM) dan F (hybrid fisika) menyusul setelah data training cukup. Baseline hidraulik menunggu data BHA/rheologi (A14).</p>
        </div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>Versi model</h3>
        <table>
          <thead><tr><th>Nama</th><th>Status</th><th>Train</th><th>Blind</th><th>Gate</th><th>Dibuat</th></tr></thead>
          <tbody>{list.data?.map((r) => (
            <tr key={r.id} className="click" onClick={() => setSel(r.id)} style={{ background: r.id === sel ? "#1A222A" : undefined }}>
              <td className="mono">{r.name}</td><td style={{ color: ST[r.status] }}>{r.status}</td><td className="small">{(r.train_wells || []).join(", ")}</td><td className="small">{(r.blind_wells || []).join(", ") || "—"}</td>
              <td className="mono">{Object.values(r.gates).filter(Boolean).length}/6</td><td className="small muted">{wib(r.created_at, true)} · {r.created_by}</td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {m && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1.3fr) minmax(0, 1fr)", marginTop: 12, alignItems: "start" }}>
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>{m.name}</h3><span style={{ color: ST[m.status] }}>{m.status}</span><span className="sp" />
              {can("model_promote") && <>
                <button onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "shadow" }))} disabled={m.status === "training" || m.status === "failed"}>→ Shadow</button>
                <button className="pri" onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "production" }))} disabled={Object.values(m.gates).filter(Boolean).length < 6}>→ Production</button>
                <button onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "archived" }))}>Arsip / rollback</button>
              </>}
            </div>
            {best && (
              <div className="kpis" style={{ marginTop: 10 }}>
                <Kpi l={`MAE ${best.blind ? "blind" : "LOWO"}`} v={M(best.blind || best.lowo, "mae")} s="ppg" />
                <Kpi l="RMSE" v={M(best.blind || best.lowo, "rmse")} />
                <Kpi l="P95 |error|" v={M(best.blind || best.lowo, "p95")} />
                <Kpi l="Dalam ±0.1 ppg" v={(best.blind || best.lowo)?.within_tol != null ? `${Math.round((best.blind || best.lowo).within_tol * 100)}%` : "—"} />
                <Kpi l="CI MAE (bootstrap per sumur)" v={best.lowo_ci_mae ? `${n(best.lowo_ci_mae[0], 3)}–${n(best.lowo_ci_mae[1], 3)}` : "—"} />
              </div>
            )}
            <h3>Perbandingan eksperimen</h3>
            {ref === " LOWO" && <p className="note">Belum ada sumur blind → kolom RMSE–±0.1 memakai hasil LOWO. Persistence memakai ECD terukur sebelumnya (pembanding, tidak tersedia di run tanpa PWD).</p>}
            <table>
              <thead><tr><th>Eksperimen</th><th>MAE LOWO</th><th>MAE blind</th><th>RMSE{ref}</th><th>R²{ref}</th><th>P90</th><th>P95</th><th>Bias</th><th>±0.1</th></tr></thead>
              <tbody>{Object.entries(ex).map(([k, e]: [string, any]) => { const b = e.blind || e.lowo || {}; return (
                <tr key={k} style={{ fontWeight: k === chosen ? 600 : undefined }}><td>{e.label}{k === chosen ? " ✓" : ""}</td><td className="mono">{M(e.lowo, "mae")}</td><td className="mono">{M(b, "mae")}</td><td className="mono">{M(b, "rmse")}</td>
                  <td className="mono">{M(b, "r2")}</td><td className="mono">{M(b, "p90")}</td><td className="mono">{M(b, "p95")}</td><td className="mono">{M(b, "bias")}</td><td className="mono">{b.within_tol != null ? `${Math.round(b.within_tol * 100)}%` : "—"}</td></tr>); })}</tbody>
            </table>
            {best?.per_state && (<>
              <h3 style={{ marginTop: 14 }}>Per state operasi</h3>
              <table><thead><tr><th>State</th><th>n</th><th>MAE</th><th>P95</th><th>Bias</th></tr></thead>
                <tbody>{Object.entries(best.per_state).map(([s, v]: [string, any]) => <tr key={s}><td>{s === "CLEANOUT" ? "CLEAN-OUT (REAM+WASH+CIRC)" : s}</td><td className="mono">{v.n}</td><td className="mono">{M(v, "mae")}</td><td className="mono">{M(v, "p95")}</td><td className="mono">{M(v, "bias")}</td></tr>)}</tbody></table>
            </>)}
            {best?.lowo_per_well && (<>
              <h3 style={{ marginTop: 14 }}>LOWO per sumur</h3>
              <table><thead><tr><th>Sumur ditahan</th><th>n</th><th>MAE</th><th>P95</th><th>Bias</th></tr></thead>
                <tbody>{Object.entries(best.lowo_per_well).map(([s, v]: [string, any]) => <tr key={s}><td>{s}</td><td className="mono">{v.n}</td><td className="mono">{M(v, "mae")}</td><td className="mono">{M(v, "p95")}</td><td className="mono">{M(v, "bias")}</td></tr>)}</tbody></table>
            </>)}
          </div>
          <div className="grid">
            <div className="card">
              <h3>Promotion gate</h3>
              {Object.entries(m.gate_labels).map(([k, l]: [string, any]) => (
                <label key={k} className="row" style={{ padding: "5px 0", borderTop: "1px solid #222B34" }}>
                  <input type="checkbox" checked={!!m.gates[k]} disabled={!can("model_gate")} onChange={(e) => act(() => api.post(`/models/${m.id}/gate`, { gate: k, value: e.target.checked }))} />
                  <span>{l}</span>
                </label>
              ))}
              <p className="note">Production butuh 6/6. Engineering review oleh Drilling Eng.</p>
            </div>
            {imp.length > 0 && (
              <div className="card"><h3>Feature importance</h3>
                <EChart height={Math.max(160, imp.length * 22)} option={{ animation: false, grid: { left: 90, right: 20, top: 4, bottom: 20 }, xAxis: { type: "value", axisLabel: { color: "#9AA5B1" }, splitLine: { lineStyle: { color: "#1E262E" } } },
                  yAxis: { type: "category", inverse: true, data: imp.map((x) => x[0]), axisLabel: { color: "#C5CDD6" } }, series: [{ type: "bar", data: imp.map((x) => x[1]), itemStyle: { color: "#7DB4FF" } }] }} />
              </div>
            )}
            <div className="card"><h3>Log</h3><pre className="small mono" style={{ whiteSpace: "pre-wrap", margin: 0, maxHeight: 260, overflow: "auto" }}>{m.log || "—"}</pre></div>
          </div>
        </div>
      )}
    </>
  );
}
