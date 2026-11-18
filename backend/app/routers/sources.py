from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import get_db
from app.models import DataSource, UserProfile, UserSource
from app.routers.chat import _profile

router = APIRouter(prefix="/api/sources")


class Toggle(BaseModel):
    enabled: bool


def allowed_sources(user: CurrentUser, db: Session) -> list[DataSource]:
    """Объекты, разрешённые ролям пользователя (верхний слой доступа)."""
    rows = db.scalars(select(DataSource).order_by(DataSource.sort)).all()
    return [s for s in rows if set(s.allowed_roles) & set(user.roles)]


def enabled_ids(profile: UserProfile, db: Session) -> set[int]:
    return set(db.scalars(select(UserSource.source_id).where(UserSource.user_id == profile.id)).all())


@router.get("")
def list_sources(
    user: CurrentUser = Depends(get_current_user),
    profile: UserProfile = Depends(_profile),
    db: Session = Depends(get_db),
):
    on = enabled_ids(profile, db)
    return [
        {"id": s.id, "section": s.section, "kind": s.kind, "title": s.title,
         "description": s.description, "fields": s.fields, "enabled": s.id in on}
        for s in allowed_sources(user, db)
    ]


@router.put("/{source_id}")
def toggle_source(
    source_id: int,
    body: Toggle,
    user: CurrentUser = Depends(get_current_user),
    profile: UserProfile = Depends(_profile),
    db: Session = Depends(get_db),
):
    if source_id not in {s.id for s in allowed_sources(user, db)}:
        raise HTTPException(403, "Источник недоступен для вашей роли")
    db.execute(delete(UserSource).where(UserSource.user_id == profile.id, UserSource.source_id == source_id))
    if body.enabled:
        db.add(UserSource(user_id=profile.id, source_id=source_id))
    db.commit()
    return {"id": source_id, "enabled": body.enabled}
