"""Engine stuck-pipe / hole problem (docs Bab 8.2–8.3, PHR-H4). Rules + statistik robust, tanpa look-ahead.

Semua baseline dihitung dari data MASA LALU (rolling, di-shift). Mode cut-off = data dipotong di T sebelum
dipanggil, jadi hasil identik dengan kondisi real-time saat T.
Output: episode deteksi + skor risiko per waktu. Bukan diagnosis; label tetap dikonfirmasi engineer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LEVEL_W = {"ADVISORY": 0.3, "WARNING": 0.6, "CRITICAL": 0.9}

DEFAULTS = {
    "baseline_min": 60,          # panjang jendela baseline (mnt)
    "lag_min": 10,               # jeda baseline -> sekarang
    "spp_rise_pct": 10.0,        # pack-off: SPP ternormalisasi naik ≥ x %
    "torque_k": 4.0,             # torque spike: median + k·MAD
    "overpull_klb": 15.0,
    "tag_wob_klb": 5.0,
    "ecdv_rise_ppg": 0.2,        # lonjakan ECD ⓥ ≥ x ppg ...
    "ecdv_window_min": 10,       # ... dalam y menit, pada flow/RPM/MW sama
    "ecdv_ignore_after_pumps_min": 10,
    "residual_ppg": 0.3,
    "loss_flowout_drop_pct": 20.0,
    "flowout_min_base_pct": 10.0,  # baseline flow out % minimum agar persentase bermakna
    "flowout_min_change_pct": 5.0, # perubahan absolut minimum (poin %)
    "pit_change_bbl": 5.0,
    "ecd_below_mw_ppg": 0.1,     # ECD terukur < MW − x saat pompa hidup = kolom lumpur turun (korroborasi loss)
    "stationary_min": 30,
    "min_duration_min": 1.0,
    # fraksi ΔSPP yang diteruskan ke annulus di bawah sensor saat pack-off. Sementara: GW339 17–24 Nov (DDR: tanpa
    # loss) konsisten dengan ≤ 0,2 (α 0,2 → 1 dari 1.344 titik > FG draft; α 1 → 302). Kalibrasi ulang dgn event lain.
    "po_transmission": 0.2,
}

RECS = {
    "packoff": "cek returns, cavings, SPP vs baseline",
    "torque": "pantau torque & RPM, bandingkan dengan baseline per depth",
    "overpull": "bandingkan P/U–S/O dengan baseline per depth",
    "tag": "catat depth tag; cek tight spot / fill",
    "ecdv_spike": "cek silang SPP, torque, overpull, flow out; verifikasi kondisi lubang",
    "residual": "bandingkan ECD terukur vs prediksi; cek cuttings loading",
    "loss": "verifikasi flow out & pit dengan Mud Eng; cek kondisi permukaan",
    "influx": "verifikasi flow check sesuai prosedur well control",
    "differential": "pertimbangkan pergerakan pipa sesuai prosedur; tinjau overbalance",
    "static_mw": "tinjau MW vs batas bawah dengan Mud Eng / Geomechanics",
}
LABELS = {
    "packoff": "SPP naik di flow sama (indikasi pack-off)", "torque": "Torque spike / stall",
    "overpull": "Overpull P/U", "tag": "Tag / set-down", "ecdv_spike": "Lonjakan ECD ⓥ (flow/RPM/MW sama)",
    "residual": "Residual ECD positif menetap", "loss": "Indikasi loss", "influx": "Indikasi influx",
    "differential": "Pipa diam lama (differential)", "static_mw": "MW statis < batas bawah (pumps off)",
}


def _n(df: pd.DataFrame, minutes: float) -> int:
    if len(df) < 2:
        return 1
    step = df.index.to_series().diff().dt.total_seconds().median() or 30
    step = 30.0 if not np.isfinite(step) or step <= 0 else float(step)
    return max(1, int(round(minutes * 60 / step)))


def _mp(n: int) -> int:
    return min(n, max(3, n // 4))


def _past_median(s: pd.Series, n: int, lag: int) -> pd.Series:
    return s.shift(lag).rolling(n, min_periods=_mp(n)).median()


def _past_mad(s: pd.Series, n: int, lag: int) -> pd.Series:
    med = _past_median(s, n, lag)
    return (s.shift(lag) - med).abs().rolling(n, min_periods=_mp(n)).median()


def _col(df, c):
    return df[c] if c in df else pd.Series(np.nan, index=df.index)


def flags(df: pd.DataFrame, p: dict) -> dict[str, tuple[pd.Series, pd.Series, pd.Series, pd.Series]]:
    """detektor -> (mask, level_series, value, baseline)."""
    nb, lag = _n(df, p["baseline_min"]), _n(df, p["lag_min"])
    st = _col(df, "state").fillna("UNKNOWN")
    pumps = st.isin(["DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC"])
    flow, spp, tq, rpm = _col(df, "flow_in"), _col(df, "spp"), _col(df, "torque"), _col(df, "rpm")
    hook, wob, bv = _col(df, "hookload"), _col(df, "wob"), _col(df, "block_vel")
    out = {}

    # pack-off: SPP dinormalisasi ke flow (SPP ∝ Q^1.8)
    qref = flow[pumps].median() if pumps.any() else np.nan
    sppn = spp / ((flow / qref).clip(lower=0.2) ** 1.8)
    base = _past_median(sppn.where(pumps), nb, lag)
    rise = (sppn / base - 1) * 100
    tq_base = _past_median(tq.where(pumps), nb, lag)
    tq_up = tq > tq_base * 1.2
    m = pumps & (rise >= p["spp_rise_pct"])
    lvl = pd.Series(np.where(tq_up, "WARNING", "ADVISORY"), index=df.index)
    out["packoff"] = (m, lvl, rise, pd.Series(p["spp_rise_pct"], index=df.index))

    # torque spike / stall
    tmed, tmad = _past_median(tq.where(rpm > 5), nb, lag), _past_mad(tq.where(rpm > 5), nb, lag)
    thr = tmed + p["torque_k"] * (tmad * 1.4826).clip(lower=0.3)
    rpm_prev = _past_median(rpm, _n(df, 5), 1)
    stall = (rpm_prev > 10) & (rpm < 0.3 * rpm_prev) & (tq > tmed)
    m = ((tq > thr) & (rpm > 5)) | stall
    out["torque"] = (m, pd.Series(np.where(stall, "WARNING", "ADVISORY"), index=df.index), tq, thr)

    # overpull: saat pipa bergerak naik (block_vel < 0)
    up = bv < -0.5
    pu_base = _past_median(hook.where(up), nb * 2, lag)
    op = hook - pu_base
    m = up & (op >= p["overpull_klb"])
    out["overpull"] = (m, pd.Series(np.where(op >= 2 * p["overpull_klb"], "WARNING", "ADVISORY"), index=df.index), hook, pu_base)

    # tag / set-down: bergerak turun, belum di bottom, WOB naik relatif baseline (drag ream/wash normal tidak dihitung)
    offb = _col(df, "off_bottom")
    down = (bv > 0.5) & (offb > 2)
    wob_base = _past_median(wob.where(down), nb, lag).fillna(0)
    m = down & ((wob - wob_base) >= p["tag_wob_klb"])
    out["tag"] = (m, pd.Series("ADVISORY", index=df.index), wob, wob_base)

    # lonjakan ECD ⓥ: naik ≥ x ppg dalam y mnt pada flow/RPM/MW sama; abaikan awal pompa hidup
    # keluaran model mentah (ecd_model): kalibrasi ke PWD tidak boleh menimbulkan / menelan lonjakan
    ecdv = df["ecd_model"] if "ecd_model" in df else df.get("ecd_pred")
    if ecdv is not None:
        e = ecdv
        w = _n(df, p["ecdv_window_min"])
        prev_e = e.shift(w).rolling(w, min_periods=min(w, max(2, w // 3))).median()
        prev_q = flow.shift(w).rolling(w, min_periods=min(w, max(2, w // 3))).median()
        prev_r = rpm.shift(w).rolling(w, min_periods=min(w, max(2, w // 3))).median()
        mw = _col(df, "mw")
        same = ((flow - prev_q).abs() <= 0.05 * prev_q.abs().clip(lower=50)) & \
               ((rpm - prev_r).abs() <= np.maximum(5, 0.15 * prev_r.abs())) & (mw.diff(w).abs().fillna(0) < 0.05)
        settled = _col(df, "t_pumps_on") >= p["ecdv_ignore_after_pumps_min"]
        d = e - prev_e
        m = pumps & settled & same & (d >= p["ecdv_rise_ppg"])
        out["ecdv_spike"] = (m, pd.Series(np.where(d >= 2 * p["ecdv_rise_ppg"], "WARNING", "ADVISORY"), index=df.index), d, prev_e)

    # residual ECD (hanya bila ada label)
    if "ecd" in df and ecdv is not None and df["ecd"].notna().any():
        r = (df["ecd"] - ecdv).rolling(_n(df, 5), min_periods=min(2, _n(df, 5))).median()
        m = pumps & (r >= p["residual_ppg"])
        out["residual"] = (m, pd.Series("ADVISORY", index=df.index), r, pd.Series(p["residual_ppg"], index=df.index))

    # loss / influx
    fo, pit = _col(df, "flow_out_pct"), _col(df, "active_pit")
    fo_base = _past_median(fo.where(pumps), nb, lag)
    q_base = _past_median(flow.where(pumps), nb, lag)
    steady = (flow - q_base).abs() <= 0.05 * q_base.abs().clip(lower=50)
    w10 = _n(df, 10)
    dpit = pit - pit.shift(w10)
    # flow out % (paddle) bising di nilai kecil: 2 % -> 1 % bukan "turun 50 %". Butuh baseline bermakna dan
    # perubahan absolut minimum. Satu indikator = ADVISORY, flow out + pit bersamaan = WARNING (korroborasi).
    valid_fo = fo_base >= p["flowout_min_base_pct"]
    dfo = fo_base - fo
    drop = (dfo / fo_base.abs().clip(lower=1) * 100).where(valid_fo)
    fo_down = (drop >= p["loss_flowout_drop_pct"]) & (dfo >= p["flowout_min_change_pct"])
    fo_up = (-drop >= p["loss_flowout_drop_pct"]) & (-dfo >= p["flowout_min_change_pct"])
    loss = pumps & steady & (fo_down | (dpit <= -p["pit_change_bbl"]))
    # ECD terukur di bawah MW saat pompa hidup: tekanan annulus < kolom penuh -> level lumpur turun. Hanya penguat
    # (bisa juga MW salah titik di batas section), jadi menaikkan loss ADVISORY -> WARNING, bukan alarm sendiri.
    ecd_low = pumps & ((_col(df, "mw") - _col(df, "ecd")) >= p["ecd_below_mw_ppg"])
    if "ecd_stale" in df:
        ecd_low &= ~df["ecd_stale"].fillna(False).astype(bool)
    both = (fo_down & (dpit <= -p["pit_change_bbl"])) | (loss & ecd_low)
    out["loss"] = (loss, pd.Series(np.where(both, "WARNING", "ADVISORY"), index=df.index), fo, fo_base)
    gain = pumps & steady & fo_up & (dpit >= p["pit_change_bbl"])
    out["influx"] = (gain, pd.Series("CRITICAL", index=df.index), fo, fo_base)

    # pipa diam lama
    still = (bv.abs() < 0.05) & (_col(df, "bit_depth").diff().abs().fillna(0) < 0.1)
    grp = (still != still.shift()).cumsum()
    step = df.index.to_series().diff().dt.total_seconds().median() if len(df) > 1 else 30.0
    step = 30.0 if not np.isfinite(step) or step <= 0 else float(step)
    dur = still.groupby(grp).cumsum() * step  # detik (langkah sebenarnya, bukan dibulatkan per menit)
    m = still & (dur / 60 >= p["stationary_min"]) & (offb > 2)
    out["differential"] = (m, pd.Series("ADVISORY", index=df.index), dur / 60, pd.Series(p["stationary_min"], index=df.index))

    # MW statis < batas bawah saat pumps off
    if "margin_static" in df:
        ms = df["margin_static"]
        m = (~pumps) & (ms < 0)
        out["static_mw"] = (m, pd.Series("WARNING", index=df.index), ms, pd.Series(0.0, index=df.index))
    return out


LOSS_NOTE_NO_PWD = ("Tanpa ECD terukur (PWD): ECD ⓥ mengasumsikan kolom lumpur penuh. Saat loss level annulus turun, "
                    "tekanan nyata bisa lebih rendah dari ECD ⓥ (\"belok kiri\", bisa < MW) — cek margin ke PP.")
LOSS_NOTE_BELOW_MW = "ECD terukur di bawah MW: level lumpur annulus turun — cek margin ECD terukur ke PP."


def loss_note(df: pd.DataFrame, a, b) -> dict:
    """Catatan untuk episode loss (klien 27 Nov: saat loss ECD 'belok kiri', biasanya masih di atas PP).
    Tanpa PWD sistem tidak melihat penurunan tekanan itu, jadi diberi tahu; overbalance statis MW − PP ditampilkan
    sebagai cadangan yang tersisa bila kolom masih penuh."""
    seg = df.loc[a:b]
    ecd = _col(seg, "ecd").where(_col(seg, "ecd").between(7, 20))
    if "ecd_stale" in seg:
        ecd = ecd.where(~seg["ecd_stale"].fillna(False).astype(bool))
    ms = _col(seg, "margin_static").dropna()
    ob = ms.median() if len(ms) else np.nan
    extra = {"overbalance_static": None if pd.isna(ob) else round(float(ob), 2)}
    tail = "" if pd.isna(ob) else f" Overbalance statis MW − PP ≈ {ob:.2f} ppg (bila kolom penuh)."
    if ecd.notna().mean() < 0.5:
        return {"no_pwd": True, "note": LOSS_NOTE_NO_PWD + tail, **extra}
    low = (_col(seg, "mw") - ecd) >= DEFAULTS["ecd_below_mw_ppg"]
    if low.any():
        mg = (ecd - _col(seg, "lower_bit")).dropna()
        m = mg.min() if len(mg) else np.nan
        t2 = "" if pd.isna(m) else f" Margin ECD terukur ke PP min {m:.2f} ppg."
        return {"no_pwd": False, "note": LOSS_NOTE_BELOW_MW + t2, **extra}
    return {"no_pwd": False, **extra}


def packoff_potential(df: pd.DataFrame, fl: dict, alpha: float = DEFAULTS["po_transmission"]) -> pd.DataFrame:
    """ECD potensial di bawah sensor saat pack-off (sumbatan di bit/stabilizer).

    Sensor PWD ±40–45 ft di belakang bit (klien 28 Nov): sumbatan di bit/stabilizer tidak terbaca ECD terukur, tetapi
    SPP melihatnya. ΔSPP = kelebihan SPP terhadap baseline pada flow yang sama (detektor pack-off).
      ecd_po    = ECD acuan + α · ΔSPP / (0,052 · TVD bit)   estimasi (α = po_transmission)
      ecd_po_hi = ECD acuan + ΔSPP / (0,052 · TVD bit)       batas atas, skenario sumbatan total
    Hanya saat detektor pack-off aktif. Sebagian ΔSPP bisa dari motor/bit (uji 13 sumur: ECD terukur tidak ikut naik)."""
    out = pd.DataFrame(index=df.index, columns=["spp_excess", "ecd_po", "ecd_po_hi"], dtype=float)
    if "packoff" not in fl:
        return out
    m, _, rise, _ = fl["packoff"]
    spp, tvd = _col(df, "spp"), _col(df, "tvd_bit")
    ref = _col(df, "ecd").fillna(_col(df, "ecd_pred"))
    ex = (spp * rise / (100 + rise)).where(m.fillna(False).astype(bool) & (rise > 0))
    d = ex / (0.052 * tvd.where(tvd > 100))
    out["spp_excess"] = ex
    out["ecd_po"] = ref + alpha * d
    out["ecd_po_hi"] = ref + d
    return out


def _po_note(df: pd.DataFrame, seg: slice, alpha: float) -> dict:
    if "ecd_po" not in df:
        return {}
    po = df["ecd_po"].loc[seg]
    if po.notna().sum() == 0:
        return {}
    i = po.idxmax()
    fg = df["fg_bit"].loc[i] if "fg_bit" in df else np.nan
    o = {"ecd_po_max": round(float(po.loc[i]), 2), "ecd_po_hi_max": round(float(df["ecd_po_hi"].loc[i]), 2),
         "spp_excess_max": round(float(df["spp_excess"].loc[i]), 0)}
    txt = (f"ECD di bawah sensor ±{o['ecd_po_max']:.2f} ppg ({alpha:.0%} dari ΔSPP {o['spp_excess_max']:.0f} psi; "
           f"batas atas sumbatan total {o['ecd_po_hi_max']:.2f})")
    if pd.notna(fg):
        o["fg_bit"] = round(float(fg), 2)
        txt += f"; FG bit {fg:.2f}" + (" → MELEBIHI FG" if po.loc[i] > fg else "")
    o["po_note"] = txt
    return o


def episodes(df: pd.DataFrame, fl: dict, p: dict) -> list[dict]:
    out = []
    gap = pd.Timedelta(minutes=2)
    mind = pd.Timedelta(minutes=p["min_duration_min"])
    md = _col(df, "bit_depth")
    st = _col(df, "state")
    for key, (mask, lvl, val, base) in fl.items():
        mask = mask.fillna(False).astype(bool)
        if not mask.any():
            continue
        idx = df.index[mask.to_numpy()]
        start = prev = idx[0]
        groups = []
        for t in idx[1:]:
            if t - prev > gap:
                groups.append((start, prev))
                start = t
            prev = t
        groups.append((start, prev))
        for a, b in groups:
            seg = slice(a, b)
            if (b - a) < mind and key not in ("tag", "influx", "loss"):
                continue
            levels = lvl.loc[seg][mask.loc[seg]]
            level = max(levels, key=lambda x: LEVEL_W.get(x, 0)) if len(levels) else "ADVISORY"
            v = val.loc[seg]
            peak = v.max() if key not in ("static_mw",) else v.min()
            out.append({
                "detector": key, "label": LABELS[key], "level": level,
                "start": a.isoformat(), "end": b.isoformat(),
                "md": None if pd.isna(md.loc[a]) else float(md.loc[a]),
                "value": None if pd.isna(peak) else float(peak),
                "baseline": None if pd.isna(base.loc[a]) else float(base.loc[a]),
                "state": None if pd.isna(st.loc[a]) else str(st.loc[a]),
                "rec": RECS[key],
                **(loss_note(df, a, b) if key == "loss" else {}),
                **(_po_note(df, seg, p["po_transmission"]) if key == "packoff" else {}),
            })
    out.sort(key=lambda d: d["start"])
    return out


def risk_score(df: pd.DataFrame, fl: dict) -> pd.Series:
    """1 − Π(1 − w_i·aktif_i), dengan peluruhan 30 mnt setelah indikator padam."""
    decay = _n(df, 30)
    acc = pd.Series(1.0, index=df.index)
    for mask, lvl, _, _ in fl.values():
        w = lvl.map(LEVEL_W).fillna(0.3) * mask.fillna(False).astype(float)
        w = w.rolling(decay, min_periods=1).max() * 0.85 + w * 0.15
        acc = acc * (1 - w.clip(0, 0.95))
    return (1 - acc).clip(0, 1)


def run(df: pd.DataFrame, params: dict | None = None) -> dict:
    p = {**DEFAULTS, **(params or {})}
    if df.empty:
        return {"detections": [], "score": pd.Series(dtype=float)}
    fl = flags(df, p)
    po = packoff_potential(df, fl, p["po_transmission"])
    df = df.assign(spp_excess=po["spp_excess"], ecd_po=po["ecd_po"], ecd_po_hi=po["ecd_po_hi"])
    return {"detections": episodes(df, fl, p), "score": risk_score(df, fl), "flags": fl, "packoff_potential": po}
