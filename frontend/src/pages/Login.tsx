import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Err } from "../components/ui";
import { DrillingScene, RigIcon } from "../components/DrillingScene";

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
      <section className="hero" aria-label="Ilustrasi pengeboran sumur">
        <DrillingScene />
        <div className="tag">
          <h2>Pantau ECD di setiap meter pengeboran</h2>
          <p>Nowcast ECD dari parameter permukaan, margin terhadap jendela tekanan PP/SFG–FG, dan indikasi dini masalah lubang.</p>
        </div>
      </section>
      <div className="side">
        <form className="card" onSubmit={submit}>
          <div className="row" style={{ gap: 12 }}>
            <RigIcon size={36} />
            <div><b style={{ fontSize: 19 }}>ECD Monitor</b><div className="muted small">PHR Drilling · Nowcast ECD berbasis ML</div></div>
          </div>
          <div className="muted small" style={{ marginTop: -2 }}>Masuk untuk melanjutkan</div>
          <label className="f">Username<input value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" /></label>
          <label className="f">Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
          <Err e={err} />
          <button className="pri" disabled={busy || !u || !p}>{busy ? "Masuk…" : "Masuk"}</button>
          <div className="note">Akun lokal. Hubungi admin Data/ML untuk membuat akun atau reset password. Integrasi SSO PHR menyusul.</div>
          <div className="foot">Alat bantu keputusan · setiap alert wajib diverifikasi engineer</div>
        </form>
      </div>
    </div>
  );
}
