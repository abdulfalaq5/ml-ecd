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


def hole_reached_robust(hole: pd.Series, base_ft: float = 200.0, ft_per_h: float = 1000.0, confirm: int = 10,
                        reset_ft: float = 150.0, reset_h: float = 2.0) -> pd.Series:
    """Hole depth tertinggi yang sudah dicapai, tahan glitch (kausal, untuk MW effective-from depth).

    cummax() polos terkunci selamanya oleh satu spike (mis. 635 → 3634 ft di GW339, 439.386 ft di BDSI 21) sehingga MW
    sesudahnya ikut salah. Kenaikan diterima bila masuk akal secara fisik (≤ base_ft + ft_per_h × jeda); lompatan lebih
    besar (termasuk sesudah data kosong lama, contoh spike GW339 29 Okt) baru diterima bila bertahan `confirm` sampel
    berturut-turut (mis. data lanjut setelah jeda / koreksi depth).

    Hole depth tidak pernah turun saat operasi normal (trip hanya menggerakkan bit). Bila hole depth mentah bertahan
    > `reset_ft` di bawah nilai tercapai selama ≥ `reset_h` jam, itu koreksi depth / sidetrack / re-entry, bukan glitch:
    nilai tercapai di-reset (GW339 16 Nov: 9.909 ft yang mustahil → 5.357 ft di shoe 7")."""
    v = hole.to_numpy(dtype=float)
    t = hole.index.asi8 / 1e9 if isinstance(hole.index, pd.DatetimeIndex) else np.arange(len(v), dtype=float) * 30
    out = np.full(len(v), np.nan)
    cur, t_cur, pend, low_since, low = np.nan, None, 0, None, []
    for i, x in enumerate(v):
        if not np.isnan(cur) and cur > 100 and x < 10:  # kanal kosong terbaca 0 saat sumur sudah dalam: bukan data
            x = np.nan
        if not np.isnan(x):
            if not np.isnan(cur) and x < cur - reset_ft:
                if low_since is None:
                    low_since, low = t[i], []
                low.append((t[i], x))
                recent = [y for tt, y in low if tt >= t[i] - 1800]
                # syarat: bertahan ≥ reset_h DAN stabil (≤ 150 ft / 30 mnt, setara mengebor). Nilai yang bergerak cepat =
                # kanal hole mengikuti bit saat trip (BDSI 21 9 Nov), bukan koreksi.
                if t[i] - low_since >= reset_h * 3600 and max(recent) - min(recent) <= 150:
                    cur = float(np.median(recent))
                    t_cur, pend, low_since = t[i], 0, None
                    out[i] = cur
                    continue
            else:
                low_since = None
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


def stale_ecd_mask(df: pd.DataFrame) -> pd.Series:
    """True = ECD terukur 'beku': nilai yang ditahan sistem permukaan sejak pompa mati.

    PWD mengirim lewat pulsa lumpur, jadi saat pompa mati tidak ada data baru dan nilai terakhir ditahan,
    bahkan beberapa menit setelah pompa hidup lagi sampai alat mengirim nilai baru (BDSI 61: 100% titik
    pompa mati bernilai sama persis). Semua baris dalam satu deret nilai sama yang sudah melewati pompa mati
    ditandai beku. Flow kosong (NaN) tidak dianggap pompa mati.
    """
    if "ecd" not in df:
        return pd.Series(False, index=df.index)
    e = df["ecd"]
    v = e.ffill()
    grp = (v != v.shift()).cumsum()
    off = df.get("flow_in", pd.Series(np.nan, index=df.index)) < get_settings().flow_min_gpm
    seen_off = off.astype(int).groupby(grp).cummax().astype(bool)
    return seen_off & e.notna()


def add_features(df: pd.DataFrame, mw: pd.DataFrame, survey: pd.DataFrame, sections: list[dict] | None = None) -> pd.DataFrame:
    """Tambahkan state + fitur turunan. MW = Rec 04 as-of hole depth tertinggi yang sudah dicapai
    (aturan effective-from 'sejak bit melewati depth', Lampiran H B14). Ukuran lubang dari data section sumur
    (wells.sections) dengan aturan yang sama; tanpa data section -> kosong."""
    out = df.copy()
    out["state"] = derive_state(out)
    hole_reached = hole_reached_robust(out.get("hole_depth", out.get("bit_depth")))
    out["hole_reached"] = hole_reached          # hole depth tercapai, tahan glitch (dipakai juga oleh ramalan)
    out["mw"] = asof_step(hole_reached, mw["md"], mw["mw"]) if len(mw) else np.nan
    from .sections import hole_size_series
    out["hole_size"] = hole_size_series(sections, hole_reached)
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
    out["ecd_stale"] = stale_ecd_mask(out)
    for f in FEATURES:
        if f not in out:
            out[f] = np.nan
    out[FEATURES] = out[FEATURES].astype(float)  # kolom yang seluruhnya kosong jangan jadi object
    return out
