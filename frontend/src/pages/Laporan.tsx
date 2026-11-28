import { useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ft, n, wib } from "../lib/fmt";
import { Err, Kpi, Level } from "../components/ui";
import { t } from "../lib/i18n";

export default function Laporan() {
  const { wells, wellId, can } = useApp();
  const list = useFetch<any>(() => api.get("/reports"), []);
  const sys = useFetch<any>(() => api.get("/settings/system/info"), []);
  const [f, setF] = useState<any>({ kind: "daily", well_id: wellId, t0: "", t1: "", ai: true });
  const aiOn = !!sys.data?.ai_enabled;
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
      <div className="top"><h1>{t("Laporan")}</h1><span className="muted small">{t("harian · event/studi kasus · evaluasi model · QC data")}</span></div>
      <Err e={msg} />
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1.6fr)", alignItems: "start" }}>
        <div className="grid">
          <div className="card">
            <h3>{t("Buat laporan")}</h3>
            <div className="grid" style={{ gridTemplateColumns: "1fr 1fr" }}>
              <label className="f">{t("Jenis")}<select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(kinds).map(([k, l]: any) => <option key={k} value={k}>{l}</option>)}</select></label>
              <label className="f">{t("Sumur")}<select value={f.well_id ?? ""} disabled={f.kind === "model"} onChange={(e) => setF({ ...f, well_id: Number(e.target.value) })}>{wells.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select></label>
              <label className="f">{t("Dari (WIB)")}<input type="datetime-local" value={f.t0} onChange={(e) => setF({ ...f, t0: e.target.value })} /></label>
              <label className="f">{t("Sampai (WIB)")}<input type="datetime-local" value={f.t1} onChange={(e) => setF({ ...f, t1: e.target.value })} /></label>
            </div>
            {aiOn ? (
              <label className="row small" style={{ margin: "8px 0" }}><input type="checkbox" checked={f.ai} onChange={(e) => setF({ ...f, ai: e.target.checked })} />{t("Narasi dibantu AI")}{" "}<span className="muted">({sys.data?.ai_model})</span>{!f.ai && <span className="muted">{" "}{t("— dimatikan: narasi otomatis tanpa AI")}</span>}</label>
            ) : (
              <div className="small muted" style={{ margin: "8px 0" }}><NarrBadge src="template" />{" "}{t("Narasi dibuat otomatis")}{" "}<b>{t("tanpa AI")}</b>{" "}{t("dari angka laporan. Isi")}{" "}<span className="mono">{t("ANTHROPIC_API_KEY")}</span>{" "}{t("di")}{" "}<span className="mono">{t(".env")}</span>{" "}{t("agar narasi dibantu AI.")}</div>
            )}
            <button className="pri" disabled={busy || !can("report")} onClick={create}>{busy ? t("Memproses…") : t("Buat laporan")}</button>
            <p className="note">{t("Kosongkan periode = 1 jam terakhir data. Narasi selalu dibuat otomatis: dengan AI bila API key diisi (AI hanya menerima ringkasan angka, bukan data mentah), tanpa AI bila tidak. Narasi wajib direview engineer.")}</p>
          </div>
          <div className="card">
            <h3>{t("Arsip")}</h3>
            <table><tbody>{list.data?.items.map((r: any) => (
              <tr key={r.id} className="click" onClick={() => open(r.id)} style={{ background: sel?.id === r.id ? "#EAF1FA" : undefined }}>
                <td>{r.title}<div className="muted small">{r.period_start ? `${wib(r.period_start, true)} → ${wib(r.period_end, true)}` : t("periode default")}</div></td>
                <td className="small muted">{wib(r.created_at, true)}<br />{r.created_by}</td>
              </tr>
            ))}</tbody></table>
          </div>
        </div>
        {sel ? (
          <div className="card" id="print">
            <div className="row"><h3 style={{ margin: 0 }}>{sel.title}</h3><span className="sp" />
              <button onClick={() => api.download(`/reports/${sel.id}/xlsx`, `laporan_${sel.kind}_${sel.id}.xlsx`)}>{t("Unduh Excel")}</button>
              <button onClick={() => window.print()}>{t("Cetak / PDF")}</button>
              {can("report") && <button className="danger" onClick={async () => { await api.del(`/reports/${sel.id}`); setSel(null); list.reload(); }}>{t("Hapus")}</button>}
            </div>
            <div className="muted small" style={{ margin: "6px 0 12px" }}>{s.period?.[0] ? `${wib(s.period[0], true)} → ${wib(s.period[1], true)}` : t("periode default")}{" "}{t("· dibuat")}{" "}{sel.created_by} {wib(sel.created_at, true)}</div>
            {(sel.kind === "daily" || sel.kind === "event") && (<>
              <div className="kpis">
                <Kpi l={t("ECD rata-rata ({p0})", { p0: s.ecd_source || "—" })} v={n(s.ecd_mean)} s={t("maks {p0} ppg", { p0: n(s.ecd_max) })} color="#E8710A" />
                <Kpi l={t("Margin atas min")} v={n(s.margin_up_min)} /><Kpi l={t("Margin bawah min")} v={n(s.margin_low_min)} />
                <Kpi l={t("Durasi data")} v={`${s.data_minutes ?? 0} mnt`} s={s.model || t("tanpa model")} />
              </div>
              <div className="row small" style={{ marginBottom: 10 }}>{Object.entries(s.level_minutes || {}).map(([k, v]: any) => <span key={k} className="row" style={{ gap: 4 }}><Level v={k} />{v}{" "}{t("mnt")}</span>)}</div>
              {s.state_table ? (<>
                <h3 style={{ marginTop: 4 }}>{t("Jam per state operasi")}</h3>
                <table><thead><tr><th>{t("State")}</th><th>{t("Operasi")}</th><th>{t("Pompa")}</th><th>{t("Aturan (data surface)")}</th><th>{t("Jam")}</th><th>%</th><th>{t("Jam ECD terukur")}</th></tr></thead>
                  <tbody>{s.state_table.filter((r: any) => r.jam != null).map((r: any, i: number) => <tr key={i}><td className="mono">{r.state}</td><td>{r.operasi}</td><td>{r.pompa}</td><td className="small muted">{r.aturan}</td><td className="mono">{n(r.jam, 1)}</td><td className="mono">{n(r.persen, 1)}</td><td className="mono">{n(r.jam_ecd_terukur, 1)}</td></tr>)}</tbody></table>
                <div className="small muted" style={{ margin: "4px 0 10px" }}>{s.state_table.find((r: any) => r.jam == null)?.operasi}</div>
              </>) : <div className="row small muted" style={{ marginBottom: 10 }}>{t("State:")}{" "}{Object.entries(s.state_minutes || {}).map(([k, v]: any) => t("{p0} {p1} mnt", { p0: k, p1: v })).join(" · ")}</div>}
              <div className="small muted">{t("PPFG:")}{" "}{s.ppfg}</div>
              <h3 style={{ marginTop: 12 }}>{t("Deteksi (")}{s.detections?.length || 0})</h3>
              <table><thead><tr><th>{t("Waktu")}</th><th>{t("Level")}</th><th>{t("Indikator")}</th><th>{t("MD")}</th></tr></thead>
                <tbody>{(s.detections || []).map((d: any, i: number) => <tr key={i}><td className="mono">{wib(d.start, true)}</td><td><Level v={d.level} /></td><td>{d.label}</td><td className="mono">{d.md ? Math.round(d.md) : "—"}</td></tr>)}</tbody></table>
              {s.events?.length > 0 && (<><h3 style={{ marginTop: 12 }}>{t("Event tercatat")}</h3>
                <table><tbody>{s.events.map((e: any, i: number) => <tr key={i}><td className="mono">{wib(e.onset, true)}</td><td>{e.category}</td><td>{e.review}</td></tr>)}</tbody></table></>)}
            </>)}
            {sel.kind === "rathole" && (<>
              {s.message && <div className="note">{s.message}</div>}
              {s.rathole && <div className="small" style={{ marginBottom: 8 }}>{t("Zona rathole")}{" "}<b>{ft(s.rathole.top_md)}–{ft(s.rathole.base_md)}{" "}{t("ft")}</b> ({n(s.rathole.length_ft, 0)}{" "}{t("ft) sejak")}{" "}{wib(s.rathole.since, true)}{" "}{t("· section")}{" "}{s.well_section || "—"}{" "}{t("· model")}{" "}{s.model?.name || "—"} ({s.model?.well_role_in_model})</div>}
              {s.phase1 && <div className="kpis">
                <Kpi l={t("Fase 1 · MAE ECD ⓥ vs terukur")} v={n(s.phase1.mae, 3)} s={t("bias {p0} · n={p1}", { p0: n(s.phase1.bias, 3), p1: s.phase1.n })} />
                <Kpi l={t("Fase 1 · di kedalaman rathole")} v={n(s.phase1.in_rathole_depth?.mae, 3)} s={t("bias {p0}", { p0: n(s.phase1.in_rathole_depth?.bias, 3) })} />
                <Kpi l={t("Fase 2 · jam pompa di rathole")} v={n((s.phase2?.rathole_pump_minutes || 0) / 60, 1)} s={t("dari {p0} jam pompa", { p0: n((s.phase2?.pump_minutes || 0) / 60, 1) })} />
                <Kpi l={t("Fase 2 · ECD ⓥ median")} v={n(s.phase2?.ecd_pred_med)} s={t("maks {p0} ppg", { p0: n(s.phase2?.ecd_pred_max) })} color="#E8710A" />
              </div>}
              {s.zone_table?.length > 0 && <table><thead><tr><th>{t("Indikasi (fase 2)")}</th><th>{t("Rathole")}</th><th>{t("Atas shoe")}</th><th>{t("Bawah rathole")}</th></tr></thead>
                <tbody>{s.zone_table.map((z: any) => <tr key={z.label}><td>{z.label}</td><td className="mono"><b>{z.rathole}</b></td><td className="mono">{z.atas_shoe}</td><td className="mono">{z.bawah_rathole}</td></tr>)}</tbody></table>}
              {s.caveats?.length > 0 && <><h3 style={{ marginTop: 12 }}>{t("Catatan")}</h3><ul className="small">{s.caveats.map((c: string, i: number) => <li key={i}>{c}</li>)}</ul></>}
              <div className="small muted">{t("Detail harian fase 1 & 2 ada di file Excel dan di halaman Studi Kasus Rathole.")}</div>
            </>)}
            {sel.kind === "model" && s.model && (
              <div className="small"><b>{s.model.name}</b> ({s.model.status}{t(") · train")}{" "}{s.model.train_wells?.join(", ")}{" "}{t("· blind")}{" "}{s.model.blind_wells?.join(", ") || "—"}
                <pre className="mono small" style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(s.model.metrics?.experiments?.[s.model.metrics?.chosen]?.blind || s.model.metrics?.experiments?.[s.model.metrics?.chosen]?.lowo, null, 2)}</pre></div>
            )}
            {sel.kind === "qc" && (
              <table><thead><tr><th>{t("File")}</th><th>{t("Rec")}</th><th>{t("Baris")}</th><th>{t("Temuan")}</th></tr></thead>
                <tbody>{(s.files || []).map((x: any, i: number) => <tr key={i}><td className="small">{x.file}</td><td>{x.record} {x.basis}</td><td className="mono">{x.rows}</td><td className="small">{(x.qc || []).filter((q: any) => q.level !== "ok").map((q: any) => q.title).join("; ") || "ok"}</td></tr>)}</tbody></table>
            )}
            <div className="row" style={{ marginTop: 14 }}><h3 style={{ margin: 0 }}>{t("Narasi")}</h3><NarrBadge src={s.narrative_source} /></div>
            {s.narrative_note && <div className="note" style={{ margin: "6px 0" }}>{s.narrative_note}</div>}
            <textarea value={narr} onChange={(e) => setNarr(e.target.value)} placeholder={t("Tulis ringkasan / kesimpulan engineer…")} style={{ minHeight: 140, height: Math.min(420, 60 + 22 * (narr || "").split("\n").reduce((a: number, l: string) => a + Math.ceil((l.length || 1) / 110), 0)) }} />
            <div className="row" style={{ marginTop: 6 }}>
              <button onClick={() => saveNarr(false)} disabled={busy}>{t("Simpan narasi")}</button>
              <button onClick={() => saveNarr(true)} disabled={busy} title={aiOn ? t("Narasi baru dibuat AI dari ringkasan angka") : t("Narasi baru dibuat otomatis tanpa AI")}>{busy ? t("Memproses…") : aiOn ? t("Buat ulang narasi (AI)") : t("Buat ulang narasi otomatis")}</button>
            </div>
          </div>
        ) : <div className="card empty">{t("Pilih laporan dari arsip atau buat baru.")}</div>}
      </div>
    </>
  );
}

/** Sumber narasi laporan: AI / otomatis tanpa AI / ditulis manual. */
function NarrBadge({ src }: { src?: string }) {
  if (!src) return null;
  const m: Record<string, [string, string, string]> = {
    ai: [t("Dibantu AI"), "#F1ECFB", "#5B34B0"], template: [t("Otomatis tanpa AI"), "#EEF1F5", "#3A4552"], manual: [t("Ditulis manual"), "#E8F5EE", "#146C3E"],
  };
  const [l, bg, c] = m[src] || [src, "#EEF1F5", "#3A4552"];
  return <span className="lvl" style={{ background: bg, color: c, border: `1px solid ${c}33` }}>{l}</span>;
}
