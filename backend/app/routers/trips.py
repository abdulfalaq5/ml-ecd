"""Trip performance: in-slip / out-of-slip per stand, per trip, per interval kedalaman (halaman 'Trip Performance')."""
from __future__ import annotations

from datetime import timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..core import sections as sec
from ..core import trips as tp
from ..core.data import load_survey, load_time, time_range
from ..ingest.parser import min_curvature
from ..db import get_db
from ..models import Setting, User
from ..security import audit, current_user, require
from .monitor import _t, _well

router = APIRouter(prefix="/api", tags=["trips"])
TARGET_KEY = "trip_targets"
DEFAULT_SPAN = timedelta(days=7)
MAX_SPAN = timedelta(days=14)
CHANNELS = ["hookload", "bit_depth", "hole_depth", "flow_in"]


def trip_frame(db: Session, wid: int, t0, t1) -> pd.DataFrame:
    """Resolusi 2 detik (data 1 detik dirata-rata 2 detik; data lebih jarang tetap per sampel aslinya)."""
    return load_time(db, wid, t0, t1, bucket_s=2, channels=CHANNELS)


def targets(db: Session) -> dict:
    s = db.get(Setting, TARGET_KEY)
    return tp.merge_targets(s.value if s else None)


@router.get("/trip-targets")
def get_targets(db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = db.get(Setting, TARGET_KEY)
    return {"value": targets(db), "defaults": tp.merge_targets(None), "updated_by": s.proposed_by if s else "",
            "updated_at": s.updated_at.isoformat() if s and s.updated_at else None}


class TargetsIn(BaseModel):
    value: dict


def _num(v, lo, hi, name):
    if v in (None, ""):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{name} harus angka")
    if not lo < x <= hi:
        raise HTTPException(400, f"{name} di luar rentang wajar ({lo}–{hi})")
    return x


@router.put("/trip-targets")
def put_targets(body: TargetsIn, db: Session = Depends(get_db), u: User = Depends(require("threshold_propose"))):
    """Target trip diisi manual dan boleh diubah kapan saja (tanpa alur persetujuan); tercatat di audit log."""
    v = body.value
    clean = {"gross_ft_h": _num(v.get("gross_ft_h"), 0, 5000, "Gross speed")}
    lim = {"jph": (0, 60), "in_min": (0, 60), "move_min": (0, 60)}
    for unit in tp.UNITS:
        clean[unit] = {}
        for loc in ("cased", "open"):
            d = (v.get(unit) or {}).get(loc) or {}
            clean[unit][loc] = {k: _num(d.get(k), *lim[k], f"{unit}/{loc}/{k}") for k in lim}
    s = db.get(Setting, TARGET_KEY) or Setting(key=TARGET_KEY, value={})
    s.value, s.status, s.proposed_by = clean, "active", u.username
    db.merge(s)
    audit(db, u.username, "trip_targets", str(clean))
    db.commit()
    return get_targets(db, u)


@router.get("/wells/{wid}/trips")
def trip_performance(wid: int, t0: str | None = None, t1: str | None = None,
                     unit: str = Query("stand", pattern="^(stand|joint)$"), db: Session = Depends(get_db),
                     _: User = Depends(current_user)):
    w = _well(db, wid)
    lo, hi = time_range(db, w.id)
    if lo is None:
        return {"empty": True}
    b = min(_t(t1) or hi, hi)
    a = max(_t(t0) or (b - DEFAULT_SPAN), lo)
    if b <= a:
        raise HTTPException(400, "Rentang waktu tidak valid")
    if b - a > MAX_SPAN:
        raise HTTPException(400, f"Rentang maksimal {MAX_SPAN.days} hari (data 1–2 detik)")
    df = trip_frame(db, w.id, a, b)
    # shoe: section yang aktif di akhir periode (lubang terdalam), selain itu shoe sumur
    hmax = float(df["hole_depth"].max()) if "hole_depth" in df and df["hole_depth"].notna().any() else None
    shoe = (sec.section_at(w.sections, hmax, b) or {}).get("shoe_md") or w.shoe_md
    res = tp.analyze(df, shoe_md=shoe, unit=unit, targets=targets(db))
    return {"empty": False, "well": w.name, "t0": pd.Timestamp(a).isoformat(), "t1": pd.Timestamp(b).isoformat(),
            "data_start": pd.Timestamp(lo).isoformat(), "data_end": pd.Timestamp(hi).isoformat(), "shoe_md": shoe, **res}


@router.get("/wells/{wid}/deviation")
def deviation(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Kolom 'Deviation data' (format SLB hal. 5): inklinasi & DLS per stasiun survey vs MD.
    DLS / TVD yang kosong dihitung minimum curvature dari MD, Inc, Azi."""
    w = _well(db, wid)
    sv = load_survey(db, w.id).dropna(subset=["md", "inc"]).sort_values("md").drop_duplicates("md").reset_index(drop=True)
    sv = sv.apply(pd.to_numeric, errors="coerce").astype(float)
    computed = False
    if len(sv) >= 2 and sv["azi"].notna().all() and (sv["dls"].iloc[1:].isna().any() or sv["tvd"].isna().any()):
        tvd, dls = min_curvature(sv["md"], sv["inc"], sv["azi"], float(sv["tvd"].iloc[0]) if pd.notna(sv["tvd"].iloc[0]) else None)
        sv["tvd"] = sv["tvd"].fillna(pd.Series(tvd))
        sv["dls"] = sv["dls"].fillna(pd.Series(dls))
        computed = True
    sects = [{"from_md": s.get("from_md"), "hole_size": s.get("hole_size"), "shoe_md": s.get("shoe_md")} for s in (w.sections or [])]
    r = lambda v, k=2: None if pd.isna(v) else round(float(v), k)
    return {"well": w.name, "n": int(len(sv)), "dls_computed": computed, "shoe_md": w.shoe_md, "sections": sects,
            "survey": [{"md": r(x.md, 1), "tvd": r(x.tvd, 1), "inc": r(x.inc), "azi": r(x.azi), "dls": r(x.dls)} for x in sv.itertuples()],
            "dls_max": r(sv["dls"].max()) if len(sv) else None, "inc_max": r(sv["inc"].max()) if len(sv) else None}
