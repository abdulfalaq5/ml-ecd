"""Laporan: ringkasan otomatis + narasi AI opsional (hanya RINGKASAN hasil yang dikirim, bukan data mentah)."""
from __future__ import annotations

import io
import json
import logging
from datetime import datetime

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..core.analysis import compute, f
from ..models import Event, IngestFile, MLModel, Well

log = logging.getLogger("report")
KINDS = {"daily": "Laporan Harian ECD", "event": "Laporan Event / Studi Kasus",
         "model": "Laporan Evaluasi Model", "qc": "Laporan QC Data",
         "rathole": "Studi Kasus Rathole (H1–H3)"}


# Aturan state (app/core/features.derive_state), ditulis untuk pembaca laporan. Ambang dari konfigurasi sistem.
STATE_RULES = {
    "DRILL_ROT": "pompa hidup, bit di dasar, putar, ROP > 0",
    "SLIDE": "pompa hidup, bit di dasar, tanpa putar, ROP > 0",
    "REAM": "pompa hidup, bit di atas dasar, pipa bergerak, putar",
    "WASH": "pompa hidup, bit di atas dasar, pipa bergerak, tanpa putar",
    "CIRC": "pompa hidup, pipa diam (atau di dasar tanpa ROP)",
    "TRIP": "pompa mati, pipa bergerak",
    "STATIC": "pompa mati, pipa diam (stand down, sambung pipa, flow check)",
    "UNKNOWN": "kanal bit depth & flow kosong",
}


STATE_MAX_GAP_S = 300      # sampel berlaku sampai sampel berikutnya, maks 5 menit; jeda lebih lama = tanpa data


def state_table(db: Session, well: Well, t0, t1) -> list[dict]:
    """Jam per state operasi (berbobot durasi). Data surface di-bucket 30 detik (resolusi training), tiap baris diberi
    satu state (app/core/features.derive_state) dan berlaku sampai baris berikutnya, maks STATE_MAX_GAP_S. Jadi rekaman
    jarang (rig LAS PDSI ±1 sampel/menit) tidak terhitung sebagai 'tanpa data'. Sisa periode = tanpa data."""
    from ..config import get_settings
    from ..core.data import load_time, time_range
    from ..core.features import PUMPS_ON_STATES, STATES, derive_state
    cfg = get_settings()
    lo, hi = time_range(db, well.id)
    if lo is None:
        return []
    a = pd.Timestamp(t0 or lo)
    b = pd.Timestamp(t1 or hi)
    df = load_time(db, well.id, a, b, bucket_s=30)
    if df.empty:
        return []
    st = derive_state(df)
    nxt = df.index.to_series().shift(-1).fillna(min(b, df.index[-1] + pd.Timedelta(seconds=30)))
    dur = (nxt - df.index.to_series()).dt.total_seconds().clip(lower=0, upper=STATE_MAX_GAP_S)
    ecd_ok = df["ecd"].between(7, 20) if "ecd" in df else pd.Series(False, index=df.index)
    span_h = max((b - a).total_seconds() / 3600, 0)
    order = ["DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC", "TRIP", "STATIC", "UNKNOWN"]
    hours = (dur.groupby(st).sum() / 3600)
    rows, used = [], 0.0
    for k in sorted(hours.index, key=lambda x: order.index(x) if x in order else 99):
        h = float(hours[k])
        used += h
        rows.append({"state": k, "operasi": STATES.get(k, k), "pompa": "hidup" if k in PUMPS_ON_STATES else "mati",
                     "aturan": STATE_RULES.get(k, ""), "jam": round(h, 1),
                     "persen": round(100 * h / span_h, 1) if span_h else None,
                     "jam_ecd_terukur": round(float(dur[(st == k) & ecd_ok].sum()) / 3600, 1)})
    gap = span_h - used
    if gap >= 0.1:
        rows.append({"state": "—", "operasi": "Tanpa data (jeda rekaman / di luar rentang data)", "pompa": "", "aturan": "",
                     "jam": round(gap, 1), "persen": round(100 * gap / span_h, 1) if span_h else None, "jam_ecd_terukur": 0.0})
    rows.append({"state": "", "operasi": f"Cara hitung: data surface per 30 detik diberi satu state; tiap baris berlaku sampai "
                 f"baris berikutnya (maks {STATE_MAX_GAP_S // 60} menit). Ambang: flow > {cfg.flow_min_gpm:g} gpm, di dasar ≤ "
                 f"{cfg.on_bottom_ft:g} ft dari hole depth, bergerak > {cfg.block_move_ft_s:g} ft/s, putar > {cfg.rpm_min:g} RPM.",
                 "pompa": "", "aturan": "", "jam": None, "persen": None, "jam_ecd_terukur": None})
    return rows


def build_summary(db: Session, kind: str, well: Well | None, t0: datetime | None, t1: datetime | None) -> tuple[dict, pd.DataFrame | None]:
    s: dict = {"kind": kind, "title": KINDS.get(kind, kind), "well": well.name if well else None,
               "period": [t0.isoformat() if t0 else None, t1.isoformat() if t1 else None]}
    frame = None
    if kind in ("daily", "event") and well:
        r = compute(db, well, t0, t1, points=3000)
        if not r.get("empty"):
            df = r["df_full"]  # resolusi hitung penuh: menit per level/state dihitung akurat
            frame = df
            ref = df["ecd_ref"].dropna()
            mu = pd.concat([df.get("margin_up_bit"), df.get("margin_up_oh")], axis=1).min(axis=1).dropna() if "margin_up_bit" in df else pd.Series(dtype=float)
            step = r["calc_bucket_s"]
            s.update({
                "ecd_mean": f(ref.mean()), "ecd_max": f(ref.max()),
                "ecd_source": "terukur" if df["ecd"].notna().any() else "prediksi ⓥ",
                "margin_up_min": f(mu.min()) if len(mu) else None,
                "margin_low_min": f(df["margin_low"].min()) if "margin_low" in df else None,
                "level_minutes": {k: round(int(v) * step / 60) for k, v in df["level"].value_counts().items()},
                "state_minutes": {k: round(int(v) * step / 60) for k, v in df["state"].value_counts().items()},
                "state_table": state_table(db, well, t0, t1),
                "detections": [{k: d.get(k) for k in ("start", "level", "label", "md", "summary", "rec")} for d in r["detections"]][:60],
                "model": f"ecd-{r['model'].algo} v{r['model'].version} ({r['model'].status})" if r["model"] else None,
                "ppfg": f"Rec 03 v{r['ppfg'].version} ({r['ppfg'].status})" if r["ppfg"] else "belum ada PPFG approved",
                "data_minutes": round(len(df) * step / 60),
            })
        evq = select(Event).where(Event.well_id == well.id)
        if t0:
            evq = evq.where(Event.onset >= t0)
        if t1:
            evq = evq.where(Event.onset <= t1)
        s["events"] = [{"onset": e.onset.isoformat(), "level": e.level, "category": e.category,
                        "review": e.review_status, "md": e.md} for e in db.scalars(evq.order_by(Event.onset))]
    elif kind == "rathole" and well:
        from ..core.rathole import analyze
        a = analyze(db, well)
        p1, p2 = a.get("phase1") or {}, a.get("phase2") or {}
        s.update({
            "well_section": a.get("section"), "shoe_md": a.get("shoe_md"), "rathole": a.get("rathole"),
            "model": a.get("model"), "message": a.get("message"),
            "phase1": {k: v for k, v in p1.items() if k not in ("series", "daily")} or None,
            "phase2": {k: v for k, v in p2.items() if k not in ("series", "daily", "detections")} or None,
            "phase1_daily": p1.get("daily"), "phase2_daily": p2.get("daily"),
            "zone_table": a.get("zone_table"), "events": a.get("events"), "caveats": a.get("caveats"),
        })
    elif kind == "model":
        m = db.scalar(select(MLModel).where(MLModel.status.in_(["production", "shadow", "candidate"])).order_by(MLModel.id.desc()))
        if m:
            s["model"] = {"name": f"ecd-{m.algo} v{m.version}", "status": m.status, "train_wells": m.train_wells,
                          "blind_wells": m.blind_wells, "metrics": m.metrics, "importance": m.importance, "gates": m.gates}
    elif kind == "qc":
        q = select(IngestFile)
        if well:
            q = q.where(IngestFile.well_id == well.id)
        s["files"] = [{"file": r.filename, "record": r.record, "basis": r.basis, "rows": r.rows, "qc": r.qc}
                      for r in db.scalars(q.order_by(IngestFile.id.desc()).limit(200))]
    return s, frame


SYSTEM = (
    "Anda menulis paragraf ringkasan untuk laporan monitoring ECD pengeboran (PHR). "
    "Tulis dalam Bahasa Indonesia, 1–2 paragraf pendek, gaya teknis netral. "
    "Gunakan hanya angka yang ada di data ringkasan; jangan menebak penyebab atau memberi perintah operasi. "
    "Sebut ECD prediksi sebagai 'estimasi' bila sumbernya prediksi. Akhiri dengan hal yang perlu diverifikasi engineer."
)


def ai_enabled() -> bool:
    """AI dipakai hanya bila ANTHROPIC_API_KEY diisi di .env."""
    return bool(get_settings().anthropic_api_key.strip())


def ai_narrative(summary: dict) -> tuple[str | None, str | None]:
    """(teks, None) bila sukses; (None, alasan) bila AI tidak tersedia / gagal."""
    s = get_settings()
    if not ai_enabled():
        return None, "API key AI belum diisi"
    try:
        import anthropic
    except ImportError:
        return None, "library anthropic tidak terpasang"

    slim = {k: v for k, v in summary.items() if k not in ("files", "narrative_source", "narrative_note")}
    client = anthropic.Anthropic(api_key=s.anthropic_api_key.strip())
    try:
        resp = client.messages.create(
            model=s.ai_model,
            max_tokens=4000,
            system=SYSTEM,
            messages=[{"role": "user", "content": "Data ringkasan (JSON):\n" + json.dumps(slim, ensure_ascii=False, default=str)}],
        )
    except anthropic.AuthenticationError:
        return None, "API key AI ditolak (cek ANTHROPIC_API_KEY)"
    except anthropic.APIConnectionError:
        log.exception("AI: koneksi gagal")
        return None, "koneksi ke layanan AI gagal"
    except anthropic.RateLimitError:
        return None, "batas pemakaian AI tercapai, coba lagi nanti"
    except anthropic.APIStatusError as e:
        log.exception("AI: error API")
        return None, f"layanan AI error {e.status_code}"
    if resp.stop_reason == "refusal":
        return None, "AI menolak membuat narasi"
    text = "\n".join(b.text for b in resp.content if b.type == "text").strip()
    return (text, None) if text else (None, "AI tidak mengembalikan teks")


# ---------------- narasi otomatis tanpa AI (templat dari angka ringkasan) ----------------

def _wib(iso) -> str:
    if not iso:
        return "—"
    return pd.Timestamp(iso).tz_convert(get_settings().display_tz).strftime("%d %b %Y %H:%M")


def _n(v, d=2) -> str:
    return "—" if v is None else f"{float(v):.{d}f}"


def _top(items: list, key: str, k: int = 3) -> str:
    cnt: dict = {}
    for x in items or []:
        cnt[x.get(key)] = cnt.get(x.get(key), 0) + 1
    return ", ".join(f"{a} ({b})" for a, b in sorted(cnt.items(), key=lambda t: -t[1])[:k])


def template_narrative(s: dict) -> str:
    kind, well = s.get("kind"), s.get("well") or "—"
    per = s.get("period") or [None, None]
    lines: list[str] = []
    if kind in ("daily", "event"):
        if s.get("ecd_mean") is None and not s.get("detections"):
            return f"Tidak ada data untuk sumur {well} pada periode yang dipilih."
        lines.append(f"Sumur {well}, periode " + (f"{_wib(per[0])} – {_wib(per[1])} WIB " if per[0] and per[1] else "default (data terakhir) ") +
                     f"({s.get('data_minutes', 0)} menit data). ECD {s.get('ecd_source', '—')} rata-rata {_n(s.get('ecd_mean'))} ppg, "
                     f"maksimum {_n(s.get('ecd_max'))} ppg.")
        if s.get("margin_up_min") is not None or s.get("margin_low_min") is not None:
            lines.append(f"Margin atas minimum {_n(s.get('margin_up_min'))} ppg dan margin bawah minimum {_n(s.get('margin_low_min'))} ppg ({s.get('ppfg')}).")
        else:
            lines.append(f"Margin terhadap FG/batas bawah belum dihitung ({s.get('ppfg') or 'PPFG belum approved'}).")
        lv = {k: v for k, v in (s.get("level_minutes") or {}).items() if k != "NORMAL" and v}
        if lv:
            lines.append("Waktu pada level di atas NORMAL: " + ", ".join(f"{k} {v} mnt" for k, v in lv.items()) + ".")
        det = s.get("detections") or []
        if det:
            lines.append(f"Terdeteksi {len(det)} indikasi; terbanyak: {_top(det, 'label')}.")
        else:
            lines.append("Tidak ada indikasi anomali terdeteksi pada data yang tersedia.")
        ev = s.get("events") or []
        if ev:
            lines.append(f"Event tercatat pada periode ini: {len(ev)} ({_top(ev, 'category')}).")
        lines.append(f"Model: {s.get('model') or 'belum ada model aktif'}.")
        lines.append("Perlu diverifikasi engineer: setiap indikasi di atas terhadap kondisi rig (returns, cuttings, pit, laporan lumpur) sebelum disimpulkan.")
    elif kind == "model":
        m = s.get("model")
        if not m:
            return "Belum ada model untuk dievaluasi."
        met = m.get("metrics") or {}
        ex = met.get("experiments") or {}
        ch = met.get("chosen")
        lines.append(f"Model {m.get('name')} (status {m.get('status')}), dilatih pada {', '.join(m.get('train_wells') or []) or '—'}; "
                     f"sumur blind: {', '.join(m.get('blind_wells') or []) or '—'}. Algoritma terpilih: {ch or '—'} (dipilih dari {met.get('selection', 'LOWO')}).")
        base, best = ex.get("mw_only") or {}, ex.get(ch) or {}
        if best:
            lines.append(f"MAE LOWO {_n((best.get('lowo') or {}).get('mae'), 3)} ppg vs baseline MW-only {_n((base.get('lowo') or {}).get('mae'), 3)} ppg; "
                         f"MAE blind {_n((best.get('blind') or {}).get('mae'), 3)} ppg vs MW-only {_n((base.get('blind') or {}).get('mae'), 3)} ppg.")
            bw = best.get("blind_per_well") or {}
            if bw:
                lines.append("Per sumur blind: " + "; ".join(f"{w} MAE {_n(v.get('mae'), 3)} (bias {_n(v.get('bias'), 3)})" for w, v in bw.items()) + ".")
        g = m.get("gates") or {}
        lines.append(f"Promotion gate terpenuhi {sum(bool(v) for v in g.values())}/6.")
        lines.append("Perlu diverifikasi engineer: akurasi per operating state (terutama clean-out) dan sumur blind sebelum promosi.")
    elif kind == "qc":
        f = s.get("files") or []
        bad = [x for x in f if any((q or {}).get("level") in ("warn", "error", "critical") for q in (x.get("qc") or []))]
        lines.append(f"{len(f)} file ter-ingest{' untuk sumur ' + well if s.get('well') else ''}, {len(bad)} file dengan peringatan QC (level warn/error).")
        if bad:
            lines.append("Contoh file dengan temuan: " + "; ".join(x.get("file", "") for x in bad[:5]) + ".")
        lines.append("Perlu diverifikasi: temuan QC sebelum QC sign-off.")
    elif kind == "rathole":
        if s.get("message"):
            return s["message"]
        rh, p1, p2 = s.get("rathole") or {}, s.get("phase1") or {}, s.get("phase2") or {}
        lines.append(f"Sumur {well} (section {s.get('well_section') or '—'}): zona rathole {_n(rh.get('top_md'), 0)}–{_n(rh.get('base_md'), 0)} ftMD "
                     f"({_n(rh.get('length_ft'), 0)} ft open hole) berlaku sejak {_wib(rh.get('since'))} WIB.")
        if p1:
            ir = p1.get("in_rathole_depth") or {}
            lines.append(f"Fase 1 ({_wib(p1.get('t0'))} – {_wib(p1.get('t1'))}, ECD terukur tersedia): ECD ⓥ vs terukur MAE {_n(p1.get('mae'), 3)} ppg, "
                         f"bias {_n(p1.get('bias'), 3)} ppg, {_n(p1.get('coverage_pct'), 0)}% titik di dalam interval (n={p1.get('n')}). "
                         + (f"Saat bit di kedalaman rathole: MAE {_n(ir.get('mae'), 3)}, bias {_n(ir.get('bias'), 3)}, ECD−MW {_n(ir.get('ecd_minus_mw_med'))} ppg." if ir else ""))
        if p2:
            d = [x for x in (s.get("phase2_daily") or []) if x.get("spp_per_100gpm") and (x.get("pump_minutes") or 0) >= 240]  # hari dengan pompa ≥ 4 jam saja
            lines.append(f"Fase 2 (sejak {_wib(p2.get('t0'))}): pompa hidup {_n((p2.get('pump_minutes') or 0) / 60, 1)} jam, "
                         f"{_n((p2.get('rathole_pump_minutes') or 0) / 60, 1)} jam di zona rathole; ECD ⓥ median {_n(p2.get('ecd_pred_med'))} ppg (maks {_n(p2.get('ecd_pred_max'))}).")
            if len(d) >= 2:
                lines.append(f"SPP per 100 gpm berubah dari {_n(d[0]['spp_per_100gpm'], 0)} ({d[0]['date']}) ke {_n(d[-1]['spp_per_100gpm'], 0)} psi ({d[-1]['date']}).")
        zt = s.get("zone_table") or []
        if zt:
            tot_r, tot_a = sum(z.get("rathole", 0) for z in zt), sum(z.get("atas_shoe", 0) for z in zt)
            top = sorted(zt, key=lambda z: -z.get("rathole", 0))[:3]
            lines.append(f"Indikasi fase 2: {tot_r} di zona rathole vs {tot_a} di atas shoe; terbanyak di rathole: "
                         + ", ".join(f"{z['label']} ({z['rathole']})" for z in top) + ".")
        for c in (s.get("caveats") or [])[:3]:
            lines.append("Catatan: " + c)
        lines.append("Perlu diverifikasi engineer: kecocokan indikasi dengan laporan harian (DDR) dan kondisi lubang aktual.")
    else:
        return ""
    return "\n".join(lines)


def narrate(summary: dict, use_ai: bool = True) -> tuple[str, str, str | None]:
    """Narasi laporan → (teks, sumber 'ai' | 'template', catatan).
    API key kosong (atau use_ai=False) → templat tanpa AI. API key diisi → AI; bila AI gagal, kembali ke templat."""
    if use_ai and ai_enabled():
        text, err = ai_narrative(summary)
        if text:
            return text, "ai", None
        return template_narrative(summary), "template", f"AI gagal ({err}); memakai narasi otomatis tanpa AI"
    return template_narrative(summary), "template", None if use_ai else "AI dimatikan untuk laporan ini"


def to_excel(summary: dict, frame: pd.DataFrame | None) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        flat = {k: (json.dumps(v, ensure_ascii=False, default=str) if isinstance(v, (dict, list)) else v)
                for k, v in summary.items()}
        pd.DataFrame(list(flat.items()), columns=["item", "nilai"]).to_excel(xw, "Ringkasan", index=False)
        if summary.get("detections"):
            pd.DataFrame(summary["detections"]).to_excel(xw, "Deteksi", index=False)
        if summary.get("events"):
            pd.DataFrame(summary["events"]).to_excel(xw, "Event", index=False)
        for key, sheet in (("state_table", "Jam per state operasi"), ("phase1_daily", "Fase 1 harian (ECD terukur)"), ("phase2_daily", "Fase 2 harian (rathole)"),
                           ("zone_table", "Indikasi per zona"), ("caveats", "Catatan")):
            if summary.get(key):
                v = summary[key]
                (pd.DataFrame(v) if isinstance(v[0], dict) else pd.DataFrame({"catatan": v})).to_excel(xw, sheet[:31], index=False)
        if frame is not None and len(frame):
            cols = [c for c in ["state", "bit_depth", "hole_depth", "flow_in", "spp", "rpm", "torque", "hookload",
                                "mw", "ecd", "ecd_pred", "ecd_lo", "ecd_hi", "fg_bit", "lower_bit",
                                "margin_up_bit", "margin_low", "level", "reason"] if c in frame]
            out = frame[cols].copy()
            out.index = out.index.tz_convert(get_settings().display_tz).tz_localize(None)
            out.to_excel(xw, "Data", index_label="waktu (WIB)")
    return buf.getvalue()
