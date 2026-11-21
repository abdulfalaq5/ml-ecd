"""Tingkat alert (docs Bab 8.4): Normal / Advisory / Warning / Critical / Unavailable + badge Low confidence.

Default = usulan; nilai aktif dibaca dari tabel settings ('thresholds'), diubah lewat persetujuan Drilling Eng + HSE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from ..models import Setting

DEFAULT_THRESHOLDS = {
    "advisory_margin": 0.5, "warning_margin": 0.25, "critical_margin": 0.0,
    "ecd_rise_ppg_5min": 0.2, "warning_persist_min": 2, "stale_min": 10,
}
LEVEL_ORDER = ["NORMAL", "ADVISORY", "WARNING", "CRITICAL"]
RANK = {"UNAVAILABLE": -1, **{k: i for i, k in enumerate(LEVEL_ORDER)}}


def thresholds(db: Session) -> dict:
    s = db.get(Setting, "thresholds")
    return {**DEFAULT_THRESHOLDS, **(s.value if s else {})}


def classify(df: pd.DataFrame, th: dict, detections: list[dict] | None = None) -> pd.DataFrame:
    """Kolom level + reason per baris. ECD acuan = terukur bila ada, selain itu ECD ⓥ."""
    out = df.copy()
    ecd = out["ecd"].where(out["ecd"].between(7, 20)) if "ecd" in out else pd.Series(np.nan, index=out.index)
    out["ecd_ref"] = ecd.fillna(out.get("ecd_pred"))
    m_up = out[["margin_up_bit", "margin_up_oh"]].min(axis=1, skipna=True) if "margin_up_bit" in out else pd.Series(np.nan, index=out.index)
    if "margin_up_bit" in out and "ecd_pred" in out:
        # margin dihitung dari ECD acuan
        m_up = pd.concat([out["fg_bit"] - out["ecd_ref"], out["fg_oh"] - out["ecd_ref"]], axis=1).min(axis=1, skipna=True)
        m_low = out["ecd_ref"] - out["lower_bit"]
    else:
        m_low = pd.Series(np.nan, index=out.index)
    margin = pd.concat([m_up, m_low], axis=1).min(axis=1, skipna=True)
    step = out.index.to_series().diff().dt.total_seconds().median() or 30
    per = max(1, int(th["warning_persist_min"] * 60 / step))
    n5 = max(1, int(300 / step))
    rise = out["ecd_ref"] - out["ecd_ref"].shift(n5)

    lvl = pd.Series("NORMAL", index=out.index, dtype=object)
    reason = pd.Series("", index=out.index, dtype=object)
    adv = (margin <= th["advisory_margin"]) | (rise > th["ecd_rise_ppg_5min"])
    warn = (margin <= th["warning_margin"]).rolling(per, min_periods=per).min().fillna(0).astype(bool)
    crit = margin <= th["critical_margin"]
    lvl[adv] = "ADVISORY"
    reason[adv] = np.where(rise[adv] > th["ecd_rise_ppg_5min"], "ECD naik cepat", "margin ≤ batas advisory")
    lvl[warn] = "WARNING"
    reason[warn] = "margin ≤ batas warning (menetap)"
    lvl[crit] = "CRITICAL"
    reason[crit] = "margin ≤ 0"

    # pompa hidup tetapi tidak ada ECD acuan (tanpa PWD dan ECD ⓥ tak bisa dihitung) -> UNAVAILABLE, bukan NORMAL
    pumps_on = out["state"].isin(["DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC"]) if "state" in out else pd.Series(False, index=out.index)
    unav = pumps_on & out["ecd_ref"].isna() & (lvl == "NORMAL")
    lvl[unav] = "UNAVAILABLE"
    if "mw" in out:
        reason[unav] = np.where(out["mw"][unav].isna(), "ECD ⓥ tidak tersedia: MW (Rec 04) kosong", "ECD ⓥ tidak tersedia: model/fitur wajib")
    else:
        reason[unav] = "ECD ⓥ tidak tersedia"

    # pumps off: yang dibandingkan MW vs batas bawah
    if "margin_static" in out and "state" in out:
        off = ~out["state"].isin(["DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC"])
        bad = off & (out["margin_static"] < 0)
        lvl[bad & (lvl != "CRITICAL")] = "WARNING"
        reason[bad] = "pumps off: MW < batas bawah"

    if detections:
        active = []
        for d in detections:
            a, b = pd.Timestamp(d["start"]), pd.Timestamp(d["end"])
            sl = (out.index >= a) & (out.index <= b + pd.Timedelta(minutes=15))
            active.append(sl)
            new = RANK[d["level"]]
            upd = sl & (lvl.map(RANK) < new).to_numpy()
            lvl[upd] = d["level"]
            reason[upd] = d["label"]
        if len(active) >= 2:
            cnt = np.sum(np.vstack(active), axis=0)
            corr = (cnt >= 2) & (lvl.map(RANK) < 2).to_numpy()
            lvl[corr] = "WARNING"
            reason[corr] = "≥ 2 indikator terkorroborasi"

    out["margin_min"] = margin
    out["level"] = lvl
    out["reason"] = reason
    low = pd.Series(False, index=out.index)
    if "ood" in out:
        low |= out["ood"].fillna(False).astype(bool)
    if "missing_feat" in out:
        low |= out["missing_feat"].fillna(0) > 0
    out["low_conf"] = low
    return out
