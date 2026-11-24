import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

import stripe

from app import billing, stripe_billing
from app.config import settings
from app.db import get_db
from app.models import AuditLog, Payment, Subscription, UserProfile
from app.routers.chat import _profile

router = APIRouter(prefix="/api")

SIGNATURE_TOLERANCE = 300  # секунд


class CheckoutIn(BaseModel):
    plan_code: str


def _payment_out(p: Payment) -> dict:
    return {
        "id": p.id, "plan": billing.PLANS[p.plan_code].name, "kind": p.kind, "amount": p.amount, "currency": p.currency,
        "status": p.status, "card_brand": p.card_brand, "card_last4": p.card_last4,
        "failure_reason": p.failure_reason, "created_at": p.created_at,
    }


def _plan_out(p: billing.Plan) -> dict:
    return {"code": p.code, "name": p.name, "price": p.price, "currency": billing.CURRENCY, "questions": p.questions, "features": list(p.features)}


@router.get("/billing")
def get_billing(profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    st = billing.state(profile, db)
    db.commit()  # автопродление могло добавить платежи
    sub = st["sub"]
    payments = db.scalars(
        select(Payment).where(Payment.user_id == profile.id, Payment.status != "pending")
        .order_by(Payment.created_at.desc()).limit(50)
    ).all()
    return {
        "plan": _plan_out(st["plan"]),
        "period_end": st["period_end"],
        "used": st["used"], "limit": st["limit"],
        "provider": settings.payment_provider,
        "portal": bool(stripe_billing.enabled() and sub is not None and sub.stripe_subscription_id and profile.stripe_customer_id),
        "paid": sub is not None,
        "cancel_at_period_end": bool(sub and sub.cancel_at_period_end),
        "card": {"brand": sub.card_brand, "last4": sub.card_last4} if sub and sub.card_last4 else None,
        "plans": [_plan_out(p) for p in billing.PLANS.values()],
        "payments": [_payment_out(p) for p in payments],
    }


@router.post("/billing/checkout", status_code=201)
def create_checkout(body: CheckoutIn, profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    plan = billing.PLANS.get(body.plan_code)
    if plan is None or plan.price == 0:
        raise HTTPException(400, "Неизвестный тариф")
    st = billing.state(profile, db)
    if st["sub"] is not None and st["plan"].code == plan.code and not st["sub"].cancel_at_period_end:
        raise HTTPException(409, "Этот тариф уже подключён")
    sub = st["sub"]
    if stripe_billing.enabled() and sub is not None and sub.stripe_subscription_id and sub.plan_code == plan.code:
        return _stripe_resume(profile, sub, db)  # тот же тариф с отменой в конце периода — просто возобновляем
    # Другой тариф всегда оформляется на странице Stripe; прежнюю подписку Stripe-вебхук закроет после успешной оплаты
    p = Payment(id=billing.new_payment_id(), user_id=profile.id, plan_code=plan.code, kind="checkout",
                amount=plan.price, currency=billing.CURRENCY, status="pending", psp_status="open")
    db.add(p)
    db.add(AuditLog(user_id=profile.id, action="checkout_created", payload={"payment_id": p.id, "plan": plan.code}))
    if stripe_billing.enabled():
        try:
            url = stripe_billing.create_checkout(profile, plan, p.id, db)
        except stripe.StripeError as e:
            db.rollback()
            raise HTTPException(502, f"Stripe: {e.user_message or 'не удалось создать оплату'}")
        db.commit()
        return {"payment_id": p.id, "checkout_url": url}
    db.commit()
    return {"payment_id": p.id, "checkout_url": f"/pay/{p.id}"}


def _stripe_resume(profile: UserProfile, sub: Subscription, db: Session) -> dict:
    try:
        stripe_billing.set_cancel(sub.stripe_subscription_id, False)
        stripe_billing.sync_subscription(db, profile, stripe_billing.fetch_subscription(sub.stripe_subscription_id))
    except stripe.StripeError as e:
        db.rollback()
        raise HTTPException(502, f"Stripe: {e.user_message or 'не удалось возобновить подписку'}")
    db.add(AuditLog(user_id=profile.id, action="subscription_resume", payload={"plan": sub.plan_code}))
    db.commit()
    return {"payment_id": None, "checkout_url": None, "changed": True}


@router.get("/billing/payments/{payment_id}")
def payment_status(payment_id: str, profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    p = db.get(Payment, payment_id)
    if p is None or p.user_id != profile.id:
        raise HTTPException(404, "Платёж не найден")
    return _payment_out(p)


@router.post("/billing/cancel")
def cancel(profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    return _set_cancel(profile, db, True)


@router.post("/billing/resume")
def resume(profile: UserProfile = Depends(_profile), db: Session = Depends(get_db)):
    return _set_cancel(profile, db, False)


def _set_cancel(profile: UserProfile, db: Session, value: bool) -> dict:
    st = billing.state(profile, db)
    sub = st["sub"]
    if sub is None:
        raise HTTPException(409, "Нет платного тарифа")
    if stripe_billing.enabled() and sub.stripe_subscription_id:
        try:
            stripe_billing.set_cancel(sub.stripe_subscription_id, value)
        except stripe.StripeError as e:
            raise HTTPException(502, f"Stripe: {e.user_message or 'не удалось изменить подписку'}")
    sub.cancel_at_period_end = value
    db.add(AuditLog(user_id=profile.id, action="subscription_cancel" if value else "subscription_resume", payload={"plan": sub.plan_code}))
    db.commit()
    return {"cancel_at_period_end": value, "period_end": sub.current_period_end}


@router.post("/billing/portal")
def portal(profile: UserProfile = Depends(_profile)):
    if not stripe_billing.enabled() or not profile.stripe_customer_id:
        raise HTTPException(409, "Портал оплаты недоступен")
    try:
        return {"url": stripe_billing.portal_url(profile.stripe_customer_id)}
    except stripe.StripeError as e:
        raise HTTPException(502, f"Stripe: {e.user_message or 'не удалось открыть портал'}")


# ---------- вебхуки платёжных провайдеров ----------

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, stripe_signature: str = Header(default="", alias="Stripe-Signature"),
                         db: Session = Depends(get_db)):
    """Stripe подписывает тело запроса (`Stripe-Signature: t=…,v1=…`); без верной подписи событие не принимается."""
    if not stripe_billing.enabled() or not settings.stripe_webhook_secret:
        raise HTTPException(404, "Stripe не включён")
    body = await request.body()
    if not stripe_billing.verify_signature(body, stripe_signature):
        raise HTTPException(400, "Неверная подпись")
    result = stripe_billing.handle_event(db, json.loads(body))
    db.commit()
    return {"ok": True, "result": result}


# ---------- вебхук симулятора ----------

def sign(secret: str, timestamp: int, body: bytes) -> str:
    return hmac.new(secret.encode(), f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()


@router.post("/webhooks/payments")
async def payments_webhook(request: Request, x_signature: str = Header(default=""), db: Session = Depends(get_db)):
    """Единственное место, где платёж меняет состояние для приложения. Подпись HMAC-SHA256: `t=<unix>,v1=<hex>`."""
    body = await request.body()
    try:
        parts = dict(kv.split("=", 1) for kv in x_signature.split(","))
        ts = int(parts["t"])
        given = parts["v1"]
    except (KeyError, ValueError):
        raise HTTPException(400, "Неверная подпись")
    if abs(time.time() - ts) > SIGNATURE_TOLERANCE:
        raise HTTPException(400, "Подпись устарела")
    if not hmac.compare_digest(sign(settings.payment_webhook_secret, ts, body), given):
        raise HTTPException(400, "Неверная подпись")

    event = json.loads(body)
    data = event["data"]
    p = db.get(Payment, data["payment_id"])
    if p is None:
        raise HTTPException(404, "Платёж не найден")
    if p.status != "pending":  # повторная доставка — игнорируем (идемпотентность)
        return {"ok": True, "duplicate": True}

    now = datetime.now(timezone.utc)
    p.card_brand, p.card_last4 = data.get("card_brand"), data.get("card_last4")
    if event["type"] == "payment.succeeded":
        p.status, p.paid_at = "succeeded", now
        sub = db.scalar(select(Subscription).where(Subscription.user_id == p.user_id))
        if sub is None:
            sub = Subscription(user_id=p.user_id, plan_code=p.plan_code, current_period_end=now + billing.PERIOD)
            db.add(sub)
        else:
            sub.plan_code = p.plan_code
            sub.current_period_end = now + billing.PERIOD
        sub.cancel_at_period_end = False
        sub.card_brand, sub.card_last4 = p.card_brand, p.card_last4
        db.add(AuditLog(user_id=p.user_id, action="payment_succeeded", payload={"payment_id": p.id, "plan": p.plan_code}))
    elif event["type"] == "payment.failed":
        p.status, p.failure_reason = "failed", data.get("reason")
        db.add(AuditLog(user_id=p.user_id, action="payment_failed", payload={"payment_id": p.id, "reason": data.get("reason")}))
    else:
        raise HTTPException(400, "Неизвестный тип события")
    db.commit()
    return {"ok": True}
