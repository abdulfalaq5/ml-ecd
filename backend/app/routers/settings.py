"""Pengaturan: threshold alert (ajukan -> setujui Drilling Eng + HSE), parameter detektor, audit log."""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..anomaly.detectors import DEFAULTS as DET_DEFAULTS
from ..config import get_settings
from ..core.alerts import DEFAULT_THRESHOLDS
from ..db import get_db
from ..models import AuditLog, Setting, User
from ..security import audit, current_user, require

router = APIRouter(prefix="/api/settings", tags=["settings"])
KEYS = {"thresholds": DEFAULT_THRESHOLDS, "detectors": DET_DEFAULTS}


def sout(key: str, s: Setting | None) -> dict:
    d = KEYS[key]
    return {"key": key, "defaults": d, "value": {**d, **(s.value if s else {})}, "proposed": s.proposed if s else None,
            "status": s.status if s else "active", "proposed_by": s.proposed_by if s else "",
            "approved_by": s.approved_by if s else "", "approvals": (s.proposed or {}).get("_approvals", []) if s and s.proposed else [],
            "updated_at": s.updated_at.isoformat() if s and s.updated_at else None}


@router.get("/{key}")
def get(key: str, db: Session = Depends(get_db), _: User = Depends(current_user)):
    if key not in KEYS:
        raise HTTPException(404, "Pengaturan tidak ada")
    return sout(key, db.get(Setting, key))


class Propose(BaseModel):
    value: dict


@router.post("/{key}/propose")
def propose(key: str, body: Propose, db: Session = Depends(get_db), u: User = Depends(require("threshold_propose"))):
    if key not in KEYS:
        raise HTTPException(404, "Pengaturan tidak ada")
    clean = {k: float(v) for k, v in body.value.items() if k in KEYS[key] and v not in (None, "")}
    if not clean:
        raise HTTPException(400, "Tidak ada parameter yang dikenali")
    s = db.get(Setting, key) or Setting(key=key, value={})
    s.proposed = {**clean, "_approvals": []}
    s.status = "pending"
    s.proposed_by = u.username
    db.merge(s)
    audit(db, u.username, f"{key}_propose", str(clean))
    db.commit()
    return sout(key, db.get(Setting, key))


@router.post("/{key}/approve")
def approve(key: str, db: Session = Depends(get_db), u: User = Depends(require("threshold_approve"))):
    """Butuh persetujuan Drilling Eng DAN HSE (admin dihitung sebagai keduanya untuk instalasi awal)."""
    s = db.get(Setting, key)
    if not s or s.status != "pending" or not s.proposed:
        raise HTTPException(400, "Tidak ada perubahan yang menunggu persetujuan")
    appr = list(s.proposed.get("_approvals", []))
    roles = {"drilling_eng", "hse"} if u.role == "admin" else {u.role}
    for r in roles:
        if r not in [a["role"] for a in appr]:
            appr.append({"role": r, "by": u.username, "at": datetime.now(timezone.utc).isoformat()})
    s.proposed = {**s.proposed, "_approvals": appr}
    have = {a["role"] for a in appr}
    if {"drilling_eng", "hse"} <= have:
        s.value = {k: v for k, v in s.proposed.items() if not k.startswith("_")}
        s.status = "active"
        s.approved_by = ", ".join(a["by"] for a in appr)
        s.proposed = None
    audit(db, u.username, f"{key}_approve", f"{sorted(have)}")
    db.commit()
    return sout(key, db.get(Setting, key))


@router.post("/{key}/reset")
def reset(key: str, db: Session = Depends(get_db), u: User = Depends(require("threshold_propose"))):
    s = db.get(Setting, key) or Setting(key=key, value={})
    s.proposed = {**KEYS[key], "_approvals": []}
    s.status = "pending"
    s.proposed_by = u.username
    db.merge(s)
    audit(db, u.username, f"{key}_reset_propose")
    db.commit()
    return sout(key, db.get(Setting, key))


@router.get("/system/info")
def system(_: User = Depends(current_user)):
    s = get_settings()
    return {"resample_s": s.resample_s, "flow_min_gpm": s.flow_min_gpm, "source_tz": s.source_tz,
            "display_tz": s.display_tz, "watch_enabled": s.watch_enabled, "watch_interval_s": s.watch_interval_s,
            "inbox_dir": s.inbox_dir, "ai_enabled": bool(s.anthropic_api_key.strip()), "ai_model": s.ai_model}


@router.get("/audit/log")
def audit_log(limit: int = 200, db: Session = Depends(get_db), _: User = Depends(current_user)):
    rows = db.scalars(select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)).all()
    return [{"ts": r.ts.isoformat(), "username": r.username, "action": r.action, "detail": r.detail} for r in rows]
