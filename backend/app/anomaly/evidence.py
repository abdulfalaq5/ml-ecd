"""Bukti kuantitatif per episode deteksi: nilai aktual vs nilai yang diharapkan, selisih, dan seberapa tidak biasa.

Klien 28 Nov: rekomendasi alert diminta "secanggih T&D" (hookload aktual vs prediksi + statistik). Tiap episode
mendapat `facts` terstruktur (dirender frontend dalam EN/ID) dan `summary` (teks Indonesia untuk laporan/Excel):

  fact = {k, v, exp?, ref?, unit, d?, dp?, z?, pct?, n_ctx?}
    k    kanal / besaran (spp, torque, hookload, ...)          v   nilai di puncak episode
    exp  nilai yang diharapkan; ref = dasar harapannya:        d   v − exp,  dp  (v/exp − 1)·100 %
         same_flow (baseline SPP dikoreksi ke flow sekarang), baseline (median 60 mnt sebelumnya, jeda 10 mnt),
         before (median jendela sebelum lonjakan), model (ECD ⓥ), limit (ambang / batas desain)
    z    (v − median konteks) / (1,4826·MAD konteks)          pct  % titik konteks yang lebih kecil dari v
         konteks = data MASA LALU sumur ini s/d awal episode (maks 6 jam, kondisi operasi yang sama)
  repeat = {n_24h, n_depth, depth_ft}: episode detektor sama dalam 24 jam terakhir / di kedalaman ±100 ft

Tidak ada look-ahead: semua pembanding diambil dari data sebelum awal episode (kecuali nilai puncak episode itu)."""
from __future__ import annotations

import numpy as np
import pandas as pd

CTX_H = 6.0
CTX_MIN_N = 20
REPEAT_DEPTH_FT = 100.0
PUMPS = ["DRILL_ROT", "SLIDE", "REAM", "WASH", "CIRC"]
# di bawah nilai harapan ini persentase selisih tidak bermakna (mis. WOB 3,3 vs 0,7 klb = "+391 %")
DP_MIN_EXP = {"klb": 2.0, "kft·lb": 1.0, "%": 5.0, "gpm": 50.0, "psi": 100.0, "rpm": 5.0, "bbl": 1e9, "ft": 1e9}
ZERO = {"klb": 0.5, "kft·lb": 0.3, "gpm": 10.0, "psi": 20.0, "rpm": 2.0}


def _c(df, c):
    return df[c] if c in df else pd.Series(np.nan, index=df.index)


def _r(x, nd=2):
    return None if x is None or pd.isna(x) or not np.isfinite(x) else round(float(x), nd)


def _ctx(s: pd.Series, a: pd.Timestamp, v: float, where: pd.Series | None = None) -> dict:
    """Seberapa tidak biasa v dibanding data sumur ini s/d awal episode (maks CTX_H jam)."""
    past = s.loc[a - pd.Timedelta(hours=CTX_H):a].iloc[:-1]
    if where is not None:
        past = past[where.reindex(past.index).fillna(False).astype(bool)]
    past = past.dropna()
    if len(past) < CTX_MIN_N or pd.isna(v):
        return {}
    med = past.median()
    mad = (past - med).abs().median() * 1.4826
    out = {"pct": _r(100 * (past < v).mean(), 0), "n_ctx": int(len(past))}
    if mad > 1e-9:
        out["z"] = _r((v - med) / mad, 1)
    return out


def _fact(k, v, unit, exp=None, ref=None, nd=2, **ctx) -> dict:
    f = {"k": k, "v": _r(v, nd), "unit": unit}
    if exp is not None and pd.notna(exp):
        f |= {"exp": _r(exp, nd), "ref": ref, "d": _r(v - exp, nd)}
        if abs(exp) >= DP_MIN_EXP.get(unit, 1e-9):
            f["dp"] = _r((v / exp - 1) * 100, 0)
    return f | {k2: v2 for k2, v2 in ctx.items() if v2 is not None}


def _peak(s: pd.Series, m: pd.Series, seg: slice, lowest=False):
    x = s.loc[seg][m.loc[seg].fillna(False).astype(bool)].dropna()
    if x.empty:
        return None
    return x.idxmin() if lowest else x.idxmax()


def _base(s: pd.Series, where: pd.Series, a: pd.Timestamp, minutes=60, lag=10) -> float:
    w = s.loc[a - pd.Timedelta(minutes=minutes + lag):a - pd.Timedelta(minutes=lag)]
    w = w[where.reindex(w.index).fillna(False).astype(bool)].dropna()
    return float(w.median()) if len(w) >= 3 else np.nan


def facts_for(key: str, df: pd.DataFrame, fl: dict, a: pd.Timestamp, b: pd.Timestamp) -> list[dict]:
    z = lambda f: f["v"] is not None and abs(f["v"]) < ZERO.get(f["unit"], -1) and abs(f.get("exp") or 0) < ZERO.get(f["unit"], -1)
    return [f for f in _facts(key, df, fl, a, b) if f["v"] is not None and not z(f)]


def _facts(key: str, df: pd.DataFrame, fl: dict, a: pd.Timestamp, b: pd.Timestamp) -> list[dict]:
    seg = slice(a, b)
    mask, _, val, base = fl[key]
    st = _c(df, "state").fillna("UNKNOWN")
    pumps = st.isin(PUMPS)
    spp, q, tq, rpm = _c(df, "spp"), _c(df, "flow_in"), _c(df, "torque"), _c(df, "rpm")
    hook, wob = _c(df, "hookload"), _c(df, "wob")
    out: list[dict] = []

    if key == "packoff":
        i = _peak(val, mask, seg)
        if i is None:
            return out
        rise = val.loc[i]
        exp = spp.loc[i] / (1 + rise / 100) if pd.notna(rise) else np.nan
        out.append(_fact("spp", spp.loc[i], "psi", exp, "same_flow", 0, **_ctx(val, a, rise, pumps)))
        qb = _base(q, pumps, a)
        out.append(_fact("flow_in", q.loc[i], "gpm", qb, "baseline", 0))
        tb = _base(tq, pumps, a)
        if pd.notna(tq.loc[i]) and pd.notna(tb):
            out.append(_fact("torque", tq.loc[i], "kft·lb", tb, "baseline", 1))
    elif key == "torque":
        i = _peak(tq, mask, seg)
        if i is None:
            return out
        on = rpm > 5
        out.append(_fact("torque", tq.loc[i], "kft·lb", _base(tq, on, a), "baseline", 1, **_ctx(tq, a, tq.loc[i], on)))
        out.append(_fact("rpm", rpm.loc[i], "rpm", _base(rpm, on, a, 5, 1), "before", 0))
        if pd.notna(wob.loc[i]):
            out.append(_fact("wob", wob.loc[i], "klb", _base(wob, on, a), "baseline", 1))
    elif key == "overpull":
        i = _peak(hook, mask, seg)
        if i is None:
            return out
        up = _c(df, "block_vel") < -0.5
        pu = base.loc[a]
        out.append(_fact("hookload_pu", hook.loc[i], "klb", pu, "baseline", 0, **_ctx(hook - base, a, hook.loc[i] - pu, up)))
    elif key == "tag":
        i = _peak(wob, mask, seg)
        if i is None:
            return out
        down = (_c(df, "block_vel") > 0.5) & (_c(df, "off_bottom") > 2)
        out.append(_fact("wob", wob.loc[i], "klb", base.loc[a], "baseline", 1, **_ctx(wob, a, wob.loc[i], down)))
        out.append(_fact("off_bottom", _c(df, "off_bottom").loc[i], "ft", nd=0))
    elif key == "ecdv_spike":
        i = _peak(val, mask, seg)
        if i is None:
            return out
        e = df["ecd_model"] if "ecd_model" in df else _c(df, "ecd_pred")
        out.append(_fact("ecd_pred", e.loc[i], "ppg", base.loc[i], "before", 2, **_ctx(val, a, val.loc[i], pumps)))
        w = pd.Timedelta(minutes=10)
        for k, s, u, nd in (("spp", spp, "psi", 0), ("torque", tq, "kft·lb", 1), ("flow_in", q, "gpm", 0)):
            prev = s.loc[i - 2 * w:i - w].median()
            if pd.notna(s.loc[i]) and pd.notna(prev):
                out.append(_fact(k, s.loc[i], u, prev, "before", nd))
    elif key == "residual":
        i = _peak(val, mask, seg)
        if i is None:
            return out
        e = df["ecd_model"] if "ecd_model" in df else _c(df, "ecd_pred")
        out.append(_fact("ecd", _c(df, "ecd").loc[i], "ppg", e.loc[i], "model", 2, **_ctx(val, a, val.loc[i], pumps)))
    elif key in ("loss", "influx"):
        fo, pit = _c(df, "flow_out_pct"), _c(df, "active_pit")
        i = _peak(fo, mask, seg, lowest=(key == "loss"))
        if i is None:
            i = a
        out.append(_fact("flow_out_pct", fo.loc[i], "%", base.loc[i] if pd.notna(base.loc[i]) else None, "baseline", 0))
        p0 = pit.loc[a - pd.Timedelta(minutes=10):a].dropna()
        pend = pit.loc[seg].dropna()
        if len(p0) and len(pend):
            ref_pit = float(p0.iloc[0])
            last = float(pend.min() if key == "loss" else pend.max())
            out.append(_fact("active_pit", last, "bbl", ref_pit, "before", 1))
        out.append(_fact("flow_in", q.loc[i], "gpm", _base(q, pumps, a), "baseline", 0))
        if key == "loss" and pd.notna(_c(df, "ecd").loc[i]) and pd.notna(_c(df, "mw").loc[i]):
            out.append(_fact("ecd", _c(df, "ecd").loc[i], "ppg", _c(df, "mw").loc[i], "mw", 2))
    elif key == "differential":
        i = b
        out.append(_fact("stationary_min", val.loc[b], "min", base.loc[a], "limit", 0))
        ms = _c(df, "margin_static").loc[seg].dropna()
        if len(ms):
            out.append(_fact("overbalance", ms.median(), "ppg", nd=2))
    elif key == "static_mw":
        i = _peak(val, mask, seg, lowest=True)
        if i is None:
            return out
        mw = _c(df, "mw").loc[i]
        lb = _c(df, "lower_bit").loc[i]
        out.append(_fact("mw", mw, "ppg", lb, "limit", 2))
    return out


def repeats(dets: list[dict], d: dict) -> dict:
    """Episode detektor sama sebelum episode ini: dalam 24 jam, dan di kedalaman ±100 ft (tight spot berulang)."""
    t = pd.Timestamp(d["start"])
    prev = [x for x in dets if x is not d and x["detector"] == d["detector"]
            and t - pd.Timedelta(hours=24) <= pd.Timestamp(x["start"]) < t]
    o = {"n_24h": len(prev)}
    if d.get("md") is not None:
        o["n_depth"] = sum(1 for x in prev if x.get("md") is not None and abs(x["md"] - d["md"]) <= REPEAT_DEPTH_FT)
        o["depth_ft"] = REPEAT_DEPTH_FT
    return o


# ---- ringkasan teks (Indonesia; frontend merender facts sendiri sesuai bahasa) ----
K_ID = {"spp": "SPP", "flow_in": "Flow in", "torque": "Torque", "rpm": "RPM", "wob": "WOB", "hookload_pu": "Hookload P/U",
        "off_bottom": "Jarak dari dasar", "ecd_pred": "ECD ⓥ", "ecd": "ECD terukur", "flow_out_pct": "Flow out",
        "active_pit": "Active pit", "stationary_min": "Pipa diam", "overbalance": "Overbalance statis MW − PP",
        "mw": "MW"}
REF_ID = {"same_flow": "harapan pada flow sama", "baseline": "baseline 60 mnt", "before": "sebelumnya",
          "model": "ECD ⓥ", "limit": "batas", "mw": "MW"}


def _num(x, unit):
    if x is None:
        return "—"
    nd = 2 if unit == "ppg" else (1 if unit in ("kft·lb", "klb", "bbl") else 0)
    return f"{x:,.{nd}f}".replace(",", ".") if nd == 0 else f"{x:.{nd}f}".replace(".", ",")


def summary(facts: list[dict], rep: dict | None = None) -> str:
    parts = []
    for f in facts:
        s = f"{K_ID.get(f['k'], f['k'])} {_num(f['v'], f['unit'])}"
        if f.get("exp") is not None:
            sign = "+" if (f.get("d") or 0) >= 0 else "−"
            s += f" vs {_num(f['exp'], f['unit'])} {f['unit']} ({REF_ID.get(f.get('ref'), '')}; {sign}{_num(abs(f['d']), f['unit'])}"
            s += f", {sign}{abs(f['dp']):.0f}%)" if f.get("dp") is not None else ")"
        else:
            s += f" {f['unit']}"
        if f.get("pct") is not None:
            s += f" — lebih tinggi dari {f['pct']:.0f}% data {CTX_H:.0f} jam terakhir"
            if f.get("z") is not None:
                s += f" ({f['z']:+.1f}× MAD)"
        parts.append(s)
    if rep and rep.get("n_depth"):
        parts.append(f"{rep['n_depth']}× sebelumnya di kedalaman ±{rep['depth_ft']:.0f} ft dalam 24 jam")
    elif rep and rep.get("n_24h"):
        parts.append(f"{rep['n_24h']}× dalam 24 jam")
    return "; ".join(parts)
