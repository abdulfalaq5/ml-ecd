import { useEffect, useMemo, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ft, n, toLocalInput, wib } from "../lib/fmt";
import { EChart, Err, Level, WellSelect, ZoneTag } from "../components/ui";
import { buildTracks, CHANNELS, type Track } from "../components/tracks";

const TRACKS: Track[] = [
  { title: "Hookload · Torque", ch: [CHANNELS.hookload, CHANNELS.torque] },
  { title: "SPP · Flow In", ch: [CHANNELS.spp, CHANNELS.flow_in] },
  { title: "ECD ⓥ · ECD terukur · MW · FG", ch: [CHANNELS.ecd_pred, CHANNELS.ecd, CHANNELS.mw, CHANNELS.fg_bit, CHANNELS.lower_bit] },
  { title: "Flow Out · Active Pit", ch: [CHANNELS.flow_out_pct, CHANNELS.active_pit] },
  { title: "Skor risiko gabungan", ch: [CHANNELS.risk] },
];

export default function AnalisisAnomali() {
  const { wellId } = useApp();
  const [t0, setT0] = useState(""); const [t1, setT1] = useState("");
  const [cut, setCut] = useState(100); // % dari jendela
  const [applied, setApplied] = useState<{ t0: string; t1: string; cutoff: string | null }>({ t0: "", t1: "", cutoff: null });
  const { data, err, loading } = useFetch<any>(() => (wellId ? api.get(`/wells/${wellId}/anomaly`, { t0: applied.t0, t1: applied.t1, cutoff: applied.cutoff, points: 1500 }) : null), [wellId, applied]);
  useEffect(() => { setApplied({ t0: "", t1: "", cutoff: null }); setT0(""); setT1(""); setCut(100); }, [wellId]);
  useEffect(() => { if (data && !data.empty && !t0) { setT0(toLocalInput(data.t0)); setT1(toLocalInput(data.t1)); } }, [data, t0]);

  const cutIso = useMemo(() => {
    if (!data || data.empty || cut >= 100) return null;
    const a = new Date(data.t0).getTime(), b = new Date(data.t1).getTime();
    return new Date(a + (b - a) * cut / 100).toISOString();
  }, [data, cut]);
  const option = useMemo(() => {
    if (!data || data.empty) return null;
    const vals = ["ecd", "ecd_pred", "mw", "fg_bit", "lower_bit"].flatMap((k) => (data.seen[k] || []).filter((x: any) => x != null));
    const rng: [number, number] = vals.length ? [Math.floor(Math.min(...vals) - 0.3), Math.ceil(Math.max(...vals) + 0.3)] : [8, 16];
    return buildTracks(data.seen, TRACKS, { marks: data.detections.map((d: any) => ({ t0: d.start, t1: d.end, label: d.label, level: d.level })), ppgRange: rng, cutoff: data.cutoff, after: data.after });
  }, [data]);
  const ecdv = (data?.detections || []).filter((d: any) => d.detector === "ecdv_spike");

  return (
    <>
      <div className="top"><h1>Analisis Anomali</h1><WellSelect /><span className="sp" />{data?.model && <span className="chip">Model: {data.model.name} ({data.model.status})</span>}</div>
      <Err e={err} />
      <div className="card" style={{ marginBottom: 12 }}>
        <div className="row">
          <label className="f">Dari (WIB)<input type="datetime-local" value={t0} onChange={(e) => setT0(e.target.value)} /></label>
          <label className="f">Sampai (WIB)<input type="datetime-local" value={t1} onChange={(e) => setT1(e.target.value)} /></label>
          <label className="f" style={{ flex: 1, minWidth: 260 }}>Cut-off: {cutIso ? wib(cutIso, true) : "tanpa cut-off (semua data)"}
            <input type="range" min={5} max={100} value={cut} onChange={(e) => setCut(Number(e.target.value))} />
          </label>
          <button className="pri" onClick={() => setApplied({ t0, t1, cutoff: cutIso ? cutIso : null })}>Jalankan</button>
          {loading && <span className="muted small">menghitung…</span>}
        </div>
        <p className="note">Mode cut-off: engine hanya melihat data ≤ cut-off (tanpa look-ahead). Data setelah cut-off ditampilkan abu-abu untuk verifikasi. Pilih cut-off sebelum event untuk menguji lead time.</p>
        {data && !data.empty && <div className="small muted">Data sumur: {wib(data.data_start, true)} → {wib(data.data_end, true)} · ECD terukur {data.ecd_measured_available ? "tersedia" : <b style={{ color: "#E8710A" }}>tidak ada — hanya ECD ⓥ (estimasi)</b>}</div>}
      </div>
      {data?.empty && <div className="card empty">Belum ada data.</div>}
      {option && (
        <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) 340px", alignItems: "start" }}>
          <div className="card"><EChart option={option} height={760} /></div>
          <div className="grid">
            <div className="card">
              <h3>Lonjakan ECD ⓥ</h3>
              {ecdv.length === 0 ? <div className="muted small">Tidak ada kenaikan mendadak ECD ⓥ pada jendela ini.</div> : ecdv.map((d: any, i: number) => (
                <div key={i} className="small" style={{ borderTop: "1px solid #E3E8EE", padding: "6px 0" }}>
                  <Level v={d.level} /> <span className="mono">{wib(d.start)}–{wib(d.end)}</span> · +{n(d.value)} ppg dari {n(d.baseline)} · {d.state}{d.md ? ` @${ft(d.md)} ft` : ""}
                </div>
              ))}
              <p className="note">Kenaikan ECD ⓥ ≥ 0.2 ppg dalam 10 mnt pada flow stabil = indikasi awal pack-off / hole problem. Diabaikan 10 mnt setelah pompa nyala; disuppress saat pumps off.</p>
            </div>
            <div className="card">
              <h3>Indikator terdeteksi ({data.detections.length})</h3>
              <div style={{ maxHeight: 300, overflow: "auto" }}>
                {data.detections.map((d: any, i: number) => (
                  <div key={i} className="small" style={{ borderTop: "1px solid #E3E8EE", padding: "6px 0" }}>
                    <div className="row"><Level v={d.level} /><ZoneTag z={d.zone} /><span className="mono">{wib(d.start)}</span><span className="muted">{d.state}</span></div>
                    <div>{d.label}{d.md ? ` @${ft(d.md)} ft` : ""}</div>{d.rec && <div className="muted">Verifikasi: {d.rec}</div>}
                  </div>
                ))}
              </div>
            </div>
            <div className="card">
              <h3>Event terkonfirmasi & lead time</h3>
              {data.lead_times.length === 0 && <div className="muted small">Belum ada event Dikonfirmasi di sumur ini (Riwayat Event).</div>}
              {data.lead_times.map((l: any, i: number) => (
                <div key={i} className="small" style={{ borderTop: "1px solid #E3E8EE", padding: "6px 0" }}>
                  <b>{l.event}</b> · {wib(l.onset, true)}<br />
                  Indikasi pertama: {l.first ? `${wib(l.first)} (${l.first_lead_min} mnt sebelum)` : "—"}<br />
                  WARNING pertama: {l.warning ? `${wib(l.warning)} (${l.warning_lead_min} mnt sebelum)` : "—"}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
