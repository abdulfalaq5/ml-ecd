import { useRef, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { dateOnly, ft, n, wib , toLocalInput } from "../lib/fmt";
import { Err, Kpi, WellSelect } from "../components/ui";
import { t } from "../lib/i18n";

const SEG: Record<string, [string, string]> = {
  rec01_ecd: ["#1E9E5A", t("Rec 01 + ECD terukur")], rec01: ["#2F6FD1", t("Rec 01 saja (ECD ⓥ)")], ecd_only: ["#B98900", t("ECD tanpa Rec 01")], gap: ["#D5DCE4", "gap"], none: ["#D5DCE4", "kosong"],
};
const LVL: Record<string, string> = { ok: "#1E9E5A", warn: "#E07A10", info: "#2F6FD1", error: "#D63A40" };
const RECS: [string, string][] = [["1_time", "01 IDS Rig · time"], ["1_depth", "01 IDS Rig · depth"], ["2_time", "02 MWD/PWD · time"], ["2_depth", "02 MWD/PWD · depth"], ["3_depth", "03 PPFG"], ["4_depth", "04 Mud Weight"], ["7_depth", "07 Survey"]];

export default function DataUpload() {
  const { wellId, well, can, reloadWells } = useApp();
  const q = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/quality`) : null), [wellId]);
  const files = useFetch<any[]>(() => (wellId ? api.get(`/wells/${wellId}/files`) : null), [wellId]);
  const [busy, setBusy] = useState(false); const [res, setRes] = useState<any[] | null>(null); const [msg, setMsg] = useState<string | null>(null);
  const [mode, setMode] = useState("append");
  const [tz, setTz] = useState("WIB");
  const [ppfgOk, setPpfgOk] = useState(false);
  const [newName, setNewName] = useState("");
  const [newRole, setNewRole] = useState("shadow");
  const [edit, setEdit] = useState<any | null>(null);
  const inp = useRef<HTMLInputElement>(null);

  const upload = async (fl: FileList | null) => {
    if (!fl?.length || !wellId) return;
    const fd = new FormData();
    Array.from(fl).forEach((f) => fd.append("files", f));
    fd.append("mode", mode);
    fd.append("tz", tz);
    if (ppfgOk) fd.append("ppfg_approved", "true");
    setBusy(true); setMsg(null);
    try { const r = await api.form(`/wells/${wellId}/upload`, fd); setRes(r.results); q.reload(); files.reload(); reloadWells(); }
    catch (e: any) { setMsg(e.message); } finally { setBusy(false); if (inp.current) inp.current.value = ""; }
  };
  const scan = async () => { setBusy(true); try { const r = await api.post("/ingest/scan"); setRes(r.processed.flatMap((p: any) => p.results.map((x: any) => ({ ...x, file: `${p.well}/${x.file}` })))); await reloadWells(); q.reload(); files.reload(); } catch (e: any) { setMsg(e.message); } finally { setBusy(false); } };
  const create = async () => { try { await api.post("/wells", { name: newName, role: newRole }); setNewName(""); setNewRole("shadow"); await reloadWells(); } catch (e: any) { setMsg(e.message); } };
  const saveWell = async () => { try { await api.put(`/wells/${wellId}`, edit); setEdit(null); await reloadWells(); q.reload(); } catch (e: any) { setMsg(e.message); } };
  const signoff = async () => { try { await api.post(`/wells/${wellId}/qc/signoff`); q.reload(); } catch (e: any) { setMsg(e.message); } };
  const d = q.data;
  const tl = d?.timeline || [];
  const T0 = tl.length ? new Date(tl[0].t0).getTime() : 0, T1 = tl.length ? new Date(tl[tl.length - 1].t1).getTime() : 1;

  return (
    <>
      <div className="top"><h1>{t("Data & Upload")}</h1><WellSelect /><span className="sp" />
        {can("well_edit") && <><input placeholder={t("nama sumur baru")} value={newName} onChange={(e) => setNewName(e.target.value)} /><select value={newRole} onChange={(e) => setNewRole(e.target.value)} title={t("shadow = sumur berjalan, tidak ikut training · train = ikut training · blind = sumur uji tetap · case = studi kasus")}><option value="shadow">{t("shadow (sumur berjalan)")}</option><option value="train">{t("train")}</option><option value="blind">{t("blind")}</option><option value="case">{t("case")}</option></select><button onClick={create} disabled={!newName}>{t("+ Sumur")}</button></>}
      </div>
      <Err e={msg || q.err} />
      {well && (
        <div className="card" style={{ marginBottom: 12 }}>
          <div className="row">
            <b>{well.name}</b><span className="chip">{t("peran:")}{" "}{well.role}</span><span className="chip" title={t("Dihitung otomatis dari survey Rec 07 (maks inklinasi < 10° Vertical, ≥ 80° Horizontal, drop ≥ 15° S, selain itu J). Sumur yang masih dibor dinilai dari survey sejauh ini.")}>{t("tipe:")}{" "}{well.well_type ?? t("belum ada survey")}</span><span className="chip">{t("section")}{" "}{well.section || "—"}</span><span className="chip">{t("shoe")}{" "}{ft(well.shoe_md)}{" "}{t("ft")}</span>{well.rathole && <span className="chip" style={{ color: "#8A4B00" }}>{t("rathole")}{" "}{ft(well.rathole.top_md)}–{ft(well.rathole.base_md)}{" "}{t("ft")}</span>}
            {well.aliases?.length > 0 && <span className="muted small">{t("alias WID:")}{" "}{well.aliases.join(", ")}</span>}
            <span className="sp" />{can("well_edit") && <button onClick={() => setEdit({ name: well.name, field: well.field, section: well.section, shoe_md: well.shoe_md, role: well.role, status: well.status, notes: well.notes, rathole: well.rathole ? { ...well.rathole } : null })}>{t("Edit sumur")}</button>}
          </div>
          {edit && (
            <div className="row" style={{ marginTop: 10 }}>
              <label className="f">{t("Section")}<input value={edit.section} onChange={(e) => setEdit({ ...edit, section: e.target.value })} placeholder='8-1/2"' /></label>
              <label className="f">{t("Shoe MD (ft)")}<input type="number" value={edit.shoe_md ?? ""} onChange={(e) => setEdit({ ...edit, shoe_md: e.target.value ? Number(e.target.value) : null })} /></label>
              <label className="f">{t("Peran")}<select value={edit.role} onChange={(e) => setEdit({ ...edit, role: e.target.value })}>{["train", "blind", "case", "shadow"].map((r) => <option key={r}>{r}</option>)}</select></label>
              <label className="f">{t("Status")}<select value={edit.status} onChange={(e) => setEdit({ ...edit, status: e.target.value })}>{["active", "archived"].map((r) => <option key={r}>{r}</option>)}</select></label>
              <label className="f" style={{ flex: 1 }}>{t("Catatan")}<input value={edit.notes} onChange={(e) => setEdit({ ...edit, notes: e.target.value })} /></label>
              <div style={{ flexBasis: "100%" }} />
              <span className="small muted" style={{ flexBasis: "100%" }}>{t("Zona rathole (opsional): open hole di bawah shoe yang tidak ter-cover casing, mis. casing di-set lebih awal. Kosongkan top MD untuk menonaktifkan.")}</span>
              <label className="f">{t("Rathole top MD (ft)")}<input type="number" value={edit.rathole?.top_md ?? ""} placeholder={t("= shoe")} onChange={(e) => setEdit({ ...edit, rathole: { ...(edit.rathole || {}), top_md: e.target.value === "" ? null : Number(e.target.value) } })} /></label>
              <label className="f">{t("Rathole base MD (ft)")}<input type="number" value={edit.rathole?.base_md ?? ""} placeholder={t("TD section lama")} onChange={(e) => setEdit({ ...edit, rathole: { ...(edit.rathole || {}), base_md: e.target.value === "" ? null : Number(e.target.value) } })} /></label>
              <label className="f">{t("Rathole berlaku sejak (WIB, kosongkan bila tidak ada rathole)")}<input type="datetime-local" value={toLocalInput(edit.rathole?.since)} onChange={(e) => setEdit({ ...edit, rathole: { ...(edit.rathole || {}), since: e.target.value ? e.target.value + ":00+07:00" : null } })} /></label>
              <label className="f" style={{ flex: 1 }}>{t("Keterangan rathole")}<input value={edit.rathole?.note ?? ""} onChange={(e) => setEdit({ ...edit, rathole: { ...(edit.rathole || {}), note: e.target.value } })} placeholder={t("mis. casing di-set lebih awal, sumber DDR")} /></label>
              <div style={{ flexBasis: "100%" }} />
              <button className="pri" onClick={saveWell}>{t("Simpan")}</button><button onClick={() => setEdit(null)}>{t("Batal")}</button>
            </div>
          )}
          <SectionsCard wellId={wellId!} canEdit={can("well_edit")} onSaved={reloadWells} />
          <MudWeightCard wellId={wellId!} canEdit={can("mw_edit")} onSaved={() => q.reload()} />
          <p className="note">{t("Peran:")}{" "}<b>{t("train")}</b>{" "}{t("ikut training (LOWO) ·")}{" "}<b>{t("blind")}</b>{" "}{t("sumur uji tetap, tidak pernah ikut training ·")}{" "}<b>{t("case")}</b>{" "}{t("studi kasus (mis. PDSI 53.2) ·")}{" "}<b>{t("shadow")}</b>{" "}{t("sumur berjalan, alert UNAVAILABLE bila data > 10 mnt.")}</p>
        </div>
      )}
      {wellId && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", alignItems: "start" }}>
          <div className="card">
            <h3>{t("Upload file")}</h3>
            <div className="row">
              <input ref={inp} type="file" multiple accept=".las,.LAS,.csv,.CSV,.zip,.txt,.xlsx,.xlsm,.xls" onChange={(e) => upload(e.target.files)} disabled={!can("upload") || busy} />
              <select value={mode} onChange={(e) => setMode(e.target.value)}><option value="append">{t("append (lewati duplikat)")}</option><option value="replace">{t("replace (timpa timestamp sama)")}</option></select>
              <select value={tz} onChange={(e) => setTz(e.target.value)} title={t("Zona waktu kolom waktu di file bila tidak tertulis offset-nya")}><option value="WIB">{t("waktu file: WIB")}</option><option value="UTC">{t("waktu file: UTC")}</option></select>
              {can("ppfg_approve") && <label className="small" title={t("PPFG (Rec 03) di file ini sudah approved oleh Navita / Geomechanics: langsung dipakai untuk margin & alert, versi approved lama jadi superseded")}><input type="checkbox" checked={ppfgOk} onChange={(e) => setPpfgOk(e.target.checked)} />{" "}{t("PPFG sudah approved di sumber")}</label>}
              {can("upload") && <button onClick={scan} disabled={busy}>{t("Scan folder inbox")}</button>}
              {busy && <span className="muted small">{t("memproses…")}</span>}
            </div>
            <p className="note">{t("Format: Navita LAS / CSV (export_las_record_0N…), LAS rig,")}{" "}<b>{t("time-based SLB / Halliburton")}</b>{" "}{t("(LAS / CSV / Excel),")}{" "}<b>{t("survey")}</b>{" "}{t("(CSV / Excel: MD, Inc, Azi; TVD & DLS dihitung bila tidak ada),")}{" "}<b>{t("tabel MW")}</b>{" "}{t("(kedalaman + MW), atau .zip berisi file-file itu. Jenis data dikenali dari nama file / kolom; satuan metrik (m, kN, bar, L/min, SG) dikonversi bila satuannya tertulis. Navita, SLB, dan Halliburton =")}{" "}<b>{t("WIB (UTC+7)")}</b>{t(", jadi biarkan default. Pilih")}{" "}<b>{t("UTC")}</b>{" "}{t("hanya bila suatu file jelas ditulis dalam UTC (waktu yang membawa Z / +07:00 selalu dibaca sesuai offset). Folder inbox:")}{" "}<span className="mono">{t("data/inbox/<nama sumur>/")}</span>{" "}{t("di-scan otomatis tiap 60 dtk.")}</p>
            {res && (
              <table style={{ marginTop: 8 }}>
                <thead><tr><th>{t("File")}</th><th>{t("Status")}</th><th>{t("Rec")}</th><th>{t("Basis")}</th><th>{t("Baris")}</th><th>{t("QC")}</th></tr></thead>
                <tbody>{res.map((r, i) => (
                  <tr key={i}><td className="small">{r.file}</td><td style={{ color: r.status === "ok" ? "#1E9E5A" : r.status === "error" ? "#D63A40" : "#5B6775" }}>{r.status}</td>
                    <td className="mono">{r.record ? String(r.record).padStart(2, "0") : ""}</td><td>{r.basis}</td><td className="mono">{r.rows?.toLocaleString()}</td>
                    <td className="small">{r.message || (r.qc || []).filter((x: any) => x.level === "error" || x.level === "warn").map((x: any, j: number) => (
                      <div key={j}><b style={{ color: LVL[x.level] }}>{x.title}</b>: <span className="muted">{x.text}</span></div>))}
                      {!r.message && (r.qc || []).filter((x: any) => x.level === "info").length > 0 && (
                        <details><summary className="muted">{t("detail (")}{(r.qc || []).filter((x: any) => x.level === "info").length})</summary>
                          {(r.qc || []).filter((x: any) => x.level === "info").map((x: any, j: number) => <div key={j}><b>{x.title}</b>: <span className="muted">{x.text}</span></div>)}</details>)}</td></tr>
                ))}</tbody>
              </table>
            )}
          </div>
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>{t("Kelengkapan data")}</h3><span className="sp" />
              {d?.signoff ? <span className="chip" style={{ color: "#1E9E5A" }}>{t("QC sign-off")}{" "}{d.signoff.by} · {dateOnly(d.signoff.at)}</span> : can("qc_signoff") && <button onClick={signoff}>{t("QC sign-off")}</button>}
            </div>
            <div className="kpis" style={{ marginTop: 10 }}>
              <Kpi l={t("Ketersediaan label ECD")} v={d?.target_availability != null ? `${Math.round(d.target_availability * 100)}%` : "—"} s={t("jam pumps-on yang punya ECD terukur")} />
              <Kpi l={t("PPFG versi")} v={d?.ppfg_versions?.length ?? 0} s={d?.ppfg_versions?.map((v: any) => t("v{p0} {p1}", { p0: v.version, p1: v.status })).join(", ")} />
              <Kpi l={t("MW / Survey")} v={`${d?.mud_weight_rows ?? 0} / ${d?.survey_rows ?? 0}`} s={t("baris MW (file / manual) / stasiun survey")} color={d && !d.mud_weight_rows ? "#D63A40" : undefined} />
            </div>
            <table>
              <thead><tr><th>{t("Record")}</th><th>{t("File")}</th><th>{t("Baris")}</th><th>{t("Rentang")}</th></tr></thead>
              <tbody>{RECS.map(([k, l]) => { const c = d?.completeness?.[k]; return (
                <tr key={k}><td>{l}</td><td className="mono">{c?.files ?? "—"}</td><td className="mono">{c?.rows?.toLocaleString() ?? "—"}</td>
                  <td className="small">{c ? (c.t0 ? `${wib(c.t0, true)} → ${wib(c.t1, true)}` : t("{p0} → {p1} ft", { p0: ft(c.d0), p1: ft(c.d1) })) : <span style={{ color: "#E07A10" }}>{t("belum ada")}</span>}</td></tr>); })}</tbody>
            </table>
          </div>
          <div className="card" style={{ gridColumn: "1 / -1" }}>
            <h3>{t("Timeline cakupan (per jam)")}</h3>
            <div style={{ display: "flex", height: 22, borderRadius: 4, overflow: "hidden", background: "#F4F6F9" }}>
              {tl.map((s: any, i: number) => { const w = ((new Date(s.t1).getTime() - new Date(s.t0).getTime()) / (T1 - T0)) * 100; return <div key={i} title={`${SEG[s.kind]?.[1]} · ${wib(s.t0, true)} → ${wib(s.t1, true)}`} style={{ width: `${w}%`, background: SEG[s.kind]?.[0] }} />; })}
            </div>
            <div className="row small muted" style={{ marginTop: 6 }}>{tl.length ? <><span>{wib(tl[0].t0, true)}</span><span className="sp" /><span>{wib(tl[tl.length - 1].t1, true)}</span></> : t("belum ada data time-based")}</div>
            <div className="row small" style={{ marginTop: 6 }}>{Object.entries(SEG).slice(0, 4).map(([k, [c, l]]) => <span key={k} className="row" style={{ gap: 4 }}><i style={{ width: 12, height: 12, background: c, display: "inline-block", borderRadius: 2 }} />{l}</span>)}</div>
          </div>
          <div className="card">
            <h3>{t("Temuan QC")}</h3>
            {(d?.qc || []).filter((x: any) => x.level !== "ok").length === 0 && <div className="muted small">{t("Tidak ada temuan.")}</div>}
            {(d?.qc || []).filter((x: any) => x.level !== "ok").map((x: any, i: number) => (
              <div key={i} style={{ borderTop: "1px solid #E3E8EE", padding: "6px 0" }} className="small">
                <b style={{ color: LVL[x.level] }}>{x.level.toUpperCase()}</b> · {x.title} <span className="muted">— {x.file}</span><div className="muted">{x.text}</div>
              </div>
            ))}
          </div>
          <div className="card">
            <h3>{t("File ter-ingest")}</h3>
            <table>
              <thead><tr><th>{t("File")}</th><th>{t("Rec")}</th><th>{t("Format")}</th><th>{t("Baris")}</th><th>{t("Oleh")}</th></tr></thead>
              <tbody>{files.data?.map((f) => (
                <tr key={f.id}><td className="small" title={f.unmapped?.length ? t("tag tak dikenal: {p0}", { p0: f.unmapped.join(", ") }) : ""}>{f.filename}</td><td className="mono">{String(f.record).padStart(2, "0")} {f.basis}</td>
                  <td className="small muted">{f.fmt}</td><td className="mono">{f.rows.toLocaleString()}</td><td className="small muted">{f.uploaded_by}</td></tr>
              ))}</tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}

type Sec = { from_md: string; hole_size: string; shoe_md: string; casing_id: string; preset: string; pv: string; yp: string; pwd_offset_ft: string; since: string; note: string };
const SEC_KEYS: (keyof Sec)[] = ["from_md", "hole_size", "shoe_md", "casing_id", "preset", "pv", "yp", "pwd_offset_ft", "since", "note"];
const TEXT_KEYS: (keyof Sec)[] = ["preset", "note", "since"];
const toSec = (r: any): Sec => Object.fromEntries(SEC_KEYS.map((k) => [k, r[k] == null ? "" : k === "since" ? toLocalInput(r[k]) : String(r[k])])) as Sec;
const HOLES = ["26", "17.5", "12.25", "8.5", "6.125"];

/** Data section depth-based (seperti MW Rec 04): dipakai Ramalan ECD (hidraulika, cutting) dan nanti estimasi bending. */
function SectionsCard({ wellId, canEdit, onSaved }: { wellId: number; canEdit: boolean; onSaved: () => void }) {
  const q = useFetch<any>(() => api.get(`/wells/${wellId}/sections`), [wellId]);
  const [rows, setRows] = useState<Sec[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const cur: Sec[] = rows ?? (q.data?.sections || []).map(toSec);
  const editing = rows !== null;
  const set = (i: number, k: keyof Sec, v: string) => setRows(cur.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const save = async () => {
    setErr(null);
    const body = cur.filter((r) => r.from_md !== "" || r.hole_size !== "").map((r) => Object.fromEntries(SEC_KEYS.map((k) => [k, k === "since" ? (r[k] ? r[k] + ":00+07:00" : null) : TEXT_KEYS.includes(k) ? r[k] || null : r[k] === "" ? null : Number(r[k])])));
    try { await api.put(`/wells/${wellId}/sections`, { sections: body }); setRows(null); setOk(true); q.reload(); onSaved(); setTimeout(() => setOk(false), 2500); }
    catch (e: any) { setErr(e.message); }
  };
  const presets: any[] = q.data?.presets || [];
  const cid = q.data?.casing_id_default || {};
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid #E3E8EE", paddingTop: 10 }}>
      <div className="row">
        <b className="small">{t("Section & lubang")}</b>
        <span className="small muted">{t("berlaku sejak hole depth tercapai (seperti MW Rec 04) · dipakai Ramalan ECD (hidraulika) dan nanti estimasi bending")}</span>
        <span className="sp" />
        {ok && <span className="small" style={{ color: "#1E9E5A" }}>{t("tersimpan")}</span>}
        {canEdit && !editing && <button onClick={() => setRows(cur.length ? cur : [toSec({ from_md: 0 })])}>{cur.length ? t("Ubah section") : t("+ Isi section")}</button>}
      </div>
      <Err e={err || q.err} />
      {cur.length === 0 && !editing ? <div className="small muted" style={{ marginTop: 6 }}>{t("Belum ada data section. Tanpa ini, Ramalan ECD memakai ukuran lubang 8-1/2\" dan respons flow sementara.")}</div> : (
        <div style={{ overflowX: "auto", marginTop: 6 }}>
          <table className="plan">
            <thead><tr><th>{t("Mulai hole depth (ft)")}</th><th>{t("Lubang (in)")}</th><th title={t("Casing yang sudah terpasang di atas section ini (dilewati string). Casing yang di-set di akhir section diisi di baris section berikutnya. Section pertama: kosong / shoe conductor.")}>{t("Shoe casing MD (ft)")} ⓘ</th><th>{t("ID casing (in)")}</th><th>{t("String (katalog)")}</th><th>{t("PV (cP)")}</th><th>{t("YP (lbf/100ft²)")}</th><th title={t("Jarak sensor PWD/ECD di belakang bit (dari tally BHA: motor + MWD). Kosong = default 40 ft (pita 40–45 ft)")}>{t("Offset sensor PWD (ft)")}</th><th title={t("Opsional: bila casing di-set lebih dangkal dari TD section sebelumnya (rathole), baris berlaku sejak waktu ini, bukan dari kedalaman")}>{t("Berlaku sejak (WIB, opsional)")}</th><th>{t("Sumber / catatan")}</th>{editing && <th />}</tr></thead>
            <tbody>
              {cur.map((r, i) => editing ? (
                <tr key={i}>
                  <td><input type="number" value={r.from_md} onChange={(e) => set(i, "from_md", e.target.value)} style={{ width: 90 }} /></td>
                  <td><input list="holes" value={r.hole_size} onChange={(e) => set(i, "hole_size", e.target.value)} style={{ width: 70 }} /></td>
                  <td><input type="number" value={r.shoe_md} onChange={(e) => set(i, "shoe_md", e.target.value)} style={{ width: 90 }} /></td>
                  <td><input type="number" step="any" value={r.casing_id} placeholder={cid[r.hole_size] ? t("otomatis {p0}", { p0: cid[r.hole_size] }) : "otomatis"} onChange={(e) => set(i, "casing_id", e.target.value)} style={{ width: 100 }} /></td>
                  <td><select value={r.preset} onChange={(e) => set(i, "preset", e.target.value)}><option value="">{t("otomatis per ukuran lubang")}</option>{presets.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></td>
                  <td><input type="number" step="any" value={r.pv} onChange={(e) => set(i, "pv", e.target.value)} style={{ width: 60 }} /></td>
                  <td><input type="number" step="any" value={r.yp} onChange={(e) => set(i, "yp", e.target.value)} style={{ width: 60 }} /></td>
                  <td><input type="number" step="any" value={r.pwd_offset_ft} placeholder="40" onChange={(e) => set(i, "pwd_offset_ft", e.target.value)} style={{ width: 70 }} /></td>
                  <td><input type="datetime-local" value={r.since} onChange={(e) => set(i, "since", e.target.value)} /></td>
                  <td><input value={r.note} onChange={(e) => set(i, "note", e.target.value)} placeholder={t("mis. DDR / mud report")} /></td>
                  <td><button className="danger" onClick={() => setRows(cur.filter((_, j) => j !== i))}>×</button></td>
                </tr>
              ) : (
                <tr key={i}>
                  <td className="mono">{ft(Number(r.from_md))}</td><td>{r.hole_size}"</td><td className="mono">{r.shoe_md ? ft(Number(r.shoe_md)) : "—"}</td>
                  <td>{r.casing_id || <span className="muted">{t("otomatis")}</span>}</td><td>{presets.find((p) => p.id === r.preset)?.name || <span className="muted">{t("otomatis")}</span>}</td>
                  <td>{r.pv || "—"}</td><td>{r.yp || "—"}</td><td>{r.pwd_offset_ft || <span className="muted">40</span>}</td><td className="small">{r.since ? r.since.replace("T", " ") : <span className="muted">{t("dari kedalaman")}</span>}</td><td className="muted small">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <datalist id="holes">{HOLES.map((h) => <option key={h} value={h} />)}</datalist>
        </div>
      )}
      {editing && (
        <div className="row" style={{ marginTop: 8 }}>
          <button onClick={() => setRows([...cur, toSec({})])}>{t("+ Baris")}</button>
          <span className="sp" />
          <button className="pri" onClick={save}>{t("Simpan section")}</button><button onClick={() => { setRows(null); setErr(null); }}>{t("Batal")}</button>
        </div>
      )}
    </div>
  );
}


type MWR = { md: string; mw: string; remark: string };
/** Tabel MW manual (DDR / mud report) untuk sumur tanpa file Rec 04 Navita. MW berlaku sejak hole depth tercapai. */
function MudWeightCard({ wellId, canEdit, onSaved }: { wellId: number; canEdit: boolean; onSaved: () => void }) {
  const q = useFetch<any>(() => api.get(`/wells/${wellId}/mud-weight`), [wellId]);
  const [rows, setRows] = useState<MWR[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState(false);
  const cur: MWR[] = rows ?? (q.data?.rows || []).map((r: any) => ({ md: String(r.md), mw: String(r.mw), remark: r.remark || "" }));
  const editing = rows !== null;
  const set = (i: number, k: keyof MWR, v: string) => setRows(cur.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const save = async () => {
    setErr(null);
    const body = cur.filter((r) => r.md !== "" || r.mw !== "").map((r) => ({ md: Number(r.md), mw: Number(r.mw), remark: r.remark || null }));
    if (body.some((r) => !isFinite(r.md) || !isFinite(r.mw))) { setErr(t("Kedalaman dan MW harus angka")); return; }
    try { await api.put(`/wells/${wellId}/mud-weight`, { rows: body }); setRows(null); setOk(true); q.reload(); onSaved(); setTimeout(() => setOk(false), 2500); }
    catch (e: any) { setErr(e.message); }
  };
  const src: string | null = q.data?.source ?? null;
  const dens: any[] = q.data?.stream_density || [];
  return (
    <div style={{ marginTop: 12, borderTop: "1px solid #E3E8EE", paddingTop: 10 }}>
      <div className="row">
        <b className="small">{t("Mud weight")}</b>
        <span className="small muted">{t("berlaku sejak hole depth tercapai · wajib untuk ECD ⓥ · sumber:")}{" "}{src || t("belum ada")}</span>
        <span className="sp" />
        {ok && <span className="small" style={{ color: "#1E9E5A" }}>{t("tersimpan")}</span>}
        {canEdit && !editing && <button onClick={() => setRows(cur.length ? cur : [{ md: "0", mw: "", remark: "" }])}>{cur.length ? t("Ubah MW") : t("+ Isi MW manual")}</button>}
      </div>
      <Err e={err || q.err} />
      {cur.length === 0 && !editing ? <div className="small" style={{ marginTop: 6, color: "#D63A40" }}>{t("Belum ada MW: ECD ⓥ, margin, dan deteksi yang memakai MW tidak dihitung untuk sumur ini. Isi dari DDR / mud report, atau upload file MW.")}</div> : (
        <div style={{ overflowX: "auto", marginTop: 6 }}>
          <table className="plan">
            <thead><tr><th>{t("Mulai hole depth (ft MD)")}</th><th>{t("MW (ppg)")}</th><th>{t("Sumber / catatan")}</th>{editing && <th />}</tr></thead>
            <tbody>
              {cur.map((r, i) => editing ? (
                <tr key={i}>
                  <td><input type="number" value={r.md} onChange={(e) => set(i, "md", e.target.value)} style={{ width: 100 }} /></td>
                  <td><input type="number" step="0.01" value={r.mw} onChange={(e) => set(i, "mw", e.target.value)} style={{ width: 80 }} /></td>
                  <td><input value={r.remark} onChange={(e) => set(i, "remark", e.target.value)} placeholder={t("mis. DDR 12 Nov / mud report")} style={{ width: 260 }} /></td>
                  <td><button className="danger" onClick={() => setRows(cur.filter((_, j) => j !== i))}>×</button></td>
                </tr>
              ) : (
                <tr key={i}><td className="mono">{ft(Number(r.md))}</td><td className="mono">{n(Number(r.mw))}</td><td className="muted small">{r.remark}</td></tr>
              ))}
            </tbody>
          </table>
          {editing && (
            <div className="row" style={{ marginTop: 6 }}>
              <button onClick={() => setRows([...cur, { md: "", mw: "", remark: "" }])}>{t("+ Baris")}</button>
              <button className="pri" onClick={save}>{t("Simpan MW")}</button><button onClick={() => { setRows(null); setErr(null); }}>{t("Batal")}</button>
              <span className="small muted">{t("Menyimpan mengganti seluruh tabel MW sumur ini. Upload file MW / Rec 04 berikutnya juga akan menggantinya.")}</span>
            </div>
          )}
        </div>
      )}
      {dens.length > 0 && <div className="small muted" style={{ marginTop: 6 }}>{t("Pembanding mud density in dari data streaming (median per 500 ft):")}{" "}{dens.map((x) => t("{p0} ft {p1}", { p0: ft(x.md_from), p1: n(x.mw) })).join(" · ")}{" "}{t("ppg")}</div>}
      <MWChangesCard wellId={wellId} canEdit={canEdit} changes={q.data?.changes || []} onSaved={() => { q.reload(); onSaved(); }} />
    </div>
  );
}

type MWC = { ts: string; mw: string; remark: string };
/** Perubahan MW berbasis waktu (jam dari DDR / mud report): displacement di shoe, lumpur baru, build-up MW. */
function MWChangesCard({ wellId, canEdit, changes, onSaved }: { wellId: number; canEdit: boolean; changes: any[]; onSaved: () => void }) {
  const [rows, setRows] = useState<MWC[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const cur: MWC[] = rows ?? changes.map((r: any) => ({ ts: toLocalInput(r.ts), mw: String(r.mw), remark: r.remark || "" }));
  const editing = rows !== null;
  const set = (i: number, k: keyof MWC, v: string) => setRows(cur.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const save = async () => {
    setErr(null);
    const body = cur.filter((r) => r.ts !== "" || r.mw !== "").map((r) => ({ ts: r.ts, mw: Number(r.mw), remark: r.remark || null }));
    if (body.some((r) => !r.ts || !isFinite(r.mw))) { setErr(t("Waktu dan MW wajib diisi")); return; }
    try { await api.put(`/wells/${wellId}/mud-weight/changes`, { rows: body }); setRows(null); onSaved(); }
    catch (e: any) { setErr(e.message); }
  };
  if (!editing && cur.length === 0 && !canEdit) return null;
  return (
    <div style={{ marginTop: 10 }}>
      <div className="row">
        <b className="small">{t("Perubahan MW berbasis waktu")}</b>
        <span className="small muted">{t("berlaku sejak jam (WIB) sampai MW per kedalaman berubah lagi · untuk ganti lumpur di shoe / build-up MW dari DDR")}</span>
        <span className="sp" />
        {canEdit && !editing && <button onClick={() => setRows(cur.length ? cur : [{ ts: "", mw: "", remark: "" }])}>{cur.length ? t("Ubah") : t("+ Tambah")}</button>}
      </div>
      <Err e={err} />
      {(cur.length > 0 || editing) && (
        <table className="plan" style={{ marginTop: 6 }}>
          <thead><tr><th>{t("Mulai (WIB)")}</th><th>{t("MW (ppg)")}</th><th>{t("Sumber / catatan")}</th>{editing && <th />}</tr></thead>
          <tbody>
            {cur.map((r, i) => editing ? (
              <tr key={i}>
                <td><input type="datetime-local" value={r.ts} onChange={(e) => set(i, "ts", e.target.value)} /></td>
                <td><input type="number" step="0.01" value={r.mw} onChange={(e) => set(i, "mw", e.target.value)} style={{ width: 80 }} /></td>
                <td><input value={r.remark} onChange={(e) => set(i, "remark", e.target.value)} placeholder={t("mis. DDR 18 Nov: mixing 9,5 → 9,7")} style={{ width: 260 }} /></td>
                <td><button className="danger" onClick={() => setRows(cur.filter((_, j) => j !== i))}>×</button></td>
              </tr>
            ) : (
              <tr key={i}><td className="mono">{wib(changes[i]?.ts, true)}</td><td className="mono">{n(Number(r.mw))}</td><td className="muted small">{r.remark}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {editing && (
        <div className="row" style={{ marginTop: 6 }}>
          <button onClick={() => setRows([...cur, { ts: "", mw: "", remark: "" }])}>{t("+ Baris")}</button>
          <button className="pri" onClick={save}>{t("Simpan")}</button><button onClick={() => { setRows(null); setErr(null); }}>{t("Batal")}</button>
          <span className="small muted">{t("Tidak terhapus oleh upload ulang Rec 04.")}</span>
        </div>
      )}
    </div>
  );
}
