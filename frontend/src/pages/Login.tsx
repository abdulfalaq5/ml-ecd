import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Err } from "../components/ui";
import { DrillingScene, RigIcon } from "../components/DrillingScene";
import { t } from "../lib/i18n";

export default function Login() {
  const [u, setU] = useState(""); const [p, setP] = useState("");
  const [show, setShow] = useState(false);
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
      <section className="hero" aria-label={t("Ilustrasi pengeboran sumur")}>
        <DrillingScene />
        <div className="tag">
          <h2>{t("Pantau ECD di setiap meter pengeboran")}</h2>
          <p>{t("Nowcast ECD dari parameter permukaan, margin terhadap jendela tekanan PP/SFG–FG, dan indikasi dini masalah lubang.")}</p>
        </div>
      </section>
      <div className="side">
        <form className="card" onSubmit={submit}>
          <div className="row" style={{ gap: 12 }}>
            <RigIcon size={36} />
            <div><b style={{ fontSize: 19 }}>{t("Paningal Sense")}</b><div className="muted small">{t("ECD & Hole Condition · PHR Drilling")}</div></div>
          </div>
          <div className="muted small" style={{ marginTop: -2 }}>{t("Masuk untuk melanjutkan")}</div>
          <label className="f">{t("Username")}<input value={u} onChange={(e) => setU(e.target.value)} autoFocus autoComplete="username" /></label>
          <label className="f">{t("Password")}
            <span className="pw">
              <input type={show ? "text" : "password"} value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" />
              <button type="button" className="pw-eye" onClick={() => setShow(!show)} aria-label={show ? t("Sembunyikan password") : t("Tampilkan password")} aria-pressed={show} title={show ? t("Sembunyikan password") : t("Tampilkan password")}>
                {show ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M3 3l18 18" /><path d="M10.6 10.6a2 2 0 0 0 2.8 2.8" /><path d="M9.9 5.1A10.4 10.4 0 0 1 12 5c6 0 9.5 7 9.5 7a17 17 0 0 1-3.2 4.1M6.6 6.6C4 8.3 2.5 12 2.5 12s3.5 7 9.5 7a9.7 9.7 0 0 0 5.4-1.6" /></svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M2.5 12S6 5 12 5s9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z" /><circle cx="12" cy="12" r="3" /></svg>
                )}
              </button>
            </span>
          </label>
          <Err e={err} />
          <button className="pri" disabled={busy || !u || !p}>{busy ? t("Masuk…") : t("Masuk")}</button>
          <div className="note">{t("Akun lokal. Hubungi admin Data/ML untuk membuat akun atau reset password. Integrasi SSO PHR menyusul.")}</div>
          <div className="foot">{t("Alat bantu keputusan · setiap alert wajib diverifikasi engineer")}</div>
        </form>
      </div>
    </div>
  );
}
