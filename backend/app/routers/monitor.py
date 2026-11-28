"""Live Monitor, Profil Depth, Analisis Anomali (cut-off)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.analysis import compute, f, rathole_zone, series
from ..core.data import active_ppfg, load_depth_profile, load_mw, load_survey
from ..core.features import STATES
from ..core.rathole import analyze as rathole_analyze
from ..core.margins import lower_bound, open_hole_extremes
from ..db import get_db
from ..models import Event, User, Well
from ..security import current_user

router = APIRouter(prefix="/api/wells", tags=["monitor"])

TRACK_COLS = ["bit_depth", "hole_depth", "block_pos", "rop", "hookload", "wob", "torque", "rpm", "spp", "flow_in",
              "flow_out_pct", "active_pit", "gain_loss", "ecd", "ecd_pred", "ecd_lo", "ecd_hi", "mw", "fg_bit",
              "lower_bit", "fg_oh", "margin_up_bit", "margin_up_oh", "margin_low", "margin_static", "risk"]


def _well(db: Session, wid: int) -> Well:
    w = db.get(Well, wid)
    if not w:
        raise HTTPException(404, "Sumur tidak ditemukan")
    return w


def _t(s: str | None) -> datetime | None:
    if not s:
        return None
    t = pd.Timestamp(s)
    if t.tzinfo is None:
        t = t.tz_localize("Asia/Jakarta")
    return t.tz_convert("UTC").to_pydatetime()


def _model_out(m):
    if not m:
        return None
    return {"id": m.id, "name": f"ecd-{m.algo} v{m.version}", "status": m.status}


@router.get("/{wid}/monitor")
def monitor(wid: int, t0: str | None = None, t1: str | None = None, minutes: int | None = Query(None, le=10080),
            points: int = Query(1500, le=5000),
            db: Session = Depends(get_db), _: User = Depends(current_user)):
    w = _well(db, wid)
    r = compute(db, w, _t(t0), _t(t1), points, minutes=minutes)
    if r.get("empty"):
        return {"empty": True}
    df = r["df"]
    last = df.iloc[-1]
    now = datetime.now(timezone.utc)
    fresh = (now - r["data_end"]).total_seconds() / 60
    ppfg = r["ppfg"]
    oh = open_hole_extremes(r["ppfg_rows"], w.shoe_md, float(last.get("hole_depth") or last.get("bit_depth") or np.nan))
    valid_feats = int(sum(pd.notna(last.get(c)) for c in ["flow_in", "spp", "rpm", "wob", "rop", "hookload", "torque",
                                                           "bit_depth", "tvd_bit", "mw", "block_vel", "off_bottom"]))
    missing = [c for c in ["flow_in", "spp", "rpm", "wob", "rop", "hookload", "torque", "bit_depth", "tvd_bit", "mw"]
               if pd.isna(last.get(c))]
    kind = "m" if pd.notna(last.get("ecd")) else ("v" if pd.notna(last.get("ecd_pred")) else None)
    snap = {
        "ts": df.index[-1].isoformat(), "state": last.get("state"), "state_label": STATES.get(last.get("state"), ""),
        "bit_depth": f(last.get("bit_depth"), 0), "hole_depth": f(last.get("hole_depth"), 0),
        "ecd": f(last.get("ecd_ref")), "ecd_kind": kind, "ecd_lo": f(last.get("ecd_lo")), "ecd_hi": f(last.get("ecd_hi")),
        "ecd_measured": f(last.get("ecd")), "ecd_pred": f(last.get("ecd_pred")), "ecd_model": f(last.get("ecd_model")),
        "cal_offset": f(last.get("cal_offset")), "cal_age_h": f(last.get("cal_age_h"), 1),
        "fg_bit": f(last.get("fg_bit")), "fg_oh": oh["fg_min"], "fg_oh_md": oh["fg_min_md"],
        "lower_bit": f(last.get("lower_bit")), "lower_oh": oh["lower_max"], "mw": f(last.get("mw")),
        "margin_up_bit": f(last.get("fg_bit") - last.get("ecd_ref")) if pd.notna(last.get("fg_bit")) and pd.notna(last.get("ecd_ref")) else None,
        "margin_up_oh": f(oh["fg_min"] - last.get("ecd_ref")) if oh["fg_min"] is not None and pd.notna(last.get("ecd_ref")) else None,
        "margin_low": f(last.get("ecd_ref") - last.get("lower_bit")) if pd.notna(last.get("lower_bit")) and pd.notna(last.get("ecd_ref")) else None,
        "margin_static": f(last.get("margin_static")), "level": last.get("level"), "reason": last.get("reason"),
        "low_conf": bool(last.get("low_conf")), "ood": bool(last.get("ood")), "risk": f(last.get("risk")),
        "interval_half": f((last.get("ecd_hi") - last.get("ecd_lo")) / 2) if pd.notna(last.get("ecd_hi")) else None,
        "zone": rathole_zone(w, f(last.get("bit_depth"), 0), df.index[-1]),
    }
    if fresh > 10 and w.role == "shadow":
        snap["level"] = "UNAVAILABLE"
        snap["reason"] = f"data terakhir {fresh:.0f} mnt lalu"
    meta = {"well": w.name, "section": w.section, "shoe_md": w.shoe_md, "rathole": w.rathole, "fresh_min": f(fresh, 0),
            "data_start": r["data_start"].isoformat(), "data_end": r["data_end"].isoformat(),
            "t0": r["t0"].isoformat(), "t1": r["t1"].isoformat(), "bucket_s": r["bucket_s"],
            "model": _model_out(r["model"]), "valid_features": valid_feats, "total_features": 12, "missing": missing,
            "ppfg": {"id": ppfg.id, "version": ppfg.version, "status": ppfg.status, "approved_by": ppfg.approved_by,
                     "approved_at": ppfg.approved_at.isoformat() if ppfg.approved_at else None} if ppfg else None}
    s = series(df, TRACK_COLS)
    s["state"] = df["state"].tolist()
    s["level"] = df["level"].tolist()
    return {"empty": False, "meta": meta, "snapshot": snap, "series": s,
            "detections": r["detections"][-50:][::-1]}


@router.get("/{wid}/anomaly")
def anomaly(wid: int, t0: str | None = None, t1: str | None = None, cutoff: str | None = None,
            points: int = Query(1200, le=5000), db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Mode cut-off: engine hanya melihat data ≤ cutoff; data setelahnya dikirim terpisah (verifikasi, abu-abu)."""
    w = _well(db, wid)
    c = _t(cutoff)
    full = compute(db, w, _t(t0), _t(t1), points)
    if full.get("empty"):
        return {"empty": True}
    r = compute(db, w, full["t0"], full["t1"], points, cutoff=c) if c else full
    cols = ["hookload", "torque", "spp", "flow_in", "flow_out_pct", "active_pit", "rpm", "wob", "bit_depth",
            "ecd", "ecd_pred", "ecd_lo", "ecd_hi", "mw", "fg_bit", "lower_bit", "risk"]
    seen = series(r["df"], cols) if not r.get("empty") else {"t": []}
    seen["state"] = r["df"]["state"].tolist() if not r.get("empty") else []
    after = None
    if c:
        rest = full["df"][full["df"].index > c]
        after = series(rest, ["hookload", "torque", "spp", "flow_out_pct", "active_pit", "ecd_pred", "risk"])
    events = db.scalars(select(Event).where(Event.well_id == wid, Event.review_status == "Dikonfirmasi")
                        .order_by(Event.onset)).all()
    ev = [{"id": e.id, "onset": e.onset.isoformat(), "category": e.category, "level": e.level, "md": e.md,
           "detail": e.detail} for e in events]
    dets = [] if r.get("empty") else r["detections"]
    # lead time: indikasi pertama & warning pertama sebelum tiap event terkonfirmasi kategori stuck/pack-off/loss
    leads = []
    for e in events:
        prior = [d for d in dets if pd.Timestamp(d["start"]) <= pd.Timestamp(e.onset)]
        warn = [d for d in prior if d["level"] in ("WARNING", "CRITICAL")]
        first = prior[0] if prior else None
        fw = warn[0] if warn else None
        leads.append({"event": e.category, "onset": e.onset.isoformat(),
                      "first": first["start"] if first else None,
                      "first_lead_min": f((pd.Timestamp(e.onset) - pd.Timestamp(first["start"])).total_seconds() / 60, 0) if first else None,
                      "warning": fw["start"] if fw else None,
                      "warning_lead_min": f((pd.Timestamp(e.onset) - pd.Timestamp(fw["start"])).total_seconds() / 60, 0) if fw else None})
    return {"empty": False, "well": w.name, "t0": full["t0"].isoformat(), "t1": full["t1"].isoformat(),
            "cutoff": c.isoformat() if c else None, "data_start": full["data_start"].isoformat(),
            "data_end": full["data_end"].isoformat(), "seen": seen, "after": after, "detections": dets,
            "events": ev, "lead_times": leads, "model": _model_out(full["model"]),
            "ecd_measured_available": bool(full["df"]["ecd"].notna().any()) if "ecd" in full["df"] else False}


@router.get("/{wid}/profile")
def profile(wid: int, ppfg_version: int | None = None, db: Session = Depends(get_db), _: User = Depends(current_user)):
    w = _well(db, wid)
    ver, pp = active_ppfg(db, wid, ppfg_version)
    mw = load_mw(db, wid)
    sv = load_survey(db, wid)
    ecd_m = load_depth_profile(db, wid, 2, 10.0)

    def thin(df, n=800):
        return df.iloc[:: max(1, len(df) // n)] if len(df) else df

    ppt = thin(pp)
    out_pp = {c: [f(x, 3) for x in ppt[c]] for c in ("md", "tvd", "pp", "sfg", "fg_min", "fg_max")} if len(ppt) else {}
    mwt = thin(mw)
    # tabel interval: pecah per perubahan MW (atau tiap 500 ft)
    rows = []
    if len(pp) and len(mw):
        top, bot = float(max(pp.md.min(), mw.md.min())), float(min(pp.md.max(), mw.md.max()))
        edges = np.arange(np.floor(top / 500) * 500, bot + 500, 500)
        lb = lower_bound(pp)
        for a, b in zip(edges[:-1], edges[1:]):
            seg = pp[(pp.md >= a) & (pp.md < b)]
            mseg = mw[(mw.md >= a) & (mw.md < b)]
            if seg.empty or mseg.empty:
                continue
            lbs = lb.loc[seg.index]
            mwv = float(mseg.mw.median())
            ecdv = ecd_m[(ecd_m.md >= a) & (ecd_m.md < b)]["ecd"].dropna() if len(ecd_m) else pd.Series(dtype=float)
            ecdmed = float(ecdv.median()) if len(ecdv) else None
            low_m = mwv - float(lbs.max()) if lbs.notna().any() else None
            rows.append({"a": float(a), "b": float(b), "pp": f(seg.pp.max()), "sfg": f(seg.sfg.max()), "mw": f(mwv),
                         "ecd": f(ecdmed), "fg_min": f(seg.fg_min.min()), "low_margin": f(low_m),
                         "up_margin": f(float(seg.fg_min.min()) - ecdmed) if ecdmed and seg.fg_min.notna().any() else None,
                         "flag": "MW < batas bawah" if low_m is not None and low_m < 0 else "dalam window"})
    bad = [r for r in rows if r["low_margin"] is not None and r["low_margin"] < 0]
    last_hole = None
    return {"well": w.name, "shoe_md": w.shoe_md, "rathole": w.rathole,
            "ppfg": {"id": ver.id, "version": ver.version, "status": ver.status, "approved_by": ver.approved_by} if ver else None,
            "pp": out_pp, "mw": {"md": [f(x, 1) for x in mwt.md], "mw": [f(x) for x in mwt.mw]} if len(mwt) else {},
            "survey": {"md": [f(x, 1) for x in sv.md], "tvd": [f(x, 1) for x in sv.tvd]} if len(sv) else {},
            "ecd_measured": {"md": [f(x, 1) for x in ecd_m.md], "ecd": [f(x) for x in ecd_m.ecd]} if len(ecd_m) else {},
            "intervals": rows, "mw_below": bad, "hole_depth": last_hole}


@router.get("/{wid}/rathole")
def rathole(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Studi kasus rathole (H1–H3): fase 1 validasi ECD ⓥ vs ECD terukur, fase 2 zona rathole tanpa ECD terukur."""
    return rathole_analyze(db, _well(db, wid))
