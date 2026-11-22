"""Estimasi bending moment, bending stress, side force, dan hookload model (soft-string) dari survey + data rig.

SEMUA ESTIMASI, BUKAN PENGUKURAN. Sensor downhole (mis. BND_MAX_DMM SLB) mengukur lengkungan aktual termasuk getaran,
whirl, buckling, dan efek lubang membesar/ledge. Modul ini hanya menghitung lengkungan yang DIPAKSAKAN oleh bentuk
lubang (survey), dengan anggapan pipa mengikuti sumbu lubang (lubang dianggap slick):

    Bending moment   M  = E · I · κ           κ = kelengkungan lubang (min. curvature antar stasiun survey)
    Bending stress   σb = E · κ · OD / 2      dibandingkan dengan batas bending sambungan (datasheet connection)
    Side force       soft-string Johancsik (1984), elemen 30 ft (≈ 1 joint)
    Hookload model   tension di permukaan, mode pick-up / slack-off / rotate (bit off-bottom) → broomstick

Konfigurasi string berasal dari KATALOG komponen + PRESET per section (bending_catalog.json), dipilih per run
"berlaku mulai hole depth X" — sama seperti MW Rec 04 (effective-from depth). Dipakai oleh script tools/bending dan
(nanti) API aplikasi; lihat docs/BENDING_INTEGRATION.md.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

STEEL_PPG = 65.5           # densitas baja untuk faktor apung
E_STEEL = 30.0e6           # psi
ELEM_FT = 30.0             # panjang elemen (≈ 1 joint) untuk side force
JOINT_FT = 31.0            # panjang joint default (range 2) bila katalog tidak mengisi joint_ft
DEFAULT_FRICTION = {"cased": 0.20, "open": 0.30}
CATALOG_PATH = Path(__file__).resolve().parent.parent / "bending_catalog.json"
ITEM_FIELDS = ("od", "id", "weight_ppf", "tj_od", "grade", "connection", "bend_limit_dls", "bend_limit_ksi")


# ------------------------------------------------------------------ komponen & run

@dataclass
class Comp:
    name: str
    od: float
    id: float
    length: float | None
    ppf: float
    bha: bool
    lim_dls: float | None = None      # batas bending sambungan, °/100 ft
    lim_ksi: float | None = None      # batas bending sambungan, ksi
    item: str | None = None           # id katalog (bila dari katalog)

    @property
    def inertia(self) -> float:       # in^4
        return math.pi / 64 * (self.od ** 4 - self.id ** 4)

    @property
    def has_limit(self) -> bool:
        return bool(self.lim_dls) or bool(self.lim_ksi)

    def util(self, dls: np.ndarray, sig_ksi: np.ndarray) -> np.ndarray:
        """Rasio terhadap batas sambungan (1,0 = tepat di batas). Diambil yang paling kritis dari DLS / stress."""
        if not self.has_limit:
            return np.full(np.shape(dls), np.nan)
        u = np.zeros(np.shape(dls))
        if self.lim_dls:
            u = np.maximum(u, np.asarray(dls) / self.lim_dls)
        if self.lim_ksi:
            u = np.maximum(u, np.asarray(sig_ksi) / self.lim_ksi)
        return u


@dataclass
class Run:
    """Satu konfigurasi string yang berlaku mulai hole depth `from_md` (sampai run berikutnya)."""
    from_md: float
    name: str
    comps: list[Comp]
    cfg: dict = field(default_factory=dict)   # friction, block_weight_klb, mw_ppg, shoe_md_ft, setting_md_ft, hole_size, E_psi


def comps_from_list(items: list[dict]) -> list[Comp]:
    comps = []
    for i, c in enumerate(items):
        nm = c.get("name") or c.get("item") or f"komp{i + 1}"
        try:
            od, idd = float(c["od"]), float(c["id"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"komponen #{i + 1} '{nm}': od/id wajib diisi angka")
        if not 0 < idd < od:
            raise ValueError(f"komponen #{i + 1} '{nm}': ID harus > 0 dan < OD")
        ppf = c.get("weight_ppf") or 2.672 * (od ** 2 - idd ** 2)   # pipa polos (baja 490 lb/ft³)
        ln = c.get("length")
        if ln is None and i != len(items) - 1:
            raise ValueError(f"komponen #{i + 1} '{nm}': hanya komponen terakhir yang boleh tanpa panjang (mengisi sampai permukaan)")
        if ln is not None and float(ln) <= 0:
            raise ValueError(f"komponen #{i + 1} '{nm}': panjang harus > 0")
        lim = [c.get("bend_limit_dls"), c.get("bend_limit_ksi")]
        if any(v is not None and float(v) <= 0 for v in lim):
            raise ValueError(f"komponen #{i + 1} '{nm}': batas bending harus > 0 atau null")
        comps.append(Comp(nm, od, idd, None if ln is None else float(ln), float(ppf),
                          bool(c.get("bha", i < len(items) - 1)),
                          float(lim[0]) if lim[0] else None, float(lim[1]) if lim[1] else None, c.get("item")))
    return comps


# ------------------------------------------------------------------ katalog & preset

def load_catalog(path: str | Path | None = None) -> dict:
    cat = json.loads(Path(path or CATALOG_PATH).read_text())
    for k in ("items", "presets"):
        if k not in cat:
            raise ValueError(f"katalog tidak punya bagian '{k}'")
    for pid, p in cat["presets"].items():
        for e in p.get("components", []):
            if e.get("item") not in cat["items"]:
                raise ValueError(f"preset {pid}: item '{e.get('item')}' tidak ada di katalog")
    return cat


def _override(ov: dict | None, idx: int, item: str):
    """Override per komponen: kunci '#<urutan mulai 1>' atau id item katalog."""
    if not ov:
        return None
    return ov.get(f"#{idx + 1}", ov.get(item))


def resolve_preset(cat: dict, preset_id: str, counts: dict | None = None, lengths: dict | None = None) -> tuple[dict, list[dict]]:
    """Preset → (cfg, daftar komponen siap pakai). `counts`/`lengths` mengganti jumlah joint / panjang per komponen."""
    if preset_id not in cat["presets"]:
        raise ValueError(f"preset '{preset_id}' tidak ada di katalog (pilihan: {', '.join(cat['presets'])})")
    p = cat["presets"][preset_id]
    out = []
    for k, e in enumerate(p["components"]):
        it = cat["items"][e["item"]]
        c = {f: it.get(f) for f in ITEM_FIELDS}
        c.update({"item": e["item"], "name": e.get("name") or it.get("name") or e["item"],
                  "bha": e.get("bha", it.get("type") != "DP")})
        n = _override(counts, k, e["item"])
        ln = _override(lengths, k, e["item"])
        n = e.get("count") if n is None and ln is None else n
        ln = e.get("length") if ln is None and n is None else ln
        c["length"] = n * float(it.get("joint_ft") or JOINT_FT) if n is not None else ln
        c["count"] = n
        out.append(c)
    cfg = {"name": p.get("name", preset_id), "preset": preset_id, "kind": p.get("kind", "drill"),
           "hole_size": p.get("bit_size"), "friction": dict(p.get("friction") or DEFAULT_FRICTION)}
    return cfg, out


def runs_from_spec(spec: dict, cat: dict | None = None) -> list[Run]:
    """Spesifikasi per sumur → daftar Run terurut. Format:
    {"shoe_md_ft":…, "mw_ppg":…, "block_weight_klb":…, "friction":{…},
     "runs":[{"from_hole_md":0, "preset":"BHA_12.25_STD", "counts":{"DC_8.25":6}, "hole_size":12.25,
              "shoe_md_ft":…, "setting_md_ft":…, "friction":{…}},            ← dari katalog
             {"from_hole_md":1500, "name":"custom", "components":[{od,id,length,…}, …]}]}   ← tanpa katalog
    Format lama (satu string: {"components":[…]}) diterima sebagai satu run dari 0 ft."""
    if "runs" not in spec:
        spec = {**{k: v for k, v in spec.items() if k != "components"},
                "runs": [{"from_hole_md": 0, "components": spec["components"], "name": spec.get("name", "string")}]}
    glob = {k: spec.get(k) for k in ("shoe_md_ft", "mw_ppg", "block_weight_klb", "E_psi") if spec.get(k) is not None}
    gfric = spec.get("friction")
    runs = []
    for j, r in enumerate(spec["runs"]):
        if r.get("preset"):
            if cat is None:
                raise ValueError("run memakai preset, tetapi katalog tidak dimuat")
            cfg, items = resolve_preset(cat, r["preset"], r.get("counts"), r.get("lengths"))
        elif r.get("components"):
            cfg, items = {"name": r.get("name", f"run{j + 1}"), "friction": dict(DEFAULT_FRICTION)}, r["components"]
        else:
            raise ValueError(f"run #{j + 1}: isi 'preset' atau 'components'")
        cfg = {**cfg, **glob}
        if gfric:
            cfg["friction"] = dict(gfric)
        for k in ("shoe_md_ft", "mw_ppg", "block_weight_klb", "setting_md_ft", "hole_size", "E_psi", "friction"):
            if r.get(k) is not None:
                cfg[k] = r[k]
        cfg["name"] = r.get("name") or cfg["name"]
        runs.append(Run(float(r.get("from_hole_md") or 0.0), cfg["name"], comps_from_list(items), cfg))
    runs.sort(key=lambda x: x.from_md)
    if len({r.from_md for r in runs}) != len(runs):
        raise ValueError("dua run punya from_hole_md yang sama")
    return runs


# ------------------------------------------------------------------ geometri lubang

def prep_survey(sv: pd.DataFrame) -> pd.DataFrame:
    sv = sv.dropna(subset=["md", "inc", "azi"]).sort_values("md").drop_duplicates("md").reset_index(drop=True)
    if sv.empty:
        raise ValueError("survey kosong (butuh MD, inklinasi, azimuth — Rec 07)")
    if sv["md"].iloc[0] > 0:
        sv = pd.concat([pd.DataFrame({"md": [0.0], "inc": [0.0], "azi": [sv["azi"].iloc[0]]}), sv], ignore_index=True)
    i1, i2 = np.radians(sv["inc"].to_numpy()[:-1]), np.radians(sv["inc"].to_numpy()[1:])
    da = np.radians(np.diff(sv["azi"].to_numpy()))
    cosb = np.cos(i2 - i1) - np.sin(i1) * np.sin(i2) * (1 - np.cos(da))
    beta = np.arccos(np.clip(cosb, -1, 1))                    # dogleg (rad) antar stasiun
    dmd = np.diff(sv["md"].to_numpy())
    kappa = np.where(dmd > 0, beta / np.where(dmd > 0, dmd, 1), 0.0)   # rad/ft
    sv["kappa_next"] = np.append(kappa, 0.0)                  # κ interval [md_i, md_i+1)
    sv["dls_calc"] = np.degrees(sv["kappa_next"]) * 100
    sv["azi_unw"] = np.degrees(np.unwrap(np.radians(sv["azi"].to_numpy())))
    return sv


class Hole:
    """Kelengkungan, inklinasi, azimuth sebagai fungsi MD."""

    def __init__(self, sv: pd.DataFrame):
        self.md = sv["md"].to_numpy(dtype=float)
        self.kap = sv["kappa_next"].to_numpy(dtype=float)
        self.inc = np.radians(sv["inc"].to_numpy(dtype=float))
        self.azi = np.radians(sv["azi_unw"].to_numpy(dtype=float))
        self.td = float(self.md[-1])

    def kappa(self, m) -> np.ndarray:
        m = np.asarray(m, dtype=float)
        i = np.clip(np.searchsorted(self.md, m, side="right") - 1, 0, len(self.md) - 1)
        last = self.kap[-2] if len(self.kap) > 1 else 0.0          # di bawah survey terakhir: κ interval terakhir
        return np.where(m >= self.td, last, self.kap[i])

    def inc_at(self, m):
        return np.interp(m, self.md, self.inc)

    def azi_at(self, m):
        return np.interp(m, self.md, self.azi)


# ------------------------------------------------------------------ model per kedalaman bit

def depth_profile(hole: Hole, run: Run, bits: np.ndarray, mw_at) -> pd.DataFrame:
    comps, cfg = run.comps, run.cfg
    E = float(cfg.get("E_psi") or E_STEEL)
    fr = cfg.get("friction") or DEFAULT_FRICTION
    mu_c, mu_o = float(fr.get("cased", .2)), float(fr.get("open", .3))
    shoe = cfg.get("shoe_md_ft")
    blk = float(cfg.get("block_weight_klb") or 0.0)
    edges = np.cumsum([0.0, *[c.length for c in comps if c.length is not None]])   # jarak dari bit ke batas komponen
    inertia = np.array([c.inertia for c in comps])
    ods = np.array([c.od for c in comps])
    bhas = np.array([c.bha for c in comps])
    ppfs = np.array([c.ppf for c in comps])
    rows = []
    for B in bits:
        n = max(1, int(math.ceil(B / ELEM_FT)))
        bot = B - np.arange(n) * ELEM_FT                          # dari bit ke atas
        top = np.maximum(bot - ELEM_FT, 0.0)
        mid = (bot + top) / 2
        ci = np.minimum(np.searchsorted(edges, B - mid, side="right") - 1, len(comps) - 1)
        k_in = hole.kappa(mid) / 12.0                             # rad/in
        M = E * inertia[ci] * k_in / 12000.0                      # kft·lbf
        sig = E * k_in * ods[ci] / 2 / 1000.0                     # ksi
        dls_e = np.degrees(k_in * 12) * 100
        util = np.full(n, np.nan)
        for j in np.unique(ci):
            if comps[j].has_limit:
                msk = ci == j
                util[msk] = comps[j].util(dls_e[msk], sig[msk])
        # ---- soft-string torque & drag (Johancsik), dari bit ke permukaan, bit off-bottom
        mw = mw_at(B)
        bf = 1 - mw / STEEL_PPG if mw and not np.isnan(mw) else 1.0
        w = ppfs[ci] * bf * (bot - top)
        tb, tt = hole.inc_at(bot), hole.inc_at(top)
        th = (tb + tt) / 2
        dth = tt - tb                                             # build (inc naik ke bawah) → negatif
        dal = hole.azi_at(top) - hole.azi_at(bot)
        mu = np.where(mid < shoe, mu_c, mu_o) if shoe else np.full(n, mu_o)
        T = np.zeros(3)                                           # [pick-up, slack-off, rotate], lbf
        sgn = np.array([1.0, -1.0, 0.0])
        N_pu = np.empty(n)
        for e in range(n):
            s_th = math.sin(th[e])
            N = np.hypot(T * dal[e] * s_th, T * dth[e] + w[e] * s_th)
            N_pu[e] = N[0]
            T = T + w[e] * math.cos(th[e]) + sgn * mu[e] * N
        openh = mid >= shoe if shoe else np.ones(n, bool)
        bha = bhas[ci]
        fin = np.isfinite(util)
        rows.append({
            "bit_md": float(B), "dls_bit": float(np.degrees(hole.kappa(max(B - 1, 0))) * 100),
            "BND_BHA_EST": float(M[bha].max()) if bha.any() else np.nan,
            "BND_STR_EST": float(M.max()), "BND_STR_AT_MD": float(mid[M.argmax()]),
            "BSTR_MAX_EST": float(sig.max()),
            "SF_MAX_EST": float(N_pu.max() / 1000), "SF_MAX_AT_MD": float(mid[N_pu.argmax()]),
            "SF_OPEN_MAX_EST": float(N_pu[openh].max() / 1000) if openh.any() else np.nan,
            "BEND_UTIL_MAX": float(util[fin].max()) if fin.any() else np.nan,
            "BEND_UTIL_AT_MD": float(mid[fin][util[fin].argmax()]) if fin.any() else np.nan,
            "HKLD_PU": float(T[0] / 1000 + blk), "HKLD_SO": float(T[1] / 1000 + blk), "HKLD_ROT": float(T[2] / 1000 + blk),
            "mw_used": mw if mw else np.nan,
        })
    return pd.DataFrame(rows)


def limit_check(hole: Hole, run: Run, setting_md: float, warn: float = 0.8) -> pd.DataFrame:
    """Lintasan: tiap komponen melewati semua kedalaman di atas posisi akhirnya. Tandai interval survey yang DLS / stress-nya
    ≥ `warn` × batas sambungan. Tidak butuh data waktu (bisa dipakai untuk perencanaan sebelum run)."""
    cols = ["run", "komponen", "md_dari", "md_ke", "dls", "stress_ksi", "batas_dls", "batas_ksi", "utilisasi", "status"]
    E = float(run.cfg.get("E_psi") or E_STEEL)
    md0, md1, kap = hole.md[:-1], hole.md[1:], hole.kap[:-1]
    dls = np.degrees(kap) * 100
    rows, off = [], 0.0
    for c in run.comps:
        reach = setting_md - off                       # kedalaman terdalam yang dicapai ujung bawah komponen
        off += c.length or 0.0
        if not c.has_limit or reach <= 0:
            continue
        sig = E * (kap / 12.0) * c.od / 2 / 1000
        u = c.util(dls, sig)
        for a, b, d, s, uu in zip(md0, md1, dls, sig, u):
            if a < reach and uu >= warn:
                rows.append({"run": run.name, "komponen": c.name, "md_dari": round(float(a), 1),
                             "md_ke": round(float(min(b, reach)), 1), "dls": round(float(d), 2),
                             "stress_ksi": round(float(s), 2), "batas_dls": c.lim_dls, "batas_ksi": c.lim_ksi,
                             "utilisasi": round(float(uu), 3),
                             "status": "LEWAT BATAS" if uu > 1 else f"MENDEKATI (≥{int(warn * 100)}%)"})
    return pd.DataFrame(rows, columns=cols)


# ------------------------------------------------------------------ pemetaan ke data waktu

GEO_COLS = ["dls_bit", "BND_BHA_EST", "BND_STR_EST", "BSTR_MAX_EST", "SF_MAX_EST", "BEND_UTIL_MAX"]


def time_channels(rig: pd.DataFrame, prof: pd.DataFrame, block: float = 0.0) -> pd.DataFrame:
    out = rig.copy()
    b = out["bit_depth"].to_numpy(dtype=float)
    for c in (*GEO_COLS, "HKLD_PU", "HKLD_SO", "HKLD_ROT"):
        out[c] = np.interp(b, prof["bit_md"], prof[c], left=np.nan, right=np.nan)
    out.loc[~(out["bit_depth"] > 0), GEO_COLS] = np.nan
    dt = out.index.to_series().diff().dt.total_seconds()
    v = out["bit_depth"].diff() / dt                               # ft/s, + = turun
    off = (out["hole_depth"] - out["bit_depth"]) > 5 if "hole_depth" in out else pd.Series(True, index=out.index)
    rot = out["rpm"].fillna(0) > 5 if "rpm" in out else pd.Series(False, index=out.index)
    mode = pd.Series(None, index=out.index, dtype=object)
    mode[off & (v < -0.05) & ~rot] = "PU"                          # POOH / pick-up
    mode[off & (v > 0.05) & ~rot] = "SO"                           # RIH / slack-off
    mode[off & rot & (v.abs() <= 0.05)] = "ROT"
    if "hookload" in out:
        # string di slips (mis. top drive diputar saat connection): hookload ≈ berat block saja → bukan beban string
        mode[out["hookload"] < block + 0.5 * (out["HKLD_ROT"] - block)] = None
    out["mode"] = mode
    out["HKLD_EXP"] = np.select([mode == "PU", mode == "SO", mode == "ROT"],
                                [out["HKLD_PU"], out["HKLD_SO"], out["HKLD_ROT"]], np.nan)
    out["HKLD_RESID"] = out["hookload"] - out["HKLD_EXP"] if "hookload" in out else np.nan
    return out


def calibrate(hole: Hole, run: Run, bits, mw_at, rig: pd.DataFrame, min_points: int = 50) -> dict:
    """Friction factor open hole + berat block yang paling cocok dengan hookload pick-up/slack-off terukur.
    FF cased = FF open × rasio di konfigurasi. Hanya titik off-bottom tanpa rotasi yang dipakai."""
    fr = run.cfg.get("friction") or DEFAULT_FRICTION
    ratio = fr.get("cased", .2) / max(fr.get("open", .3), 1e-6)
    best = None
    for mu in np.round(np.arange(0.05, 0.551, 0.05), 2):
        r2 = Run(run.from_md, run.name, run.comps,
                 {**run.cfg, "friction": {"open": float(mu), "cased": round(float(mu) * ratio, 3)}, "block_weight_klb": 0.0})
        tc = time_channels(rig, depth_profile(hole, r2, bits, mw_at), block=0.0)
        r = tc.loc[tc["mode"].isin(["PU", "SO"]), "HKLD_RESID"].dropna()
        if len(r) < min_points:
            return {"ok": False, "reason": f"titik pick-up/slack-off terlalu sedikit ({len(r)})"}
        blk = float(r.median())
        score = float((r - blk).abs().mean())
        if best is None or score < best["mae_klb"]:
            best = {"ok": True, "friction_open": float(mu), "friction_cased": round(float(mu) * ratio, 3),
                    "block_weight_klb": round(blk, 1), "mae_klb": round(score, 2), "n": int(len(r))}
    return best


def assign_runs(rig: pd.DataFrame, runs: list[Run]) -> np.ndarray:
    """Indeks run per baris data waktu, dari hole depth tertinggi yang sudah dicapai (tahan glitch, sama dengan MW)."""
    if len(runs) == 1 or rig.empty:
        return np.zeros(len(rig), dtype=int)
    from .features import hole_reached_robust
    src = rig["hole_depth"] if "hole_depth" in rig and rig["hole_depth"].notna().any() else rig["bit_depth"]
    reached = hole_reached_robust(src).to_numpy()
    starts = np.array([r.from_md for r in runs])
    idx = np.searchsorted(starts, np.nan_to_num(reached, nan=0.0), side="right") - 1
    return np.clip(idx, 0, len(runs) - 1)


# ------------------------------------------------------------------ orkestrasi

def compute(sv: pd.DataFrame, rig: pd.DataFrame, mw: pd.DataFrame, runs: list[Run], step: float = 50.0,
            do_calibrate: bool = False, setting_depth: float | None = None) -> dict:
    """Hitung semua: profil per kedalaman bit per run, channel per waktu (run dipilih dari hole depth), cek batas sambungan.
    Kembalian: dict survey/profile/time/limits (DataFrame atau None), runs (ringkasan per run), warnings, summary."""
    sv = prep_survey(sv)
    hole = Hole(sv)
    mwd = mw.dropna(subset=["md", "mw"]).sort_values("md") if mw is not None and len(mw) else pd.DataFrame(columns=["md", "mw"])
    has_time = rig is not None and len(rig) > 0 and "bit_depth" in rig and rig["bit_depth"].notna().any()
    max_bit = max(hole.td, float(np.nanmax(rig["bit_depth"])) if has_time else 0.0)
    idx = assign_runs(rig, runs) if has_time else np.array([], dtype=int)
    warnings: list[str] = []
    profiles, times, limits, info = [], [], [], []
    for i, run in enumerate(runs):
        def mw_at(md, _cfg=run.cfg):
            if _cfg.get("mw_ppg"):
                return float(_cfg["mw_ppg"])
            if len(mwd) == 0:
                return np.nan
            j = np.searchsorted(mwd["md"].to_numpy(), md, side="right") - 1
            return float(mwd["mw"].iloc[max(j, 0)])

        nxt = runs[i + 1].from_md if i + 1 < len(runs) else None
        hi = min(max_bit, nxt) if nxt else max_bit
        bits = np.arange(step, hi + step, step)
        sub = rig[idx == i] if has_time else None
        calib = None
        if do_calibrate:
            if sub is not None and "hookload" in sub and len(sub):
                calib = calibrate(hole, run, bits, mw_at, sub)
                if calib.get("ok"):
                    run.cfg["friction"] = {"open": calib["friction_open"], "cased": calib["friction_cased"]}
                    run.cfg["block_weight_klb"] = calib["block_weight_klb"]
                else:
                    warnings.append(f"{run.name}: kalibrasi dilewati — {calib['reason']}")
            else:
                warnings.append(f"{run.name}: kalibrasi dilewati — tidak ada hookload basis waktu di run ini")
        prof = depth_profile(hole, run, bits, mw_at)
        prof.insert(0, "run", run.name)
        profiles.append(prof)
        setting = float(run.cfg.get("setting_md_ft") or (nxt if nxt else (setting_depth or max_bit)))
        shoe = run.cfg.get("shoe_md_ft")
        if shoe and shoe >= setting - ELEM_FT:
            warnings.append(f"{run.name}: shoe_md_ft {shoe:g} ft ≥ kedalaman akhir {setting:g} ft → seluruh string dianggap di "
                            "dalam casing. Untuk run casing/liner isi shoe_md_ft = shoe casing SEBELUMNYA.")
        lim = limit_check(hole, run, setting) if any(c.has_limit for c in run.comps) else None
        if lim is not None:
            limits.append(lim)
        ri = {"run": run.name, "preset": run.cfg.get("preset"), "from_hole_md": run.from_md, "setting_md_ft": setting,
              "hole_size": run.cfg.get("hole_size"), "shoe_md_ft": shoe, "friction": run.cfg.get("friction"),
              "block_weight_klb": run.cfg.get("block_weight_klb"), "calibration": calib,
              "components": [{"name": c.name, "item": c.item, "od": c.od, "id": c.id, "length": c.length, "ppf": c.ppf,
                              "bha": c.bha, "bend_limit_dls": c.lim_dls, "bend_limit_ksi": c.lim_ksi} for c in run.comps],
              "bnd_bha_max_kftlbf": _fmax(prof["BND_BHA_EST"]), "bnd_str_max_kftlbf": _fmax(prof["BND_STR_EST"]),
              "bstr_max_ksi": _fmax(prof["BSTR_MAX_EST"]), "sf_max_klbf_per_joint": _fmax(prof["SF_MAX_EST"]),
              "bend_util_max": _fmax(prof["BEND_UTIL_MAX"]),
              "limit_intervals_over": int((lim["status"] == "LEWAT BATAS").sum()) if lim is not None else None,
              "limit_intervals_warn": int(len(lim)) if lim is not None else None}
        if sub is not None and len(sub):
            tc = time_channels(sub, prof, block=float(run.cfg.get("block_weight_klb") or 0.0))
            tc["run"] = run.name
            tc["RUN_IDX"] = float(i + 1)
            times.append(tc)
            r = tc["HKLD_RESID"]
            ri.update({"time_rows": int(len(tc)), "time_start": str(tc.index.min()), "time_end": str(tc.index.max()),
                       "mode_counts": {k: int(v) for k, v in tc["mode"].value_counts().items()},
                       **{f"hkld_resid_med_{m}": _fmed(r[tc["mode"] == m]) for m in ("PU", "SO", "ROT")}})
        info.append(ri)
    summary = {"td_survey_ft": hole.td, "n_survey": int(len(sv)), "dls_max": float(sv["dls_calc"].max()),
               "dls_max_at_md": float(sv.loc[sv["dls_calc"].idxmax(), "md"]), "n_runs": len(runs)}
    if "dls" in sv and sv["dls"].notna().any():
        summary["dls_vs_file_mae"] = float((sv["dls_calc"].iloc[:-1] - sv["dls"].shift(-1).iloc[:-1]).abs().mean())
    return {"survey": sv, "profile": pd.concat(profiles, ignore_index=True),
            "time": pd.concat(times).sort_index() if times else None,
            "limits": pd.concat(limits, ignore_index=True) if limits else None,
            "runs": info, "warnings": warnings, "summary": summary}


def _fmax(s: pd.Series):
    return float(s.max()) if s.notna().any() else None


def _fmed(s: pd.Series):
    s = s.dropna()
    return float(s.median()) if len(s) else None
