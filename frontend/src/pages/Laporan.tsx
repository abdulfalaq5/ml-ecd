import { useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ft, n, wib } from "../lib/fmt";
import { Err, Kpi, Level } from "../components/ui";

export default function Laporan() {
  const { wells, wellId, can } = useApp();
  const list = useFetch<any>(() => api.get("/reports"), []);
  const sys = useFetch<any>(() => api.get("/settings/system/info"), []);
  const [f, setF] = useState<any>({ kind: "daily", well_id: wellId, t0: "", t1: "", ai: false });
  const [sel, setSel] = useState<any | null>(null);
  const [busy, setBusy] = useState(false); const [msg, setMsg] = useState<string | null>(null);
  const [narr, setNarr] = useState("");
  const create = async () => {
    setBusy(true); setMsg(null);
    try { const r = await api.post("/reports", { ...f, well_id: f.kind === "model" ? null : f.well_id }); setSel(r); setNarr(r.narrative); list.reload(); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); }
  };
  const open = async (id: number) => { const r = await api.get(`/reports/${id}`); setSel(r); setNarr(r.narrative); };
  const saveNarr = async (ai: boolean) => { setBusy(true); try { const r = await api.post(`/reports/${sel.id}/narrative`, { narrative: narr, ai }); setSel(r); setNarr(r.narrative); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); } };
  const s = sel?.summary || {};
  const kinds = list.data?.kinds || {};
  return (
    <>
      <div className="top"><h1>Laporan</h1><span className="muted small">harian · event/studi kasus · evaluasi model · QC data</span></div>
      <Err e={msg} />
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.6fr)", alignItems: "start" }}>
        <div className="grid">
          <div className="card">
            <h3>Buat laporan</h3>
            <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <label className="f">Jenis<select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(kinds).map(([k, l]: any) => <option key={k} value={k}>{l}</option>)}</select></label>
              <label className="f">Sumur<select value={f.well_id ?? ""} disabled={f.kind === "model"} onChange={(e) => setF({ ...f, well_id: Number(e.target.value) })}>{wells.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
              <label className="f">Dari (WIB)<input type="datetime-local" value={f.t0} onChange={(e) => setF({ ...f, t0: e.target.value })} /></label>
              <label className="f">Sampai (WIB)<input type="datetime-local" value={f.t1} onChange={(e) => setF({ ...f, t1: e.target.value })} /></label>
            </div>
            <label className="row small" style={{ margin: "8px 0" }}><input type="checkbox" checked={f.ai} disabled={!sys.data?.ai_enabled} onChange={(e) => setF({ ...f, ai: e.target.checked })} />Narasi otomatis (AI){!sys.data?.ai_enabled && <span className="muted"> — set ANTHROPIC_API_KEY di .env untuk mengaktifkan</span>}</label>
            <button className="pri" disabled={busy || !can("report")} onClick={create}>{busy ? "Memproses…" : "Buat laporan"}</button>
            <p className="note">Kosongkan periode = 1 jam terakhir data. Narasi AI hanya menerima ringkasan angka (bukan data mentah); wajib direview engineer.</p>
          </div>
          <div className="card">
            <h3>Arsip</h3>
            <table><tbody>{list.data?.items.map((r: any) => (
              <tr key={r.id} className="click" onClick={() => open(r.id)} style={{ background: sel?.id === r.id ? "#EAF1FA" : undefined }}>
                <td>{r.title}<div className="muted small">{r.period_start ? `${wib(r.period_start, true)} → ${wib(r.period_end, true)}` : "periode default"}</div></td>
                <td className="small muted">{wib(r.created_at, true)}<br />{r.created_by}</td>
              </tr>
            ))}</tbody></table>
          </div>
        </div>
        {sel ? (
          <div className="card" id="print">
            <div className="row"><h3 style={{ margin: 0 }}>{sel.title}</h3><span className="sp" />
              <button onClick={() => api.download(`/reports/${sel.id}/xlsx`, `laporan_${sel.kind}_${sel.id}.xlsx`)}>Unduh Excel</button>
              <button onClick={() => window.print()}>Cetak / PDF</button>
              {can("report") && <button className="danger" onClick={async () => { await api.del(`/reports/${sel.id}`); setSel(null); list.reload(); }}>Hapus</button>}
            </div>
            <div className="muted small" style={{ margin: "6px 0 12px" }}>{s.period?.[0] ? `${wib(s.period[0], true)} → ${wib(s.period[1], true)}` : "periode default"} · dibuat {sel.created_by} {wib(sel.created_at, true)}</div>
            {(sel.kind === "daily" || sel.kind === "event") && (<>
              <div className="kpis">
                <Kpi l={`ECD rata-rata (${s.ecd_source || "—"})`} v={n(s.ecd_mean)} s={`maks ${n(s.ecd_max)} ppg`} color="#E8710A" />
                <Kpi l="Margin atas min" v={n(s.margin_up_min)} /><Kpi l="Margin bawah min" v={n(s.margin_low_min)} />
                <Kpi l="Durasi data" v={`${s.data_minutes ?? 0} mnt`} s={s.model || "tanpa model"} />
              </div>
              <div className="row small" style={{ marginBottom: 10 }}>{Object.entries(s.level_minutes || {}).map(([k, v]: any) => <span key={k} className="row" style={{ gap: 4 }}><Level v={k} />{v} mnt</span>)}</div>
              <div className="row small muted" style={{ marginBottom: 10 }}>State: {Object.entries(s.state_minutes || {}).map(([k, v]: any) => `${k} ${v} mnt`).join(" · ")}</div>
              <div className="small muted">PPFG: {s.ppfg}</div>
              <h3 style={{ marginTop: 12 }}>Deteksi ({s.detections?.length || 0})</h3>
              <table><thead><tr><th>Waktu</th><th>Level</th><th>Indikator</th><th>MD</th></tr></thead>
                <tbody>{(s.detections || []).map((d: any, i: number) => <tr key={i}><td className="mono">{wib(d.start, true)}</td><td><Level v={d.level} /></td><td>{d.label}</td><td className="mono">{d.md ? Math.round(d.md) : "—"}</td></tr>)}</tbody></table>
              {s.events?.length > 0 && (<><h3 style={{ marginTop: 12 }}>Event tercatat</h3>
                <table><tbody>{s.events.map((e: any, i: number) => <tr key={i}><td className="mono">{wib(e.onset, true)}</td><td>{e.category}</td><td>{e.review}</td></tr>)}</tbody></table></>)}
            </>)}
            {sel.kind === "rathole" && (<>
              {s.message && <div className="note">{s.message}</div>}
              {s.rathole && <div className="small" style={{ marginBottom: 8 }}>Zona rathole <b>{ft(s.rathole.top_md)}–{ft(s.rathole.base_md)} ft</b> ({n(s.rathole.length_ft, 0)} ft) sejak {wib(s.rathole.since, true)} · section {s.well_section || "—"} · model {s.model?.name || "—"} ({s.model?.well_role_in_model})</div>}
              {s.phase1 && <div className="kpis">
                <Kpi l="Fase 1 · MAE ECD ⓥ vs terukur" v={n(s.phase1.mae, 3)} s={`bias ${n(s.phase1.bias, 3)} · n=${s.phase1.n}`} />
                <Kpi l="Fase 1 · di kedalaman rathole" v={n(s.phase1.in_rathole_depth?.mae, 3)} s={`bias ${n(s.phase1.in_rathole_depth?.bias, 3)}`} />
                <Kpi l="Fase 2 · jam pompa di rathole" v={n((s.phase2?.rathole_pump_minutes || 0) / 60, 1)} s={`dari ${n((s.phase2?.pump_minutes || 0) / 60, 1)} jam pompa`} />
                <Kpi l="Fase 2 · ECD ⓥ median" v={n(s.phase2?.ecd_pred_med)} s={`maks ${n(s.phase2?.ecd_pred_max)} ppg`} color="#E8710A" />
              </div>}
              {s.zone_table?.length > 0 && <table><thead><tr><th>Indikasi (fase 2)</th><th>Rathole</th><th>Atas shoe</th><th>Bawah rathole</th></tr></thead>
                <tbody>{s.zone_table.map((z: any) => <tr key={z.label}><td>{z.label}</td><td className="mono"><b>{z.rathole}</b></td><td className="mono">{z.atas_shoe}</td><td className="mono">{z.bawah_rathole}</td></tr>)}</tbody></table>}
              {s.caveats?.length > 0 && <><h3 style={{ marginTop: 12 }}>Catatan</h3><ul className="small">{s.caveats.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul></>}
              <div className="small muted">Detail harian fase 1 &amp; 2 ada di file Excel dan di halaman Studi Kasus Rathole.</div>
            </>)}
            {sel.kind === "model" && s.model && (
              <div className="small"><b>{s.model.name}</b> ({s.model.status}) · train {s.model.train_wells?.join(", ")} · blind {s.model.blind_wells?.join(", ") || "—"}
                <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(s.model.metrics?.experiments?.[s.model.metrics?.chosen]?.blind || s.model.metrics?.experiments?.[s.model.metrics?.chosen]?.lowo, null, 2)}</pre></div>
            )}
            {sel.kind === "qc" && (
              <table><thead><tr><th>File</th><th>Rec</th><th>Baris</th><th>Temuan</th></tr></thead>
                <tbody>{(s.files || []).map((x: any, i: number) => <tr key={i}><td className="small">{x.file}</td><td>{x.record} {x.basis}</td><td className="mono">{x.rows}</td><td className="small">{(x.qc || []).filter((q: any) => q.level !== "ok").map((q: any) => q.title).join("; ") || "ok"}</td></tr>)}</tbody></table>
            )}
            <h3 style={{ marginTop: 14 }}>Narasi</h3>
            <textarea value={narr} onChange={(e) => setNarr(e.target.value)} placeholder="Tulis ringkasan / kesimpulan engineer…" style={{ minHeight: 140 }} />
            <div className="row" style={{ marginTop: 6 }}>
              <button onClick={() => saveNarr(false)} disabled={busy}>Simpan narasi</button>
              {sys.data?.ai_enabled && <button onClick={() => saveNarr(true)} disabled={busy}>Buat ulang dengan AI</button>}
            </div>
          </div>
        ) : <div className="card empty">Pilih laporan dari arsip atau buat baru.</div>}
      </div>
    </>
  );
}
