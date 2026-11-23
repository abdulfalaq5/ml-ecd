"""Rugi gesek annulus (APL) model power-law, untuk respons flow di ramalan ECD.

Rumus (satuan lapangan; Bourgoyne dkk., Applied Drilling Engineering, §4.6–4.7):
  reologi dari PV/YP (Fann θ600 = 2·PV + YP, θ300 = PV + YP):
      n = 3,32·log10(θ600/θ300),   K = 510·θ300 / 511^n   (eq. cP)
  kecepatan annulus  v = q / (2,448·(d2² − d1²))                                   ft/s, q gpm, d in
  Reynolds           Re = 109000·ρ·v^(2−n)/K · (0,0208·(d2 − d1)/(2 + 1/n))^n
  laminar            dp/dL = K·v^n·((2 + 1/n)/0,0208)^n / (144000·(d2 − d1)^(1+n))    psi/ft
  turbulen (Re ≥ 4270 − 1370·n): f = 0,0791/Re^0,25, dp/dL = f·ρ·v² / (21,1·(d2 − d1))
  transisi (3470 − 1370·n … 4270 − 1370·n, API RP 13D): interpolasi linear laminar → turbulen, supaya respons flow
  tidak melompat (uji 5 sumur: tanpa transisi, flow +30% bisa menaikkan ECD ±1 ppg)
  ECD tambahan (ppg) = APL (psi) / (0,052·TVD)

Geometri: string dari preset katalog bending (dipilih dari data section sumur, atau otomatis per ukuran lubang):
BHA + DC + HWDP + DP. Tool joint (OD `tj_od`) dihitung sebagai ±1,5 ft per joint 31 ft; sisanya OD body.
Lubang terbuka = hole size di bawah shoe, ID casing di atas shoe. Tanpa PV/YP klien dipakai contoh
(PV 15 cP, YP 15 lbf/100 ft²) dan diberi label. Besaran mutlak dikalibrasi ke ECD terukur di ramalan.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from . import bending as bd

DEFAULT_PV, DEFAULT_YP = 15.0, 15.0
CASING_ID_FOR_HOLE = {26.0: 19.124, 17.5: 19.124, 16.0: 15.124, 12.25: 12.415, 8.5: 8.681, 6.125: 6.276, 6.0: 6.276}
PRESET_FOR_HOLE = {12.25: "BHA_12.25_STD", 8.5: "BHA_8.5_STD", 6.125: "BHA_6.125_STD"}
TJ_LEN_FT = 1.5                # panjang tool joint (box + pin) per joint


@dataclass(frozen=True)
class Rheo:
    pv: float
    yp: float

    @property
    def n(self) -> float:
        t600, t300 = 2 * self.pv + self.yp, self.pv + self.yp
        return float(np.clip(3.32 * np.log10(t600 / t300), 0.1, 1.0))

    @property
    def K(self) -> float:
        return 510 * (self.pv + self.yp) / 511 ** self.n


def grad(q: float, d2: float, d1: float, mw: float, r: Rheo) -> tuple[float, bool]:
    """(psi/ft, turbulen?) untuk satu ruas annulus."""
    gap = d2 - d1
    if q <= 0 or gap <= 0.05:
        return 0.0, False
    n, K = r.n, r.K
    v = q / (2.448 * (d2 ** 2 - d1 ** 2))
    lam = K * v ** n * ((2 + 1 / n) / 0.0208) ** n / (144000 * gap ** (1 + n))
    re = 109000 * mw * v ** (2 - n) / K * (0.0208 * gap / (2 + 1 / n)) ** n
    re_lam, re_turb = 3470 - 1370 * n, 4270 - 1370 * n
    if re <= re_lam:
        return lam, False
    turb = max(0.0791 / re ** 0.25 * mw * v ** 2 / (21.1 * gap), lam)
    if re >= re_turb:
        return turb, True
    w = (re - re_lam) / (re_turb - re_lam)
    return lam + w * (turb - lam), True


@lru_cache(maxsize=32)
def string_for_hole(hole_size: float, preset: str | None = None) -> tuple[str, tuple]:
    """(nama preset, ((nama, OD, panjang ft | None = sisa ke permukaan, OD tool joint | None, panjang joint), ...))
    dari bawah (bit) ke atas. `preset` dari data section; kosong = otomatis per ukuran lubang."""
    cat = bd.load_catalog()
    if preset:
        pid = preset
        name = cat["presets"][pid]["name"]
    else:
        key = min(PRESET_FOR_HOLE, key=lambda h: abs(h - hole_size))
        pid = PRESET_FOR_HOLE[key]
        name = cat["presets"][pid]["name"]
        if abs(key - hole_size) > 0.5:
            name += f" (pendekatan untuk lubang {hole_size}\")"
    _, items = bd.resolve_preset(cat, pid)
    return name, tuple((it.get("name", it.get("item", "")), float(it["od"]), it.get("length"),
                        float(it["tj_od"]) if it.get("tj_od") else None, float(it.get("joint_ft") or bd.JOINT_FT))
                       for it in items)


def casing_id_for(hole_size: float) -> float:
    key = min(CASING_ID_FOR_HOLE, key=lambda h: abs(h - hole_size))
    return CASING_ID_FOR_HOLE[key] if abs(key - hole_size) <= 0.5 else hole_size + 0.3


def annular_loss(q: float, bit_md: float, mw: float, r: Rheo, hole_size: float, casing_id: float,
                 shoe_md: float | None, string: tuple) -> tuple[float, bool]:
    """APL (psi) dari bit ke permukaan, dan apakah ada ruas turbulen."""
    if q <= 0 or not np.isfinite(bit_md) or bit_md <= 0:
        return 0.0, False
    total, turb_any = 0.0, False
    bot = bit_md
    shoe = shoe_md if shoe_md is not None and np.isfinite(shoe_md) else 0.0
    for _name, od, length, tj_od, joint in string:
        top = 0.0 if length is None else max(bot - float(length), 0.0)
        f_tj = min(TJ_LEN_FT / joint, 1.0) if tj_od and tj_od > od else 0.0
        for a, b, d2 in ((max(top, shoe), bot, hole_size), (top, min(bot, shoe), casing_id)):
            if b > a:
                g, t = grad(q, d2, od, mw, r)
                total += g * (b - a) * (1 - f_tj)
                turb_any |= t
                if f_tj:
                    g2, t2 = grad(q, d2, tj_od, mw, r)
                    total += g2 * (b - a) * f_tj
                    turb_any |= t2
        bot = top
        if bot <= 0:
            break
    return total, turb_any


def ecd_add(q, bit_md, tvd, mw, r: Rheo, hole_size: float, casing_id: float, shoe_md: float | None, string: tuple) -> np.ndarray:
    """Tambahan ECD (ppg) per baris; dihitung sekali per kombinasi unik (kedalaman 1 ft, flow 1 gpm, MW 0,01)."""
    q, bit_md, tvd, mw = (np.broadcast_to(np.asarray(x, float), np.shape(bit_md)) for x in (q, bit_md, tvd, mw))
    out = np.zeros(len(bit_md))
    cache: dict = {}
    for i in range(len(bit_md)):
        key = (round(q[i]), round(bit_md[i]), round(mw[i], 2))
        if key not in cache:
            cache[key] = annular_loss(key[0], key[1], key[2], r, hole_size, casing_id, shoe_md, string)[0]
        out[i] = cache[key] / (0.052 * tvd[i]) if tvd[i] > 0 else 0.0
    return out
