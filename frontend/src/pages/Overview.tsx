import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import { useApp, useFetch } from "../lib/ctx";
import { ago, ft, n, STATE_LABEL, C } from "../lib/fmt";
import { EChart, Err, Level } from "../components/ui";

export default function Overview() {
  const { setWellId } = useApp();
  const nav = useNavigate();
  const { data, err, loading } = useFetch<any[]>(() => api.get("/overview"), [], 60000);
  return (
    <>
      <div className="top"><h1>Overview</h1><span className="muted small">Semua sumur aktif · refresh 60 dtk</span><span className="sp" />{loading && <span className="muted small">memuat…</span>}</div>
      <Err e={err} />
      {data && data.length === 0 && <div className="card empty">Belum ada sumur. Upload data di halaman <a href="/data">Data &amp; Upload</a> atau taruh file di folder inbox.</div>}
      <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))" }}>
        {data?.map((w) => (
          <div key={w.id} className="card" style={{ cursor: "pointer", borderColor: w.level === "CRITICAL" ? "#F3C2C5" : undefined }} onClick={() => { setWellId(w.id); nav("/monitor"); }}>
            <div className="row"><b>{w.name}</b><span className="chip">{w.role}</span><span className="sp" /><Level v={w.level} /></div>
            <div className="muted small" style={{ margin: "4px 0 8px" }}>{w.section || "section ?"} · {w.state ? STATE_LABEL[w.state] || w.state : "—"} · bit {ft(w.bit_depth)} ft</div>
            <div className="row" style={{ gap: 18 }}>
              <div><div className="muted small">ECD {w.ecd_kind === "v" ? "ⓥ" : w.ecd_kind === "m" ? "terukur" : ""}</div><div className="mono" style={{ fontSize: 22, color: C.ecd }}>{n(w.ecd)}</div></div>
              <div><div className="muted small">Margin atas</div><div className="mono" style={{ fontSize: 18 }}>{n(w.margin_up)}</div></div>
              <div><div className="muted small">Margin bawah</div><div className="mono" style={{ fontSize: 18 }}>{n(w.margin_low)}</div></div>
            </div>
            {w.spark?.length > 1 && (
              <EChart height={54} option={{ animation: false, grid: { left: 0, right: 0, top: 4, bottom: 4 }, xAxis: { type: "category", show: false }, yAxis: { type: "value", show: false, scale: true },
                series: [{ type: "line", data: w.spark, showSymbol: false, lineStyle: { color: C.ecd, width: 1.5, type: w.ecd_kind === "v" ? "dashed" : "solid" } }] }} />
            )}
            <div className="small" style={{ marginTop: 6 }}>{w.note}</div>
            <div className="muted small" style={{ marginTop: 4 }}>Data terakhir: {ago(w.fresh_min)}{w.stale ? " · data offline/upload" : ""}</div>
          </div>
        ))}
      </div>
      <p className="note" style={{ marginTop: 16 }}>Normal berarti "tidak ada anomali terdeteksi pada data yang tersedia", bukan izin melanjutkan operasi. Sistem tidak memberi perintah perubahan flow / MW.</p>
    </>
  );
}
