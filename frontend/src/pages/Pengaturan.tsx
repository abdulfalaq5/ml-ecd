import { useEffect, useState } from "react";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { wib } from "../lib/fmt";
import { Err } from "../components/ui";

const LABELS: Record<string, string> = {
  advisory_margin: "Advisory bila margin ≤ (ppg)", warning_margin: "Warning bila margin ≤ (ppg)", warning_persist_min: "Warning bertahan (mnt)", critical_margin: "Critical bila margin ≤ (ppg)",
  ecd_rise_ppg_5min: "Kenaikan ECD dalam 5 mnt (ppg)", stale_min: "Data basi setelah (mnt)",
  baseline_min: "Baseline rolling (mnt)", lag_min: "Lag baseline (mnt)", spp_rise_pct: "Pack-off: SPP naik (%)", torque_k: "Torque spike (× MAD)", overpull_klb: "Overpull (klb)",
  tag_wob_klb: "Tag WOB (klb)", ecdv_rise_ppg: "Lonjakan ECD ⓥ (ppg)", ecdv_window_min: "… jendela (mnt)", ecdv_ignore_after_pumps_min: "Abaikan setelah pompa nyala (mnt)",
  residual_ppg: "Residual ECD terukur − ⓥ (ppg)", loss_flowout_drop_pct: "Loss: flow out turun (%)", flowout_min_base_pct: "Baseline flow out minimum (%)", flowout_min_change_pct: "Perubahan flow out minimum (poin %)", pit_change_bbl: "Perubahan pit (bbl)", stationary_min: "Diam (differential) (mnt)", min_duration_min: "Durasi minimum (mnt)",
};

function SettingCard({ k, title }: { k: string; title: string }) {
  const { can } = useApp();
  const s = useFetch<any>(() => api.get(`/settings/${k}`), [k]);
  const [v, setV] = useState<Record<string, any>>({});
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => { if (s.data) setV(s.data.value); }, [s.data]);
  const act = async (fn: () => Promise<any>) => { setMsg(null); try { await fn(); s.reload(); } catch (e: any) { setMsg(e.message); } };
  const d = s.data;
  return (
    <div className="card">
      <div className="row"><h3 style={{ margin: 0 }}>{title}</h3><span className="sp" /><span className="chip" style={{ color: d?.status === "pending" ? "#B98900" : "#1E9E5A" }}>{d?.status === "pending" ? "menunggu persetujuan" : "aktif"}</span></div>
      <Err e={msg} />
      <table style={{ marginTop: 8 }}>
        <thead><tr><th>Parameter</th><th>Aktif</th><th>Default</th>{d?.proposed && <th>Diajukan</th>}</tr></thead>
        <tbody>{d && Object.keys(d.defaults).map((key) => (
          <tr key={key}><td className="small">{LABELS[key] || key}</td>
            <td><input type="number" step="any" style={{ width: 100 }} value={v[key] ?? ""} disabled={!can("threshold_propose")} onChange={(e) => setV({ ...v, [key]: e.target.value })} /></td>
            <td className="mono muted">{d.defaults[key]}</td>{d.proposed && <td className="mono" style={{ color: "#B98900" }}>{d.proposed[key]}</td>}</tr>
        ))}</tbody>
      </table>
      <div className="row" style={{ marginTop: 8 }}>
        {can("threshold_propose") && <button onClick={() => act(() => api.post(`/settings/${k}/propose`, { value: v }))}>Ajukan perubahan</button>}
        {can("threshold_propose") && <button onClick={() => act(() => api.post(`/settings/${k}/reset`))}>Ajukan reset default</button>}
        {d?.status === "pending" && can("threshold_approve") && <button className="pri" onClick={() => act(() => api.post(`/settings/${k}/approve`))}>Setujui</button>}
      </div>
      <div className="muted small" style={{ marginTop: 6 }}>
        {d?.status === "pending" ? `Diajukan ${d.proposed_by}; persetujuan: ${d.approvals.map((a: any) => `${a.role} (${a.by})`).join(", ") || "belum ada"} — butuh Drilling Eng + HSE.` : d?.approved_by ? `Disetujui ${d.approved_by}` : "Nilai default"}
      </div>
    </div>
  );
}

function Users() {
  const u = useFetch<any[]>(() => api.get("/users"), []);
  const roles = useFetch<any[]>(() => api.get("/roles"), []);
  const [f, setF] = useState<any>({ username: "", full_name: "", role: "viewer", password: "", active: true });
  const [msg, setMsg] = useState<string | null>(null);
  const act = async (fn: () => Promise<any>) => { setMsg(null); try { await fn(); u.reload(); } catch (e: any) { setMsg(e.message); } };
  return (
    <div className="card" style={{ gridColumn: "1 / -1" }}>
      <h3>Akun lokal & peran</h3>
      <Err e={msg} />
      <table>
        <thead><tr><th>Username</th><th>Nama</th><th>Peran</th><th>Aktif</th><th>Login terakhir</th><th></th></tr></thead>
        <tbody>{u.data?.map((x) => (
          <tr key={x.id}><td className="mono">{x.username}</td><td>{x.full_name}</td>
            <td><select value={x.role} onChange={(e) => act(() => api.put(`/users/${x.id}`, { ...x, role: e.target.value, password: "" }))}>{(roles.data || []).map((r: any) => <option key={r.id} value={r.id}>{r.label}</option>)}</select></td>
            <td><input type="checkbox" checked={x.active} onChange={(e) => act(() => api.put(`/users/${x.id}`, { ...x, active: e.target.checked, password: "" }))} /></td>
            <td className="small muted">{wib(x.last_login, true)}</td>
            <td><button onClick={() => { const p = prompt(`Password baru untuk ${x.username}`); if (p) act(() => api.put(`/users/${x.id}`, { ...x, password: p })); }}>Reset password</button></td></tr>
        ))}</tbody>
      </table>
      <div className="row" style={{ marginTop: 10 }}>
        <input placeholder="username" value={f.username} onChange={(e) => setF({ ...f, username: e.target.value })} />
        <input placeholder="nama lengkap" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} />
        <select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>{(roles.data || []).map((r: any) => <option key={r.id} value={r.id}>{r.label}</option>)}</select>
        <input placeholder="password awal" type="password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} />
        <button className="pri" disabled={!f.username || !f.password} onClick={() => act(() => api.post("/users", f).then(() => setF({ username: "", full_name: "", role: "viewer", password: "", active: true })))}>+ Akun</button>
      </div>
    </div>
  );
}

export default function Pengaturan() {
  const { can, user } = useApp();
  const sys = useFetch<any>(() => api.get("/settings/system/info"), []);
  const log = useFetch<any[]>(() => api.get("/settings/audit/log", { limit: 100 }), []);
  const [pw, setPw] = useState({ old: "", new: "" }); const [pwMsg, setPwMsg] = useState<string | null>(null);
  const changePw = async () => { try { await api.post("/auth/password", { old_password: pw.old, new_password: pw.new }); setPwMsg("Password diganti."); setPw({ old: "", new: "" }); } catch (e: any) { setPwMsg(e.message); } };
  return (
    <>
      <div className="top"><h1>Pengaturan</h1><span className="muted small">threshold alert & detektor (persetujuan Drilling Eng + HSE), akun, audit</span></div>
      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 1fr) minmax(0, 1fr)", alignItems: "start" }}>
        <SettingCard k="thresholds" title="Threshold alert" />
        <SettingCard k="detectors" title="Parameter detektor anomali" />
        {can("users") && <Users />}
        <div className="card">
          <h3>Akun saya</h3>
          <div className="small muted">{user?.username} · {user?.role_label}</div>
          <div className="row" style={{ marginTop: 8 }}>
            <input type="password" placeholder="password lama" value={pw.old} onChange={(e) => setPw({ ...pw, old: e.target.value })} />
            <input type="password" placeholder="password baru" value={pw.new} onChange={(e) => setPw({ ...pw, new: e.target.value })} />
            <button onClick={changePw} disabled={!pw.old || pw.new.length < 8}>Ganti password</button>
          </div>
          {pwMsg && <div className="small" style={{ marginTop: 6 }}>{pwMsg}</div>}
          <h3 style={{ marginTop: 14 }}>Sistem</h3>
          {sys.data && <table><tbody>{Object.entries(sys.data).map(([k, v]: any) => <tr key={k}><td className="small muted">{k}</td><td className="mono small">{String(v)}</td></tr>)}</tbody></table>}
        </div>
        <div className="card">
          <h3>Audit log</h3>
          <div style={{ maxHeight: 380, overflow: "auto" }}>
            <table><tbody>{log.data?.map((r, i) => <tr key={i}><td className="small mono">{wib(r.ts, true)}</td><td className="small">{r.username}</td><td className="small">{r.action}</td><td className="small muted">{r.detail}</td></tr>)}</tbody></table>
          </div>
        </div>
      </div>
    </>
  );
}
