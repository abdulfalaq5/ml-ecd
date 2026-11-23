"""Data section per sumur (depth-based, seperti MW Rec 04): ukuran lubang, casing shoe, string, PV/YP spek.

Satu baris = berlaku sejak hole depth `from_md` tercapai sampai baris berikutnya. Dipakai ramalan ECD (hidraulika,
cutting) dan nantinya estimasi bending (preset string). Disimpan di kolom JSON `wells.sections`.

  {"from_md": 1500, "hole_size": 12.25, "shoe_md": 1495, "casing_id": 12.415, "preset": "BHA_12.25_STD",
   "pv": 18, "yp": 20, "note": "DDR 12 Okt"}
"""
from __future__ import annotations

import numpy as np

from . import bending as bd
from . import hydraulics as hy

FIELDS = ("from_md", "hole_size", "shoe_md", "casing_id", "preset", "pv", "yp", "note")


def _num(v, name: str, lo: float, hi: float, i: int, required: bool = False) -> float | None:
    if v in (None, ""):
        if required:
            raise ValueError(f"baris {i + 1}: {name} wajib diisi")
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"baris {i + 1}: {name} harus angka")
    if not lo <= x <= hi:
        raise ValueError(f"baris {i + 1}: {name} {x:g} di luar rentang {lo:g}–{hi:g}")
    return x


def clean_sections(rows: list[dict] | None) -> list[dict]:
    """Validasi + urutkan. Kosong → []. ValueError dengan pesan berbahasa Indonesia bila salah."""
    if not rows:
        return []
    presets = bd.load_catalog()["presets"]
    out = []
    for i, r in enumerate(rows):
        s = {
            "from_md": _num(r.get("from_md"), "mulai hole depth", 0, 40000, i, True),
            "hole_size": _num(r.get("hole_size"), "ukuran lubang", 3, 36, i, True),
            "shoe_md": _num(r.get("shoe_md"), "shoe casing MD", 0, 40000, i),
            "casing_id": _num(r.get("casing_id"), "ID casing", 3, 30, i),
            "pv": _num(r.get("pv"), "PV", 1, 150, i),
            "yp": _num(r.get("yp"), "YP", 1, 150, i),
            "preset": (r.get("preset") or None),
            "note": str(r.get("note") or "")[:200],
        }
        if s["preset"] and s["preset"] not in presets:
            raise ValueError(f"baris {i + 1}: preset string '{s['preset']}' tidak ada di katalog")
        if s["shoe_md"] is not None and s["shoe_md"] > s["from_md"] + 50:
            raise ValueError(f"baris {i + 1}: shoe casing ({s['shoe_md']:g} ft) lebih dalam dari awal section ({s['from_md']:g} ft)")
        if s["casing_id"] is not None and s["casing_id"] <= s["hole_size"] * 0.6:
            raise ValueError(f"baris {i + 1}: ID casing {s['casing_id']:g}\" terlalu kecil untuk lubang {s['hole_size']:g}\"")
        if (s["pv"] is None) != (s["yp"] is None):
            raise ValueError(f"baris {i + 1}: isi PV dan YP keduanya, atau kosongkan keduanya")
        out.append(s)
    out.sort(key=lambda s: s["from_md"])
    mds = [s["from_md"] for s in out]
    if len(set(mds)) != len(mds):
        raise ValueError("ada dua baris dengan 'mulai hole depth' yang sama")
    return out


def section_at(sections: list[dict] | None, hole_md: float | None) -> dict | None:
    """Baris aktif: from_md terbesar ≤ hole depth yang sudah dicapai. Sebelum baris pertama → None."""
    if not sections or hole_md is None or not np.isfinite(hole_md):
        return None
    act = None
    for s in sorted(sections, key=lambda s: s["from_md"]):
        if s["from_md"] <= hole_md:
            act = s
    return act


def presets_for_ui() -> list[dict]:
    cat = bd.load_catalog()
    return [{"id": k, "name": p["name"], "bit_size": p.get("bit_size"), "kind": p.get("kind")}
            for k, p in cat["presets"].items() if p.get("kind") == "drill"]


def casing_id_defaults() -> dict:
    return {str(k): v for k, v in hy.CASING_ID_FOR_HOLE.items()}
