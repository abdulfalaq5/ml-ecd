import { useRef, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { dateOnly, ft, n, wib } from "../lib/fmt";
import { Err, Kpi, WellSelect } from "../components/ui";

const SEG: Record<string, [string, string]> = {
  rec01_ecd: ["#1E9E5A", "Rec 01 + ECD terukur"], rec01: ["#2F6FD1", "Rec 01 saja (ECD ⓥ)"], ecd_only: ["#B98900", "ECD tanpa Rec 01"], gap: ["#D5DCE4", "gap"], none: ["#D5DCE4", "kosong"],
};
const LVL: Record<string, string> = { ok: "#1E9E5A", warn: "#E07A10", info: "#2F6FD1" };
const RECS: [string, string][] = [["1_time", "01 IDS Rig · time"], ["1_depth", "01 IDS Rig · depth"], ["2_time", "02 MWD/PWD · time"], ["2_depth", "02 MWD/PWD · depth"], ["3_depth", "03 PPFG"], ["4_depth", "04 Mud Weight"], ["7_depth", "07 Survey"]];

export default function DataUpload() {
  const { wellId, well, can, reloadWells } = useApp();
  const q = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/quality`) : null), [wellId]);
  const files = useFetch<any[]>(() => (wellId ? api.get(`/wells/${wellId}/files`) : null), [wellId]);
  const [busy, setBusy] = useState(false); const [res, setRes] = useState<any[] | null>(null); const [msg, setMsg] = useState<string | null>(null);
  const [mode, setMode] = useState("append");
  const [newName, setNewName] = useState("");
  const [edit, setEdit] = useState<any | null>(null);
  const inp = useRef<HTMLInputElement>(null);

  const upload = async (fl: FileList | null) => {
    if (!fl?.length || !wellId) return;
    const fd = new FormData();
    Array.from(fl).forEach((f) => fd.append("files", f));
    fd.append("mode", mode);
    setBusy(true); setMsg(null);
    try { const r = await api.form(`/wells/${wellId}/upload`, fd); setRes(r.results); q.reload(); files.reload(); reloadWells(); }
    catch (e: any) { setMsg(e.message); } finally { setBusy(false); if (inp.current) inp.current.value = ""; }
  };
  const scan = async () => { setBusy(true); try { const r = await api.post("/ingest/scan"); setRes(r.processed.flatMap((p: any) => p.results.map((x: any) => ({ ...x, file: `${p.well}/${x.file}` })))); await reloadWells(); q.reload(); files.reload(); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); } };
  const create = async () => { try { await api.post("/wells", { name: newName, role: "train" }); setNewName(""); await reloadWells(); } catch (e: any) { setMsg(e.message); } };
  const saveWell = async () => { try { await api.put(`/wells/${wellId}`, edit); setEdit(null); await reloadWells(); q.reload(); } catch (e: any) { setMsg(e.message); } };
  const signoff = async () => { try { await api.post(`/wells/${wellId}/qc/signoff`); q.reload(); } catch (e: any) { setMsg(e.message); } };
  const d = q.data;
  const tl = d?.timeline || [];
  const T0 = tl.length ? new Date(tl[0].t0).getTime() : 0, T1 = tl.length ? new Date(tl[tl.length - 1].t1).getTime() : 1;

  return (
    <>
      <div className="top"><h1>Data &amp; Upload</h1><WellSelect /><span className="sp" />
        {can("well_edit") && <><input placeholder="nama sumur baru" value={newName} onChange={(e) => setNewName(e.target.value)} /><button onClick={create} disabled={!newName}>+ Sumur</button></>}
      </div>
      <Err e={msg || q.err} />
      {well && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="row">
            <b>{well.name}</b><span className="chip">peran: {well.role}</span><span className="chip">section {well.section || "—"}</span><span className="chip">shoe {ft(well.shoe_md)} ft</span>
            {well.aliases?.length > 0 && <span className="muted small">alias WID: {well.aliases.join(", ")}</span>}
            <span className="sp" />{can("well_edit") && <button onClick={() => setEdit({ name: well.name, field: well.field, section: well.section, shoe_md: well.shoe_md, role: well.role, status: well.status, notes: well.notes })}>Edit sumur</button>}
          </div>
          {edit && (
            <div className="row" style={{ marginTop: 10 }}>
              <label className="f">Section<input value={edit.section} onChange={(e) => setEdit({ ...edit, section: e.target.value })} placeholder='8-1/2"' /></label>
              <label className="f">Shoe MD (ft)<input type="number" value={edit.shoe_md ?? ""} onChange={(e) => setEdit({ ...edit, shoe_md: e.target.value ? Number(e.target.value) : null })} /></label>
              <label className="f">Peran<select value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value })}>{["train", "blind", "case", "shadow"].map((r) => <option key={r}>{r}</option>)}</select></label>
              <label className="f">Status<select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>{["active", "archived"].map((r) => <option key={r}>{r}</option>)}</select></label>
              <label className="f" style={{ flex: 1 }}>Catatan<input value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} /></label>
              <button className="pri" onClick={saveWell}>Simpan</button><button onClick={() => setEdit(null)}>Batal</button>
            </div>
          )}
          <p className="note">Peran: <b>train</b> ikut training (LOWO) · <b>blind</b> sumur uji tetap, tidak pernah ikut training · <b>case</b> studi kasus (mis. PDSI 53.2) · <b>shadow</b> sumur berjalan, alert UNAVAILABLE bila data &gt; 10 mnt.</p>
        </div>
      )}
      {wellId && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", alignItems: "start" }}>
          <div className="card">
            <h3>Upload file</h3>
            <div className="row">
              <input ref={inp} type="file" multiple accept=".las,.LAS,.csv,.CSV,.zip,.txt" onChange={(e) => upload(e.target.files)} disabled={!can("upload") || busy} />
              <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="append">append (lewati duplikat)</option><option value="replace">replace (timpa timestamp sama)</option></select>
              {can("upload") && <button onClick={scan} disabled={busy}>Scan folder inbox</button>}
              {busy && <span className="muted small">memproses…</span>}
            </div>
            <p className="note">Format: Navita LAS / CSV (export_las_record_0N…, export_csv_record_0N…), LAS rig (tab), atau .zip berisi file-file itu. Record dikenali dari nama file / isi. Folder inbox: <span className="mono">data/inbox/&lt;nama sumur&gt;/</span> di-scan otomatis tiap 60 dtk.</p>
            {res && (
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>File</th><th>Status</th><th>Rec</th><th>Basis</th><th>Baris</th><th>QC</th></tr></thead>
                <tbody>{res.map((r, i) => (
                  <tr key={i}><td className="small">{r.file}</td><td style={{ color: r.status === "ok" ? "#1E9E5A" : r.status === "error" ? "#D63A40" : "#5B6775" }}>{r.status}</td>
                    <td className="mono">{r.record ? String(r.record).padStart(2, "0") : ""}</td><td>{r.basis}</td><td className="mono">{r.rows?.toLocaleString()}</td>
                    <td className="small">{r.message || (r.qc || []).filter((x: any) => x.level !== "ok").map((x: any) => x.title).join("; ")}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>Kelengkapan data</h3><span className="sp" />
              {d?.signoff ? <span className="chip" style={{ color: "#1E9E5A" }}>QC sign-off {d.signoff.by} · {dateOnly(d.signoff.at)}</span> : can("qc_signoff") && <button onClick={signoff}>QC sign-off</button>}
            </div>
            <div className="kpis" style={{ marginTop: 10 }}>
              <Kpi l="Ketersediaan label ECD" v={d?.target_availability != null ? `${Math.round(d.target_availability * 100)}%` : "—"} s="jam pumps-on yang punya ECD terukur" />
              <Kpi l="PPFG versi" v={d?.ppfg_versions?.length ?? 0} s={d?.ppfg_versions?.map((v: any) => `v${v.version} ${v.status}`).join(", ")} />
              <Kpi l="MW / Survey" v={`${d?.mud_weight_rows ?? 0} / ${d?.survey_rows ?? 0}`} s="baris Rec 04 / Rec 07" />
            </div>
            <table>
              <thead><tr><th>Record</th><th>File</th><th>Baris</th><th>Rentang</th></tr></thead>
              <tbody>{RECS.map(([k, l]) => { const c = d?.completeness?.[k]; return (
                <tr key={k}><td>{l}</td><td className="mono">{c?.files ?? "—"}</td><td className="mono">{c?.rows?.toLocaleString() ?? "—"}</td>
                  <td className="small">{c ? (c.t0 ? `${wib(c.t0, true)} → ${wib(c.t1, true)}` : `${ft(c.d0)} → ${ft(c.d1)} ft`) : <span style={{ color: "#E07A10" }}>belum ada</span>}</td></tr>); })}</tbody>
            </table>
          </div>
          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h3>Timeline cakupan (per jam)</h3>
            <div style={{ display: "flex", height: 22, borderRadius: 4, overflow: "hidden", background: "#F4F6F9" }}>
              {tl.map((s: any, i: number) => { const w = ((new Date(s.t1).getTime() - new Date(s.t0).getTime()) / (T1 - T0)) * 100; return <div key={i} title={`${SEG[s.kind]?.[1]} · ${wib(s.t0, true)} → ${wib(s.t1, true)}`} style={{ width: `${w}%`, background: SEG[s.kind]?.[0] }} />; })}
            </div>
            <div className="row small muted" style={{ marginTop: 6 }}>{tl.length ? <><span>{wib(tl[0].t0, true)}</span><span className="sp" /><span>{wib(tl[tl.length - 1].t1, true)}</span></> : "belum ada data time-based"}</div>
            <div className="row small" style={{ marginTop: 6 }}>{Object.entries(SEG).slice(0, 4).map(([k, [c, l]]) => <span key={k} className="row" style={{ gap: 4 }}><i style={{ width: 12, height: 12, background: c, display: "inline-block", borderRadius: 2 }} />{l}</span>)}</div>
          </div>
          <div className="card">
            <h3>Temuan QC</h3>
            {(d?.qc || []).filter((x: any) => x.level !== "ok").length === 0 && <div className="muted small">Tidak ada temuan.</div>}
            {(d?.qc || []).filter((x: any) => x.level !== "ok").map((x: any, i: number) => (
              <div key={i} style={{ borderTop: "1px solid #E3E8EE", padding: "6px 0" }} className="small">
                <b style={{ color: LVL[x.level] }}>{x.level.toUpperCase()}</b> · {x.title} <span className="muted">— {x.file}</span><div className="muted">{x.text}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3>File ter-ingest</h3>
            <table>
              <thead><tr><th>File</th><th>Rec</th><th>Format</th><th>Baris</th><th>Oleh</th></tr></thead>
              <tbody>{files.data?.map((f) => (
                <tr key={f.id}><td className="small" title={f.unmapped?.length ? `tag tak dikenal: ${f.unmapped.join(", ")}` : ""}>{f.filename}</td><td className="mono">{String(f.record).padStart(2, "0")} {f.basis}</td>
                  <td className="small muted">{f.fmt}</td><td className="mono">{f.rows.toLocaleString()}</td><td className="small muted">{f.uploaded_by}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
