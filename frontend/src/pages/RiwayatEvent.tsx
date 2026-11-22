import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ft, wib, toLocalInput } from "../lib/fmt";
import { Err, Level } from "../components/ui";

const REVIEW_COLOR: Record<string, string> = { Draft: "#5B6775", "Menunggu review": "#B98900", Dikonfirmasi: "#1E9E5A", Ditolak: "#D63A40" };

export default function RiwayatEvent() {
  const { wells, wellId, can } = useApp();
  const [fw, setFw] = useState<string>(""); const [fc, setFc] = useState(""); const [fr, setFr] = useState("");
  const meta = useFetch<any>(() => api.get("/events/meta"), []);
  const { data, err, reload } = useFetch<any[]>(() => api.get("/events", { well_id: fw, category: fc, review: fr }), [fw, fc, fr]);
  const [sel, setSel] = useState<any | null>(null);
  const [form, setForm] = useState<any | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const save = async () => {
    try { await api.post("/events", form); setForm(null); reload(); } catch (e: any) { setMsg(e.message); }
  };
  const review = async (status: string) => {
    try { const r = await api.post(`/events/${sel.id}/review`, { status, note: "" }); setSel(r); reload(); } catch (e: any) { setMsg(e.message); }
  };
  const m = meta.data;
  return (
    <>
      <div className="top"><h1>Riwayat Event</h1><span className="muted small">katalog event + review (Draft → Menunggu review → Dikonfirmasi / Ditolak)</span><span className="sp" />
        {can("event_label") && <button className="pri" onClick={() => setForm({ well_id: wellId, onset: "", level: "WARNING", category: m?.categories?.[0], confidence: "Sedang", evidence: "", detail: "", md: null, source: "manual" })}>+ Event baru</button>}
      </div>
      <div className="row" style={{ marginBottom: 12 }}>
        <select value={fw} onChange={(e) => setFw(e.target.value)}><option value="">Semua sumur</option>{wells.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
        <select value={fc} onChange={(e) => setFc(e.target.value)}><option value="">Semua kategori</option>{m?.categories.map((c: string) => <option key={c}>{c}</option>)}</select>
        <select value={fr} onChange={(e) => setFr(e.target.value)}><option value="">Semua status review</option>{m?.review.map((c: string) => <option key={c}>{c}</option>)}</select>
      </div>
      <Err e={err || msg} />
      <div className="grid" style={{ gridTemplateColumns: sel ? "minmax(0, 1.4fr) minmax(0, 1fr)" : "1fr", alignItems: "start" }}>
        <div className="card">
          <table>
            <thead><tr><th>Onset (WIB)</th><th>Sumur</th><th>MD ft</th><th>Level</th><th>Kategori</th><th>Confidence</th><th>Review</th><th>Sumber</th></tr></thead>
            <tbody>
              {data?.length === 0 && <tr><td colSpan={8} className="muted">Belum ada event.</td></tr>}
              {data?.map((e) => (
                <tr key={e.id} className="click" onClick={() => setSel(e)}>
                  <td className="mono">{wib(e.onset, true)}</td><td>{e.well}</td><td className="mono">{ft(e.md)}</td><td><Level v={e.level} /></td>
                  <td>{e.category}</td><td>{e.confidence}</td><td style={{ color: REVIEW_COLOR[e.review_status] }}>{e.review_status}</td><td className="muted small">{e.source}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {sel && (
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>{sel.category}</h3><Level v={sel.level} /><span className="sp" /><button onClick={() => setSel(null)}>Tutup</button></div>
            <div className="muted small" style={{ margin: "6px 0" }}>{sel.well} · {wib(sel.onset, true)}{sel.end ? ` – ${wib(sel.end)}` : ""} · MD {ft(sel.md)} ft · {sel.mode || "—"}</div>
            <p><b className="small muted">Bukti</b><br />{sel.evidence || "—"}</p>
            <p><b className="small muted">Detail</b><br />{sel.detail || "—"}</p>
            <div className="row small"><span>Status: <b style={{ color: REVIEW_COLOR[sel.review_status] }}>{sel.review_status}</b></span></div>
            <div className="row" style={{ marginTop: 10 }}>
              {sel.review_status === "Draft" && can("event_label") && <button onClick={() => review("Menunggu review")}>Ajukan review</button>}
              {can("event_review") && sel.review_status !== "Dikonfirmasi" && <button className="pri" onClick={() => review("Dikonfirmasi")}>Konfirmasi</button>}
              {can("event_review") && sel.review_status !== "Ditolak" && <button className="danger" onClick={() => review("Ditolak")}>Tolak</button>}
              <Link to="/anomali" className="small">Lihat di Analisis Anomali →</Link>
            </div>
            <h3 style={{ marginTop: 14 }}>Riwayat</h3>
            {(sel.history || []).map((h: any, i: number) => <div key={i} className="small muted">{wib(h.at, true)} · {h.by}: {h.action}{h.note ? ` — ${h.note}` : ""}</div>)}
          </div>
        )}
      </div>
      {form && (
        <div className="card" style={{ marginTop: 12, maxWidth: 760 }}>
          <h3>Event baru (label)</h3>
          <div className="grid" style={{ gridTemplateColumns: "repeat(3, 1fr)" }}>
            <label className="f">Sumur<select value={form.well_id ?? ""} onChange={(e) => setForm({ ...form, well_id: Number(e.target.value) })}>{wells.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
            <label className="f">Onset (WIB)<input type="datetime-local" value={form.onset} onChange={(e) => setForm({ ...form, onset: e.target.value })} /></label>
            <label className="f">Selesai (opsional)<input type="datetime-local" value={form.end || ""} onChange={(e) => setForm({ ...form, end: e.target.value })} /></label>
            <label className="f">MD (ft)<input type="number" value={form.md ?? ""} onChange={(e) => setForm({ ...form, md: e.target.value ? Number(e.target.value) : null })} /></label>
            <label className="f">Level<select value={form.level} onChange={(e) => setForm({ ...form, level: e.target.value })}>{m?.levels.map((c: string) => <option key={c}>{c}</option>)}</select></label>
            <label className="f">Kategori<select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{m?.categories.map((c: string) => <option key={c}>{c}</option>)}</select></label>
            <label className="f">Confidence<select value={form.confidence} onChange={(e) => setForm({ ...form, confidence: e.target.value })}>{m?.confidence.map((c: string) => <option key={c}>{c}</option>)}</select></label>
            <label className="f">Mode / state<input value={form.mode || ""} onChange={(e) => setForm({ ...form, mode: e.target.value })} placeholder="mis. REAM, TRIP" /></label>
            <label className="f">Sumber<input value={form.source} onChange={(e) => setForm({ ...form, source: e.target.value })} /></label>
          </div>
          <label className="f" style={{ marginTop: 8 }}>Bukti (DDR, laporan PHR, catatan RTO)<textarea value={form.evidence} onChange={(e) => setForm({ ...form, evidence: e.target.value })} /></label>
          <label className="f">Detail<textarea value={form.detail} onChange={(e) => setForm({ ...form, detail: e.target.value })} /></label>
          <div className="row" style={{ marginTop: 8 }}><button className="pri" onClick={save} disabled={!form.onset || !form.well_id}>Simpan sebagai Draft</button><button onClick={() => setForm(null)}>Batal</button></div>
        </div>
      )}
    </>
  );
}
