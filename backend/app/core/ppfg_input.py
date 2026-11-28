"""PPFG tanpa file Rec 03: input manual per interval MD + approve (dipakai router PPFG dan ingest).

Klien 28 Nov: PPFG approved sudah ada sejak awal (Navita mengisinya bersama survey plan). Input di sini dalam MD;
TVD diisi dari survey sumur bila MD berada di rentang survey, selain itu dibiarkan kosong (margin memakai MD)."""
from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import PPFGRow, PPFGVersion
from ..security import audit

VALUE_KEYS = ("pp", "sfg", "fg_min", "fg_max")
LABEL = {"pp": "PP", "sfg": "SFG", "fg_min": "FG min", "fg_max": "FG max"}
STEP_GAP_FT = 0.1   # interval bersambung: titik bawah digeser 0,1 ft supaya nilai berubah bertingkat, bukan miring


def _num(v, name: str, i: int, lo: float, hi: float) -> float | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"Baris {i}: {name} bukan angka ({v!r})") from None
    if not np.isfinite(x) or not lo <= x <= hi:
        raise ValueError(f"Baris {i}: {name} {x:g} di luar rentang {lo:g}–{hi:g}")
    return x


def clean_intervals(rows: list[dict]) -> list[dict]:
    """Validasi interval (MD atas–bawah, ppg). Error bila MD terbalik/tumpang tindih, nilai di luar 4–25 ppg,
    FG min > FG max, atau FG min ≤ PP. Interval tanpa nilai apa pun dibuang."""
    out = []
    for i, r in enumerate(rows, 1):
        a = _num(r.get("md_top"), "MD atas", i, 0, 60000)
        b = _num(r.get("md_bottom"), "MD bawah", i, 0, 60000)
        vals = {k: _num(r.get(k), LABEL[k], i, 4, 25) for k in VALUE_KEYS}
        form = (str(r.get("formation") or "").strip() or None)
        if a is None and b is None and all(v is None for v in vals.values()):
            continue
        if a is None or b is None:
            raise ValueError(f"Baris {i}: MD atas dan MD bawah wajib diisi")
        if b <= a:
            raise ValueError(f"Baris {i}: MD bawah ({b:g}) harus lebih dalam dari MD atas ({a:g})")
        if all(v is None for v in vals.values()):
            raise ValueError(f"Baris {i}: isi minimal satu nilai (PP, SFG, FG min, FG max)")
        if vals["fg_min"] is not None and vals["fg_max"] is not None and vals["fg_min"] > vals["fg_max"]:
            raise ValueError(f"Baris {i}: FG min ({vals['fg_min']:g}) lebih besar dari FG max ({vals['fg_max']:g})")
        if vals["fg_min"] is not None and vals["pp"] is not None and vals["fg_min"] <= vals["pp"]:
            raise ValueError(f"Baris {i}: FG min ({vals['fg_min']:g}) tidak lebih besar dari PP ({vals['pp']:g})")
        out.append({"md_top": a, "md_bottom": b, **vals, "formation": form[:64] if form else None, "_i": i})
    out.sort(key=lambda r: r["md_top"])
    for p, q in zip(out, out[1:]):
        if q["md_top"] < p["md_bottom"]:
            raise ValueError(f"Baris {q['_i']}: MD {q['md_top']:g}–{q['md_bottom']:g} tumpang tindih dengan baris "
                             f"{p['_i']} ({p['md_top']:g}–{p['md_bottom']:g})")
    if not out:
        raise ValueError("Tidak ada interval yang diisi")
    return [{k: v for k, v in r.items() if k != "_i"} for r in out]


def intervals_to_points(iv: list[dict], survey: pd.DataFrame | None = None) -> list[dict]:
    """Interval → titik PPFG (atas + bawah per interval) agar interpolasi linear sistem memberi nilai konstan di dalam
    interval dan berubah bertingkat di batas interval."""
    pts = []
    for j, r in enumerate(iv):
        nxt = iv[j + 1]["md_top"] if j + 1 < len(iv) else None
        bot = r["md_bottom"] - STEP_GAP_FT if nxt is not None and nxt - r["md_bottom"] < STEP_GAP_FT else r["md_bottom"]
        base = {k: r[k] for k in VALUE_KEYS} | {"formation": r["formation"]}
        pts += [{"md": r["md_top"], **base}, {"md": bot, **base}]
    if survey is not None and len(survey) >= 2 and survey["tvd"].notna().sum() >= 2:
        sv = survey.dropna(subset=["md", "tvd"]).sort_values("md")
        for p in pts:
            if sv["md"].iloc[0] <= p["md"] <= sv["md"].iloc[-1]:
                p["tvd"] = round(float(np.interp(p["md"], sv["md"], sv["tvd"])), 1)
    return pts


def approve_version(db: Session, v: PPFGVersion, user: str, effective_date: datetime | None = None,
                    tvd_datum: str | None = None, notes: str = "", how: str = "ppfg_approve") -> PPFGVersion:
    """Jadikan approved; versi approved lama → superseded. Tidak commit."""
    for o in db.scalars(select(PPFGVersion).where(PPFGVersion.well_id == v.well_id, PPFGVersion.status == "approved",
                                                  PPFGVersion.id != v.id)):
        o.status = "superseded"
    now = datetime.now(timezone.utc)
    v.status, v.approved_by, v.approved_at = "approved", user, now
    v.effective_date = effective_date or now
    v.tvd_datum = tvd_datum or v.tvd_datum or "RKB"
    if notes:
        v.notes = notes
    audit(db, user, how, f"well {v.well_id} v{v.version}")
    return v


def new_version(db: Session, well_id: int, user: str, notes: str, source_file_id: int | None = None) -> PPFGVersion:
    nxt = (db.scalar(select(func.max(PPFGVersion.version)).where(PPFGVersion.well_id == well_id)) or 0) + 1
    v = PPFGVersion(well_id=well_id, version=nxt, status="draft", source_file_id=source_file_id, created_by=user,
                    notes=notes)
    db.add(v)
    db.flush()
    return v


def store_manual(db: Session, well_id: int, rows: list[dict], user: str, approved: bool, notes: str = "",
                 survey: pd.DataFrame | None = None) -> tuple[PPFGVersion, int]:
    iv = clean_intervals(rows)
    pts = intervals_to_points(iv, survey)
    v = new_version(db, well_id, user, notes or f"input manual {len(iv)} interval MD")
    db.bulk_insert_mappings(PPFGRow, [{**p, "version_id": v.id} for p in pts])
    audit(db, user, "ppfg_manual", f"well {well_id} v{v.version}: {len(iv)} interval")
    if approved:
        approve_version(db, v, user, notes=v.notes + " · approved di sumber", how="ppfg_approve_source")
    db.flush()
    return v, len(iv)
