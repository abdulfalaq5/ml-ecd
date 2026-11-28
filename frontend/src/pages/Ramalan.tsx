import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { C, ft, LEVEL_COLOR, n, toLocalInput, wib } from "../lib/fmt";
import { AX, EChart, Err, Kpi, Level, TIP, WellSelect } from "../components/ui";
import { t } from "../lib/i18n";

type Row = { op: string; hours: string; to_md: string; flow: string; rpm: string; wob: string; rop: string; mw: string };
const KEYS = ["hours", "to_md", "flow", "rpm", "wob", "rop", "mw"] as const;
const CARRY = ["flow", "rpm", "wob", "mw"] as const;          // kosong = nilai segmen sebelumnya
const OPS: Record<string, string> = { drill: "Bor", circ: "Sirkulasi", static: t("Pompa mati / diam") };
const blank = (op = "drill"): Row => ({ op, hours: "", to_md: "", flow: "", rpm: "", wob: "", rop: "", mw: "" });
const toRow = (s: any): Row => ({ ...blank(s.op), ...Object.fromEntries(KEYS.map((k) => [k, s[k] == null ? "" : String(s[k])])) });
const num = (v: string) => (v.trim() === "" ? undefined : Number(v));
/** WIB datetime-local -> ISO */
const fromLocal = (v: string) => (v ? new Date(v + ":00+07:00").toISOString() : undefined);

export default function Ramalan() {
  const { wellId } = useApp();
  const [tCut, setTCut] = useState("");
  const [hours, setHours] = useState(6);
  const [init, setInit] = useState<any>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [conn, setConn] = useState(true);
  const [everyFt, setEveryFt] = useState("");
  const [offMin, setOffMin] = useState("");
  const [hole, setHole] = useState("");
  const [ppfgV, setPpfgV] = useState("");
  const [pv, setPv] = useState(""); const [yp, setYp] = useState("");
  const [casingId, setCasingId] = useState(""); const [base, setBase] = useState("hyd");
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState("");

  const load = async (cut?: string) => {
    if (!wellId) return;
    setBusy(t("menyiapkan rencana…")); setErr(null); setRes(null);
    try {
      const d = await api.get(`/wells/${wellId}/forecast/init`, { t_cut: cut, hours });
      setInit(d); setTCut(toLocalInput(d.t_cut)); setRows(d.plan.map(toRow));
      setEveryFt(String(d.connections.every_ft)); setOffMin(String(d.connections.off_min));
      const sc = d.section || {};
      setHole(sc.hole_size != null ? String(sc.hole_size) : (h: string) => h || String(d.cfg.hole_size));
      setPv(sc.pv != null ? String(sc.pv) : ""); setYp(sc.yp != null ? String(sc.yp) : "");
      setCasingId(sc.casing_id != null ? String(sc.casing_id) : "");
      setPpfgV((v) => v || (d.ppfg ? String(d.ppfg.id) : ""));
    } catch (e: any) { setErr(e.message); setInit(null); setRows([]); }
    setBusy("");
  };
  useEffect(() => { setInit(null); setRes(null); setRows([]); setTCut(""); setHole(""); setPpfgV(""); if (wellId) load(); }, [wellId]); // eslint-disable-line

  /** nilai efektif per segmen (kosong = bawa dari segmen sebelumnya, awal = acuan) */
  const eff = useMemo(() => {
    const ref = init?.reference || {};
    let cur: Record<string, number> = { flow: ref.flow, rpm: ref.rpm, wob: ref.wob, mw: ref.mw };
    return rows.map((r) => { cur = { ...cur }; CARRY.forEach((k) => { const v = num(r[k]); if (v !== undefined) cur[k] = v; }); return cur; });
  }, [rows, init]);

  const scale = (k: (typeof CARRY)[number], f: number, add = 0) =>
    setRows(rows.map((r, i) => (r.op === "static" && k !== "mw" ? r : { ...r, [k]: String(Math.round((eff[i][k] * f + add) * (k === "mw" ? 100 : 10)) / (k === "mw" ? 100 : 10)) })));
  const set = (i: number, k: keyof Row, v: string) => setRows(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)));

  const run = async (reveal: boolean) => {
    if (!wellId || !init) return;
    setBusy(reveal ? t("membuka data asli…") : t("menghitung ramalan…")); setErr(null);
    try {
      const plan = rows.map((r) => ({ op: r.op, ...Object.fromEntries(KEYS.map((k) => [k, num(r[k])]).filter(([, v]) => v !== undefined)) }));
      const d = await api.post(`/wells/${wellId}/forecast`, {
        t_cut: init.t_cut, plan, connections: conn, reveal,
        every_ft: num(everyFt), off_min: num(offMin), hole_size: num(hole), ppfg_version: ppfgV ? Number(ppfgV) : undefined,
        pv: num(pv), yp: num(yp), casing_id: num(casingId), base, preset: init.section?.preset || undefined,
      });
      setRes(d);
    } catch (e: any) { setErr(e.message); }
    setBusy("");
  };

  const option = useMemo(() => res && chart(res), [res]);
  const s = res?.summary;
  const m = res?.metrics;
  const totalH = rows.reduce((a, r) => a + (num(r.hours) || 0), 0);

  return (
    <>
      <div className="top"><h1>{t("Ramalan ECD")}</h1><WellSelect /><span className="sp" />{init?.model && <span className="chip">{t("Model:")}{" "}{init.model.name} ({init.model.status})</span>}</div>
      <Err e={err} />
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row">
          <label className="f">{t("Jam mulai ramalan (WIB)")}<input type="datetime-local" value={tCut} onChange={(e) => setTCut(e.target.value)} /></label>
          <label className="f">{t("Durasi rencana awal")}
            <select value={hours} onChange={(e) => setHours(Number(e.target.value))}>{[2, 4, 6, 12, 24].map((h) => <option key={h} value={h}>{h}{" "}{t("jam")}</option>)}</select>
          </label>
          <button onClick={() => load(fromLocal(tCut))} disabled={!!busy}>{t("Isi rencana dari jam ini")}</button>
          {init && <button onClick={() => load(undefined)} disabled={!!busy}>{t("Data terakhir")}</button>}
          {busy && <span className="muted small">{busy}</span>}
        </div>
        {init && <div className="small muted" style={{ marginTop: 6 }}>
          {t("Data sumur:")}{" "}{wib(init.data_start, true)} → {wib(init.data_end, true)}{" "}{t("· rencana awal dari")}{" "}{init.plan_source}
          {init.has_actual ? <> · <b style={{ color: C.ecd }}>{t("mode uji coba")}</b>{t(": data sesudah jam mulai disembunyikan sampai klik \"Buka data asli\"")}</> : t(" · ramalan ke depan (belum ada data sesudah jam mulai)")}
        </div>}
        <p className="note">{t("Ramalan dihitung dari")}{" "}<b>{t("rencana operasi")}</b>{" "}{t("(seperti roadmap T&D), bukan dari tren data. Kosongkan sel flow/RPM/WOB/MW untuk memakai nilai segmen sebelumnya. Bor: isi target MD + jam (ROP dihitung, termasuk waktu sambung pipa), atau ROP, atau WOB saja (ROP ikut WOB).")}</p>
      </div>

      {init && (
        <div className="card" style={{ marginBottom: 12 }}>
          <h3>{t("Rencana operasi")}{" "}<span className="muted small">{t("· total")}{" "}{n(totalH, 1)}{" "}{t("jam · acuan 1 jam sebelum jam mulai: flow")}{" "}{n(init.reference.flow, 0)}{" "}{t("gpm, RPM")}{" "}{n(init.reference.rpm, 0)}{t(", WOB")}{" "}{n(init.reference.wob, 1)}{" "}{t("klb, ROP")}{" "}{n(init.reference.rop, 0)}{" "}{t("ft/jam, MW")}{" "}{n(init.reference.mw)}{" "}{t("ppg, hole depth")}{" "}{ft(init.reference.hole_md)}{" "}{t("ft")}</span></h3>
          <div style={{ overflowX: "auto" }}>
            <table className="plan">
              <thead><tr><th>#</th><th>{t("Operasi")}</th><th>{t("Jam")}</th><th>{t("Target MD (ft)")}</th><th>{t("Flow (gpm)")}</th><th>{t("RPM")}</th><th>{t("WOB (klb)")}</th><th>{t("ROP (ft/jam)")}</th><th>{t("MW (ppg)")}</th><th /></tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    <td className="muted">{i + 1}</td>
                    <td><select value={r.op} onChange={(e) => set(i, "op", e.target.value)}>{Object.entries(OPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></td>
                    {KEYS.map((k) => {
                      const off = (r.op !== "drill" && (k === "to_md" || k === "rop" || k === "wob")) || (r.op === "static" && (k === "flow" || k === "rpm"));
                      const ph = (CARRY as readonly string[]).includes(k) && eff[i] ? n(eff[i][k], k === "mw" ? 2 : k === "wob" ? 1 : 0) : "";
                      return <td key={k}><input type="number" step="any" value={off ? "" : r[k]} disabled={off} placeholder={off ? "—" : ph} onChange={(e) => set(i, k, e.target.value)} style={{ width: k === "to_md" ? 90 : 72 }} /></td>;
                    })}
                    <td><button className="danger" title={t("Hapus segmen")} onClick={() => setRows(rows.filter((_, j) => j !== i))} disabled={rows.length === 1}>×</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="row" style={{ marginTop: 8 }}>
            <button onClick={() => setRows([...rows, blank(rows[rows.length - 1]?.op === "static" ? "drill" : rows[rows.length - 1]?.op)])}>{t("+ Segmen")}</button>
            <span className="sp" />
            <span className="small muted">{t("Coba-coba semua segmen:")}</span>
            <span className="segs">
              <button className="seg" onClick={() => scale("flow", 0.9)}>{t("Flow −10%")}</button><button className="seg" onClick={() => scale("flow", 1.1)}>{t("Flow +10%")}</button>
            </span>
            <span className="segs">
              <button className="seg" onClick={() => scale("rpm", 0.8)}>{t("RPM −20%")}</button><button className="seg" onClick={() => scale("rpm", 1.2)}>{t("RPM +20%")}</button>
            </span>
            <span className="segs">
              <button className="seg" onClick={() => scale("wob", 0.8)}>{t("WOB −20%")}</button><button className="seg" onClick={() => scale("wob", 1.2)}>{t("WOB +20%")}</button>
            </span>
            <span className="segs">
              <button className="seg" onClick={() => scale("mw", 1, -0.1)}>{t("MW −0.1")}</button><button className="seg" onClick={() => scale("mw", 1, 0.1)}>{t("MW +0.1")}</button>
            </span>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <label className="row small"><input type="checkbox" checked={conn} onChange={(e) => setConn(e.target.checked)} />{" "}{t("Dengan sambung pipa")}</label>
            <label className="f">{t("tiap (ft)")}<input type="number" value={everyFt} disabled={!conn} onChange={(e) => setEveryFt(e.target.value)} style={{ width: 70 }} /></label>
            <label className="f">{t("pompa mati (mnt)")}<input type="number" value={offMin} disabled={!conn} onChange={(e) => setOffMin(e.target.value)} style={{ width: 70 }} /></label>
            <span className="small muted">{init.connections_from_data ? t("dari data sumur ({p0} sambungan)", { p0: init.connections.n }) : t("default (data sambungan kurang)")}</span>
            <label className="f">{t("Ukuran lubang (in)")}<input type="number" step="any" value={hole} onChange={(e) => setHole(e.target.value)} style={{ width: 70 }} /></label>
            <span className="sp" />
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <span className="small" style={{ fontWeight: 600 }}>{t("Hidraulika annulus")}</span>
            <span className="chip" title={t("Diisi di Data & Upload → Section & lubang")}>{init.section ? t("section {p0}\" sejak {p1} ft{p2}", { p0: init.section.hole_size, p1: ft(init.section.from_md), p2: init.section.preset ? "" : "" }) : init.n_sections ? t("di luar data section") : t("belum ada data section")}</span>
            <label className="f">{t("PV (cP)")}<input type="number" step="any" value={pv} placeholder="spek" onChange={(e) => setPv(e.target.value)} style={{ width: 70 }} /></label>
            <label className="f">{t("YP (lbf/100ft²)")}<input type="number" step="any" value={yp} placeholder="spek" onChange={(e) => setYp(e.target.value)} style={{ width: 80 }} /></label>
            <label className="f">{t("ID casing di atas shoe (in)")}<input type="number" step="any" value={casingId} placeholder={init.casing_id_default ? "otomatis" : ""} onChange={(e) => setCasingId(e.target.value)} style={{ width: 90 }} /></label>
            <label className="f">{t("Dasar rugi gesek")}
              <select value={base} onChange={(e) => setBase(e.target.value)} disabled={!(num(pv) && num(yp))}>
                <option value="hyd">{t("Hidraulika × kalibrasi ECD terukur")}</option>
                <option value="ml">{t("Model ECD ⓥ + koreksi")}</option>
              </select>
            </label>
            <span className="small muted" style={{ maxWidth: 360 }}>{num(pv) && num(yp) ? t("Aktif: respons flow dari model power-law + geometri string katalog.") : t("Isi PV & YP spek lumpur untuk mengaktifkan hidraulika. Kosong = respons sementara.")}</span>
          </div>
          <div className="row" style={{ marginTop: 10 }}>
            <label className="f">{t("PPFG untuk margin")}
              <select value={ppfgV} onChange={(e) => setPpfgV(e.target.value)}>
                <option value="">{init.ppfg_versions.length ? t("tanpa margin") : t("belum ada PPFG")}</option>
                {init.ppfg_versions.map((v: any) => <option key={v.id} value={v.id}>v{v.version} · {v.status === "approved" ? "approved" : t("{p0} (belum approved, uji coba)", { p0: v.status })}</option>)}
              </select>
            </label>
            <span className="sp" />
            <button className="pri" onClick={() => run(false)} disabled={!!busy}>{t("Hitung ramalan")}</button>
            {res && init.has_actual && <button onClick={() => run(true)} disabled={!!busy}>{t("Buka data asli")}</button>}
          </div>
        </div>
      )}

      {res && (
        <>
          {res.ppfg && res.ppfg.status !== "approved" && <div className="err" style={{ background: "#FFF8E6", borderColor: "#F1D48A", color: "#7A5A00" }}>{t("Margin & alert memakai PPFG v")}{res.ppfg.version}{" "}{t("berstatus")}{" "}<b>{res.ppfg.status}</b>{" "}{t("(belum di-approve Geomechanics): hanya untuk uji coba, bukan acuan keputusan.")}</div>}
          {res.warnings.length > 0 && <div className="err" style={{ background: "#FFF8E6", borderColor: "#F1D48A", color: "#7A5A00" }}>{res.warnings.map((w: string, i: number) => <div key={i}>⚠ {w}</div>)}</div>}
          <div className="kpis">
            <Kpi l={t("ECD sirkulasi tertinggi")} v={s.ecd_circ_max ? n(s.ecd_circ_max.ecd) : "—"} color={C.ecd}
              s={s.ecd_circ_max ? t("{p0} · {p1} ft", { p0: wib(s.ecd_circ_max.time), p1: ft(s.ecd_circ_max.md) }) : ""} />
            <Kpi l={t("Margin terkecil")} v={s.margin_min ? n(s.margin_min.margin) : "—"}
              color={s.margin_min ? LEVEL_COLOR[s.margin_min.margin <= 0 ? "CRITICAL" : s.margin_min.margin <= 0.25 ? "WARNING" : s.margin_min.margin <= 0.5 ? "ADVISORY" : "NORMAL"] : undefined}
              s={s.margin_min ? t("{p0} · {p1} · {p2} ft", { p0: s.margin_min.kind, p1: wib(s.margin_min.time), p2: ft(s.margin_min.md) }) : res.ppfg ? "" : t("belum ada PPFG approved")} />
            <Kpi l={t("Alert pertama")} v={firstAlert(s) ? <Level v={firstAlert(s)![0]} /> : res.ppfg ? <Level v="NORMAL" /> : "—"}
              s={firstAlert(s) ? t("{p0} · {p1} ft · {p2}", { p0: wib(firstAlert(s)![1].time), p1: ft(firstAlert(s)![1].md), p2: firstAlert(s)![1].kind }) : res.ppfg ? t("tidak ada sepanjang rencana") : t("butuh PPFG approved")} />
            <Kpi l={t("Akhir rencana")} v={`${ft(s.md_end)} ft`} s={t("{p0} · {p1} sambung pipa{p2}", { p0: wib(s.end, true), p1: s.connections, p2: res.summary_continuous ? ` (tanpa sambung tiba ${wib(res.summary_continuous.end)})` : "" })} />
            {m && <Kpi l={t("Uji coba vs data asli")} v={`${n(m.mae)} ppg`} color={m.mae <= m.mae_persist ? LEVEL_COLOR.NORMAL : LEVEL_COLOR.WARNING}
              s={t("rata-rata meleset · \"ECD tetap\" {p0} · ECD maks ramalan {p1} vs asli {p2}", { p0: n(m.mae_persist), p1: n(m.ecd_max_fc), p2: n(m.ecd_max_actual) })} />}
          </div>
          <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) 320px", alignItems: "start" }}>
            <div className="card"><EChart option={option} height={620} /></div>
            <div className="grid">
              <div className="card">
                <h3>{t("Kalibrasi & asumsi")}</h3>
                <div className="small">
                  {t("Koreksi dari ECD terukur:")}{" "}<b>{res.reference.n_calib}</b>{" "}{t("titik, bias")}{" "}{n(res.reference.bias, 3)}{" "}{t("ppg")}<br />
                  {t("Rugi gesek acuan (ECD − MW):")}{" "}<b>{n(res.reference.apl)}</b>{" "}{t("ppg")}<br />
                  {t("Respons flow:")}{" "}{res.hydraulics ? t("hidraulika power-law (lihat kartu Hidraulika)") : <>{t("rugi gesek × (Q/Q acuan)")}<sup>{res.cfg.flow_exp}</sup>{" "}{t("(sementara, PV/YP kosong)")}</>}<br />
                  {t("Respons RPM: +")}{Math.round(res.cfg.rpm_k * 100)}{t("% rugi gesek per 100 rpm")}<br />
                  {t("WOB → ROP → cutting (lubang")}{" "}{res.cfg.hole_size}{t("\", transport")}{" "}{res.cfg.transport})<br />
                  {t("Sambung pipa:")}{" "}{conn ? t("tiap {p0} ft, {p1} mnt", { p0: res.cfg.every_ft, p1: res.cfg.off_min }) : "tidak"}
                </div>
                {res.reference.notes.map((x: string, i: number) => <p key={i} className="note">{x}</p>)}
                <p className="note">{t("Besaran respons masih")}{" "}<b>{t("sementara")}</b>{" "}{t("sampai PV/YP spek dan ukuran lubang per section tersedia. Saat pompa mati ditampilkan tekanan statis ≈ MW; lonjakan saat pompa hidup belum dimodelkan.")}</p>
              </div>
              {res.hydraulics && (
                <div className="card">
                  <h3>{t("Hidraulika annulus")}</h3>
                  <div className="small">
                    {t("PV")}{" "}{n(res.hydraulics.pv, 0)}{" "}{t("cP · YP")}{" "}{n(res.hydraulics.yp, 0)}{" "}{t("lbf/100ft² → n")}{" "}{n(res.hydraulics.n, 2)}, K {n(res.hydraulics.K, 0)}{" "}{t("eq.cP")}<br />
                    {t("Lubang")}{" "}{res.hydraulics.hole_size}{t("\" · ID casing")}{" "}{n(res.hydraulics.casing_id, 3)}{t("\" · shoe")}{" "}{res.hydraulics.shoe_md ? t("{p0} ft", { p0: ft(res.hydraulics.shoe_md) }) : t("belum diisi (semua open hole)")}<br />
                    {t("String:")}{" "}{res.hydraulics.preset}<br />
                    {t("Di jam mulai: rugi gesek hitungan")}{" "}{n(res.hydraulics.apl_psi_ref, 0)}{" "}{t("psi =")}{" "}{n(res.hydraulics.apl_ppg_ref, 2)}{" "}{t("ppg (")}{res.hydraulics.turbulent_ref ? t("ada ruas turbulen") : "laminar"}{t(") vs terukur")}{" "}{n(res.hydraulics.apl_meas_ref, 2)}{" "}{t("ppg → faktor kalibrasi")}{" "}<b>{n(res.hydraulics.c, 2)}</b><br />
                    {t("Dasar:")}{" "}{res.hydraulics.base === "hyd" ? t("hidraulika × kalibrasi") : t("model ECD ⓥ + koreksi")}
                  </div>
                  <p className="note">{t("Faktor kalibrasi jauh dari 1 berarti ukuran lubang, string, atau PV/YP belum sesuai kondisi sumur. String = preset katalog bending (OD body, tool joint diabaikan).")}</p>
                </div>
              )}
              {m && (
                <div className="card">
                  <h3>{t("Uji coba: ramalan vs data asli")}</h3>
                  <div className="small">
                    {t("Rata-rata meleset:")}{" "}<b>{n(m.mae, 3)}</b>{" "}{t("ppg (bias")}{" "}{n(m.bias, 3)})<br />
                    {t("Bila dianggap \"ECD tetap\"")}{" "}{n(m.ecd_last)}: {n(m.mae_persist, 3)}{" "}{t("ppg")}<br />
                    {t("ECD tertinggi: ramalan")}{" "}<b>{n(m.ecd_max_fc)}</b>{" "}{t("· asli")}{" "}<b>{n(m.ecd_max_actual)}</b> ({wib(m.t_max_actual)})<br />
                    {t("Kedalaman akhir: ramalan")}{" "}{ft(m.md_end_fc)}{" "}{t("· asli")}{" "}{ft(m.md_end_actual)}{" "}{t("ft")}<br />
                    {t("Titik dibandingkan:")}{" "}{m.n}{" "}{t("(pompa hidup, ECD terukur tidak beku)")}
                  </div>
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}

function firstAlert(s: any): [string, any] | null {
  for (const l of ["CRITICAL", "WARNING", "ADVISORY"]) if (s.first?.[l]) return [l, s.first[l]];
  return null;
}

const pts = (sr: any, k: string) => (sr && sr[k] ? sr.t.map((t: string, i: number) => [t, sr[k][i]]) : []);
/** ECD terukur sering jarang (update tiap beberapa menit): buang titik kosong, putus bila jeda > 10 menit */
const sparse = (sr: any, k: string) => {
  const out: any[] = []; let last = 0;
  pts(sr, k).forEach(([t, v]: [string, number | null]) => {
    if (v == null) return;
    const ms = new Date(t).getTime();
    if (last && ms - last > 600e3) out.push([t, null]);
    out.push([t, v]); last = ms;
  });
  return out;
};

function chart(r: any) {
  const tl = r.timeline, h = r.history, a = r.actual, c = r.continuous;
  const vals = [...(tl.ecd || []), ...(h.ecd_ok || []), ...(a?.ecd_ok || []), ...(tl.mw || []), ...(tl.fg_bit || [])].filter((v: any) => v != null);
  const lo = Math.floor((Math.min(...vals) - 0.2) * 5) / 5, hi = Math.ceil((Math.max(...vals) + 0.2) * 5) / 5;
  const alert = firstAlert(r.summary);
  const line = (name: string, data: any[], color: string, o: any = {}) =>
    ({ name, type: "line", data, showSymbol: false, connectNulls: false, lineStyle: { width: 1.6, color }, itemStyle: { color }, ...o });
  return {
    animation: false, tooltip: { ...TIP, valueFormatter: (v: any) => (v == null ? "—" : Number(v).toFixed(2)) },
    legend: { top: 0, textStyle: { fontSize: 11 } },
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    grid: [{ left: 56, right: 18, top: 40, height: "58%" }, { left: 56, right: 18, top: "74%", height: "19%" }],
    xAxis: [0, 1].map((i) => ({ type: "time", gridIndex: i, ...AX, axisLabel: { ...AX.axisLabel, show: i === 1, formatter: (v: number) => wib(new Date(v).toISOString()) } })),
    yAxis: [
      { type: "value", gridIndex: 0, min: lo, max: hi, name: "ppg", ...AX },
      { type: "value", gridIndex: 1, inverse: true, name: t("MD ft"), scale: true, ...AX },
    ],
    dataZoom: [{ type: "inside", xAxisIndex: [0, 1] }],
    series: [
      line(t("ECD terukur (sebelum)"), sparse(h, "ecd_ok"), "#7A8694", { showSymbol: true, symbolSize: 3 }),
      line(t("Ramalan ECD"), pts(tl, "ecd"), C.ecd, { lineStyle: { width: 2.2, color: C.ecd },
        markLine: { symbol: "none", label: { fontSize: 11 }, data: [
          { xAxis: r.t_cut, lineStyle: { color: "#1B2430", type: "solid" }, label: { formatter: t("jam mulai"), position: "insideEndTop" } },
          ...(alert ? [{ xAxis: alert[1].time, lineStyle: { color: LEVEL_COLOR[alert[0]] }, label: { formatter: alert[0], position: "insideEndTop", color: LEVEL_COLOR[alert[0]] } }] : []),
        ] } }),
      ...(c ? [line(t("ECD sirkulasi tanpa sambung pipa"), pts(c, "ecd_circ"), C.ecd, { lineStyle: { width: 1, type: "dashed", color: C.ecd, opacity: 0.6 } })] : []),
      line("MW", pts(tl, "mw"), C.mw, { step: "end" }),
      line(t("FG di bit"), pts(tl, "fg_bit"), C.fg, { lineStyle: { width: 1.4, color: C.fg } }),
      line(t("Batas bawah max(PP,SFG)"), pts(tl, "lower_bit"), C.pp, { lineStyle: { width: 1.2, type: "dashed", color: C.pp } }),
      ...(a ? [line(t("ECD terukur (data asli)"), sparse(a, "ecd_ok"), "#1B2430", { showSymbol: true, symbolSize: 3, lineStyle: { width: 1.2, color: "#1B2430" } })] : []),
      line(t("Bit depth ramalan"), pts(tl, "bit_depth"), C.ecd, { xAxisIndex: 1, yAxisIndex: 1 }),
      line(t("Bit depth sebelum"), pts(h, "bit_depth"), "#7A8694", { xAxisIndex: 1, yAxisIndex: 1 }),
      ...(a ? [line(t("Bit depth asli"), pts(a, "bit_depth"), "#1B2430", { xAxisIndex: 1, yAxisIndex: 1, lineStyle: { width: 1, color: "#1B2430" } })] : []),
    ],
  };
}
