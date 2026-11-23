"""Satu jalur hitung untuk semua halaman: data -> fitur -> ECD ⓥ -> margin -> deteksi -> level."""
from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..anomaly import detectors
from ..config import get_settings
from ..ml.pipeline import active_model, predict_frame
from ..models import MLModel, Setting, Well
from .alerts import RANK, classify, thresholds
from .data import active_ppfg, load_mw, load_survey, load_time, time_range
from .features import add_features
from .margins import add_margins

WARMUP = timedelta(hours=2)  # data sebelum t0 untuk baseline detektor (tetap masa lalu)


def detector_params(db: Session) -> dict:
    s = db.get(Setting, "detectors")
    return {**detectors.DEFAULTS, **(s.value if s else {})}


def pick_bucket(t0: datetime, t1: datetime, points: int) -> int:
    span = max(1.0, (t1 - t0).total_seconds())
    base = get_settings().resample_s
    return int(max(base, np.ceil(span / max(points, 50) / base) * base))


MAX_CALC_ROWS = 25_000  # ±8,7 hari pada 30 dtk; rentang lebih panjang dihitung pada bucket lebih kasar


def calc_bucket(t0: datetime, t1: datetime) -> int:
    """Resolusi hitung (fitur, ECD ⓥ, detektor, alert) — tidak bergantung pada zoom tampilan."""
    return pick_bucket(t0 - WARMUP, t1, MAX_CALC_ROWS)


def thin(df: pd.DataFrame, bucket_s: int) -> pd.DataFrame:
    """Turunkan resolusi untuk tampilan: per bucket ambil baris dengan level terburuk (seri: yang terakhir),
    sehingga alert tidak hilang ketika grafik di-zoom out."""
    if df.empty:
        return df
    key = df.index.floor(f"{bucket_s}s")
    rank = df["level"].map(RANK).fillna(-2).to_numpy() if "level" in df else np.zeros(len(df))
    tmp = pd.DataFrame({"k": key, "r": rank, "i": np.arange(len(df))}).sort_values(["k", "r", "i"])
    pick = np.sort(tmp.groupby("k", sort=False).tail(1)["i"].to_numpy())
    return df.iloc[pick]


def rathole_zone(well: Well, md, ts) -> str | None:
    """'rathole' | 'atas_shoe' | 'bawah_rathole' untuk titik setelah zona rathole berlaku; None bila tidak relevan."""
    r = well.rathole
    if not r or md is None or ts is None or (isinstance(md, float) and np.isnan(md)):
        return None
    if r.get("since") and pd.Timestamp(ts) < pd.Timestamp(r["since"]):
        return None
    if md < r["top_md"]:
        return "atas_shoe"
    return "rathole" if md <= r["base_md"] else "bawah_rathole"


def compute(db: Session, well: Well, t0: datetime | None = None, t1: datetime | None = None,
            points: int = 1500, cutoff: datetime | None = None, model: MLModel | None = None,
            ppfg_version: int | None = None, minutes: int | None = None) -> dict:
    lo, hi = time_range(db, well.id)
    if lo is None:
        return {"empty": True}
    t1 = min(t1 or hi, hi)
    t0 = max(t0 or (t1 - timedelta(minutes=minutes or 60)), lo)
    end = min(cutoff, t1) if cutoff else t1
    cb = calc_bucket(t0, t1)
    df = load_time(db, well.id, t0 - WARMUP, end, bucket_s=cb)
    if df.empty:
        return {"empty": True, "t0": t0, "t1": t1}
    df = add_features(df, load_mw(db, well.id), load_survey(db, well.id), well.sections)
    rec = model or active_model(db)
    df = predict_frame(rec, df)
    ver, ppfg = active_ppfg(db, well.id, ppfg_version)
    df = add_margins(df, ppfg, well.shoe_md)
    det = detectors.run(df, detector_params(db))
    df["risk"] = det["score"]
    df = classify(df, thresholds(db), det["detections"])
    full = df[df.index >= t0]
    bucket = pick_bucket(t0, t1, points)
    view = thin(full, bucket) if bucket > cb and len(full) > points else full
    dets = [d for d in det["detections"] if pd.Timestamp(d["end"]) >= t0]
    for d in dets:
        d["zone"] = rathole_zone(well, d.get("md"), d.get("start"))
    return {"empty": False, "df": view, "df_full": full, "calc_bucket_s": cb, "detections": dets, "model": rec,
            "ppfg": ver, "ppfg_rows": ppfg, "bucket_s": max(bucket, cb) if view is not full else cb,
            "t0": t0, "t1": t1, "data_start": lo, "data_end": hi, "cutoff": cutoff}


def f(v, nd=2):
    if v is None:
        return None
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(v, (np.floating, float)):
        return round(float(v), nd)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def series(df: pd.DataFrame, cols: list[str], nd: int = 3) -> dict:
    out = {"t": [t.isoformat() for t in df.index]}
    for c in cols:
        if c in df:
            s = df[c]
            if s.dtype == object:
                out[c] = [None if (x is None or (isinstance(x, float) and np.isnan(x))) else x for x in s.tolist()]
            else:
                out[c] = [None if pd.isna(x) else round(float(x), nd) for x in s.to_numpy()]
    return out
