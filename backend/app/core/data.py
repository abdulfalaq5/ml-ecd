"""Akses data time/depth + tabel pendukung (MW, survey, PPFG) sebagai DataFrame."""
from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..models import CHANNELS, MudWeight, PPFGRow, PPFGVersion, Survey

MAX_AGG = {"hookload_max", "torque_max"}


def time_range(db: Session, well_id: int) -> tuple[datetime | None, datetime | None]:
    # per record lewat primary key (well_id, record, ts): ±10 ms vs ±1–2 dtk lewat indeks ts
    r = db.execute(text(TIME_RANGE_SQL), {"w": well_id}).one()
    return r[0], r[1]


TIME_RANGE_SQL = (
    "SELECT min(a), max(b) FROM (VALUES (1), (2)) v(r), LATERAL ("
    "SELECT (SELECT ts FROM ts_data WHERE well_id=:w AND record=v.r ORDER BY ts ASC LIMIT 1) a, "
    "(SELECT ts FROM ts_data WHERE well_id=:w AND record=v.r ORDER BY ts DESC LIMIT 1) b) x")


def load_time(db: Session, well_id: int, t0: datetime | None = None, t1: datetime | None = None,
              bucket_s: int = 30, channels: list[str] | None = None) -> pd.DataFrame:
    """Data Rec 01 (utama) + Rec 02 (ECD/ANP + cadangan kanal rig), di-bucket per `bucket_s` detik.

    Indeks: ts (UTC). Kanal Rec 01 diutamakan; nilai kosong diisi dari Rec 02. ECD/ANP hanya dari data terukur.
    """
    chans = channels or CHANNELS
    agg = ", ".join(f"{'max' if c in MAX_AGG else 'avg'}({c}) AS {c}" for c in chans)
    where = "well_id=:w"
    params: dict = {"w": well_id, "s": bucket_s}
    if t0 is not None:
        where += " AND ts >= :t0"
        params["t0"] = t0
    if t1 is not None:
        where += " AND ts <= :t1"
        params["t1"] = t1
    q = text(f"SELECT time_bucket(make_interval(secs => :s), ts) AS ts, record, {agg} "
             f"FROM ts_data WHERE {where} GROUP BY 1, 2 ORDER BY 1")
    df = pd.read_sql(q, db.connection(), params=params)
    if df.empty:
        return pd.DataFrame(columns=chans, index=pd.DatetimeIndex([], tz="UTC", name="ts"))
    df["ts"] = pd.to_datetime(df["ts"], utc=True)
    r1 = df[df.record == 1].drop(columns="record").set_index("ts")
    r2 = df[df.record == 2].drop(columns="record").set_index("ts")
    if r1.empty:
        out = r2
    elif r2.empty:
        out = r1
    else:
        out = r1.combine_first(r2)
        for c in ("ecd", "anp"):
            if c in r2:
                # ECD/ANP dari Rec 02; file template (Rec 01 + ECD, mis. BEKA) jadi cadangan
                out[c] = r2[c].reindex(out.index).combine_first(r1[c]) if c in r1 else r2[c].reindex(out.index)
    return out.sort_index()


def load_depth_profile(db: Session, well_id: int, record: int = 2, step_ft: float = 10.0) -> pd.DataFrame:
    q = text("SELECT floor(md / :s) * :s AS md, avg(ecd) ecd, avg(bit_tvd) bit_tvd, avg(hole_tvd) hole_tvd "
             "FROM depth_data WHERE well_id=:w AND record=:r GROUP BY 1 ORDER BY 1")
    return pd.read_sql(q, db.connection(), params={"w": well_id, "r": record, "s": step_ft})


def load_mw(db: Session, well_id: int) -> pd.DataFrame:
    rows = db.execute(select(MudWeight.md, MudWeight.tvd, MudWeight.mw, MudWeight.remark)
                      .where(MudWeight.well_id == well_id).order_by(MudWeight.md)).all()
    return pd.DataFrame(rows, columns=["md", "tvd", "mw", "remark"])


def load_survey(db: Session, well_id: int) -> pd.DataFrame:
    rows = db.execute(select(Survey.md, Survey.tvd, Survey.inc, Survey.azi, Survey.dls)
                      .where(Survey.well_id == well_id).order_by(Survey.md)).all()
    return pd.DataFrame(rows, columns=["md", "tvd", "inc", "azi", "dls"])


def active_ppfg(db: Session, well_id: int, version_id: int | None = None) -> tuple[PPFGVersion | None, pd.DataFrame]:
    """Versi approved terbaru (atau versi tertentu). Tanpa approved -> None (margin tidak dihitung)."""
    if version_id:
        ver = db.get(PPFGVersion, version_id)
    else:
        ver = db.scalar(select(PPFGVersion).where(PPFGVersion.well_id == well_id, PPFGVersion.status == "approved")
                        .order_by(PPFGVersion.version.desc()))
    if not ver:
        return None, pd.DataFrame(columns=["md", "tvd", "pp", "sfg", "fg_min", "fg_max"])
    rows = db.execute(select(PPFGRow.md, PPFGRow.tvd, PPFGRow.pp, PPFGRow.sfg, PPFGRow.fg_min, PPFGRow.fg_max,
                             PPFGRow.formation).where(PPFGRow.version_id == ver.id).order_by(PPFGRow.md)).all()
    return ver, pd.DataFrame(rows, columns=["md", "tvd", "pp", "sfg", "fg_min", "fg_max", "formation"])


def interp(x: np.ndarray | pd.Series, xp: pd.Series, fp: pd.Series) -> np.ndarray:
    m = xp.notna() & fp.notna()
    if m.sum() == 0:
        return np.full(len(x), np.nan)
    xs, fs = xp[m].to_numpy(float), fp[m].to_numpy(float)
    o = np.argsort(xs)
    xs, fs = xs[o], fs[o]
    xv = np.asarray(x, dtype=float)
    out = np.interp(xv, xs, fs)
    out[np.isnan(xv)] = np.nan
    return out


def asof_step(x: np.ndarray | pd.Series, xp: pd.Series, fp: pd.Series) -> np.ndarray:
    """Nilai fungsi tangga: fp pada xp terbesar yang <= x (untuk MW as-of depth)."""
    m = xp.notna() & fp.notna()
    xs, fs = xp[m].to_numpy(float), fp[m].to_numpy(float)
    xv = np.asarray(x, dtype=float)
    if len(xs) == 0:
        return np.full(len(xv), np.nan)
    o = np.argsort(xs)
    xs, fs = xs[o], fs[o]
    idx = np.searchsorted(xs, xv, side="right") - 1
    out = np.where(idx >= 0, fs[np.clip(idx, 0, None)], fs[0])
    out = out.astype(float)
    out[np.isnan(xv)] = np.nan
    return out
