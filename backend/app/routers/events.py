"""Riwayat Event: katalog event + review workflow (Draft -> Menunggu review -> Dikonfirmasi / Ditolak)."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Event, User, Well
from ..security import audit, current_user, require

router = APIRouter(prefix="/api/events", tags=["events"])

CATEGORIES = ["Loss", "Influx", "Pack-off / poor hole cleaning", "Tight hole / sloughing", "Differential sticking",
              "Mechanical sticking", "Stuck", "Operasi (casing / cementing)", "Noise sensor", "Lainnya"]
REVIEW = ["Draft", "Menunggu review", "Dikonfirmasi", "Ditolak"]
LEVELS = ["INFO", "ADVISORY", "WARNING", "CRITICAL", "STUCK", "NOISE"]


def out(e: Event, wells: dict) -> dict:
    return {"id": e.id, "well_id": e.well_id, "well": wells.get(e.well_id, ""), "onset": e.onset.isoformat(),
            "end": e.end.isoformat() if e.end else None, "md": e.md, "level": e.level, "category": e.category,
            "confidence": e.confidence, "review_status": e.review_status, "evidence": e.evidence, "detail": e.detail,
            "mode": e.mode, "source": e.source, "created_by": e.created_by, "history": e.history or []}


@router.get("/meta")
def meta(_: User = Depends(current_user)):
    return {"categories": CATEGORIES, "review": REVIEW, "levels": LEVELS, "confidence": ["Tinggi", "Sedang", "Rendah"]}


@router.get("")
def list_events(well_id: int | None = None, category: str | None = None, review: str | None = None,
                db: Session = Depends(get_db), _: User = Depends(current_user)):
    q = select(Event).order_by(Event.onset.desc())
    if well_id:
        q = q.where(Event.well_id == well_id)
    if category:
        q = q.where(Event.category == category)
    if review:
        q = q.where(Event.review_status == review)
    wells = {w.id: w.name for w in db.scalars(select(Well))}
    return [out(e, wells) for e in db.scalars(q.limit(1000))]


class EventIn(BaseModel):
    well_id: int
    onset: str
    end: str | None = None
    md: float | None = None
    level: str = "ADVISORY"
    category: str = "Lainnya"
    confidence: str = "Sedang"
    evidence: str = ""
    detail: str = ""
    mode: str = ""
    source: str = "manual"


def _ts(s):
    """Waktu tanpa zona dianggap WIB (input form), disimpan UTC."""
    from .monitor import _t
    return _t(s) if s else None


@router.post("")
def create(body: EventIn, db: Session = Depends(get_db), u: User = Depends(require("event_label"))):
    if body.category not in CATEGORIES:
        raise HTTPException(400, "Kategori tidak dikenal")
    now = datetime.now(timezone.utc).isoformat()
    e = Event(well_id=body.well_id, onset=_ts(body.onset), end=_ts(body.end), md=body.md, level=body.level,
              category=body.category, confidence=body.confidence, evidence=body.evidence, detail=body.detail,
              mode=body.mode, source=body.source, created_by=u.username, review_status="Draft",
              history=[{"at": now, "by": u.username, "action": "dibuat"}])
    db.add(e)
    audit(db, u.username, "event_create", f"{body.category} {body.onset}")
    db.commit()
    return out(e, {w.id: w.name for w in db.scalars(select(Well))})


class ReviewIn(BaseModel):
    status: str
    category: str | None = None
    confidence: str | None = None
    note: str = ""


@router.post("/{eid}/review")
def review(eid: int, body: ReviewIn, db: Session = Depends(get_db), u: User = Depends(current_user)):
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Event tidak ada")
    if body.status not in REVIEW:
        raise HTTPException(400, "Status tidak dikenal")
    need = "event_review" if body.status in ("Dikonfirmasi", "Ditolak") else "event_label"
    from ..security import PERM
    if u.role not in PERM[need]:
        raise HTTPException(403, "Peran tidak berhak mengubah status ini")
    if body.category:
        e.category = body.category
    if body.confidence:
        e.confidence = body.confidence
    e.review_status = body.status
    e.history = [*(e.history or []), {"at": datetime.now(timezone.utc).isoformat(), "by": u.username,
                                      "action": body.status, "note": body.note,
                                      "category": e.category, "confidence": e.confidence}]
    audit(db, u.username, "event_review", f"#{e.id} -> {body.status}")
    db.commit()
    return out(e, {w.id: w.name for w in db.scalars(select(Well))})


@router.delete("/{eid}")
def delete(eid: int, db: Session = Depends(get_db), u: User = Depends(require("event_review"))):
    e = db.get(Event, eid)
    if not e:
        raise HTTPException(404, "Event tidak ada")
    db.delete(e)
    audit(db, u.username, "event_delete", f"#{eid}")
    db.commit()
    return {"ok": True}
