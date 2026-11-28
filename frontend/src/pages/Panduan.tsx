import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { FLOWS, HOWTOS, LIMITS, LIVE_REQS, MENUS, TERMS, type HowTo, type Limit, type MenuGuide, type Req } from "../lib/guide";
import { t } from "../lib/i18n";

/* ---------- pencarian ---------- */
const STOP = new Set(["cara", "bagaimana", "gimana", "untuk", "yang", "di", "ke", "dan", "atau", "apa", "saya", "mau", "ingin", "pingin",
  "itu", "ini", "dong", "ya", "nya", "melakukan", "bisa", "tolong", "dengan", "pada", "dari", "buat", "bikin", "kalau", "kalo", "menu", "tombol", "fungsi",
  "how", "to", "do", "i", "the", "a", "an", "of", "for", "in", "on", "is", "it", "can", "what", "my", "me", "with", "and", "or", "button"]);
// sinonim sederhana: kata yang diketik user → kata yang dipakai di panduan
const SYN: Record<string, string[]> = {
  latih: ["training"], melatih: ["training"], train: ["training"], retrain: ["training"], pelatihan: ["training"],
  akurasi: ["mae", "akurasi"], akurat: ["mae", "akurasi"], error: ["mae", "error"], hasil: ["hasil", "evaluasi"], evaluasi: ["evaluasi", "mae"],
  unggah: ["upload"], masukkan: ["upload", "ingest"], import: ["upload", "ingest"], impor: ["upload", "ingest"], file: ["file", "upload"],
  sumur: ["sumur", "well"], well: ["sumur"], room: ["sumur", "room"],
  sandi: ["password"], katasandi: ["password"], pass: ["password"], lupa: ["password", "reset"],
  user: ["akun", "user"], pengguna: ["akun", "user"], akun: ["akun", "user"], role: ["peran"], hak: ["peran"],
  laporan: ["laporan", "report"], report: ["laporan"], pdf: ["cetak", "pdf"], print: ["cetak"], excel: ["excel", "unduh"], download: ["unduh"],
  kejadian: ["event", "kejadian"], insiden: ["event"], label: ["event", "label"],
  ambang: ["threshold"], batas: ["threshold", "batas"], kalibrasi: ["threshold", "kalibrasi"],
  pantau: ["monitor", "pantau"], monitoring: ["monitor"], realtime: ["realtime", "monitor"],
  prediksi: ["ecd", "prediksi"], virtual: ["ecd", "virtual"], kosong: ["kosong", "unavailable"],
  fg: ["fg", "ppfg"], ppfg: ["ppfg"], frac: ["fg", "ppfg"], lumpur: ["mw"], mudweight: ["mw"],
  cadangan: ["backup"], pulihkan: ["restore"], production: ["production", "promosi"], produksi: ["production", "promosi"],
};
const norm = (s: string) => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^a-z0-9ⓥ.\- ]+/g, " ");
const tokens = (q: string) => norm(q).split(/\s+/).filter((w) => w.length > 1 && !STOP.has(w));

type Hit = { kind: "Cara" | "Menu" | "Tombol" | "Istilah" | "Alur" | "Batasan" | "Syarat"; title: string; body: ReactNode; text: string; menu?: MenuGuide; score: number; id: string };

function score(words: string[][], title: string, keys: string, body: string): number {
  const t = norm(title), k = norm(keys), b = norm(body);
  let s = 0, matched = 0;
  for (const alts of words) {
    let best = 0;
    for (const w of alts) best = Math.max(best, t.includes(w) ? 3 : k.includes(w) ? 2 : b.includes(w) ? 1 : 0);
    if (best) matched++;
    s += best;
  }
  // semua kata cocok → bonus; hanya sebagian → tetap muncul tapi di bawah
  return matched === 0 ? 0 : s + (matched === words.length ? 4 : 0) + matched;
}

function Hl({ text, words }: { text: string; words: string[] }) {
  if (!words.length) return <>{text}</>;
  const esc = words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).sort((a, b) => b.length - a.length);
  const parts = text.split(new RegExp(`(${esc.join("|")})`, "gi"));
  return <>{parts.map((p, i) => (i % 2 ? <mark key={i}>{p}</mark> : <Fragment key={i}>{p}</Fragment>))}</>;
}

const menuOf = (key?: string) => MENUS.find((m) => m.key === key);
const SUGGEST = [t("upload harian"), t("data kosong"), t("input PPFG manual"), "section", t("MW berubah waktu"), t("seberapa akurat"), t("syarat realtime"), t("cek hasil training"), t("upload file besar"), t("approve PPFG"), t("kenapa UNAVAILABLE"), t("buat laporan"), t("konfirmasi event"), t("ganti password"), t("zona rathole"), "cut-off", t("bending moment"), t("ramalan 6 jam")];

/* ---------- komponen tampilan ---------- */
function Steps({ h, words }: { h: HowTo; words: string[] }) {
  const m = menuOf(h.menu);
  return (
    <div>
      <ol className="guide-steps">{h.steps.map((s, i) => <li key={i}><Hl text={s} words={words} /></li>)}</ol>
      {h.note && <div className="note" style={{ marginTop: 6 }}><Hl text={h.note} words={words} /></div>}
      <div className="row small" style={{ marginTop: 8 }}>
        {h.who && <span className="chip">{t("Peran:")}{" "}{h.who}</span>}
        {m && m.key !== "panduan" && <Link to={m.path} className="chip guide-go">{t("Buka")}{" "}{m.title} →</Link>}
      </div>
    </div>
  );
}

function MenuCard({ m, words, open }: { m: MenuGuide; words: string[]; open?: boolean }) {
  return (
    <details className="card guide-menu" open={open} id={`menu-${m.key}`}>
      <summary><b><Hl text={m.title} words={words} /></b><span className="muted small"> — <Hl text={m.purpose.split(":")[0].split(".")[0]} words={words} /></span></summary>
      <p className="small" style={{ margin: "10px 0 4px" }}><Hl text={m.purpose} words={words} /></p>
      <p className="small muted" style={{ margin: "0 0 10px" }}><b>{t("Kapan dipakai:")}</b> <Hl text={m.when} words={words} /></p>
      <table><thead><tr><th style={{ width: "28%" }}>{t("Tombol / kontrol")}</th><th>{t("Fungsi")}</th><th style={{ width: "22%" }}>{t("Siapa yang bisa")}</th></tr></thead>
        <tbody>{m.controls.map((c) => <tr key={c.name}><td><b><Hl text={c.name} words={words} /></b></td><td className="small"><Hl text={c.desc} words={words} /></td><td className="small muted">{c.who || t("semua peran")}</td></tr>)}</tbody></table>
      {m.tips?.map((t, i) => <div key={i} className="note" style={{ marginTop: 8 }}>{t}</div>)}
      {m.key !== "panduan" && <div style={{ marginTop: 10 }}><Link to={m.path} className="chip guide-go">{t("Buka")}{" "}{m.title} →</Link></div>}
    </details>
  );
}

export default function Panduan() {
  const [sp, setSp] = useSearchParams();
  const [q, setQ] = useState(sp.get("q") || "");
  const [tab, setTab] = useState<"alur" | "menu" | "cara" | "batasan" | "live" | "istilah">("alur");
  const setQuery = (v: string) => { setQ(v); const n = new URLSearchParams(sp); if (v) n.set("q", v); else n.delete("q"); setSp(n, { replace: true }); };

  const words = useMemo(() => tokens(q), [q]);
  // petunjuk dari kata yang dibuang: kode menu (mis. "menu A", "menu 6"), "tombol", "menu"
  const ctx = useMemo(() => {
    const raw = norm(q).split(/\s+/).filter(Boolean);
    const codes = new Set(MENUS.map((m) => norm(m.title.split(" ")[0])));
    return { codes: new Set(raw.filter((w) => w.length === 1 && codes.has(w))), btn: raw.some((w) => ["tombol", "button", "klik"].includes(w)), menu: raw.includes("menu") };
  }, [q]);
  const groups = useMemo(() => words.map((w) => [w, ...(SYN[w] || [])].map(norm)), [words]);
  const hlWords = useMemo(() => Array.from(new Set(groups.flat())), [groups]);

  const hits = useMemo<Hit[]>(() => {
    if (!groups.length) {
      const only = MENUS.filter((m) => ctx.codes.has(norm(m.title.split(" ")[0])));
      return only.map((m) => ({ kind: "Menu" as const, id: "m-" + m.key, title: m.title, text: m.purpose, menu: m, score: 1, body: <MenuCard m={m} words={[]} open /> }));
    }
    const out: Hit[] = [];
    for (const h of HOWTOS) {
      const s = score(groups, h.title, h.keywords, h.steps.join(" ") + " " + (h.note || ""));
      if (s) out.push({ kind: "Cara", id: "h-" + h.id, title: h.title, text: h.steps.join(" "), score: s + 2, body: <Steps h={h} words={hlWords} /> });
    }
    for (const m of MENUS) {
      const s = score(groups, m.title, m.key, m.purpose + " " + m.when);
      if (s) out.push({ kind: "Menu", id: "m-" + m.key, title: m.title, text: m.purpose, menu: m, score: s, body: <MenuCard m={m} words={hlWords} open /> });
      for (const c of m.controls) {
        const sc = score(groups, c.name, m.title, c.desc);
        if (sc) out.push({
          kind: "Tombol", id: `c-${m.key}-${c.name}`, title: `${c.name}`, text: c.desc, menu: m, score: sc,
          body: <div className="small"><div><Hl text={c.desc} words={hlWords} /></div>
            <div className="row" style={{ marginTop: 6 }}><span className="chip">{t("di menu")}{" "}{m.title}</span>{c.who && <span className="chip">{t("Peran:")}{" "}{c.who}</span>}
              {m.key !== "panduan" && <Link to={m.path} className="chip guide-go">{t("Buka menu →")}</Link>}</div></div>,
        });
      }
    }
    for (const l of LIMITS) {
      const s = score(groups, l.title, (l.keywords || "") + " batasan " + l.group, l.desc + " " + l.impact);
      if (s) out.push({ kind: "Batasan", id: "l-" + l.id, title: l.title, text: l.desc, score: s + 1, body: <LimitView l={l} words={hlWords} /> });
    }
    for (const r of LIVE_REQS) {
      const s = score(groups, r.title, (r.keywords || "") + t(" syarat live monitor realtime"), r.need + " " + r.ifMissing);
      if (s) out.push({ kind: "Syarat", id: "r-" + r.id, title: r.title, text: r.need, menu: menuOf(r.where), score: s + 1, body: <ReqView r={r} words={hlWords} /> });
    }
    for (const t of TERMS) {
      const s = score(groups, t.term, t.keywords || "", t.desc);
      if (s) out.push({ kind: "Istilah", id: "t-" + t.term, title: t.term, text: t.desc, score: s, body: <div className="small"><Hl text={t.desc} words={hlWords} /></div> });
    }
    for (const f of FLOWS) {
      const s = score(groups, f.title, f.who, f.steps.map((x) => x.label + " " + x.text).join(" "));
      if (s) out.push({ kind: "Alur", id: "f-" + f.id, title: f.title, text: "", score: s - 1, body: <FlowView f={f} /> });
    }
    const code = (m?: MenuGuide) => (m ? norm(m.title.split(" ")[0]) : "");
    for (const h of out) {
      const m = h.menu || (h.kind === "Cara" ? menuOf(HOWTOS.find((x) => "h-" + x.id === h.id)?.menu) : undefined);
      if (ctx.codes.size && ctx.codes.has(code(m))) h.score += 5;
      if (ctx.btn && h.kind === "Tombol") h.score += 4;
      if (ctx.menu && h.kind === "Menu") h.score += 2;
    }
    out.sort((a, b) => b.score - a.score);
    const top = out[0]?.score || 0;
    return out.filter((h) => h.score >= top * 0.4).slice(0, 20);  // buang kecocokan lemah
  }, [groups, hlWords, ctx]);

  return (
    <>
      <div className="top"><h1>{t("Panduan")}</h1><span className="muted small">{t("alur kerja · menu & tombol · cara melakukan sesuatu · batasan sistem · syarat Live Monitor · istilah")}</span></div>

      <div className="card guide-search">
        <label htmlFor="guide-q" className="small muted">{t("Cari cara melakukan sesuatu")}</label>
        <div className="guide-input">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></svg>
          <input id="guide-q" type="search" autoFocus value={q} onChange={(e) => setQuery(e.target.value)} placeholder={t("mis. cek hasil training, upload file, approve PPFG, kenapa UNAVAILABLE…")} />
          {q && <button type="button" className="guide-clear" onClick={() => setQuery("")} aria-label={t("Hapus pencarian")}>×</button>}
        </div>
        <div className="row small" style={{ marginTop: 8, gap: 6 }}>
          <span className="muted">{t("Contoh:")}</span>
          {SUGGEST.map((s) => <button key={s} type="button" className="chip guide-sug" onClick={() => setQuery(s)}>{s}</button>)}
        </div>
      </div>

      {words.length > 0 || hits.length > 0 ? (
        <div style={{ marginTop: 12 }}>
          <div className="muted small" style={{ marginBottom: 8 }}>{hits.length ? t("{p0} hasil untuk \"{p1}\"", { p0: hits.length, p1: q }) : t("Tidak ada hasil untuk \"{p0}\". Coba kata lain, mis. \"training\", \"upload\", \"laporan\", \"event\".", { p0: q })}</div>
          <div className="grid">
            {hits.map((h) => h.kind === "Menu" ? <div key={h.id}>{h.body}</div> : (
              <div key={h.id} className="card">
                <div className="row" style={{ marginBottom: 6 }}><span className={`lvl guide-kind k-${h.kind}`}>{t(h.kind)}</span><b><Hl text={h.title} words={hlWords} /></b>
                  {h.kind === "Tombol" && h.menu && <span className="muted small">· {h.menu.title}</span>}</div>
                {h.body}
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 12 }}>
          <div className="tabs" role="tablist">
            {([["alur", t("Alur kerja")], ["menu", t("Menu & tombol")], ["cara", t("Cara melakukan…")], ["batasan", t("Batasan sistem")], ["live", t("Syarat Live Monitor")], ["istilah", t("Istilah")]] as const).map(([k, l]) =>
              <button key={k} role="tab" aria-selected={tab === k} className={tab === k ? "on" : ""} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          {tab === "alur" && <div className="grid">{FLOWS.map((f) => <div key={f.id} className="card"><h3>{f.title} <span className="muted small" style={{ fontWeight: 400 }}>· {f.who}</span></h3><FlowView f={f} /></div>)}</div>}
          {tab === "menu" && <div className="grid">{MENUS.map((m) => <MenuCard key={m.key} m={m} words={[]} />)}</div>}
          {tab === "cara" && <div className="grid">{HOWTOS.map((h) => (
            <details key={h.id} className="card guide-menu"><summary><b>{h.title}</b></summary><div style={{ marginTop: 8 }}><Steps h={h} words={[]} /></div></details>
          ))}</div>}
          {tab === "batasan" && <LimitsTab />}
          {tab === "live" && <LiveTab />}
          {tab === "istilah" && <div className="card"><table><tbody>{TERMS.map((t) => <tr key={t.term}><td style={{ width: "24%" }}><b>{t.term}</b></td><td className="small">{t.desc}</td></tr>)}</tbody></table></div>}
        </div>
      )}
    </>
  );
}

function FlowView({ f }: { f: (typeof FLOWS)[number] }) {
  return (
    <div className="guide-flow">
      {f.steps.map((s, i) => {
        const m = menuOf(s.menu);
        return (
          <div key={i} className="guide-step">
            <div className="guide-num">{i + 1}</div>
            <div>
              <b>{s.label.replace(/^\d+\.\s*/, "")}</b>
              <div className="small muted">{s.text}</div>
              {m && <Link to={m.path} className="small">{m.title} →</Link>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LimitView({ l, words }: { l: Limit; words: string[] }) {
  return (
    <div className="small">
      <div><Hl text={l.desc} words={words} /></div>
      <div className="guide-impact"><b>{t("Artinya bagi user:")}</b> <Hl text={l.impact} words={words} /></div>
      <div className="row" style={{ marginTop: 6 }}><span className="chip">{l.group}</span></div>
    </div>
  );
}

function ReqView({ r, words }: { r: Req; words: string[] }) {
  const m = menuOf(r.where);
  return (
    <div className="small">
      <div><b>{t("Yang dibutuhkan:")}</b> <Hl text={r.need} words={words} /></div>
      <div className="guide-impact"><b>{t("Bila tidak terpenuhi:")}</b> <Hl text={r.ifMissing} words={words} /></div>
      <div className="row" style={{ marginTop: 6 }}>
        <span className={`lvl ${r.required ? "k-wajib" : "k-opsional"}`}>{r.required ? t("Wajib") : t("Opsional / disarankan")}</span>
        {m && <Link to={m.path} className="chip guide-go">{t("Buka")}{" "}{m.title} →</Link>}
      </div>
    </div>
  );
}

function LimitsTab() {
  const groups = Array.from(new Set(LIMITS.map((l) => l.group)));
  return (
    <div className="grid">
      <div className="note">{t("Bagian ini menjelaskan apa yang")}{" "}<b>{t("tidak")}</b>{" "}{t("bisa dilakukan sistem dan seberapa jauh hasilnya bisa dipercaya, supaya harapan user sesuai kemampuan sistem. Angka akurasi per 22 Nov 2026 (model ecd-rf v1); akan berubah setelah training ulang.")}</div>
      {groups.map((g) => (
        <div key={g} className="card">
          <h3>{g}</h3>
          <div className="grid">{LIMITS.filter((l) => l.group === g).map((l) => (
            <details key={l.id} className="guide-menu guide-limit"><summary><b>{l.title}</b></summary><div style={{ marginTop: 6 }}><LimitView l={l} words={[]} /></div></details>
          ))}</div>
        </div>
      ))}
    </div>
  );
}

function LiveTab() {
  return (
    <div className="grid">
      <div className="note">{t("Live Monitor bukan koneksi langsung ke Navita dan bukan pengganti tampilan realtime Navita. Aplikasi ini lapisan analisa (ECD ⓥ, margin, anomali, bending) di atas data ekspor Navita, sehingga sifatnya near-realtime: tertinggal sebesar interval ekspor. Monitor terus terbarui bila file ekspor Navita terus masuk ke folder pantau server. Checklist di bawah menjelaskan apa yang harus ada, dan apa gejalanya bila tidak terpenuhi.")}</div>
      <div className="card">
        <h3>{t("Alur data realtime")}</h3>
        <div className="guide-flow">
          {[[t("Navita di rig"), t("Data rig + manual entry MW (Rec 04) oleh RTO")], [t("Ekspor berkala"), t("Rec 01 Time (+ Rec 02 bila ada PWD), tiap 1–5 menit")],
            [t("Folder pantau server"), t("data/inbox/<nama sumur>/ — dipindai tiap 60 detik")], [t("Ingest + QC"), t("Data masuk database, temuan QC dicatat")],
            [t("Analisis"), t("State, ECD ⓥ, margin, detektor anomali, level alert")], [t("Layar"), t("Live Monitor refresh 30 dtk, Overview 60 dtk")]].map(([a, b], i) => (
            <div key={i} className="guide-step"><div className="guide-num">{i + 1}</div><div><b>{a}</b><div className="small muted">{b}</div></div></div>
          ))}
        </div>
      </div>
      <div className="card">
        <h3>{t("Checklist syarat")}</h3>
        <table><thead><tr><th style={{ width: "26%" }}>{t("Syarat")}</th><th>{t("Yang dibutuhkan")}</th><th style={{ width: "30%" }}>{t("Bila tidak terpenuhi")}</th></tr></thead>
          <tbody>{LIVE_REQS.map((r) => (
            <tr key={r.id}><td><b>{r.title}</b><div style={{ marginTop: 4 }}><span className={`lvl ${r.required ? "k-wajib" : "k-opsional"}`}>{r.required ? t("Wajib") : t("Opsional")}</span></div></td>
              <td className="small">{r.need}</td><td className="small muted">{r.ifMissing}</td></tr>
          ))}</tbody></table>
      </div>
    </div>
  );
}
