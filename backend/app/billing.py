"""Тарифы, лимиты и состояние подписки пользователя."""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, ChatSession, Message, Payment, Subscription, UserProfile

PERIOD = timedelta(days=30)


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    price: int  # в тиынах, 0 — бесплатный
    questions: int  # вопросов за период
    features: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "free": Plan("free", "Старт", 0, 10, ("10 вопросов в месяц", "Все доступные вам источники", "История диалогов")),
    "pro": Plan("pro", "Профессионал", 990_000, 300, ("300 вопросов в месяц", "Все доступные вам источники", "История диалогов", "Приоритетная поддержка")),
    "business": Plan("business", "Бизнес", 2_990_000, 2000, ("2 000 вопросов в месяц", "Все доступные вам источники", "История диалогов", "Приоритетная поддержка", "Выгрузка в Excel (скоро)")),
}
CURRENCY = "KZT"


def new_payment_id() -> str:
    return "pay_" + uuid.uuid4().hex[:24]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _renew_if_due(profile: UserProfile, sub: Subscription, db: Session) -> None:
    """Автопродление: по окончании периода списываем с сохранённой карты (в симуляторе — всегда успешно)."""
    if sub.stripe_subscription_id:  # продлением и списаниями управляет Stripe
        return
    now = _now()
    while sub.current_period_end <= now and not sub.cancel_at_period_end:
        plan = PLANS[sub.plan_code]
        paid_at = sub.current_period_end
        db.add(Payment(
            id=new_payment_id(), user_id=profile.id, plan_code=plan.code, kind="renewal", amount=plan.price,
            currency=CURRENCY, status="succeeded", psp_status="succeeded",
            card_brand=sub.card_brand, card_last4=sub.card_last4, paid_at=paid_at,
        ))
        db.add(AuditLog(user_id=profile.id, action="payment_succeeded", payload={"plan": plan.code, "kind": "renewal"}))
        sub.current_period_end = paid_at + PERIOD
    db.flush()


def state(profile: UserProfile, db: Session) -> dict:
    """Действующий тариф, период и расход лимита."""
    now = _now()
    sub = db.scalar(select(Subscription).where(Subscription.user_id == profile.id))
    if sub is not None:
        _renew_if_due(profile, sub, db)
    if sub is not None and sub.current_period_end > now:
        plan = PLANS[sub.plan_code]
        end = sub.current_period_end
        start = end - PERIOD
    else:
        plan = PLANS["free"]
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=32)).replace(day=1)
        sub = None
    used = db.scalar(
        select(func.count()).select_from(Message).join(ChatSession, ChatSession.id == Message.session_id)
        .where(ChatSession.user_id == profile.id, Message.role == "user", Message.created_at >= start)
    ) or 0
    return {"plan": plan, "sub": sub, "period_start": start, "period_end": end, "used": used, "limit": plan.questions}
