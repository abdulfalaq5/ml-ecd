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
                        reset_ft: float = 150.0, reset_h: float = 2.0, bit: pd.Series | None = None,
                        flow: pd.Series | None = None, bit_tol_ft: float = 50.0, flow_min: float | None = None) -> pd.Series:
    """Hole depth tertinggi yang sudah dicapai, tahan glitch (kausal, untuk MW effective-from depth).

    cummax() polos terkunci selamanya oleh satu spike (mis. 635 → 3634 ft di GW339, 439.386 ft di BDSI 21) sehingga MW
    sesudahnya ikut salah. Kenaikan diterima bila masuk akal secara fisik (≤ base_ft + ft_per_h × jeda); lompatan lebih
    besar (termasuk sesudah data kosong lama, contoh spike GW339 29 Okt) baru diterima bila bertahan `confirm` sampel
    berturut-turut (mis. data lanjut setelah jeda / koreksi depth).

    Hole depth tidak pernah turun saat operasi normal (trip hanya menggerakkan bit). Bila hole depth mentah bertahan
    > `reset_ft` di bawah nilai tercapai selama ≥ `reset_h` jam, itu koreksi depth / sidetrack / re-entry, bukan glitch:
    nilai tercapai di-reset (GW339 16 Nov: 9.909 ft yang mustahil → 5.357 ft di shoe 7").

    Bila `bit` / `flow` diberikan: lubang baru hanya terbentuk di bit dan saat pompa hidup. Pendalaman ditolak bila bit
    > `bit_tol_ft` di atas kedalaman baru (BLSO-717 25 Nov: hole 1.026 → 3.633 ft saat bit di 754 ft) atau flow
    < `flow_min` (BEKA-255 30 Sep: hole & bit "naik" 3.061 → 4.470 ft dengan pompa mati, ROP 1.900 ft/jam; pengeboran
    nyata 1 Okt dari 3.061 ke 4.144 ft). Hanya berlaku di atas puncak yang pernah dicapai. NaN tidak menolak.
    Dengan `bit` / `flow`, lompatan > base_ft + ft_per_h × jeda sejak sampel sebelumnya tidak dikonfirmasi (GW339 15 Nov
    9.909 ft = shifting depth tracking); konfirmasi hanya untuk data yang lanjut sesudah jeda."""
    v = hole.to_numpy(dtype=float)
    t = hole.index.asi8 / 1e9 if isinstance(hole.index, pd.DatetimeIndex) else np.arange(len(v), dtype=float) * 30
    out = np.full(len(v), np.nan)
    b = bit.reindex(hole.index).to_numpy(dtype=float) if bit is not None else np.full(len(v), np.nan)
    q = flow.reindex(hole.index).to_numpy(dtype=float) if flow is not None else np.full(len(v), np.nan)
    qmin = get_settings().flow_min_gpm if flow_min is None else flow_min
    cur, t_cur, pend, low_since, low, peak = np.nan, None, 0, None, [], -np.inf
    # jeda sejak sampel hole sebelumnya (detik): lompatan besar tanpa jeda data tidak bisa dibor -> bukan lubang baru
    ok = ~np.isnan(v)
    t_prev = pd.Series(np.where(ok, t, np.nan)).ffill().shift(1).to_numpy()
    dt_prev = np.where(np.isnan(t_prev), np.inf, t - t_prev)
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
            # hanya untuk kedalaman BARU (> puncak yang pernah dicapai): kembali ke kedalaman lama sesudah reset palsu
            # (BDSI 21 7 Nov: kanal hole sempat 1–2 ft lalu kembali 3.328 saat bit masih di permukaan) tetap boleh
            if not np.isnan(cur) and x > max(cur, peak) + 1 and ((b[i] < x - bit_tol_ft) or (q[i] < qmin)):
                out[i] = cur  # "pendalaman" tanpa bit di dasar / tanpa pompa: bukan lubang baru
                pend = 0
                continue
            if np.isnan(cur) or x <= cur:  # sampel wajar (tidak lebih dalam dari yang sudah dicapai)
                cur = x if np.isnan(cur) else cur
                t_cur, pend = t[i], 0
            elif x - cur <= base_ft + ft_per_h * min(max(0.0, t[i] - t_cur), 360.0) / 3600:  # maks ±300 ft; lebih → konfirmasi
                cur, t_cur, pend = x, t[i], 0
            elif (pend == 0 and x > peak + 1 and not (np.isnan(b[i]) or np.isnan(q[i]))
                  and x - cur > base_ft + ft_per_h * dt_prev[i] / 3600):
                # GW339 14–16 Nov: bit tracking "shifting" 5.652 → 9.909 ft (klien 27 Nov: bukan pengeboran; hookload
                # ±20 klb, pompa mati lalu sempat hidup). Tanpa jeda data, lompatan sebesar ini mustahil dibor: tolak,
                # jangan dikonfirmasi. Dicek di sampel pertama lompatan saja: data yang lanjut
                # sesudah jeda (dt besar) tetap lewat jalur konfirmasi.
                pend = 0
            else:
                pend += 1
                if pend >= confirm:
                    cur, t_cur, pend = x, t[i], 0
        out[i] = cur
        if not np.isnan(cur):
            peak = max(peak, cur)
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


# MW baru berlaku sesudah bit membuat ≥ MW_LAG_FT lubang baru melewati titik Rec 04. Di batas section Rec 04 mencatat
# lumpur section berikutnya tepat di TD section (BEKA-255 3.061 ft → 8,8; TD 12-1/4" 3.062), padahal selama trip keluar,
# casing & semen lumpur lama (10,3) masih di lubang. Uji 14 sumur (27 Nov): label ECD−MW mustahil (< 0 atau > 2 ppg)
# 4.613 → 3.390 baris dengan 10 ft (20 ft: 3.587; 50 ft: 3.495).
MW_LAG_FT = 10.0


def add_features(df: pd.DataFrame, mw: pd.DataFrame, survey: pd.DataFrame, sections: list[dict] | None = None) -> pd.DataFrame:
    """Tambahkan state + fitur turunan. MW = Rec 04 as-of hole depth tertinggi yang sudah dicapai
    (aturan effective-from 'sejak bit melewati depth', Lampiran H B14). Ukuran lubang dari data section sumur
    (wells.sections) dengan aturan yang sama; tanpa data section -> kosong."""
    out = df.copy()
    out["state"] = derive_state(out)
    hole_reached = hole_reached_robust(out.get("hole_depth", out.get("bit_depth")), bit=out.get("bit_depth"),
                                       flow=out.get("flow_in"))
    out["hole_reached"] = hole_reached          # hole depth tercapai, tahan glitch (dipakai juga oleh ramalan)
    out["mw"] = asof_step(hole_reached - MW_LAG_FT, mw["md"], mw["mw"]) if len(mw) else np.nan
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
