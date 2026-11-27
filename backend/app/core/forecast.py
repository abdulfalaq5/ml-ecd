"""Ramalan ECD ke depan berbasis rencana operasi (ECD roadmap) + uji coba what-if.

Klien (24 Nov 2026): hampir semua run PHR sudah punya ECD terukur; yang dibutuhkan adalah ramalan beberapa jam
ke depan (6–12 jam) untuk siaga, dan bisa mengubah flow / RPM / WOB / MW untuk melihat responsnya.

Kenapa berbasis rencana: ramalan dari tren data saja lebih buruk daripada "ECD tetap" (uji BDSI 61), karena ECD
ke depan ditentukan keputusan yang belum terjadi. Jadi rencana operasi adalah input, seperti roadmap T&D.

Cara hitung tiap titik waktu (30 dtk) sepanjang rencana:
  1. ECD acuan = model ECD ⓥ pada kedalaman/TVD/MW rencana, dengan parameter ACUAN (kondisi 1 jam terakhir)
     + koreksi bias dari ECD terukur 1 jam terakhir (nilai beku setelah pompa mati tidak dipakai).
  2. Rugi gesek acuan APL = ECD acuan − MW.
  3. Respons parameter (fisika, sementara sampai PV/YP + hole size tersedia):
       flow : APL × (Q/Q_acuan)^n            n default 0,6 (aliran laminar annulus, power-law)
       RPM  : APL × (1 + k·ΔRPM/100)          k default 0,05 (rotasi menaikkan rugi gesek; kecil)
       WOB  : ROP = ROP_acuan × (WOB/WOB_acuan) → beban cutting annulus (konsentrasi cutting × (ρ_cutting − MW)),
              hanya bila ROP tidak dipaksa oleh target kedalaman + jam
     Model ML saja tidak dipakai untuk respons ini: uji BDSI 61 flow +10% → ECD ⓥ turun (arah salah), ROP tanpa efek.
  4. Pompa mati (sambung pipa): ECD = ESD ≈ MW (tidak ada rugi gesek). Sambungan disisipkan tiap `every_ft`
     selama `off_min` (default dari data sumur: BDSI 61 / ACS26 / BDSI 18 ≈ 62 ft, 5–6 menit).
  5. Margin terhadap PPFG approved di kedalaman rencana: sirkulasi vs FG & max(PP,SFG); pompa mati vs max(PP,SFG).

Lonjakan saat pompa hidup (surge) belum dimodelkan: ECD terukur masih beku ±5–7 menit setelah pompa hidup.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from ..config import get_settings
from . import hydraulics as hy
from .features import FEATURES, stale_ecd_mask
from .margins import add_margins

CUTTINGS_PPG = 21.7            # 2,6 SG
DEFAULT_CFG = {
    "step_s": 30, "calib_min": 60,
    "flow_exp": 0.6, "rpm_k": 0.05, "wob_rop_exp": 1.0,
    "hole_size": 8.5, "transport": 0.6, "cut_tau_min": 30.0, "cut_hole_size": 8.5,
    "every_ft": 62.0, "off_min": 5.5,
    # hidraulika annulus (core/hydraulics.py): respons flow = APL(Q)/APL(Q acuan) pada geometri yang sama
    # "auto" = aktif hanya bila PV & YP diisi. Uji mundur 5 sumur (24 Nov) dengan PV/YP contoh + lubang 8,5" untuk
    # semua section: MAE median 12 jam 0,141 (respons sementara) vs 0,156 (hidraulika) → tanpa data klien tidak dipakai.
    "hydraulics": "auto", "pv": None, "yp": None, "casing_id": None, "preset": None,
    "base": "hyd",       # dasar rugi gesek vs kedalaman/MW: "hyd" = hidraulika × kalibrasi; "ml" = ECD ⓥ + koreksi
}
DEFAULT_TH = {"advisory_margin": 0.5, "warning_margin": 0.25, "critical_margin": 0.0}
CTRL = ("flow", "rpm", "wob", "rop", "mw")
Predictor = Callable[[pd.DataFrame], np.ndarray]


def predictor_from_artifact(art: dict | None) -> Predictor | None:
    if not art:
        return None
    feats = art["features"]
    return lambda X: art["model"].predict(X[feats])


# ------------------------------------------------------------------ acuan dari data sebelum T

@dataclass
class Reference:
    t0: pd.Timestamp
    bit_md: float
    hole_md: float
    mw: float
    flow: float
    rpm: float
    wob: float
    rop: float
    apl: float                       # ECD − MW terukur (median), atau dari model bila tak ada ECD
    bias: float                      # ECD terukur − ECD ⓥ (median)
    n_calib: int                     # jumlah titik ECD terukur untuk koreksi
    x: dict = field(default_factory=dict)     # nilai fitur acuan (median jendela)
    notes: list = field(default_factory=list)

    def public(self) -> dict:
        d = asdict(self)
        d.pop("x")
        d["t0"] = self.t0.isoformat()
        return {k: (round(v, 3) if isinstance(v, float) else v) for k, v in d.items()}


def _med(s: pd.Series, default: float = np.nan) -> float:
    s = s.dropna()
    return float(s.median()) if len(s) else default


def reference(hist: pd.DataFrame, predict: Predictor | None, cfg: dict | None = None) -> Reference:
    """Kondisi acuan dari jendela `calib_min` terakhir saat pompa hidup (sebelum jam potong T)."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    if hist.empty:
        raise ValueError("tidak ada data sebelum jam mulai ramalan")
    fmin = get_settings().flow_min_gpm
    t0 = hist.index[-1]
    pumping = hist[hist["flow_in"] > fmin]
    notes = []
    win = pumping[pumping.index >= t0 - pd.Timedelta(minutes=cfg["calib_min"])]
    if len(win) < 10:
        win = pumping[pumping.index >= t0 - pd.Timedelta(hours=12)]
        notes.append("pompa hidup < 10 titik dalam jendela kalibrasi; acuan diambil dari 12 jam terakhir")
    if win.empty:
        raise ValueError("tidak ada data pompa hidup dalam 12 jam sebelum jam mulai; acuan flow tidak bisa ditentukan")
    hcol = "hole_reached" if "hole_reached" in hist else "hole_depth" if "hole_depth" in hist else "bit_depth"
    hole = hist[hcol].dropna()                  # hole_reached: tahan glitch (mis. spike 9.909 ft GW339)
    drill = win[(win.get("rop", 0) > 0) & (win["state"].isin(["DRILL_ROT", "SLIDE"]) if "state" in win else True)]
    mw = _med(hist["mw"].tail(20))
    if np.isnan(mw):
        raise ValueError("MW (Rec 04) kosong; ramalan butuh MW")
    x = {f: _med(win[f]) if f in win else np.nan for f in FEATURES}
    ref = Reference(
        t0=t0, bit_md=float(hist["bit_depth"].dropna().iloc[-1]),
        hole_md=float(hole.iloc[-1] if hcol == "hole_reached" else hole.max()) if len(hole) else np.nan,
        mw=mw, flow=_med(win["flow_in"]), rpm=_med(win.get("rpm", pd.Series(dtype=float)), 0.0),
        wob=_med(drill.get("wob", pd.Series(dtype=float)), _med(win.get("wob", pd.Series(dtype=float)), 0.0)),
        rop=_med(drill.get("rop", pd.Series(dtype=float)), 0.0), apl=np.nan, bias=0.0, n_calib=0, x=x, notes=notes)
    # koreksi dari ECD terukur (bukan nilai beku)
    e = win["ecd"].where(win["ecd"].between(7, 20)) if "ecd" in win else pd.Series(np.nan, index=win.index)
    stale = win["ecd_stale"] if "ecd_stale" in win else stale_ecd_mask(hist).reindex(win.index)
    ok = e.notna() & ~stale.fillna(False).astype(bool) & win["mw"].notna()
    if ok.sum() >= 5:
        ref.apl = _med(e[ok] - win.loc[ok, "mw"])
        ref.n_calib = int(ok.sum())
        if predict is not None:
            X = win.loc[ok, FEATURES].fillna(pd.Series(x))
            ref.bias = float(np.median(e[ok].to_numpy() - predict(X)))
    else:
        notes.append("tidak ada ECD terukur di jendela kalibrasi: tanpa koreksi bias (pakai ECD ⓥ apa adanya)")
        if predict is not None:
            X = win[FEATURES].fillna(pd.Series(x))
            ref.apl = _med(pd.Series(predict(X), index=win.index) - win["mw"])
    if np.isnan(ref.apl):
        raise ValueError("tidak ada ECD terukur maupun model ECD ⓥ untuk menentukan rugi gesek acuan")
    if ref.rop <= 0:
        notes.append("tidak ada data pengeboran di jendela acuan: ROP acuan 0 (segmen bor wajib isi ROP atau target + jam)")
    return ref


def connection_stats(frame: pd.DataFrame, min_n: int = 5) -> dict | None:
    """Jarak antar sambungan (ft) dan lama pompa mati (menit) dari data sumur. None bila kurang dari `min_n`."""
    if frame.empty or "hole_depth" not in frame:
        return None
    step = frame.index.to_series().diff().dt.total_seconds().median() or 30
    step = 30.0 if not np.isfinite(step) or step <= 0 else float(step)
    off = ((frame["flow_in"] < get_settings().flow_min_gpm) & ((frame["hole_depth"] - frame["bit_depth"]) < 60)).fillna(False)
    grp = (off != off.shift()).cumsum()
    seg = frame[off].groupby(grp[off])
    d = pd.DataFrame({"dur": seg.size() * step / 60, "hd": seg["hole_depth"].first()})
    d = d[(d["dur"] >= 1) & (d["dur"] <= 30)].sort_values("hd")
    gap = d["hd"].diff()
    gap = gap[(gap > 10) & (gap < 200)]
    if len(d) < min_n or len(gap) < min_n:
        return None
    return {"every_ft": round(float(gap.median()), 1), "off_min": round(float(d["dur"].median()), 1), "n": int(len(d))}


# ------------------------------------------------------------------ rencana → garis waktu

def _cuttings_ppg(rop: np.ndarray, flow: np.ndarray, hole_in: float, mw: np.ndarray, transport: float) -> np.ndarray:
    """Tambahan densitas annulus dari cutting (tanpa slip, dibagi rasio transport)."""
    area_ft2 = np.pi / 4 * (hole_in / 12) ** 2
    qc = np.asarray(rop, float) / 60 * area_ft2 * 7.48            # gpm volume cutting
    q = np.asarray(flow, float)
    ca = np.where(q > 0, qc / np.maximum(qc + q, 1e-9), 0.0) / transport
    return np.clip(ca, 0, 0.2) * (CUTTINGS_PPG - np.asarray(mw, float))


def _segment_rop(seg: dict, ref: Reference, start_md: float, cfg: dict, conn: bool, since_conn: float = 0.0) -> float:
    if seg.get("rop") is not None:
        return float(seg["rop"])
    to_md, hours = seg.get("to_md"), seg.get("hours")
    if to_md is not None and hours:
        dist = float(to_md) - start_md
        # sambungan yang jatuh sebelum target (terhitung dari sambungan terakhir; tidak ada sambungan di target)
        n_conn = max(int(np.ceil((since_conn + dist) / cfg["every_ft"] - 1e-9)) - 1, 0) if conn else 0
        on_bottom = hours * 60 - n_conn * cfg["off_min"]
        if on_bottom <= 0:
            raise ValueError(f"target {to_md} ft dalam {hours} jam tidak mungkin: waktu habis untuk sambung pipa")
        return dist / on_bottom * 60
    if seg.get("wob") is not None and ref.wob > 0 and ref.rop > 0:
        return ref.rop * (float(seg["wob"]) / ref.wob) ** cfg["wob_rop_exp"]
    if ref.rop > 0:
        return ref.rop
    raise ValueError("segmen bor butuh ROP, atau target kedalaman + jam (tidak ada ROP acuan)")


def build_timeline(ref: Reference, plan: list[dict], cfg: dict, connections: bool) -> tuple[pd.DataFrame, list]:
    """Segmen: {op: drill|circ|static, hours?, to_md?, flow?, rpm?, wob?, rop?, mw?}. Nilai kosong = nilai sebelumnya
    (awal: acuan). drill tanpa `hours` berhenti saat `to_md` tercapai."""
    step = cfg["step_s"]
    warns: list = []
    rows = []
    t = ref.t0
    hole = ref.hole_md if not np.isnan(ref.hole_md) else ref.bit_md
    bit = min(ref.bit_md, hole) if not np.isnan(ref.bit_md) else hole     # bit tak mungkin di bawah dasar lubang
    cur = {"flow": ref.flow, "rpm": ref.rpm, "wob": ref.wob, "rop": ref.rop, "mw": ref.mw}
    t_on = ref.x.get("t_pumps_on")
    t_on = 0.0 if t_on is None or np.isnan(t_on) else float(t_on)
    since_conn = 0.0
    off_left = 0.0
    for i, seg in enumerate(plan):
        op = seg.get("op", "drill")
        if op not in ("drill", "circ", "static"):
            raise ValueError(f"segmen {i + 1}: op harus drill / circ / static")
        for k in ("flow", "rpm", "wob", "mw"):
            if seg.get(k) is not None:
                cur[k] = float(seg[k])
        hours, to_md = seg.get("hours"), seg.get("to_md")
        seg_start = hole
        if op == "drill":
            if to_md is None and not hours:
                raise ValueError(f"segmen {i + 1}: bor butuh to_md dan/atau hours")
            if to_md is not None and float(to_md) <= hole:
                raise ValueError(f"segmen {i + 1}: to_md {to_md} ≤ kedalaman lubang {hole:.0f} ft")
            if bit < hole - 1:
                warns.append(f"segmen {i + 1}: bit {bit:.0f} ft di atas dasar {hole:.0f} ft; dianggap langsung ke dasar")
                bit = hole
            rop = _segment_rop(seg, ref, hole, cfg, connections, since_conn)
        elif not hours:
            raise ValueError(f"segmen {i + 1}: {op} butuh hours")
        else:
            rop = 0.0
        end_t = t + pd.Timedelta(hours=float(hours)) if hours else None
        guard = 0
        while True:
            if end_t is not None and t >= end_t:
                break
            if end_t is None and hole >= float(to_md) and off_left <= 0:
                break
            guard += 1
            if guard > 200_000:
                raise ValueError("rencana terlalu panjang")
            t = t + pd.Timedelta(seconds=step)
            pumps = op != "static" and off_left <= 0
            r_now = 0.0
            if off_left > 0:
                off_left -= step / 60
            elif op == "drill" and (to_md is None or hole < float(to_md)):
                r_now = rop
                adv = rop * step / 3600
                if to_md is not None:
                    adv = min(adv, float(to_md) - hole)
                hole += adv
                bit = hole
                since_conn += adv
                if connections and since_conn >= cfg["every_ft"] and (to_md is None or hole < float(to_md)):
                    since_conn = 0.0
                    off_left = cfg["off_min"]
            t_on = t_on + step / 60 if pumps else 0.0
            rows.append({"time": t, "seg": i + 1, "op": op if pumps or op == "static" else "sambung",
                         "pumps": pumps, "bit_depth": bit, "hole_depth": hole,
                         "flow": cur["flow"] if pumps else 0.0, "rpm": cur["rpm"] if pumps else 0.0,
                         "wob": cur["wob"] if r_now > 0 else 0.0, "rop": r_now, "mw": cur["mw"], "t_on": t_on})
        if op == "drill" and to_md is not None and hole < float(to_md) - max(5.0, 0.02 * (float(to_md) - seg_start)):
            warns.append(f"segmen {i + 1}: target {to_md} ft tidak tercapai dalam {hours} jam (berhenti di {hole:.0f} ft)")
    if not rows:
        raise ValueError("rencana kosong")
    return pd.DataFrame(rows).set_index("time"), warns


def _tvd_inc(md: np.ndarray, survey: pd.DataFrame | None, ref: Reference) -> tuple[np.ndarray, np.ndarray]:
    if survey is None or survey.empty or survey["tvd"].notna().sum() < 2:
        tvd0, inc0 = ref.x.get("tvd_bit"), ref.x.get("inc_bit")
        tvd0 = ref.bit_md if tvd0 is None or np.isnan(tvd0) else tvd0
        inc0 = 0.0 if inc0 is None or np.isnan(inc0) else inc0
        return tvd0 + (md - ref.bit_md) * np.cos(np.radians(inc0)), np.full(len(md), inc0)
    sv = survey.dropna(subset=["md", "tvd"]).sort_values("md")
    tvd = np.interp(md, sv["md"], sv["tvd"])
    inc_s = sv["inc"].ffill().fillna(0)
    inc = np.interp(md, sv["md"], inc_s)
    beyond = md > sv["md"].iloc[-1]
    tvd[beyond] = sv["tvd"].iloc[-1] + (md[beyond] - sv["md"].iloc[-1]) * np.cos(np.radians(inc_s.iloc[-1]))
    return tvd, inc


def evaluate(tl: pd.DataFrame, ref: Reference, predict: Predictor | None, survey: pd.DataFrame | None, cfg: dict) -> pd.DataFrame:
    out = tl.copy()
    md = out["bit_depth"].to_numpy(float)
    tvd, inc = _tvd_inc(md, survey, ref)
    if predict is not None:
        X = pd.DataFrame({f: ref.x.get(f, np.nan) for f in FEATURES}, index=out.index)
        X["bit_depth"], X["tvd_bit"], X["inc_bit"] = md, tvd, inc
        X["off_bottom"] = (out["hole_depth"] - out["bit_depth"]).clip(lower=0)
        X["mw"] = out["mw"]
        X["block_vel"] = out["rop"] / 60
        X["t_pumps_on"] = np.where(out["pumps"], out["t_on"].clip(upper=120), X["t_pumps_on"])
        X["flow_in"], X["rpm"] = ref.flow, ref.rpm
        X["wob"], X["rop"] = ref.wob, ref.rop
        X = X.fillna(pd.Series({f: v for f, v in ref.x.items() if v is not None and not np.isnan(v)}))
        ecd_ref = predict(X) + ref.bias
        apl_ref = np.clip(ecd_ref - out["mw"].to_numpy(), 0, None)
    else:
        apl_ref = np.full(len(out), ref.apl)
    out["tvd_bit"], out["inc_bit"] = tvd, inc
    q = out["flow"].where(out["pumps"], ref.flow).to_numpy(float)
    r = out["rpm"].where(out["pumps"], ref.rpm).to_numpy(float)
    f_flow = (np.maximum(q, 0) / max(ref.flow, 1.0)) ** cfg["flow_exp"]
    h = cfg.get("_hyd")
    if h:
        args = (h["rheo"], h["hole_size"], h["casing_id"], h["shoe_md"], h["string"])
        mwv = out["mw"].to_numpy(float)
        p = hy.ecd_add(q, md, tvd, mwv, *args)
        p0 = hy.ecd_add(ref.flow, md, tvd, mwv, *args)
        f_flow = np.where(p0 > 1e-6, p / np.where(p0 > 1e-6, p0, 1.0), f_flow)
        out["apl_hyd"] = p
        if h["base"] == "hyd":
            apl_ref = h["c"] * p0
    f_rpm = np.clip(1 + cfg["rpm_k"] * (r - ref.rpm) / 100, 0.8, None)
    # respons cutting memakai lubang kalibrasi (cut_hole_size), bukan lubang asli: uji mundur 5 sumur (24 Nov) — dengan
    # lubang 12-1/4" asli lonjakan ECD dari perubahan ROP 2× terlalu besar (MAE 0,167 → 0,253 ppg)
    ch = cfg.get("cut_hole_size") or cfg["hole_size"]
    cut = _cuttings_ppg(out["rop"], q, ch, out["mw"], cfg["transport"]) \
        - _cuttings_ppg(np.full(len(out), ref.rop), np.full(len(out), ref.flow), ch, out["mw"], cfg["transport"])
    a = min(1.0, cfg["step_s"] / 60 / cfg["cut_tau_min"])
    lag = np.zeros(len(cut))
    for i in range(len(cut)):                 # cutting menumpuk / terangkat bertahap (≈ waktu bottoms-up)
        prev = lag[i - 1] if i else 0.0
        lag[i] = prev + (cut[i] - prev) * a if out["pumps"].iat[i] else prev
    out["apl_ref"] = apl_ref
    out["d_flow"] = apl_ref * (f_flow - 1)
    out["d_rpm"] = apl_ref * f_flow * (f_rpm - 1)
    out["d_cut"] = lag
    out["ecd_circ_all"] = out["mw"] + apl_ref * f_flow * f_rpm + lag        # seandainya sirkulasi
    out["ecd_circ"] = out["ecd_circ_all"].where(out["pumps"])
    out["esd"] = out["mw"]
    out["ecd"] = np.where(out["pumps"], out["ecd_circ"], out["esd"])
    return out


def _margins(tl: pd.DataFrame, ppfg: pd.DataFrame | None, shoe_md: float | None, th: dict) -> pd.DataFrame:
    out = tl
    if ppfg is None or ppfg.empty:
        out["margin"] = np.nan
        out["margin_kind"] = None
        out["level"] = "TANPA PPFG"
        return out
    m = add_margins(out, ppfg, shoe_md, ecd_col="ecd")
    up = m[["margin_up_bit", "margin_up_oh"]].min(axis=1, skipna=True)
    low = m["margin_low"]
    static = out["esd"] - m["lower_oh"].fillna(m["lower_bit"])
    circ = pd.concat([up, low], axis=1).min(axis=1, skipna=True)
    out = m
    out["margin"] = np.where(out["pumps"], circ, static)
    out["margin_kind"] = np.where(out["pumps"], np.where(up <= low, "FG (loss)", "PP (kick)"), "statis vs PP")
    lvl = pd.Series("NORMAL", index=out.index, dtype=object)
    lvl[out["margin"] <= th["advisory_margin"]] = "ADVISORY"
    lvl[out["margin"] <= th["warning_margin"]] = "WARNING"
    lvl[out["margin"] <= th["critical_margin"]] = "CRITICAL"
    lvl[out["margin"].isna()] = "TANPA PPFG"
    out["level"] = lvl
    return out


def _summary(tl: pd.DataFrame, ref: Reference) -> dict:
    def at(i):
        return {"time": i.isoformat(), "md": round(float(tl.at[i, "bit_depth"]), 0)}
    circ = tl["ecd_circ"].dropna()
    s = {"start": ref.t0.isoformat(), "end": tl.index[-1].isoformat(), "hours": round((tl.index[-1] - ref.t0).total_seconds() / 3600, 2),
         "md_start": round(ref.hole_md, 0), "md_end": round(float(tl["hole_depth"].iloc[-1]), 0),
         "connections": int(((tl["op"] == "sambung") & (tl["op"].shift() != "sambung")).sum()),
         "ecd_circ_max": None, "esd_min": round(float(tl["esd"].min()), 2), "margin_min": None, "first": {}}
    if len(circ):
        i = circ.idxmax()
        s["ecd_circ_max"] = {"ecd": round(float(circ.max()), 2), **at(i)}
    if tl["margin"].notna().any():
        i = tl["margin"].idxmin()
        s["margin_min"] = {"margin": round(float(tl.at[i, "margin"]), 2), "kind": tl.at[i, "margin_kind"], **at(i)}
        for lv in ("ADVISORY", "WARNING", "CRITICAL"):
            hit = tl.index[tl["level"].isin({"ADVISORY": ["ADVISORY", "WARNING", "CRITICAL"], "WARNING": ["WARNING", "CRITICAL"],
                                              "CRITICAL": ["CRITICAL"]}[lv])]
            if len(hit):
                s["first"][lv] = {**at(hit[0]), "kind": tl.at[hit[0], "margin_kind"], "margin": round(float(tl.at[hit[0], "margin"]), 2)}
    return s


def _hyd_setup(cfg: dict, ref: Reference, survey: pd.DataFrame | None, shoe_md: float | None, predict) -> dict:
    """Siapkan reologi, geometri, dan faktor kalibrasi c = APL terukur / APL hidraulika (di kondisi acuan)."""
    pv, yp = cfg.get("pv"), cfg.get("yp")
    rheo = hy.Rheo(float(pv or hy.DEFAULT_PV), float(yp or hy.DEFAULT_YP))
    hole = float(cfg["hole_size"])
    cid = float(cfg.get("casing_id") or hy.casing_id_for(hole))
    name, string = hy.string_for_hole(hole, cfg.get("preset") or None)
    tvd0 = _tvd_inc(np.array([ref.bit_md]), survey, ref)[0][0]
    loss0, turb = hy.annular_loss(ref.flow, ref.bit_md, ref.mw, rheo, hole, cid, shoe_md, string)
    p_ref = loss0 / (0.052 * tvd0) if tvd0 > 0 else 0.0
    base = cfg.get("base", "ml") if predict is not None else "hyd"
    c = max(ref.apl, 0.05) / p_ref if p_ref > 1e-6 else 1.0     # ECD−MW ≤ 0 terukur (mis. dangkal) tak bisa dikalibrasi
    return {"rheo": rheo, "string": string, "hole_size": hole, "casing_id": cid, "shoe_md": shoe_md, "base": base,
            "pv": rheo.pv, "yp": rheo.yp, "n": round(rheo.n, 3), "K": round(rheo.K, 1), "default_rheo": not (pv and yp),
            "preset": name, "apl_psi_ref": round(loss0, 1), "apl_ppg_ref": round(p_ref, 3), "turbulent_ref": turb,
            "c": round(float(c), 3), "apl_meas_ref": round(ref.apl, 3)}


def forecast(hist: pd.DataFrame, plan: list[dict], predict: Predictor | None = None, survey: pd.DataFrame | None = None,
             ppfg: pd.DataFrame | None = None, shoe_md: float | None = None, th: dict | None = None,
             cfg: dict | None = None, connections: bool = True, both: bool = True, ref: Reference | None = None) -> dict:
    """Ramalan dari data sampai jam T (= akhir `hist`) sepanjang `plan`.
    Hasil: timeline (dengan sambung pipa bila `connections`), continuous (tanpa sambung pipa, bila `both`), ringkasan."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    th = {**DEFAULT_TH, **(th or {})}
    ref = ref or reference(hist, predict, cfg)
    res = {"reference": ref.public(), "cfg": cfg, "warnings": list(ref.notes)}
    cfg.pop("_hyd", None)
    use_hyd = cfg.get("hydraulics", "auto")
    use_hyd = bool(cfg.get("pv") and cfg.get("yp")) if use_hyd == "auto" else bool(use_hyd)
    if not use_hyd:
        res["warnings"].append("Hidraulika tidak aktif (PV/YP belum diisi): respons flow memakai pendekatan sementara "
                               f"APL × (Q/Q acuan)^{cfg['flow_exp']}")
    if use_hyd:
        cfg["_hyd"] = _hyd_setup(cfg, ref, survey, shoe_md, predict)
        res["hydraulics"] = {k: v for k, v in cfg["_hyd"].items() if k not in ("rheo", "string")}
        res["hydraulics"]["string"] = [{"name": nm, "od": od, "length": ln, "tj_od": tj} for nm, od, ln, tj, _j in cfg["_hyd"]["string"]]
        if cfg["_hyd"]["default_rheo"]:
            res["warnings"].append(f"PV/YP belum diisi: dipakai contoh PV {hy.DEFAULT_PV:g} cP / YP {hy.DEFAULT_YP:g} lbf/100ft² (respons flow kasar)")
    variants = [("timeline", connections)] + ([("continuous", False)] if both and connections else [])
    for key, conn in variants:
        tl, w = build_timeline(ref, plan, cfg, conn)
        tl = _margins(evaluate(tl, ref, predict, survey, cfg), ppfg, shoe_md, th)
        res[key] = tl
        res[f"summary_{key}"] = _summary(tl, ref)
        if key == "timeline":
            res["warnings"] += w
    res["summary"] = res["summary_timeline"]
    return res


# ------------------------------------------------------------------ uji mundur

def plan_from_actual(actual: pd.DataFrame, chunk_h: float = 1.0) -> list[dict]:
    """Rencana kasar dari data yang sebenarnya terjadi (per `chunk_h` jam): untuk uji mundur & isian awal form."""
    fmin = get_settings().flow_min_gpm
    plan = []
    t0 = actual.index[0]
    n = max(1, int(np.ceil((actual.index[-1] - t0).total_seconds() / 3600 / chunk_h)))
    hole_prev = None
    for k in range(n):
        a, b = t0 + pd.Timedelta(hours=k * chunk_h), t0 + pd.Timedelta(hours=(k + 1) * chunk_h)
        c = actual[(actual.index >= a) & (actual.index < b)]
        if c.empty:
            plan.append({"op": "static", "hours": chunk_h})
            continue
        pw = c[c["flow_in"] > fmin]
        hc = c["hole_reached"] if "hole_reached" in c else c["hole_depth"]
        hole_end = float(hc.max())
        hole_prev = hole_prev if hole_prev is not None else float(hc.dropna().iloc[0])
        seg = {"hours": chunk_h, "mw": _med(c["mw"])}
        if len(pw) / len(c) >= 0.3:
            seg.update(flow=_med(pw["flow_in"]), rpm=_med(pw.get("rpm", pd.Series(dtype=float)), 0.0))
            dr = pw[pw.get("rop", 0) > 0]
            if len(dr):
                seg["wob"] = _med(dr.get("wob", pd.Series(dtype=float)))
            if hole_end - hole_prev > 5:
                seg.update(op="drill", to_md=round(hole_end, 1))
            else:
                seg["op"] = "circ"
        else:
            seg["op"] = "static"
        nd = {"flow": 0, "rpm": 0, "wob": 1, "mw": 2, "to_md": 0}
        seg = {k: (round(v, nd[k]) if k in nd else v) for k, v in seg.items() if not (isinstance(v, float) and np.isnan(v))}
        plan.append(seg)
        hole_prev = max(hole_prev, hole_end)
    return plan


def backtest(frame: pd.DataFrame, t_cut: pd.Timestamp, hours: float, predict: Predictor | None,
             survey: pd.DataFrame | None = None, ppfg: pd.DataFrame | None = None, shoe_md: float | None = None,
             plan: list[dict] | None = None, cfg: dict | None = None, th: dict | None = None) -> dict:
    """Pura-pura di jam `t_cut`: data sesudahnya disembunyikan, diramal sepanjang `plan` (default: rencana kasar dari
    data aktual), lalu dibandingkan dengan ECD terukur. Pembanding: 'ECD tetap' (nilai terukur terakhir)."""
    cfg = {**DEFAULT_CFG, **(cfg or {})}
    hist = frame[frame.index <= t_cut]
    actual = frame[(frame.index > t_cut) & (frame.index <= t_cut + pd.Timedelta(hours=hours))]
    if actual.empty:
        raise ValueError("tidak ada data aktual sesudah jam potong")
    cs = connection_stats(hist)
    if cs:
        cfg.update(every_ft=cs["every_ft"], off_min=cs["off_min"])
    plan = plan or plan_from_actual(actual)
    fc = forecast(hist, plan, predict, survey, ppfg, shoe_md, th, cfg, connections=True, both=False)
    tl = fc["timeline"]
    stale = actual["ecd_stale"] if "ecd_stale" in actual else stale_ecd_mask(frame).reindex(actual.index)
    y = actual["ecd"].where(actual["ecd"].between(7, 20) & ~stale.fillna(False).astype(bool)
                           & (actual["flow_in"] > get_settings().flow_min_gpm))
    y = y.dropna()
    hv = hist["ecd"].where(hist["ecd"].between(7, 20) & ~hist.get("ecd_stale", pd.Series(False, index=hist.index)).fillna(False).astype(bool)).dropna()
    met = {"n": int(len(y)), "plan": plan, "cfg_conn": {k: cfg[k] for k in ("every_ft", "off_min")}}
    if len(y) and len(hv):
        p = tl["ecd_circ_all"].reindex(y.index, method="nearest", tolerance=pd.Timedelta(seconds=cfg["step_s"]))
        ok = p.notna()
        last = float(hv.iloc[-1])
        met.update(mae=float((p[ok] - y[ok]).abs().mean()), mae_persist=float((y - last).abs().mean()),
                   ecd_max_actual=float(y.max()), ecd_max_fc=float(p[ok].max()) if ok.any() else None,
                   ecd_last=last)
        met["max_err"] = abs(met["ecd_max_fc"] - met["ecd_max_actual"]) if met["ecd_max_fc"] is not None else None
        met["max_err_persist"] = abs(last - met["ecd_max_actual"])
    return {"forecast": fc, "actual": actual, "metrics": met}
