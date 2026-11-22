"""Laporan: harian, event/studi kasus, evaluasi model, QC. Ringkasan JSON + unduh Excel + narasi AI opsional."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Report, User, Well
from ..reports.report import KINDS, build_summary, narrate, to_excel
from ..security import audit, current_user, require
from .monitor import _t

router = APIRouter(prefix="/api/reports", tags=["reports"])


def rout(r: Report, full: bool = False) -> dict:
    d = {"id": r.id, "kind": r.kind, "kind_label": KINDS.get(r.kind, r.kind), "well_id": r.well_id, "title": r.title,
         "period_start": r.period_start.isoformat() if r.period_start else None,
         "period_end": r.period_end.isoformat() if r.period_end else None,
         "created_by": r.created_by, "created_at": r.created_at.isoformat() if r.created_at else None,
         "has_narrative": bool(r.narrative)}
    if full:
        d.update({"summary": r.summary, "narrative": r.narrative})
    return d


@router.get("")
def list_reports(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return {"kinds": KINDS, "items": [rout(r) for r in db.scalars(select(Report).order_by(Report.id.desc()).limit(200))]}


class ReportIn(BaseModel):
    kind: str = "daily"
    well_id: int | None = None
    t0: str | None = None
    t1: str | None = None
    ai: bool = True  # dipakai hanya bila API key AI diisi; False = paksa tanpa AI
    title: str | None = None


def _well(db, wid):
    if wid is None:
        return None
    w = db.get(Well, wid)
    if not w:
        raise HTTPException(404, "Sumur tidak ada")
    return w


@router.post("")
def create(body: ReportIn, db: Session = Depends(get_db), u: User = Depends(require("report"))):
    if body.kind not in KINDS:
        raise HTTPException(400, "Jenis laporan tidak dikenal")
    w = _well(db, body.well_id)
    if body.kind in ("daily", "event", "rathole") and not w:
        raise HTTPException(400, "Pilih sumur")
    t0, t1 = _t(body.t0), _t(body.t1)
    summary, _ = build_summary(db, body.kind, w, t0, t1)
    narrative, src, note = narrate(summary, body.ai)
    summary = {**summary, "narrative_source": src, "narrative_note": note}
    r = Report(kind=body.kind, well_id=w.id if w else None,
               title=body.title or f"{KINDS[body.kind]}{' — ' + w.name if w else ''}",
               period_start=t0, period_end=t1, summary=summary, narrative=narrative, created_by=u.username)
    db.add(r)
    audit(db, u.username, "report_create", f"{body.kind} well={w.name if w else '-'} narasi={src}")
    db.commit()
    return rout(r, True)


@router.get("/{rid}")
def get(rid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404, "Laporan tidak ada")
    return rout(r, True)


class NarrIn(BaseModel):
    narrative: str | None = None
    ai: bool = False


@router.post("/{rid}/narrative")
def narrative(rid: int, body: NarrIn, db: Session = Depends(get_db), u: User = Depends(require("report"))):
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404, "Laporan tidak ada")
    if body.ai:  # "Buat ulang narasi": AI bila API key diisi, selain itu templat tanpa AI
        r.narrative, src, note = narrate(r.summary)
    else:
        r.narrative, src, note = body.narrative or "", "manual", None
    r.summary = {**(r.summary or {}), "narrative_source": src, "narrative_note": note}  # dict baru → JSON ter-update
    audit(db, u.username, "report_narrative", f"#{r.id} narasi={src}")
    db.commit()
    return rout(r, True)


@router.get("/{rid}/xlsx")
def xlsx(rid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    r = db.get(Report, rid)
    if not r:
        raise HTTPException(404, "Laporan tidak ada")
    w = _well(db, r.well_id)
    frame = None
    if r.kind in ("daily", "event") and w:
        _, frame = build_summary(db, r.kind, w, r.period_start, r.period_end)
    data = to_excel({**r.summary, "narrative": r.narrative}, frame)
    fn = f"laporan_{r.kind}_{r.id}.xlsx"
    return Response(data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


@router.delete("/{rid}")
def delete(rid: int, db: Session = Depends(get_db), u: User = Depends(require("report"))):
    r = db.get(Report, rid)
    if r:
        db.delete(r)
        audit(db, u.username, "report_delete", f"#{rid}")
        db.commit()
    return {"ok": True}
