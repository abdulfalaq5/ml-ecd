import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { dateOnly, n, wib } from "../lib/fmt";
import { EChart, Err, Kpi } from "../components/ui";
import { t } from "../lib/i18n";

const ST: Record<string, string> = { production: "#1E9E5A", shadow: "#2F6FD1", candidate: "#B98900", training: "#E8710A", archived: "#7A8694", failed: "#D63A40" };
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
      <div className="top"><h1>{t("Model ML")}</h1><span className="muted small">{t("Nowcast ECD dari parameter permukaan · validasi grouped-by-well (LOWO + blind tetap)")}</span></div>
      <Err e={msg || list.err} />
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", alignItems: "start" }}>
        <div className="card">
          <h3>{t("Dataset per sumur")}</h3>
          <table>
            <thead><tr><th>{t("Sumur")}</th><th>{t("Peran")}</th><th>{t("Titik ECD terukur")}</th><th>{t("Titik rig (Rec 01)")}</th><th>{t("Rentang")}</th></tr></thead>
            <tbody>{ds.data?.map((w) => (
              <tr key={w.id}><td>{w.name}</td><td>{w.role}</td><td className="mono">{w.ecd_points.toLocaleString()}</td><td className="mono">{w.rig_points.toLocaleString()}</td><td className="small">{dateOnly(w.t0)} → {dateOnly(w.t1)}</td></tr>
            ))}</tbody>
          </table>
          <p className="note">{t("Atur peran sumur di Data & Upload. Sumur")}{" "}<b>{t("blind")}</b>{" "}{t("tidak pernah ikut training;")}{" "}<b>{t("case")}</b>{" "}{t("(mis. PDSI 53.2) dan")}{" "}<b>{t("shadow")}</b>{" "}{t("hanya inferensi.")}</p>
        </div>
        <div className="card">
          <h3>{t("Training baru")}</h3>
          <div className="small">{t("Train:")}{" "}{train.join(", ") || <span style={{ color: "#E07A10" }}>{t("belum ada sumur peran train")}</span>}</div>
          <div className="small" style={{ marginBottom: 8 }}>{t("Blind:")}{" "}{blind.join(", ") || <span className="muted">{t("tidak ada (hanya LOWO)")}</span>}</div>
          <div className="row">
            <select value={algo} onChange={(e) => setAlgo(e.target.value)}>
              <option value="all">{t("Semua (A–D, pilih terbaik di LOWO)")}</option><option value="mw_only">{t("A · Baseline MW-only")}</option><option value="rf">{t("B · Random Forest")}</option><option value="xgb">{t("C · XGBoost")}</option><option value="lgbm">{t("D · LightGBM")}</option>
            </select>
            <label className="row small"><input type="checkbox" checked={lowo} onChange={(e) => setLowo(e.target.checked)} />{t("Leave-one-well-out")}</label>
            <button className="pri" disabled={!can("model_train") || !train.length} onClick={() => act(() => api.post("/models/train", { algo, lowo }))}>{t("Mulai training")}</button>
          </div>
          <p className="note">{t("E (LSTM) dan F (hybrid fisika) menyusul setelah data training cukup. Baseline hidraulik menunggu data BHA/rheologi (A14).")}</p>
        </div>
      </div>
      <div className="card" style={{ marginTop: 12 }}>
        <h3>{t("Versi model")}</h3>
        <table>
          <thead><tr><th>{t("Nama")}</th><th>{t("Status")}</th><th>{t("Train")}</th><th>{t("Blind")}</th><th>{t("Gate")}</th><th>{t("Dibuat")}</th></tr></thead>
          <tbody>{list.data?.map((r) => (
            <tr key={r.id} className="click" onClick={() => setSel(r.id)} style={{ background: r.id === sel ? "#EAF1FA" : undefined }}>
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
                <button onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "shadow" }))} disabled={m.status === "training" || m.status === "failed"}>{t("→ Shadow")}</button>
                <button className="pri" onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "production" }))} disabled={Object.values(m.gates).filter(Boolean).length < 6}>{t("→ Production")}</button>
                <button onClick={() => act(() => api.post(`/models/${m.id}/status`, { status: "archived" }))}>{t("Arsip / rollback")}</button>
              </>}
            </div>
            {best && (
              <div className="kpis" style={{ marginTop: 10 }}>
                <Kpi l={t("MAE {p0}", { p0: best.blind ? "blind" : "LOWO" })} v={M(best.blind || best.lowo, "mae")} s="ppg" />
                <Kpi l="RMSE" v={M(best.blind || best.lowo, "rmse")} />
                <Kpi l={t("P95 |error|")} v={M(best.blind || best.lowo, "p95")} />
                <Kpi l={t("Dalam ±0.1 ppg")} v={(best.blind || best.lowo)?.within_tol != null ? `${Math.round((best.blind || best.lowo).within_tol * 100)}%` : "—"} />
                <Kpi l={t("CI MAE (bootstrap per sumur)")} v={best.lowo_ci_mae ? `${n(best.lowo_ci_mae[0], 3)}–${n(best.lowo_ci_mae[1], 3)}` : "—"} />
              </div>
            )}
            <h3>{t("Perbandingan eksperimen")}</h3>
            {ref === " LOWO" && <p className="note">{t("Belum ada sumur blind → kolom RMSE–±0.1 memakai hasil LOWO. Persistence memakai ECD terukur sebelumnya (pembanding, tidak tersedia di run tanpa PWD).")}</p>}
            <table>
              <thead><tr><th>{t("Eksperimen")}</th><th>{t("MAE LOWO")}</th><th>{t("MAE blind")}</th><th>{t("RMSE")}{ref}</th><th>R²{ref}</th><th>P90</th><th>P95</th><th>{t("Bias")}</th><th>±0.1</th></tr></thead>
              <tbody>{Object.entries(ex).map(([k, e]: [string, any]) => { const b = e.blind || e.lowo || {}; return (
                <tr key={k} style={{ fontWeight: k === chosen ? 600 : undefined }}><td>{e.label}{k === chosen ? " ✓" : ""}</td><td className="mono">{M(e.lowo, "mae")}</td><td className="mono">{M(b, "mae")}</td><td className="mono">{M(b, "rmse")}</td>
                  <td className="mono">{M(b, "r2")}</td><td className="mono">{M(b, "p90")}</td><td className="mono">{M(b, "p95")}</td><td className="mono">{M(b, "bias")}</td><td className="mono">{b.within_tol != null ? `${Math.round(b.within_tol * 100)}%` : "—"}</td></tr>); })}</tbody>
            </table>
            {best?.per_state && (<>
              <h3 style={{ marginTop: 14 }}>{t("Per state operasi")}</h3>
              <table><thead><tr><th>{t("State")}</th><th>n</th><th>{t("MAE")}</th><th>P95</th><th>{t("Bias")}</th></tr></thead>
                <tbody>{Object.entries(best.per_state).map(([s, v]: [string, any]) => <tr key={s}><td>{s === "CLEANOUT" ? t("CLEAN-OUT (REAM+WASH+CIRC)") : s}</td><td className="mono">{v.n}</td><td className="mono">{M(v, "mae")}</td><td className="mono">{M(v, "p95")}</td><td className="mono">{M(v, "bias")}</td></tr>)}</tbody></table>
            </>)}
            {best?.lowo_per_well && (<>
              <h3 style={{ marginTop: 14 }}>{t("LOWO per sumur")}</h3>
              <table><thead><tr><th>{t("Sumur ditahan")}</th><th>n</th><th>{t("MAE")}</th><th>P95</th><th>{t("Bias")}</th></tr></thead>
                <tbody>{Object.entries(best.lowo_per_well).map(([s, v]: [string, any]) => <tr key={s}><td>{s}</td><td className="mono">{v.n}</td><td className="mono">{M(v, "mae")}</td><td className="mono">{M(v, "p95")}</td><td className="mono">{M(v, "bias")}</td></tr>)}</tbody></table>
            </>)}
          </div>
          <div className="grid">
            <div className="card">
              <h3>{t("Promotion gate")}</h3>
              {Object.entries(m.gate_labels).map(([k, l]: [string, any]) => (
                <label key={k} className="row" style={{ padding: "5px 0", borderTop: "1px solid #E3E8EE" }}>
                  <input type="checkbox" checked={!!m.gates[k]} disabled={!can("model_gate")} onChange={(e) => act(() => api.post(`/models/${m.id}/gate`, { gate: k, value: e.target.checked }))} />
                  <span>{l}</span>
                </label>
              ))}
              <p className="note">{t("Production butuh 6/6. Engineering review oleh Drilling Eng.")}</p>
            </div>
            {imp.length > 0 && (
              <div className="card"><h3>{t("Feature importance")}</h3>
                <EChart height={Math.max(160, imp.length * 22)} option={{ animation: false, grid: { left: 90, right: 20, top: 4, bottom: 20 }, xAxis: { type: "value", axisLabel: { color: "#5B6775" }, splitLine: { lineStyle: { color: "#EEF1F5" } } },
                  yAxis: { type: "category", inverse: true, data: imp.map((x) => x[0]), axisLabel: { color: "#3A4552" } }, series: [{ type: "bar", data: imp.map((x) => x[1]), itemStyle: { color: "#2F6FD1" } }] }} />
              </div>
            )}
            <div className="card"><h3>{t("Log")}</h3><pre className="small mono" style={{ whiteSpace: "pre-wrap", margin: 0, maxHeight: 260, overflow: "auto" }}>{m.log || "—"}</pre></div>
          </div>
        </div>
      )}
    </>
  );
}
