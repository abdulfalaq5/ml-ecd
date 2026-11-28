"""Formasi & FG: versi PPFG (draft -> approved Geomechanics -> superseded) + aturan MW."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.analysis import f
from ..db import get_db
from ..core.data import load_survey
from ..core.ppfg_input import approve_version, store_manual
from ..models import PPFGRow, PPFGVersion, Setting, User, Well
from ..security import PERM, audit, current_user, require

router = APIRouter(prefix="/api", tags=["ppfg"])


def vout(v: PPFGVersion) -> dict:
    return {"id": v.id, "well_id": v.well_id, "version": v.version, "status": v.status, "tvd_datum": v.tvd_datum,
            "effective_date": v.effective_date.isoformat() if v.effective_date else None,
            "approved_by": v.approved_by, "approved_at": v.approved_at.isoformat() if v.approved_at else None,
            "created_by": v.created_by, "notes": v.notes, "created_at": v.created_at.isoformat()}


@router.get("/wells/{wid}/ppfg")
def versions(wid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    vs = db.scalars(select(PPFGVersion).where(PPFGVersion.well_id == wid).order_by(PPFGVersion.version)).all()
    return [vout(v) for v in vs]


@router.get("/ppfg/{vid}/intervals")
def intervals(vid: int, step: float = 250.0, db: Session = Depends(get_db), _: User = Depends(current_user)):
    """Ringkasan per interval `step` ft (tabel halaman Formasi & FG)."""
    b = (func.floor(PPFGRow.md / step) * step).label("b")
    rows = db.execute(select(b, func.max(PPFGRow.pp), func.max(PPFGRow.sfg),
                             func.min(PPFGRow.fg_min), func.max(PPFGRow.fg_max), func.min(PPFGRow.tvd),
                             func.max(PPFGRow.formation))
                      .where(PPFGRow.version_id == vid).group_by(b).order_by(b)).all()
    return [{"a": float(r[0]), "b": float(r[0]) + step, "pp": f(r[1]), "sfg": f(r[2]), "fg_min": f(r[3]),
             "fg_max": f(r[4]), "tvd": f(r[5], 0), "formation": r[6]} for r in rows]


class Approve(BaseModel):
    effective_date: str | None = None
    tvd_datum: str = "RKB"
    notes: str = ""


@router.post("/ppfg/{vid}/approve")
def approve(vid: int, body: Approve, db: Session = Depends(get_db), u: User = Depends(require("ppfg_approve"))):
    v = db.get(PPFGVersion, vid)
    if not v:
        raise HTTPException(404, "Versi tidak ada")
    if v.status != "draft":
        raise HTTPException(400, "Hanya versi draft yang bisa di-approve")
    approve_version(db, v, u.username, datetime.fromisoformat(body.effective_date) if body.effective_date else None,
                    body.tvd_datum, body.notes)
    db.commit()
    return vout(v)


class ManualPPFG(BaseModel):
    rows: list[dict]
    approved: bool = False
    notes: str = ""


@router.post("/wells/{wid}/ppfg/manual")
def manual(wid: int, body: ManualPPFG, db: Session = Depends(get_db), u: User = Depends(require("ppfg_edit"))):
    """PPFG tanpa file Rec 03: interval MD (atas–bawah) + PP/SFG/FG. `approved` = sudah approved di sumber
    (Navita / Geomechanics), hanya untuk peran yang berhak approve."""
    if not db.get(Well, wid):
        raise HTTPException(404, "Sumur tidak ditemukan")
    if body.approved and u.role not in PERM["ppfg_approve"]:
        raise HTTPException(403, "Hanya admin / geomech yang boleh menandai PPFG approved")
    try:
        v, n = store_manual(db, wid, body.rows, u.username, body.approved, body.notes.strip()[:500], load_survey(db, wid))
    except ValueError as e:
        db.rollback()
        raise HTTPException(400, str(e)) from None
    db.commit()
    return {**vout(v), "intervals": n}


@router.post("/ppfg/{vid}/draft")
def copy_to_draft(vid: int, db: Session = Depends(get_db), u: User = Depends(require("ppfg_edit"))):
    """Koreksi = versi draft baru (salinan), versi lama tidak diubah."""
    v = db.get(PPFGVersion, vid)
    if not v:
        raise HTTPException(404, "Versi tidak ada")
    nxt = (db.scalar(select(func.max(PPFGVersion.version)).where(PPFGVersion.well_id == v.well_id)) or 0) + 1
    nv = PPFGVersion(well_id=v.well_id, version=nxt, status="draft", source_file_id=v.source_file_id,
                     created_by=u.username, notes=f"salinan v{v.version}", tvd_datum=v.tvd_datum)
    db.add(nv)
    db.flush()
    rows = db.scalars(select(PPFGRow).where(PPFGRow.version_id == v.id)).all()
    db.bulk_insert_mappings(PPFGRow, [{"version_id": nv.id, "md": r.md, "tvd": r.tvd, "pp": r.pp, "sfg": r.sfg,
                                       "fg_min": r.fg_min, "fg_max": r.fg_max, "shmax": r.shmax, "obg": r.obg,
                                       "formation": r.formation} for r in rows])
    audit(db, u.username, "ppfg_draft", f"well {v.well_id} v{nxt} dari v{v.version}")
    db.commit()
    return vout(nv)


class RowEdit(BaseModel):
    md_from: float
    md_to: float
    field: str
    value: float | None


@router.post("/ppfg/{vid}/edit")
def edit_rows(vid: int, body: RowEdit, db: Session = Depends(get_db), u: User = Depends(require("ppfg_edit"))):
    v = db.get(PPFGVersion, vid)
    if not v or v.status != "draft":
        raise HTTPException(400, "Hanya versi draft yang bisa dikoreksi")
    if body.field not in {"pp", "sfg", "fg_min", "fg_max"}:
        raise HTTPException(400, "Kolom tidak boleh diubah")
    n = 0
    for r in db.scalars(select(PPFGRow).where(PPFGRow.version_id == vid, PPFGRow.md >= body.md_from, PPFGRow.md < body.md_to)):
        setattr(r, body.field, body.value)
        n += 1
    audit(db, u.username, "ppfg_edit", f"v{v.version} {body.field}={body.value} {body.md_from}-{body.md_to} ({n} baris)")
    db.commit()
    return {"updated": n}


class MWRule(BaseModel):
    rule: str  # bit_passes | mud_report


@router.get("/settings/mw_rule")
def get_mw_rule(db: Session = Depends(get_db), _: User = Depends(current_user)):
    s = db.get(Setting, "mw_rule")
    return s.value if s else {"rule": "bit_passes", "approved_by": None}


@router.post("/settings/mw_rule")
def set_mw_rule(body: MWRule, db: Session = Depends(get_db), u: User = Depends(require("mw_rule"))):
    s = db.get(Setting, "mw_rule") or Setting(key="mw_rule")
    s.value = {"rule": body.rule, "approved_by": u.username, "at": datetime.now(timezone.utc).isoformat()}
    db.merge(s)
    audit(db, u.username, "mw_rule", body.rule)
    db.commit()
    return s.value
