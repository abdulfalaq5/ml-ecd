from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import User
from ..security import PERM, ROLES, audit, check_pw, current_user, hash_pw, make_token, require

router = APIRouter(prefix="/api", tags=["auth"])


def user_out(u: User) -> dict:
    return {"id": u.id, "username": u.username, "full_name": u.full_name, "role": u.role,
            "role_label": ROLES.get(u.role, u.role), "active": u.active,
            "last_login": u.last_login.isoformat() if u.last_login else None,
            "perms": sorted(p for p, roles in PERM.items() if u.role in roles)}


@router.post("/auth/login")
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    u = db.scalar(select(User).where(User.username == form.username.strip()))
    if not u or not u.active or not check_pw(form.password, u.password_hash):
        raise HTTPException(401, "Username atau password salah")
    u.last_login = datetime.now(timezone.utc)
    audit(db, u.username, "login")
    db.commit()
    return {"access_token": make_token(u), "token_type": "bearer", "user": user_out(u)}


@router.get("/auth/me")
def me(user: User = Depends(current_user)):
    return user_out(user)


class UserIn(BaseModel):
    username: str
    full_name: str = ""
    role: str
    password: str | None = None
    active: bool = True


@router.get("/users")
def list_users(db: Session = Depends(get_db), _: User = Depends(require("users"))):
    return [user_out(u) for u in db.scalars(select(User).order_by(User.username))]


@router.get("/roles")
def roles(_: User = Depends(current_user)):
    return [{"id": k, "label": v} for k, v in ROLES.items()]


@router.post("/users")
def create_user(body: UserIn, db: Session = Depends(get_db), me: User = Depends(require("users"))):
    if body.role not in ROLES:
        raise HTTPException(400, "Peran tidak dikenal")
    if db.scalar(select(User).where(User.username == body.username)):
        raise HTTPException(400, "Username sudah dipakai")
    if not body.password or len(body.password) < 8:
        raise HTTPException(400, "Password minimal 8 karakter")
    u = User(username=body.username.strip(), full_name=body.full_name, role=body.role,
             password_hash=hash_pw(body.password), active=body.active)
    db.add(u)
    audit(db, me.username, "user_create", f"{u.username} ({u.role})")
    db.commit()
    return user_out(u)


@router.put("/users/{uid}")
def update_user(uid: int, body: UserIn, db: Session = Depends(get_db), me: User = Depends(require("users"))):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "User tidak ada")
    if body.role not in ROLES:
        raise HTTPException(400, "Peran tidak dikenal")
    u.full_name, u.role, u.active = body.full_name, body.role, body.active
    if body.password:
        if len(body.password) < 8:
            raise HTTPException(400, "Password minimal 8 karakter")
        u.password_hash = hash_pw(body.password)
    audit(db, me.username, "user_update", u.username)
    db.commit()
    return user_out(u)


class PwIn(BaseModel):
    old_password: str
    new_password: str


@router.post("/auth/password")
def change_password(body: PwIn, db: Session = Depends(get_db), me: User = Depends(current_user)):
    if not check_pw(body.old_password, me.password_hash):
        raise HTTPException(400, "Password lama salah")
    if len(body.new_password) < 8:
        raise HTTPException(400, "Password minimal 8 karakter")
    me.password_hash = hash_pw(body.new_password)
    audit(db, me.username, "password_change")
    db.commit()
    return {"ok": True}
