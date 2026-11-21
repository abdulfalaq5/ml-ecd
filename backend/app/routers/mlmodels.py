"""Model ML: dataset per sumur, training (grouped), hasil blind, promotion gate, rollback."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from ..db import get_db
from ..ml.pipeline import ALGOS, start_training
from ..models import MLModel, User, Well
from ..security import audit, current_user, require

router = APIRouter(prefix="/api/models", tags=["models"])
GATES = [("qc", "Data QC"), ("blind", "Blind-well test"), ("review", "Engineering review"),
         ("shadow", "Shadow monitoring"), ("threshold", "Threshold terdokumentasi"), ("rollback", "Rollback teruji")]


def mout(m: MLModel, full: bool = False) -> dict:
    d = {"id": m.id, "name": f"ecd-{m.algo} v{m.version}", "version": m.version, "algo": m.algo, "status": m.status,
         "train_wells": m.train_wells, "blind_wells": m.blind_wells, "created_by": m.created_by,
         "created_at": m.created_at.isoformat(), "promoted_at": m.promoted_at.isoformat() if m.promoted_at else None,
         "gates": {k: bool((m.gates or {}).get(k)) for k, _ in GATES}, "gate_labels": dict(GATES)}
    if full:
        d.update({"metrics": m.metrics, "features": m.features, "importance": m.importance,
                  "residual_q": m.residual_q, "feature_ranges": m.feature_ranges, "log": m.log})
    return d


@router.get("")
def list_models(db: Session = Depends(get_db), _: User = Depends(current_user)):
    return [mout(m) for m in db.scalars(select(MLModel).order_by(MLModel.id.desc()))]


@router.get("/dataset")
def dataset(db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.execute(text(
        "SELECT w.id, w.name, w.role, w.section, "
        "count(*) FILTER (WHERE t.ecd BETWEEN 7 AND 20) ecd_n, "
        "count(*) FILTER (WHERE t.record=1) rig_n, min(t.ts), max(t.ts) "
        "FROM wells w LEFT JOIN ts_data t ON t.well_id=w.id GROUP BY w.id ORDER BY w.name")).all()
    return [{"id": r[0], "name": r[1], "role": r[2], "section": r[3], "ecd_points": r[4], "rig_points": r[5],
             "t0": r[6].isoformat() if r[6] else None, "t1": r[7].isoformat() if r[7] else None} for r in rows]


@router.get("/{mid}")
def get_model(mid: int, db: Session = Depends(get_db), _: User = Depends(current_user)):
    m = db.get(MLModel, mid)
    if not m:
        raise HTTPException(404, "Model tidak ada")
    return mout(m, True)


class TrainIn(BaseModel):
    algo: str = "all"
    train_wells: list[str] | None = None
    blind_wells: list[str] | None = None
    lowo: bool = True


@router.post("/train")
def train(body: TrainIn, db: Session = Depends(get_db), u: User = Depends(require("model_train"))):
    if body.algo not in ALGOS + ["all"]:
        raise HTTPException(400, "Algoritma tidak dikenal")
    wells = db.scalars(select(Well)).all()
    tr = body.train_wells if body.train_wells is not None else [w.name for w in wells if w.role == "train"]
    bl = body.blind_wells if body.blind_wells is not None else [w.name for w in wells if w.role == "blind"]
    if set(tr) & set(bl):
        raise HTTPException(400, "Sumur blind tidak boleh ikut training")
    if db.scalar(select(MLModel).where(MLModel.status == "training")):
        raise HTTPException(409, "Masih ada training berjalan")
    m = start_training(db, body.algo, tr, bl, body.lowo, u.username)
    audit(db, u.username, "model_train", f"v{m.version} algo={body.algo} train={tr} blind={bl}")
    db.commit()
    return mout(m)


class GateIn(BaseModel):
    gate: str
    value: bool


@router.post("/{mid}/gate")
def gate(mid: int, body: GateIn, db: Session = Depends(get_db), u: User = Depends(require("model_gate"))):
    m = db.get(MLModel, mid)
    if not m or body.gate not in dict(GATES):
        raise HTTPException(400, "Gate tidak dikenal")
    if body.gate == "review" and u.role not in {"drilling_eng", "admin"}:
        raise HTTPException(403, "Engineering review oleh Drilling Eng")
    m.gates = {**(m.gates or {}), body.gate: body.value, f"{body.gate}_by": u.username}
    audit(db, u.username, "model_gate", f"v{m.version} {body.gate}={body.value}")
    db.commit()
    return mout(m)


class StatusIn(BaseModel):
    status: str  # shadow | production | archived


@router.post("/{mid}/status")
def set_status(mid: int, body: StatusIn, db: Session = Depends(get_db), u: User = Depends(require("model_promote"))):
    m = db.get(MLModel, mid)
    if not m:
        raise HTTPException(404, "Model tidak ada")
    if body.status not in {"shadow", "production", "archived", "candidate"}:
        raise HTTPException(400, "Status tidak dikenal")
    if body.status == "production" and not all((m.gates or {}).get(k) for k, _ in GATES):
        raise HTTPException(400, "Promotion gate belum lengkap (6/6)")
    if body.status in {"shadow", "production"}:
        for o in db.scalars(select(MLModel).where(MLModel.status == body.status, MLModel.id != m.id)):
            o.status = "archived"
        m.promoted_at = datetime.now(timezone.utc)
    m.status = body.status
    audit(db, u.username, "model_status", f"v{m.version} -> {body.status}")
    db.commit()
    return mout(m)
