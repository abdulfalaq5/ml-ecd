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
                "detections": [{k: d[k] for k in ("start", "level", "label", "md", "rec")} for d in r["detections"]][:60],
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


def ai_narrative(summary: dict) -> str:
    s = get_settings()
    if not s.anthropic_api_key:
        return ""
    import anthropic

    slim = {k: v for k, v in summary.items() if k not in ("files",)}
    client = anthropic.Anthropic(api_key=s.anthropic_api_key)
    try:
        resp = client.beta.messages.create(
            model=s.ai_model,
            max_tokens=16000,
            system=SYSTEM,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": "Data ringkasan (JSON):\n" + json.dumps(slim, ensure_ascii=False, default=str)}],
        )
    except anthropic.APIConnectionError:
        log.exception("AI: koneksi gagal")
        return "(narasi AI tidak tersedia: koneksi gagal)"
    except anthropic.RateLimitError:
        return "(narasi AI tidak tersedia: rate limit, coba lagi nanti)"
    except anthropic.APIStatusError as e:
        log.exception("AI: error API")
        return f"(narasi AI tidak tersedia: {e.status_code})"
    if resp.stop_reason == "refusal":
        return "(narasi AI ditolak oleh model; tulis manual)"
    return "\n".join(b.text for b in resp.content if b.type == "text").strip()


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
        for key, sheet in (("phase1_daily", "Fase 1 harian (ECD terukur)"), ("phase2_daily", "Fase 2 harian (rathole)"),
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
