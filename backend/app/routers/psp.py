"""Симулятор платёжного провайдера (аналог Stripe в тестовом режиме).

Живёт отдельно от логики приложения: приложение знает только id платежа и принимает результат по подписанному вебхуку.
Номера карт здесь проверяются и сразу забываются — сохраняются только бренд и последние 4 цифры.
В боевой версии этот модуль заменяется настоящим провайдером (страница оплаты на его стороне)."""
import json
import time
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app import billing
from app.config import settings
from app.db import get_db
from app.models import Payment
from app.routers.billing import sign

router = APIRouter(prefix="/api/psp")

CHECKOUT_TTL = timedelta(minutes=30)

# Тестовые карты: номер -> (результат, текст отказа)
TEST_CARDS = {
    "4242424242424242": ("succeeded", None),
    "5555555555554444": ("succeeded", None),
    "4000000000000002": ("failed", "Карта отклонена банком-эмитентом"),
    "4000000000009995": ("failed", "Недостаточно средств на карте"),
    "4000002760003184": ("3ds", None),  # требуется подтверждение в банке
}


class CardIn(BaseModel):
    number: str
    exp: str  # MM/YY
    cvc: str
    name: str = ""


class AuthIn(BaseModel):
    approve: bool


def _brand(number: str) -> str:
    return "mastercard" if number[:1] == "5" else "visa"


def _luhn(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2:
            d = d * 2 - 9 if d * 2 > 9 else d * 2
        total += d
    return total % 10 == 0


def _load_open(payment_id: str, db: Session) -> Payment:
    p = db.get(Payment, payment_id)
    if p is None:
        raise HTTPException(404, "Платёжная сессия не найдена")
    if p.psp_status == "open" and datetime.now(timezone.utc) - p.created_at > CHECKOUT_TTL:
        raise HTTPException(410, "Срок платёжной сессии истёк, начните оплату заново")
    return p


def _send_webhook(event_type: str, payment_id: str, card_brand: str | None, card_last4: str | None, reason: str | None) -> None:
    body = json.dumps({
        "id": f"evt_{payment_id}_{event_type}", "type": event_type,
        "data": {"payment_id": payment_id, "card_brand": card_brand, "card_last4": card_last4, "reason": reason},
    }).encode()
    ts = int(time.time())
    headers = {"Content-Type": "application/json", "X-Signature": f"t={ts},v1={sign(settings.payment_webhook_secret, ts, body)}"}
    for attempt in range(3):  # провайдеры повторяют доставку при ошибках
        try:
            r = httpx.post(f"{settings.internal_url}/api/webhooks/payments", content=body, headers=headers, timeout=10)
            if r.status_code < 500:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1 + attempt)


def _finish(p: Payment, ok: bool, reason: str | None, tasks: BackgroundTasks, db: Session) -> dict:
    p.psp_status = "succeeded" if ok else "failed"
    db.commit()
    tasks.add_task(_send_webhook, "payment.succeeded" if ok else "payment.failed", p.id, p.card_brand, p.card_last4, reason)
    return {"status": p.psp_status, "message": None if ok else reason, "return_url": f"/billing?payment={p.id}"}


@router.get("/checkout/{payment_id}")
def checkout_info(payment_id: str, db: Session = Depends(get_db)):
    p = _load_open(payment_id, db)
    plan = billing.PLANS[p.plan_code]
    return {
        "id": p.id, "status": p.psp_status, "plan_code": p.plan_code, "amount": p.amount, "currency": p.currency,
        "description": f"Тариф «{plan.name}», 30 дней", "merchant": "Ассистент 1С",
        "card": {"brand": p.card_brand, "last4": p.card_last4} if p.card_last4 else None,
        "return_url": f"/billing?payment={p.id}",
    }


@router.post("/checkout/{payment_id}/pay")
def pay(payment_id: str, card: CardIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    p = _load_open(payment_id, db)
    if p.psp_status != "open":
        raise HTTPException(409, "Платёж уже обработан")
    number = "".join(ch for ch in card.number if ch.isdigit())
    if not (13 <= len(number) <= 19) or not _luhn(number):
        raise HTTPException(422, "Неверный номер карты")
    try:
        month, year = (int(x) for x in card.exp.replace(" ", "").split("/"))
        year += 2000 if year < 100 else 0
        now = datetime.now(timezone.utc)
        if not (1 <= month <= 12) or (year, month) < (now.year, now.month):
            raise ValueError
    except ValueError:
        raise HTTPException(422, "Неверный или истёкший срок действия")
    if not (card.cvc.isdigit() and len(card.cvc) in (3, 4)):
        raise HTTPException(422, "Неверный код CVC")
    if number not in TEST_CARDS:
        raise HTTPException(422, "Это тестовый режим: принимаются только тестовые карты. Реальные данные карты вводить не нужно.")

    outcome, reason = TEST_CARDS[number]
    p.card_brand, p.card_last4 = _brand(number), number[-4:]
    if outcome == "3ds":
        p.psp_status, p.psp_outcome = "requires_action", "succeeded"
        db.commit()
        return {"status": "requires_action", "message": "Подтвердите платёж в приложении банка"}
    return _finish(p, outcome == "succeeded", reason, tasks, db)


@router.post("/checkout/{payment_id}/authenticate")
def authenticate(payment_id: str, body: AuthIn, tasks: BackgroundTasks, db: Session = Depends(get_db)):
    p = _load_open(payment_id, db)
    if p.psp_status != "requires_action":
        raise HTTPException(409, "Подтверждение не требуется")
    return _finish(p, body.approve, None if body.approve else "Платёж не подтверждён в банке", tasks, db)
