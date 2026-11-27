"""Trip performance (trip in / trip out): waktu in-slip & out-of-slip per stand dari hookload dan bit depth.

Prinsip (data surface Rec 01, tanpa kanal slips khusus):
  * In slips  : string digantung di slips → hookload hanya berat block/top drive (±15–30 klb).
  * Out of slips: string tergantung di elevator/top drive → hookload naik ke berat string.
  Ambang in-slip = berat block + `slip_margin_klb`. Berat block = persentil 5 hookload saat bit jauh di atas dasar
  (dihitung per periode), jadi tiap rig/sumur memakai berat blocknya sendiri.

Satu SIKLUS STAND = in-slip (sambung/lepas sambungan) → out-of-slip (stand diturunkan/diangkat, bit bergerak satu stand)
  * TIH: bit bergerak turun (bit depth naik) 1 stand saat out-of-slip.
  * TOH: bit bergerak naik (bit depth turun) 1 stand saat out-of-slip.
  Waktu in-slip = slips terpasang → slips dilepas (connection time). Waktu out-of-slip = slips dilepas → slips
  terpasang lagi (waktu memindahkan satu stand). Siklus = in-slip + out-of-slip.
In-slip lebih lama dari `in_max_s` (mis. flow check, perbaikan, menunggu) tidak masuk median, dicatat sebagai berhenti.

KPI ala laporan SLB / dokumen "RTO Performa Best Practice" (klien, Nov 2026):
  * Siklus per stand/joint = out-of-slip → out-of-slip berikutnya (stand berikutnya dalam trip yang sama).
    Estimated JPH (joint/stand per jam) = 60 / siklus (menit). Garis utama = rolling 5 stand; ringkasan = median.
  * In-slip time & moving time (= out-of-slip) per stand: median dan P25 (makin kecil makin baik).
  * Gross trip speed = kedalaman ditempuh / waktu berlalu (termasuk berhenti) per lokasi (cased / open hole, dari shoe).
  * Target: P75 stand/jam, P25 in-slip, P25 moving, gross ft/jam — diisi manual (Setting 'trip_targets'); bila kosong
    dibandingkan dengan P75/P25 data periode itu sendiri. Crew AM = 06:00–18:00 WIB, PM = sisanya.
  * Mode 'joint' (casing single ±40 ft) memakai rentang gerak 25–50 ft; mode 'stand' (DP double PHR ±62 ft) 55–105 ft.

Trip = rangkaian siklus searah dengan jeda < `trip_gap_min` dan ≥ `trip_min_stands` stand.
Hanya saat bit ≥ `off_bottom_ft` di atas dasar (bukan sambungan saat drilling).
Resolusi: waktu slips butuh data rapat. Sampel > `warn_step_s` detik diberi peringatan, > `max_step_s` tidak dihitung
(PDSI 53.2 rig LAS ±78 detik/sampel, satu sambungan hanya 1–3 menit).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import get_settings

DEFAULTS = {
    "off_bottom_ft": 100.0,     # bit minimal sejauh ini di atas dasar lubang
    "slip_margin_klb": 15.0,    # ambang in-slip = berat block + x
    "stand_min_ft": 55.0,       # gerak bit satu stand (double ±60 ft, triple ±93 ft)
    "stand_max_ft": 105.0,
    "still_ft": 5.0,            # bit dianggap diam saat in-slip
    "in_min_s": 6.0,
    "in_max_s": 900.0,          # in-slip > 15 mnt = berhenti (flow check, perbaikan, menunggu)
    "out_max_s": 900.0,
    "trip_gap_min": 45.0,
    "trip_min_stands": 5,
    "bin_ft": 1000.0,
    "warn_step_s": 10.0,
    "max_step_s": 30.0,
    "gap_s": 60.0,              # data kosong lebih lama dari ini memutus segmen
    "worse_tol_pct": 20.0,      # interpretasi: lebih buruk dari target > x% dianggap menyimpang
}
UNITS = {"stand": {"stand_min_ft": 55.0, "stand_max_ft": 105.0},   # DP/BHA, PHR racking double ±62 ft
         "joint": {"stand_min_ft": 25.0, "stand_max_ft": 50.0}}    # casing single (range 3 ±40 ft)
SHIFT_AM = (6, 18)              # jam WIB crew AM (klien)
# target manual (Setting 'trip_targets'): per mode × lokasi; None = pakai P75/P25 data periode itu
DEFAULT_TARGETS = {
    "gross_ft_h": 525.0,        # 75% × 700 ft/jam (target PHR, klien 28 Nov 2026)
    "stand": {"cased": {"jph": None, "in_min": None, "move_min": None}, "open": {"jph": None, "in_min": None, "move_min": None}},
    "joint": {"cased": {"jph": None, "in_min": None, "move_min": None}, "open": {"jph": None, "in_min": None, "move_min": None}},
}
LOC_LABEL = {"all": "Semua", "cased": "Cased hole", "open": "Open hole"}


def merge_targets(saved: dict | None) -> dict:
    t = {"gross_ft_h": DEFAULT_TARGETS["gross_ft_h"],
         **{u: {l: dict(v) for l, v in DEFAULT_TARGETS[u].items()} for u in UNITS}}
    for k, v in (saved or {}).items():
        if k == "gross_ft_h":
            t[k] = v
        elif k in UNITS and isinstance(v, dict):
            for l, d in v.items():
                if l in t[k] and isinstance(d, dict):
                    t[k][l].update({kk: d[kk] for kk in t[k][l] if kk in d})
    return t


def _q(s: pd.Series, q: float):
    s = s.dropna()
    return None if s.empty else round(float(s.quantile(q)), 2)


def _stats(in_s: pd.Series, out_s: pd.Series) -> dict:
    """Median dan p25–p75 dalam MENIT."""
    i, o = in_s.dropna() / 60, out_s.dropna() / 60
    return {"n_in": int(len(i)), "n_out": int(len(o)),
            "in_med": _q(i, .5), "in_p25": _q(i, .25), "in_p75": _q(i, .75),
            "out_med": _q(o, .5), "out_p25": _q(o, .25), "out_p75": _q(o, .75),
            "cycle_med": round(float(i.median() + o.median()), 2) if len(i) and len(o) else None}


def segments(df: pd.DataFrame, p: dict) -> tuple[pd.DataFrame, dict]:
    """Potong data jadi segmen in-slip / out-of-slip. df: hookload, bit_depth, hole_depth (indeks waktu)."""
    d = df[["hookload", "bit_depth", "hole_depth"]].copy()
    d["flow_in"] = df["flow_in"] if "flow_in" in df else np.nan
    d = d.dropna(subset=["hookload", "bit_depth"])
    if len(d) < 20:
        return pd.DataFrame(), {}
    step = float(d.index.to_series().diff().dt.total_seconds().median())
    hk = d["hookload"].rolling(3, center=True, min_periods=1).median()
    off = (d["hole_depth"] - d["bit_depth"]) >= p["off_bottom_ft"]
    if off.sum() < 20:
        return pd.DataFrame(), {"step_s": step}
    block = float(np.nanpercentile(hk[off], 5))
    thr = block + p["slip_margin_klb"]
    ins = hk < thr
    t = d.index.to_series()
    brk = (ins != ins.shift()) | (t.diff().dt.total_seconds() > p["gap_s"])
    g = brk.cumsum()
    grp = d.assign(ins=ins, off=off, hk=hk, t=t).groupby(g)
    seg = pd.DataFrame({
        "a": grp["t"].first(), "b": grp["t"].last(), "ins": grp["ins"].first(),
        "bit0": grp["bit_depth"].first(), "bit1": grp["bit_depth"].last(),
        "bit_rng": grp["bit_depth"].max() - grp["bit_depth"].min(),
        "off": grp["off"].mean() > 0.9, "hk": grp["hk"].median(), "flow": grp["flow_in"].median(),
    })
    # durasi: sampai sampel pertama segmen berikutnya (bila bersambung), jadi tidak bergantung resolusi
    nxt = seg["a"].shift(-1)
    cont = (nxt - seg["b"]).dt.total_seconds() <= p["gap_s"]
    end = seg["b"].where(~cont, nxt).fillna(seg["b"] + pd.Timedelta(seconds=step))
    seg["dur"] = (end - seg["a"]).dt.total_seconds()
    seg["dbit"] = seg["bit1"] - seg["bit0"]
    seg = seg.reset_index(drop=True)
    return seg, {"step_s": step, "block_klb": round(block, 1), "threshold_klb": round(thr, 1)}


def stands(seg: pd.DataFrame, p: dict) -> pd.DataFrame:
    """Satu baris per stand: out-of-slip yang memindahkan bit satu stand, dengan in-slip tepat sebelumnya."""
    if seg.empty:
        return pd.DataFrame()
    out = seg[~seg["ins"] & seg["off"] & seg["dbit"].abs().between(p["stand_min_ft"], p["stand_max_ft"])
              & (seg["dur"] <= p["out_max_s"])]
    rows = []
    for i, r in out.iterrows():
        prev = seg.loc[i - 1] if i - 1 in seg.index else None
        in_s, stop = None, False
        if prev is not None and prev["ins"] and prev["off"] and prev["bit_rng"] <= p["still_ft"] \
                and (r["a"] - prev["b"]).total_seconds() <= p["gap_s"]:
            if p["in_min_s"] <= prev["dur"] <= p["in_max_s"]:
                in_s = float(prev["dur"])
            elif prev["dur"] > p["in_max_s"]:
                stop = True
        # awal gerak = posisi bit saat masih di slips (sampel pertama out-of-slip sudah bergerak)
        md0 = float(prev["bit1"]) if prev is not None and (r["a"] - prev["b"]).total_seconds() <= p["gap_s"] else float(r["bit0"])
        rows.append({"t": r["a"], "t_in": prev["a"] if in_s is not None else None, "dir": "TIH" if r["dbit"] > 0 else "TOH",
                     "md": float(r["bit1"]), "ft": round(abs(float(r["bit1"]) - md0), 1), "in_s": in_s, "out_s": float(r["dur"]),
                     "stop_before": stop, "hk": round(float(r["hk"]), 1),
                     "pumping": bool(pd.notna(r["flow"]) and r["flow"] > get_settings().flow_min_gpm)})
    return pd.DataFrame(rows)


def trip_groups(st: pd.DataFrame, p: dict) -> pd.Series:
    """Nomor trip per stand (st terurut waktu); -1 = stand lepas (bukan bagian trip)."""
    gap = st["t"].diff().dt.total_seconds() / 60
    g = ((st["dir"] != st["dir"].shift()) | (gap > p["trip_gap_min"])).cumsum()
    n = g.map(g.value_counts())
    return g.where(n >= p["trip_min_stands"], -1)


def trips(st: pd.DataFrame, p: dict) -> list[dict]:
    """Kelompokkan stand searah berurutan menjadi trip. st terurut waktu dengan kolom 'trip' (trip_groups)."""
    if st.empty:
        return []
    out = []
    for k, s in st.groupby("trip"):
        if k < 0:
            continue
        a = s["t_in"].dropna().min() if s["t_in"].notna().any() else s["t"].iloc[0]
        a = min(a, s["t"].iloc[0])
        b = s["t"].iloc[-1] + pd.Timedelta(seconds=float(s["out_s"].iloc[-1]))
        h = max((b - a).total_seconds() / 3600, 1e-6)
        md0 = float(s["md"].iloc[0] - (s["ft"].iloc[0] if s["dir"].iloc[0] == "TIH" else -s["ft"].iloc[0]))
        md1 = float(s["md"].iloc[-1])
        out.append({"dir": s["dir"].iloc[0], "start": a.isoformat(), "end": b.isoformat(), "hours": round(h, 2),
                    "md_from": round(md0), "md_to": round(md1), "stands": int(len(s)),
                    "stands_per_h": round(len(s) / h, 1), "ft_per_h": round(abs(md1 - md0) / h),
                    "ft_per_h_moving": round(float((s["ft"] / (s["out_s"] / 3600)).median())),
                    "stops": int(s["stop_before"].sum()), "pumping_pct": round(100 * float(s["pumping"].mean())),
                    "jph_med": _q(s["jph"], .5), **_stats(s["in_s"], s["out_s"])})
    return out


def add_cycles(st: pd.DataFrame, p: dict, shoe_md: float | None) -> pd.DataFrame:
    """Siklus out-of-slip → out-of-slip berikutnya, JPH, rolling 5, crew, lokasi. st: kolom 'trip' sudah ada."""
    st = st.copy()
    nxt_t = st.groupby("trip")["t"].shift(-1)
    nxt_stop = st.groupby("trip")["stop_before"].shift(-1).eq(True)
    span = (nxt_t - st["t"]).dt.total_seconds()
    last = st["out_s"] + st["in_s"].fillna(0)
    # waktu berlalu per stand (gross, termasuk berhenti); stand terakhir trip = out-of-slip + in-slip sebelumnya
    st["elapsed_s"] = span.fillna(last)
    ok = span.notna() & ~nxt_stop & (span <= p["in_max_s"] + p["out_max_s"])
    st["cycle_s"] = span.where(ok)
    st["jph"] = 3600 / st["cycle_s"]
    roll = st.groupby("trip")["cycle_s"].transform(lambda c: c.rolling(5, min_periods=3).mean())
    st["jph_roll"] = 3600 / roll
    hour = st["t"].dt.tz_convert(get_settings().display_tz).dt.hour
    st["crew"] = np.where((hour >= SHIFT_AM[0]) & (hour < SHIFT_AM[1]), "AM", "PM")
    st["loc"] = None if not shoe_md else np.where(st["md"] <= shoe_md, "cased", "open")
    return st


def _pct(v, t):
    if v is None or t in (None, 0):
        return None
    return round(100 * (v - t) / t, 1)


def kpi(s: pd.DataFrame, tgt: dict, gross_target: float | None, p: dict) -> dict:
    """KPI satu kelompok (arah × lokasi): median, target (manual atau P75/P25 data), selisih %, interpretasi."""
    cyc, ins, mov = s["jph"].dropna(), s["in_s"].dropna() / 60, s["out_s"].dropna() / 60
    elapsed = float(s["elapsed_s"].sum())
    gross = round(float(s["ft"].sum()) / (elapsed / 3600)) if elapsed > 0 else None
    r = {"n": int(len(s)), "jph_med": _q(cyc, .5), "in_med": _q(ins, .5), "move_med": _q(mov, .5), "gross_ft_h": gross,
         "jph_p75_data": _q(cyc, .75), "in_p25_data": _q(ins, .25), "move_p25_data": _q(mov, .25),
         "in_p75": _q(ins, .75), "move_p75": _q(mov, .75), "n_in": int(len(ins)),
         "ft": round(float(s["ft"].sum())), "hours": round(elapsed / 3600, 2)}
    tj, ti, tm = tgt.get("jph"), tgt.get("in_min"), tgt.get("move_min")
    r["target"] = {"jph": tj if tj is not None else r["jph_p75_data"], "in_min": ti if ti is not None else r["in_p25_data"],
                   "move_min": tm if tm is not None else r["move_p25_data"], "gross_ft_h": gross_target,
                   "manual": {"jph": tj is not None, "in_min": ti is not None, "move_min": tm is not None,
                              "gross_ft_h": gross_target is not None}}
    T = r["target"]
    r["vs"] = {"jph": _pct(r["jph_med"], T["jph"]), "in_min": _pct(r["in_med"], T["in_min"]),
               "move_min": _pct(r["move_med"], T["move_min"]), "gross_ft_h": _pct(gross, gross_target)}
    # interpretasi hanya terhadap target MANUAL: median vs P25 data sendiri selalu "lebih buruk" (definisi persentil)
    tol, man = p["worse_tol_pct"], T["manual"]
    move_hi = man["move_min"] and (r["vs"]["move_min"] or 0) > tol
    in_hi = man["in_min"] and (r["vs"]["in_min"] or 0) > tol
    gross_lo = man["gross_ft_h"] and r["vs"]["gross_ft_h"] is not None and r["vs"]["gross_ft_h"] < 0
    notes = []
    if move_hi:
        notes.append("Moving time di atas target → indikasi drag, restriction, atau batasan surge/swab.")
    if in_hi:
        notes.append("In-slip time di atas target → indikasi crew, handling, atau make-up/break-out.")
    if gross_lo and move_hi:
        notes.append("Gross speed turun dan moving time naik → indikasi kondisi lubang (cek hookload vs depth).")
    elif gross_lo and man["move_min"]:
        notes.append("Gross speed di bawah target sementara moving time normal → bottleneck di proses connection / berhenti.")
    elif gross_lo:
        notes.append("Gross speed di bawah target. Isi target moving time untuk membedakan masalah connection vs kondisi lubang.")
    r["notes"] = notes
    return r


def by_depth(st: pd.DataFrame, p: dict, shoe_md: float | None = None) -> list[dict]:
    if st.empty:
        return []
    b = p["bin_ft"]
    st = st.assign(bin=(st["md"] // b) * b)
    rows = []
    for (d, lo), s in st.groupby(["dir", "bin"]):
        r = {"dir": d, "md_from": int(lo), "md_to": int(lo + b), **_stats(s["in_s"], s["out_s"])}
        if shoe_md:
            r["zone"] = "cased" if lo + b <= shoe_md else ("open hole" if lo >= shoe_md else "campuran")
        rows.append(r)
    return rows


def analyze(df: pd.DataFrame, params: dict | None = None, shoe_md: float | None = None, max_stands: int = 3000,
            unit: str = "stand", targets: dict | None = None) -> dict:
    """Ringkasan trip performance untuk satu periode data (indeks waktu UTC)."""
    if unit not in UNITS:
        raise ValueError(f"unit harus salah satu dari {list(UNITS)}")
    p = {**DEFAULTS, **UNITS[unit], **(params or {})}
    tg = merge_targets(targets)
    res = {"params": p, "unit": unit, "targets": tg, "warnings": [], "summary": {}, "kpi": {}, "trips": [], "by_depth": [],
           "stands": [], "step_s": None}
    if df.empty or "hookload" not in df or df["hookload"].notna().sum() < 20:
        res["warnings"].append("Hookload kosong: trip performance tidak bisa dihitung.")
        return res
    seg, meta = segments(df, p)
    res.update(meta)
    step = meta.get("step_s")
    if step and step > p["max_step_s"]:
        res["warnings"].append(f"Resolusi data ±{step:.0f} detik/sampel: terlalu kasar untuk waktu slips "
                               f"(satu sambungan ±1–3 menit). Perlu data ≤ {p['warn_step_s']:.0f} detik.")
        return res
    if step and step > p["warn_step_s"]:
        res["warnings"].append(f"Resolusi data ±{step:.0f} detik/sampel: waktu slips berketelitian ±{step:.0f} detik.")
    if seg.empty:
        res["warnings"].append("Tidak ada periode bit jauh di atas dasar (trip) di rentang ini.")
        return res
    st = stands(seg, p)
    if st.empty:
        res["warnings"].append("Tidak ada stand terdeteksi (tidak ada trip di rentang ini).")
        return res
    st = st.sort_values("t").reset_index(drop=True)
    st["trip"] = trip_groups(st, p)
    # ringkasan hanya dari stand yang termasuk trip (stand lepas, mis. saat reaming/kerja pipa, tidak dihitung)
    sti = add_cycles(st[st["trip"] >= 0], p, shoe_md)
    tr = trips(sti, p)
    for d in ("TIH", "TOH"):
        s = sti[sti["dir"] == d]
        if len(s):
            trs = [t for t in tr if t["dir"] == d]
            res["summary"][d] = {**_stats(s["in_s"], s["out_s"]), "stands": int(len(s)), "trips": len(trs),
                                 "stands_per_h_med": round(float(np.median([t["stands_per_h"] for t in trs])), 1),
                                 "ft_per_h_med": round(float(np.median([t["ft_per_h"] for t in trs])))}
            res["kpi"][d] = {}
            for loc in ("all", "cased", "open"):
                ss = s if loc == "all" else s[s["loc"] == loc]
                if len(ss) == 0:
                    continue
                res["kpi"][d][loc] = kpi(ss, {} if loc == "all" else tg[unit][loc], tg.get("gross_ft_h"), p)
    res["trips"] = tr
    res["by_depth"] = by_depth(sti, p, shoe_md)
    show = sti.tail(max_stands)
    nn = lambda v, k=2: None if v is None or pd.isna(v) else round(float(v), k)
    res["stands"] = [{"t": r.t.isoformat(), "dir": r.dir, "md": round(r.md), "ft": r.ft, "trip": int(r.trip),
                      "in_min": nn(r.in_s / 60 if r.in_s is not None and not pd.isna(r.in_s) else None),
                      "out_min": round(r.out_s / 60, 2), "cycle_min": nn(r.cycle_s / 60), "jph": nn(r.jph, 1),
                      "jph_roll": nn(r.jph_roll, 1), "crew": r.crew, "loc": r.loc, "hk": r.hk,
                      "pumping": r.pumping} for r in show.itertuples()]
    res["n_stands_total"] = int(len(sti))
    return res
