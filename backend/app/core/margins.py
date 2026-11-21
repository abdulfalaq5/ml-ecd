"""Margin terhadap PPFG approved (docs Bab 8.1).

margin atas  = FG_min − ECD (di bit dan titik FG_min terendah open hole shoe→hole depth)
margin bawah = ECD − max(PP, SFG) di bit (usulan, menunggu Geomechanics)
margin statis = MW − max(PP, SFG) terburuk di open hole (berlaku saat pumps off)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import interp


def lower_bound(ppfg: pd.DataFrame) -> pd.Series:
    return ppfg[["pp", "sfg"]].max(axis=1, skipna=True)


def open_hole_extremes(ppfg: pd.DataFrame, shoe_md: float | None, hole_md: float) -> dict:
    if ppfg.empty or hole_md is None or np.isnan(hole_md):
        return {"fg_min": None, "fg_min_md": None, "lower_max": None, "lower_max_md": None}
    top = shoe_md if shoe_md is not None else hole_md
    seg = ppfg[(ppfg["md"] >= top) & (ppfg["md"] <= hole_md)]
    if seg.empty:
        seg = ppfg.iloc[[int(np.argmin(np.abs(ppfg["md"].to_numpy() - hole_md)))]]
    out = {"fg_min": None, "fg_min_md": None, "lower_max": None, "lower_max_md": None}
    fg = seg["fg_min"].dropna()
    if len(fg):
        out["fg_min"], out["fg_min_md"] = float(fg.min()), float(seg.loc[fg.idxmin(), "md"])
    lb = lower_bound(seg).dropna()
    if len(lb):
        out["lower_max"], out["lower_max_md"] = float(lb.max()), float(seg.loc[lb.idxmax(), "md"])
    return out


def add_margins(df: pd.DataFrame, ppfg: pd.DataFrame, shoe_md: float | None, ecd_col: str = "ecd_pred") -> pd.DataFrame:
    out = df.copy()
    if ppfg.empty:
        for c in ("fg_bit", "lower_bit", "fg_oh", "lower_oh", "margin_up_bit", "margin_up_oh", "margin_low", "margin_static"):
            out[c] = np.nan
        return out
    out["fg_bit"] = interp(out["bit_depth"], ppfg["md"], ppfg["fg_min"])
    out["lower_bit"] = interp(out["bit_depth"], ppfg["md"], lower_bound(ppfg))
    # open hole: hitung per perubahan hole depth (murah)
    hole = out.get("hole_depth", out["bit_depth"]).ffill()
    uniq = pd.Series(hole.round(0).unique()).dropna()
    cache = {h: open_hole_extremes(ppfg, shoe_md, h) for h in uniq}
    key = hole.round(0)
    out["fg_oh"] = key.map(lambda h: cache.get(h, {}).get("fg_min") if pd.notna(h) else None).astype(float)
    out["lower_oh"] = key.map(lambda h: cache.get(h, {}).get("lower_max") if pd.notna(h) else None).astype(float)
    ecd = out[ecd_col]
    out["margin_up_bit"] = out["fg_bit"] - ecd
    out["margin_up_oh"] = out["fg_oh"] - ecd
    out["margin_low"] = ecd - out["lower_bit"]
    out["margin_static"] = out["mw"] - out["lower_oh"].fillna(out["lower_bit"])
    return out
