"""Operating state (docs Bab 6.3) + fitur surface-only untuk nowcast ECD (Bab 5.5).

ECD / ANP / PWD tidak pernah menjadi fitur (konfigurasi surface-only).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import get_settings
from .data import asof_step, interp

STATES = {
    "DRILL_ROT": "Drilling rotary", "SLIDE": "Sliding", "REAM": "Reaming / back-reaming", "WASH": "Washing",
    "CIRC": "Sirkulasi", "TRIP": "TIH / TOH", "STATIC": "Pumps off / statis", "UNKNOWN": "Tidak diketahui",
}
PUMPS_ON_STATES = {"DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC"}
CLEANOUT_STATES = {"REAM", "WASH", "CIRC"}

FEATURES = ["flow_in", "spp", "rpm", "wob", "rop", "hookload", "torque", "bit_depth", "tvd_bit",
            "off_bottom", "mw", "block_vel", "t_pumps_on", "inc_bit"]


def derive_state(df: pd.DataFrame) -> pd.Series:
    s = get_settings()
    flow = df.get("flow_in", pd.Series(np.nan, index=df.index)).fillna(0)
    rpm = df.get("rpm", pd.Series(np.nan, index=df.index)).fillna(0)
    rop = df.get("rop", pd.Series(np.nan, index=df.index)).fillna(0)
    bit = df.get("bit_depth", pd.Series(np.nan, index=df.index))
    hole = df.get("hole_depth", pd.Series(np.nan, index=df.index))
    off = (hole - bit)
    dt = df.index.to_series().diff().dt.total_seconds().replace(0, np.nan)
    bitv = (bit.diff() / dt).abs().fillna(0)
    blk = df.get("block_pos", pd.Series(np.nan, index=df.index))
    blkv = (blk.diff() / dt).abs().fillna(0)
    moving = (bitv > s.block_move_ft_s) | (blkv > s.block_move_ft_s)
    pumps = flow > s.flow_min_gpm
    on_bottom = off.fillna(np.inf) <= s.on_bottom_ft
    rot = rpm > s.rpm_min

    st = pd.Series("UNKNOWN", index=df.index, dtype=object)
    st[~pumps & moving] = "TRIP"
    st[~pumps & ~moving] = "STATIC"
    st[pumps & ~on_bottom & ~moving] = "CIRC"
    st[pumps & ~on_bottom & moving & rot] = "REAM"
    st[pumps & ~on_bottom & moving & ~rot] = "WASH"
    st[pumps & on_bottom & rot & (rop > 0)] = "DRILL_ROT"
    st[pumps & on_bottom & ~rot & (rop > 0)] = "SLIDE"
    st[pumps & on_bottom & (rop <= 0)] = "CIRC"
    st[bit.isna() & flow.isna()] = "UNKNOWN"
    return st


def hole_reached_robust(hole: pd.Series, base_ft: float = 200.0, ft_per_h: float = 1000.0, confirm: int = 10) -> pd.Series:
    """Hole depth tertinggi yang sudah dicapai, tahan glitch (kausal, untuk MW effective-from depth).

    cummax() polos terkunci selamanya oleh satu spike (mis. 635 → 3634 ft di GW339, 439.386 ft di BDSI 21) sehingga MW
    sesudahnya ikut salah. Kenaikan diterima bila masuk akal secara fisik (≤ base_ft + ft_per_h × jeda); lompatan lebih
    besar (termasuk sesudah data kosong lama, contoh spike GW339 29 Okt) baru diterima bila bertahan `confirm` sampel
    berturut-turut (mis. data lanjut setelah jeda / koreksi depth)."""
    v = hole.to_numpy(dtype=float)
    t = hole.index.asi8 / 1e9 if isinstance(hole.index, pd.DatetimeIndex) else np.arange(len(v), dtype=float) * 30
    out = np.full(len(v), np.nan)
    cur, t_cur, pend = np.nan, None, 0
    for i, x in enumerate(v):
        if not np.isnan(x):
            if np.isnan(cur) or x <= cur:  # sampel wajar (tidak lebih dalam dari yang sudah dicapai)
                cur = x if np.isnan(cur) else cur
                t_cur, pend = t[i], 0
            elif x - cur <= base_ft + ft_per_h * min(max(0.0, t[i] - t_cur), 360.0) / 3600:  # maks ±300 ft; lebih → konfirmasi
                cur, t_cur, pend = x, t[i], 0
            else:
                pend += 1
                if pend >= confirm:
                    cur, t_cur, pend = x, t[i], 0
        out[i] = cur
    return pd.Series(out, index=hole.index)


def add_features(df: pd.DataFrame, mw: pd.DataFrame, survey: pd.DataFrame) -> pd.DataFrame:
    """Tambahkan state + fitur turunan. MW = Rec 04 as-of hole depth tertinggi yang sudah dicapai
    (aturan effective-from 'sejak bit melewati depth', Lampiran H B14)."""
    out = df.copy()
    out["state"] = derive_state(out)
    hole_reached = hole_reached_robust(out.get("hole_depth", out.get("bit_depth")))
    out["mw"] = asof_step(hole_reached, mw["md"], mw["mw"]) if len(mw) else np.nan
    if len(survey) and survey["tvd"].notna().sum() >= 2:
        out["tvd_bit"] = interp(out["bit_depth"], survey["md"], survey["tvd"])
        out["inc_bit"] = interp(out["bit_depth"], survey["md"], survey["inc"]) if survey["inc"].notna().any() else np.nan
    else:
        out["tvd_bit"] = out.get("bit_tvd", out["bit_depth"])
        out["inc_bit"] = out.get("inclination", np.nan)
    if "bit_tvd" in out:
        out["tvd_bit"] = out["tvd_bit"].fillna(out["bit_tvd"])
    out["off_bottom"] = (out.get("hole_depth") - out.get("bit_depth")).clip(lower=0)
    dt = out.index.to_series().diff().dt.total_seconds().replace(0, np.nan)
    out["block_vel"] = (out["bit_depth"].diff() / dt * 60).fillna(0)  # ft/mnt, + = turun
    pumps = out.get("flow_in", pd.Series(0, index=out.index)).fillna(0) > get_settings().flow_min_gpm
    grp = (pumps != pumps.shift()).cumsum()
    since = out.index.to_series().groupby(grp).transform(lambda x: (x - x.iloc[0]).dt.total_seconds() / 60)
    out["t_pumps_on"] = np.where(pumps, since.clip(upper=120), 0.0)
    for f in FEATURES:
        if f not in out:
            out[f] = np.nan
    out[FEATURES] = out[FEATURES].astype(float)  # kolom yang seluruhnya kosong jangan jadi object
    return out
