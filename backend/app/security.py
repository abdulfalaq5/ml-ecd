"""Login akun lokal (bcrypt + JWT) dan pembatasan per peran (docs Bab 10.2, Lampiran H F3/F4)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .db import get_db
from .models import AuditLog, User

ROLES = {
    "admin": "Data/ML (Admin)", "data_ml": "Data/ML", "rto": "RTO", "drilling_eng": "Drilling Eng",
    "mud_eng": "Mud Eng", "geomech": "Geomechanics", "mwd": "Directional/MWD", "hse": "HSE", "viewer": "Viewer rig",
}

PERM = {
    "upload": {"admin", "data_ml", "rto"},
    "qc_signoff": {"admin", "rto"},
    "event_label": {"admin", "rto", "drilling_eng", "mwd", "mud_eng"},
    "event_review": {"admin", "rto", "drilling_eng"},
    "ppfg_edit": {"admin", "rto", "data_ml", "geomech"},
    "ppfg_approve": {"admin", "geomech"},
    "mw_rule": {"admin", "mud_eng"},
    "threshold_propose": {"admin", "rto", "drilling_eng", "data_ml", "hse"},
    "threshold_approve": {"admin", "drilling_eng", "hse"},
    "model_train": {"admin", "data_ml"},
    "model_gate": {"admin", "data_ml", "drilling_eng", "rto"},
    "model_promote": {"admin"},
    "users": {"admin"},
    "report": {"admin", "data_ml", "rto", "drilling_eng", "mud_eng", "geomech", "mwd", "hse"},
    "well_edit": {"admin", "data_ml", "rto"},
}

oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def check_pw(pw: str, h: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), h.encode())
    except ValueError:
        return False


def make_token(user: User) -> str:
    s = get_settings()
    exp = datetime.now(timezone.utc) + timedelta(hours=s.token_hours)
    return jwt.encode({"sub": user.username, "role": user.role, "exp": exp}, s.secret_key, algorithm="HS256")


def current_user(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> User:
    try:
        data = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesi tidak valid atau kedaluwarsa")
    u = db.scalar(select(User).where(User.username == data.get("sub")))
    if not u or not u.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Akun tidak aktif")
    return u


def require(perm: str):
    def dep(user: User = Depends(current_user)) -> User:
        if user.role not in PERM[perm]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"Peran {ROLES.get(user.role, user.role)} tidak berhak ({perm})")
        return user
    return dep


def audit(db: Session, user: str, action: str, detail: str = "") -> None:
    db.add(AuditLog(username=user, action=action, detail=detail))


def bootstrap_admin(db: Session) -> None:
    s = get_settings()
    if not db.scalar(select(User).where(User.username == s.admin_username)):
        db.add(User(username=s.admin_username, full_name="Administrator", role="admin",
                    password_hash=hash_pw(s.admin_password)))
        db.commit()
