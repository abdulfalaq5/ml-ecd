"""Ramalan ECD berbasis rencana + uji coba (halaman 'Ramalan ECD'). Hanya menghitung, tidak mengubah data."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..core import forecast as fc
from ..core import hydraulics as hy
from ..core import sections as sec
from ..core.alerts import thresholds
from ..core.analysis import f
from ..core.data import active_ppfg, load_mw, load_survey, load_time, time_range
from ..core.features import add_features
from ..db import get_db
from ..ml.pipeline import _load, active_model
from sqlalchemy import select

from ..models import PPFGVersion, User, Well
from ..security import current_user
from .monitor import _model_out, _t, _well

router = APIRouter(prefix="/api/wells", tags=["forecast"])
WARMUP = timedelta(hours=72)        # riwayat sebelum jam mulai: hole depth tercapai (tahan glitch), acuan, sambungan
MAX_HOURS = 48
HIST_SHOW = timedelta(hours=3)


def _frame(db: Session, w: Well, t0, t1) -> pd.DataFrame:
    df = load_time(db, w.id, t0, t1, bucket_s=30)
    if df.empty:
        return df
    return add_features(df, load_mw(db, w.id), load_survey(db, w.id), w.sections)


def _predictor(db: Session):
    rec = active_model(db)
    return rec, fc.predictor_from_artifact(_load(rec) if rec else None)


def _cut(db: Session, w: Well, t_cut: str | None):
    lo, hi = time_range(db, w.id)
    if lo is None:
        raise HTTPException(404, "Sumur belum punya data waktu (Rec 01)")
    c = _t(t_cut) if t_cut else hi
    if c < lo or c > hi:
        raise HTTPException(400, "Jam mulai di luar rentang data sumur")
    return lo, hi, pd.Timestamp(c)


def _series(df: pd.DataFrame, cols: list[str]) -> dict:
    out = {"t": [t.isoformat() for t in df.index]}
    for c in cols:
        if c in df:
            out[c] = [f(x, 3) for x in df[c]]
    return out


@router.get("/{wid}/forecast/init")
def init(wid: int, t_cut: str | None = None, hours: float = 6, db: Session = Depends(get_db),
         _: User = Depends(current_user)):
    """Kondisi acuan di jam mulai + rencana awal. Bila sesudah jam mulai ada data, rencana awal = rencana kasar dari
    data yang sebenarnya terjadi (uji coba); bila tidak, 'lanjut bor dengan parameter acuan'."""
    w = _well(db, wid)
    hours = min(max(hours, 0.5), MAX_HOURS)
    lo, hi, c = _cut(db, w, t_cut)
    rec, pred = _predictor(db)
    df = _frame(db, w, c - WARMUP, min(c + timedelta(hours=hours), hi))
    hist = df[df.index <= c]
    try:
        ref = fc.reference(hist, pred)
    except ValueError as e:
        raise HTTPException(400, str(e))
    actual = df[df.index > c]
    has_actual = len(actual) >= 60
    if has_actual:
        plan = fc.plan_from_actual(actual)
        src = "data aktual sesudah jam mulai (rencana kasar per jam)"
    else:
        plan = [{"op": "drill" if ref.rop > 0 else "circ", "hours": hours}]
        src = "parameter acuan 1 jam terakhir"
    cs = fc.connection_stats(hist)
    sect = sec.section_at(w.sections, ref.hole_md, c)
    ver, ppfg = active_ppfg(db, w.id)
    versions = [{"id": v.id, "version": v.version, "status": v.status} for v in
                db.scalars(select(PPFGVersion).where(PPFGVersion.well_id == w.id).order_by(PPFGVersion.version.desc()))]
    return {"well": w.name, "data_start": lo.isoformat(), "data_end": hi.isoformat(), "t_cut": c.isoformat(),
            "reference": ref.public(), "plan": plan, "plan_source": src, "has_actual": has_actual,
            "connections": cs or {"every_ft": fc.DEFAULT_CFG["every_ft"], "off_min": fc.DEFAULT_CFG["off_min"], "n": 0},
            "connections_from_data": bool(cs), "ppfg": {"id": ver.id, "version": ver.version, "status": ver.status} if ver else None,
            "ppfg_versions": versions,
            "shoe_md": (sect or {}).get("shoe_md") or w.shoe_md, "model": _model_out(rec),
            "section": sect, "n_sections": len(w.sections or []),
            "cfg": {k: fc.DEFAULT_CFG[k] for k in ("flow_exp", "rpm_k", "hole_size", "transport", "cut_tau_min")},
            "casing_id_default": {str(k): v for k, v in hy.CASING_ID_FOR_HOLE.items()}}


class Segment(BaseModel):
    op: str = "drill"
    hours: float | None = Field(None, gt=0, le=MAX_HOURS)
    to_md: float | None = Field(None, gt=0)
    flow: float | None = Field(None, ge=0, le=3000)
    rpm: float | None = Field(None, ge=0, le=400)
    wob: float | None = Field(None, ge=0, le=200)
    rop: float | None = Field(None, ge=0, le=1000)
    mw: float | None = Field(None, ge=6, le=20)


class ForecastIn(BaseModel):
    t_cut: str | None = None
    plan: list[Segment] = Field(min_length=1, max_length=48)
    connections: bool = True
    every_ft: float | None = Field(None, gt=5, le=200)
    off_min: float | None = Field(None, gt=0, le=60)
    hole_size: float | None = Field(None, gt=3, le=36)
    flow_exp: float | None = Field(None, ge=0, le=2)
    preset: str | None = None                             # preset string katalog (default: dari data section / otomatis)
    pv: float | None = Field(None, gt=0, le=150)          # cP — hidraulika aktif bila PV & YP diisi
    yp: float | None = Field(None, gt=0, le=150)          # lbf/100 ft²
    casing_id: float | None = Field(None, gt=3, le=30)
    base: str | None = Field(None, pattern="^(ml|hyd)$")
    reveal: bool = False            # tampilkan data asli sesudah jam mulai (uji coba)
    ppfg_version: int | None = None  # versi PPFG tertentu (mis. draft untuk uji coba); default: approved terbaru


@router.post("/{wid}/forecast")
def run(wid: int, body: ForecastIn, db: Session = Depends(get_db), _: User = Depends(current_user)):
    w = _well(db, wid)
    lo, hi, c = _cut(db, w, body.t_cut)
    plan = [s.model_dump(exclude_none=True) for s in body.plan]
    total_h = sum(s.get("hours") or 0 for s in plan)
    cfg = {k: v for k, v in (("every_ft", body.every_ft), ("off_min", body.off_min), ("hole_size", body.hole_size),
                             ("flow_exp", body.flow_exp), ("pv", body.pv), ("yp", body.yp), ("casing_id", body.casing_id),
                             ("base", body.base), ("preset", body.preset)) if v is not None}
    rec, pred = _predictor(db)
    df = _frame(db, w, c - WARMUP, min(c + timedelta(hours=max(total_h, 1) + 12), hi))
    hist = df[df.index <= c]
    # data section aktif di jam mulai mengisi yang tidak dikirim form (ukuran lubang, casing, string, PV/YP, shoe)
    hcol = "hole_reached" if "hole_reached" in hist else "hole_depth"
    sect = sec.section_at(w.sections, float(hist[hcol].dropna().iloc[-1]) if len(hist) and hist[hcol].notna().any() else None, c)
    if sect:
        for k_cfg, k_sec in (("hole_size", "hole_size"), ("casing_id", "casing_id"), ("preset", "preset"), ("pv", "pv"), ("yp", "yp")):
            if k_cfg not in cfg and sect.get(k_sec) is not None:
                cfg[k_cfg] = sect[k_sec]
    shoe = (sect or {}).get("shoe_md") or w.shoe_md
    if "preset" in cfg and cfg["preset"] not in hy.bd.load_catalog()["presets"]:
        raise HTTPException(400, f"Preset string '{cfg['preset']}' tidak ada di katalog")
    ver, ppfg = active_ppfg(db, w.id, body.ppfg_version)
    if ver is not None and ver.well_id != w.id:
        raise HTTPException(400, "Versi PPFG bukan milik sumur ini")
    try:
        res = fc.forecast(hist, plan, pred, load_survey(db, w.id), ppfg, shoe, thresholds(db), cfg,
                          connections=body.connections, both=True)
    except ValueError as e:
        raise HTTPException(400, str(e))
    tl = res["timeline"]
    if (tl.index[-1] - c) > timedelta(hours=MAX_HOURS):
        raise HTTPException(400, f"Rencana lebih dari {MAX_HOURS} jam")
    cols = ["op", "pumps", "bit_depth", "hole_depth", "flow", "rpm", "wob", "rop", "mw", "ecd", "ecd_circ", "ecd_circ_all",
            "esd", "fg_bit", "lower_bit", "fg_oh", "margin", "margin_kind", "level", "d_flow", "d_rpm", "d_cut"]
    h = hist[hist.index >= c - HIST_SHOW]
    out = {"t_cut": c.isoformat(), "reference": res["reference"], "warnings": res["warnings"], "summary": res["summary"],
           "summary_continuous": res.get("summary_continuous"),
           "timeline": _series(tl, cols), "continuous": _series(res["continuous"], ["ecd_circ", "bit_depth"]) if "continuous" in res else None,
           "history": _series(h.assign(ecd_ok=h["ecd"].where(h["ecd"].between(7, 20) & ~h["ecd_stale"])),
                              ["ecd_ok", "ecd", "mw", "bit_depth", "flow_in"]),
           "ppfg": {"id": ver.id, "version": ver.version, "status": ver.status} if ver else None, "model": _model_out(rec),
           "cfg": {k: res["cfg"][k] for k in ("every_ft", "off_min", "flow_exp", "rpm_k", "hole_size", "transport")},
           "hydraulics": res.get("hydraulics"), "section": sect,
           "has_actual": bool((df.index > c).sum() >= 60), "actual": None, "metrics": None}
    if body.reveal and out["has_actual"]:
        a = df[(df.index > c) & (df.index <= tl.index[-1])]
        ok = a["ecd"].between(7, 20) & ~a["ecd_stale"] & (a["flow_in"] > 50)
        a = a.assign(ecd_ok=a["ecd"].where(ok))
        out["actual"] = _series(a, ["ecd_ok", "ecd", "mw", "bit_depth", "hole_depth", "flow_in", "rpm", "wob"])
        y = a["ecd_ok"].dropna()
        hv = h["ecd"].where(h["ecd"].between(7, 20) & ~h["ecd_stale"]).dropna()
        if len(y) >= 10 and len(hv):
            p = tl["ecd_circ_all"].reindex(y.index, method="nearest", tolerance=pd.Timedelta(seconds=30))
            m = p.notna()
            last = float(hv.iloc[-1])
            out["metrics"] = {
                "n": int(m.sum()), "mae": f((p[m] - y[m]).abs().mean(), 3), "mae_persist": f((y - last).abs().mean(), 3),
                "ecd_last": f(last), "ecd_max_actual": f(y.max()), "ecd_max_fc": f(p[m].max()) if m.any() else None,
                "t_max_actual": y.idxmax().isoformat(), "bias": f((p[m] - y[m]).mean(), 3),
                "md_end_actual": f(a["hole_depth"].max(), 0), "md_end_fc": f(tl["hole_depth"].iloc[-1], 0)}
    return out
