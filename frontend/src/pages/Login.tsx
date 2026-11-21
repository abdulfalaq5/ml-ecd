import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Err } from "../components/ui";

export default function Login() {
  const [u, setU] = useState(""); const [p, setP] = useState("");
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const { setUser, reloadWells } = useApp();
  const nav = useNavigate();
  const submit = async (e: React.FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const j = await api.login(u, p);
      setUser(j.user); await reloadWells(); nav("/");
    } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <div className="row">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#FF9F43" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 17a8 8 0 1 1 16 0" /><path d="M12 17l4-6" /><circle cx="12" cy="17" r="1.5" /></svg>
          <div><b style={{ fontSize: 18 }}>ECD Monitor</b><div className="muted small">PHR Drilling · Nowcast ECD berbasis ML</div></div>
        </div>
        <label className="f">Username<input value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" /></label>
        <label className="f">Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
        <Err e={err} />
        <button className="pri" disabled={busy || !u || !p}>{busy ? "Masuk…" : "Masuk"}</button>
        <div className="note">Akun lokal. Hubungi admin Data/ML untuk membuat akun atau reset password. Integrasi SSO PHR menyusul.</div>
      </form>
    </div>
  );
}
