import { useEffect, useMemo, useState, type ClipboardEvent } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { C, dateOnly, ft, n } from "../lib/fmt";
import { AX, EChart, Err, TIP, WellSelect } from "../components/ui";
import { t } from "../lib/i18n";

const ST: Record<string, string> = { approved: "#1E9E5A", draft: "#B98900", superseded: "#7A8694" };

type Iv = { md_top: string; md_bottom: string; pp: string; sfg: string; fg_min: string; fg_max: string; formation: string };
const IV_KEYS: (keyof Iv)[] = ["md_top", "md_bottom", "pp", "sfg", "fg_min", "fg_max", "formation"];
const blank = (): Iv => ({ md_top: "", md_bottom: "", pp: "", sfg: "", fg_min: "", fg_max: "", formation: "" });

/** Input PPFG tanpa file Rec 03: interval MD + nilai ppg; bisa tempel dari Excel (urutan kolom = IV_KEYS). */
function ManualPPFG({ wellId, onSaved }: { wellId: number; onSaved: () => void }) {
  const { can } = useApp();
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<Iv[]>([blank()]);
  const [approved, setApproved] = useState(false);
  const [notes, setNotes] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const set = (i: number, k: keyof Iv, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));
  const paste = (i: number, e: ClipboardEvent<HTMLInputElement>) => {
    const t = e.clipboardData.getData("text");
    if (!/[\t\n]/.test(t)) return;
    e.preventDefault();
    const lines = t.replace(/\r/g, "").split("\n").filter((l) => l.trim()).map((l) => l.split("\t"));
    const num = (x: string) => x.trim().replace(/\s/g, "").replace(/^(-?\d+),(\d+)$/, "$1.$2");
    const parsed = lines.filter((c) => !isNaN(Number(num(c[0] || "")))).map((c) => Object.fromEntries(IV_KEYS.map((k, j) => [k, k === "formation" ? (c[j] || "").trim() : num(c[j] || "")])) as Iv);
    setRows([...rows.slice(0, i), ...parsed, ...rows.slice(i + 1)]);
  };
  const save = async () => {
    setErr(null); setOk(null);
    try {
      const r = await api.post(`/wells/${wellId}/ppfg/manual`, { rows, approved, notes });
      setOk(t("Tersimpan sebagai v{p0} ({p1}, {p2} interval).", { p0: r.version, p1: r.status, p2: r.intervals })); setRows([blank()]); setNotes(""); setApproved(false); onSaved();
    } catch (e: any) { setErr(e.message); }
  };
  if (!can("ppfg_edit")) return null;
  if (!open) return <button onClick={() => setOpen(true)}>{t("+ Input PPFG manual (MD)")}</button>;
  return (
    <div className="card" style={{ marginBottom: 12 }}>
      <div className="row"><h3 style={{ margin: 0 }}>{t("Input PPFG manual (per interval MD)")}</h3><span className="sp" /><button onClick={() => setOpen(false)}>{t("Tutup")}</button></div>
      <p className="note">{t("Tanpa file Rec 03. Satu baris = satu interval MD dengan nilai konstan (ppg). Tempel langsung dari Excel ke sel mana pun, urutan kolom: MD atas, MD bawah, PP, SFG, FG min, FG max, formasi. TVD diisi otomatis dari survey bila MD ada di rentang survey. Hasilnya versi PPFG baru; versi lama tetap tersimpan.")}</p>
      <Err e={err} />
      <table>
        <thead><tr><th>{t("MD atas (ft)")}</th><th>{t("MD bawah (ft)")}</th><th>{t("PP")}</th><th>{t("SFG")}</th><th>{t("FG min")}</th><th>{t("FG max")}</th><th>{t("Formasi")}</th><th></th></tr></thead>
        <tbody>{rows.map((r, i) => (
          <tr key={i}>{IV_KEYS.map((k) => <td key={k}><input type={k === "formation" ? "text" : "number"} step="any" value={r[k]} onPaste={(e) => paste(i, e)} onChange={(e) => set(i, k, e.target.value)} style={{ width: k === "formation" ? 120 : 80 }} /></td>)}
            <td><button onClick={() => setRows(rows.length > 1 ? rows.filter((_, j) => j !== i) : [blank()])}>✕</button></td></tr>
        ))}</tbody>
      </table>
      <div className="row" style={{ marginTop: 8 }}>
        <button onClick={() => setRows([...rows, { ...blank(), md_top: rows[rows.length - 1]?.md_bottom || "" }])}>{t("+ Interval")}</button>
        <input placeholder={t("catatan (mis. sumber: Navita, PPFG rev 2)")} value={notes} onChange={(e) => setNotes(e.target.value)} style={{ width: 280 }} />
        {can("ppfg_approve") && <label className="small"><input type="checkbox" checked={approved} onChange={(e) => setApproved(e.target.checked)} />{" "}{t("Sudah approved di sumber (Navita / Geomechanics)")}</label>}
        <span className="sp" />
        <button className="pri" onClick={save}>{t("Simpan versi baru")}</button>
      </div>
      {ok && <div className="small" style={{ color: "#1E9E5A", marginTop: 6 }}>{ok}</div>}
      {!approved && <div className="small muted" style={{ marginTop: 4 }}>{t("Tanpa centang approved, versi tersimpan sebagai draft dan belum dipakai untuk margin & alert.")}</div>}
    </div>
  );
}

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
      xAxis: { type: "value", scale: true, name: "ppg", position: "top", ...AX }, yAxis: { type: "value", inverse: true, name: t("MD ft"), ...AX },
      series: [L("PP", "pp", C.pp), L("SFG", "sfg", C.sfg, true), L("FG_min", "fg_min", C.fg), L("FG_max", "fg_max", "#B42318", true)] };
  }, [rows.data]);

  return (
    <>
      <div className="top"><h1>{t("Formasi & FG")}</h1><WellSelect /><span className="sp" />
        <span className="chip">{t("Aturan MW:")}{" "}{mwRule.data?.rule === "mud_report" ? t("per laporan lumpur") : t("effective-from saat bit melewati depth")}{mwRule.data?.approved_by ? ` · ${mwRule.data.approved_by}` : t(" · default")}</span>
        {can("mw_rule") && <select value={mwRule.data?.rule || "bit_passes"} onChange={(e) => act(() => api.post("/settings/mw_rule", { rule: e.target.value }).then(mwRule.reload))}><option value="bit_passes">{t("effective-from bit")}</option><option value="mud_report">{t("laporan lumpur")}</option></select>}
      </div>
      <Err e={msg || vers.err} />
      {wellId && <div style={{ marginBottom: 12 }}><ManualPPFG wellId={wellId} onSaved={() => vers.reload()} /></div>}
      <div className="card" style={{ marginBottom: 12 }}>
        <h3>{t("Versi PPFG (Rec 03)")}</h3>
        <table>
          <thead><tr><th>{t("Versi")}</th><th>{t("Status")}</th><th>{t("TVD datum")}</th><th>{t("Efektif")}</th><th>{t("Approved")}</th><th>{t("Dibuat")}</th><th>{t("Catatan")}</th><th></th></tr></thead>
          <tbody>
            {vers.data?.length === 0 && <tr><td colSpan={8} className="muted">{t("Belum ada PPFG. Upload file Rec 03 di Data & Upload, atau isi manual per interval MD di atas.")}</td></tr>}
            {vers.data?.map((v) => (
              <tr key={v.id} className="click" onClick={() => setVid(v.id)} style={{ background: v.id === vid ? "#EAF1FA" : undefined }}>
                <td className="mono">v{v.version}</td><td style={{ color: ST[v.status] }}>{v.status}</td><td>{v.tvd_datum}</td><td>{dateOnly(v.effective_date)}</td>
                <td className="small">{v.approved_by ? `${v.approved_by} · ${dateOnly(v.approved_at)}` : "—"}</td><td className="small muted">{v.created_by}</td><td className="small">{v.notes}</td>
                <td className="row" onClick={(e) => e.stopPropagation()}>
                  {v.status === "draft" && can("ppfg_approve") && <button className="pri" onClick={() => act(() => api.post(`/ppfg/${v.id}/approve`, { tvd_datum: v.tvd_datum || "RKB" }))}>{t("Approve")}</button>}
                  {can("ppfg_edit") && <button onClick={() => act(() => api.post(`/ppfg/${v.id}/draft`))}>{t("Salin → draft")}</button>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <p className="note">{t("Hanya versi")}{" "}<b>{t("approved")}</b>{" "}{t("(Geomechanics) yang dipakai untuk margin & alert. Koreksi dilakukan di salinan draft; versi lama tetap tersimpan untuk audit.")}</p>
      </div>
      {cur && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 0.9fr) minmax(0, 1.1fr)", alignItems: "start" }}>
          <div className="card">{option && <EChart option={option} height={640} />}</div>
          <div className="card">
            <div className="row"><h3 style={{ margin: 0 }}>{t("Ringkasan v")}{cur.version}{" "}{t("per interval")}</h3><span className="sp" />
              <select value={step} onChange={(e) => setStep(Number(e.target.value))}>{[100, 250, 500, 1000].map((s) => <option key={s} value={s}>{s}{" "}{t("ft")}</option>)}</select></div>
            {cur.status === "draft" && can("ppfg_edit") && (
              <div className="row" style={{ margin: "10px 0" }}>
                <span className="small muted">{t("Koreksi draft:")}</span>
                <input style={{ width: 90 }} placeholder={t("MD dari")} value={ed.md_from} onChange={(e) => setEd({ ...ed, md_from: e.target.value })} />
                <input style={{ width: 90 }} placeholder={t("MD ke")} value={ed.md_to} onChange={(e) => setEd({ ...ed, md_to: e.target.value })} />
                <select value={ed.field} onChange={(e) => setEd({ ...ed, field: e.target.value })}>{["pp", "sfg", "fg_min", "fg_max"].map((f) => <option key={f}>{f}</option>)}</select>
                <input style={{ width: 80 }} placeholder="ppg" value={ed.value} onChange={(e) => setEd({ ...ed, value: e.target.value })} />
                <button onClick={() => act(() => api.post(`/ppfg/${cur.id}/edit`, { md_from: Number(ed.md_from), md_to: Number(ed.md_to), field: ed.field, value: ed.value === "" ? null : Number(ed.value) }))}>{t("Terapkan")}</button>
              </div>
            )}
            <table>
              <thead><tr><th>{t("MD (ft)")}</th><th>{t("TVD")}</th><th>{t("Formasi")}</th><th>{t("PP")}</th><th>{t("SFG")}</th><th>{t("FG_min")}</th><th>{t("FG_max")}</th><th>{t("max(PP,SFG)")}</th></tr></thead>
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
