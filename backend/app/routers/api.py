from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user, require_role
from app.db import get_db
from app.models import AuditLog, UserProfile

router = APIRouter(prefix="/api")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(UserProfile).where(UserProfile.keycloak_sub == user.sub))
    if profile is None:
        profile = UserProfile(keycloak_sub=user.sub, username=user.username)
        db.add(profile)
    profile.username = user.username
    profile.email = user.email
    profile.full_name = user.name
    db.flush()

    # Один вход = одна сессия Keycloak (sid): пишем в аудит только первое обращение сессии
    session_key = user.sid or "no-sid"
    seen = db.scalar(
        select(AuditLog.id).where(
            AuditLog.user_id == profile.id,
            AuditLog.action == "login",
            AuditLog.payload["sid"].astext == session_key,
        )
    )
    if seen is None:
        profile.last_login_at = datetime.now(timezone.utc)
        db.add(AuditLog(user_id=profile.id, action="login", payload={"sid": session_key, "roles": user.roles}))
    db.commit()
    return {
        "id": profile.id,
        "username": profile.username,
        "email": profile.email,
        "full_name": profile.full_name,
        "roles": user.roles,
        "last_login_at": profile.last_login_at,
    }


@router.get("/admin/ping")
def admin_ping(user: CurrentUser = Depends(require_role("admin"))):
    return {"pong": True, "user": user.username}
