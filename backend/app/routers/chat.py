import json
from typing import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.auth import CurrentUser, get_current_user
from app.db import SessionLocal, get_db
from app import billing
from app.llm import LLMError, get_provider
from app.tools import Toolbox
from app.models import AuditLog, ChatSession, DataSource, Message, UserProfile, UserSource

router = APIRouter(prefix="/api/chats")

HISTORY_LIMIT = 20  # сколько последних сообщений уходит в модель


class TitleIn(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class MessageIn(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _profile(user: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)) -> UserProfile:
    profile = db.scalar(select(UserProfile).where(UserProfile.keycloak_sub == user.sub))
    if profile is None:
        profile = UserProfile(keycloak_sub=user.sub, username=user.username, email=user.email, full_name=user.name)
        db.add(profile)
        db.commit()
    return profile


def _own_chat(chat_id: int, profile: UserProfile, db: Session) -> ChatSession:
    chat = db.get(ChatSession, chat_id)
    if chat is None or chat.user_id != profile.id:
        raise HTTPException(404, "Диалог не найден")
    return chat


def _chat_out(c: ChatSession) -> dict:
    return {"id": c.id, "title": c.title or "Новый диалог", "created_at": c.created_at}


def _msg_out(m: Message) -> dict:
    try:
        trace = json.loads(m.generated_query) if m.generated_query else None
    except ValueError:
        trace = None
    return {"id": m.id, "role": m.role, "content": m.content, "trace": trace, "created_at": m.created_at}


@router.get("")
def list_chats(profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(ChatSession).where(ChatSession.user_id == profile.id).order_by(ChatSession.id.desc())
    ).all()
    return [_chat_out(c) for c in rows]


@router.post("", status_code=201)
def create_chat(profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    chat = ChatSession(user_id=profile.id)
    db.add(chat)
    db.commit()
    return _chat_out(chat)


@router.get("/{chat_id}")
def get_chat(chat_id: int, profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    chat = _own_chat(chat_id, profile, db)
    msgs = db.scalars(select(Message).where(Message.session_id == chat.id).order_by(Message.id)).all()
    return {**_chat_out(chat), "messages": [_msg_out(m) for m in msgs]}


@router.patch("/{chat_id}")
def rename_chat(chat_id: int, body: TitleIn, profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    chat = _own_chat(chat_id, profile, db)
    chat.title = body.title.strip()
    db.commit()
    return _chat_out(chat)


@router.delete("/{chat_id}", status_code=204)
def delete_chat(chat_id: int, profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    chat = _own_chat(chat_id, profile, db)
    db.execute(delete(Message).where(Message.session_id == chat.id))
    db.delete(chat)
    db.commit()


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.post("/{chat_id}/messages")
def send_message(
    chat_id: int,
    body: MessageIn,
    user: CurrentUser = Depends(get_current_user),
    profile: UserProfile = Depends(_profile),
    db: Session = Depends(get_db),
):
    """Сохраняет вопрос и стримит ответ ассистента как Server-Sent Events."""
    chat = _own_chat(chat_id, profile, db)
    st = billing.state(profile, db)
    if st["used"] >= st["limit"]:
        db.commit()
        raise HTTPException(402, f"Лимит тарифа «{st['plan'].name}» исчерпан: {st['limit']} вопросов за период. Перейдите на другой тариф.")
    provider = get_provider()
    # выбранные пользователем источники, которые ещё разрешены его ролям
    chosen = db.scalars(
        select(DataSource).join(UserSource, UserSource.source_id == DataSource.id)
        .where(UserSource.user_id == profile.id).order_by(DataSource.sort)
    ).all()
    allowed = [s for s in chosen if set(s.allowed_roles) & set(user.roles)]
    source_titles = [s.title for s in allowed]
    toolbox = Toolbox(allowed)
    text = body.content.strip()

    db.add(Message(session_id=chat.id, role="user", content=text))
    if not chat.title:
        chat.title = text[:60]
    db.add(AuditLog(user_id=profile.id, action="question", payload={"chat_id": chat.id, "provider": provider.name, "length": len(text), "sources": source_titles}))
    db.commit()

    recent = db.scalars(
        select(Message).where(Message.session_id == chat.id).order_by(Message.id.desc()).limit(HISTORY_LIMIT)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(recent)]
    chat_pk, user_pk = chat.id, profile.id

    def events() -> Iterator[str]:
        parts: list[str] = []

        def save() -> int | None:
            """Сохраняет ответ (в том числе частичный, если пользователь нажал «Стоп») вместе с трассой запросов к 1С."""
            text = "".join(parts).strip()
            if not text:
                return None
            with SessionLocal() as s:
                m = Message(session_id=chat_pk, role="assistant", content=text,
                            generated_query=json.dumps(toolbox.trace, ensure_ascii=False, default=str) if toolbox.trace else None)
                s.add(m)
                s.commit()
                return m.id

        try:
            for chunk in provider.stream(history, source_titles, toolbox):
                if isinstance(chunk, dict):  # служебные события: «запрашиваю 1С» и результат запроса
                    yield _sse(chunk)
                    continue
                parts.append(chunk)
                yield _sse({"delta": chunk})
        except GeneratorExit:  # клиент оборвал соединение
            save()
            raise
        except Exception as e:  # ошибка провайдера не должна рвать соединение молча
            save()
            yield _sse({"error": str(e) if isinstance(e, LLMError) else f"Не удалось получить ответ: {type(e).__name__}"})
            with SessionLocal() as s:
                s.add(AuditLog(user_id=user_pk, action="llm_error", payload={"chat_id": chat_pk, "error": str(e)[:500]}))
                s.commit()
            return
        if toolbox.trace:
            with SessionLocal() as s:
                s.add(AuditLog(user_id=user_pk, action="onec_query", payload={"chat_id": chat_pk, "requests": [t.get("request") for t in toolbox.trace]}))
                s.commit()
        yield _sse({"done": True, "message_id": save()})

    return StreamingResponse(events(), media_type="text/event-stream", headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})
