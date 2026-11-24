"""Интеграция со Stripe (тестовый режим): Checkout, подписки, Customer Portal, обработка вебхуков.

Источник истины о подписке — Stripe. Наша таблица `subscriptions` — зеркало: после каждого события
мы заново читаем подписку из Stripe и приводим к ней локальную запись (так устаревшие или пришедшие
не по порядку события ничего не ломают).
"""
import json
import logging
from datetime import datetime, timezone

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import billing
from app.config import settings
from app.models import AuditLog, Payment, Subscription, UserProfile

log = logging.getLogger(__name__)

SIGNATURE_TOLERANCE = 300  # секунд


def enabled() -> bool:
    return settings.payment_provider == "stripe"


def _init() -> None:
    if not settings.stripe_secret_key:
        raise RuntimeError("STRIPE_SECRET_KEY не задан")
    stripe.api_key = settings.stripe_secret_key


def plain(obj) -> dict:
    """Объект Stripe SDK -> обычный dict (не зависит от версии SDK)."""
    return json.loads(str(obj))


# ---------- каталог: тарифы -> Price в Stripe ----------

def lookup_key(plan: billing.Plan) -> str:
    # цена входит в ключ: сменили цену в коде — создастся новый Price, старые подписки не трогаем
    return f"{plan.code}:{plan.price}:{billing.CURRENCY}"


def plan_code_from_lookup(key: str | None) -> str | None:
    code = (key or "").split(":", 1)[0]
    return code if code in billing.PLANS else None


def ensure_price(plan: billing.Plan) -> str:
    _init()
    key = lookup_key(plan)
    found = stripe.Price.list(lookup_keys=[key], active=True, limit=1).data
    if found:
        return found[0].id
    price = stripe.Price.create(
        currency=billing.CURRENCY.lower(), unit_amount=plan.price, recurring={"interval": "month"},
        lookup_key=key, product_data={"name": f"1С Ассистент — {plan.name}"},
    )
    return price.id


def ensure_customer(profile: UserProfile, db: Session) -> str:
    _init()
    if profile.stripe_customer_id:
        return profile.stripe_customer_id
    customer = stripe.Customer.create(
        email=profile.email or None, name=profile.full_name or profile.username,
        metadata={"user_id": str(profile.id), "username": profile.username},
        idempotency_key=f"customer-user-{profile.id}",
    )
    profile.stripe_customer_id = customer.id
    db.flush()
    return customer.id


# ---------- действия пользователя ----------

def create_checkout(profile: UserProfile, plan: billing.Plan, payment_id: str, db: Session) -> str:
    customer = ensure_customer(profile, db)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer,
        client_reference_id=payment_id,
        line_items=[{"price": ensure_price(plan), "quantity": 1}],
        subscription_data={"metadata": {"payment_id": payment_id, "user_id": str(profile.id)}},
        success_url=f"{settings.public_url}/billing?payment={payment_id}",
        cancel_url=f"{settings.public_url}/billing?canceled=1",
        locale="ru",
        idempotency_key=f"checkout-{payment_id}",
    )
    return session.url


def set_cancel(subscription_id: str, value: bool) -> None:
    _init()
    stripe.Subscription.modify(subscription_id, cancel_at_period_end=value)


def portal_url(customer_id: str) -> str:
    """Customer Portal: смена карты, счета, отмена. Требует включённого портала в Dashboard (Settings → Billing → Customer portal)."""
    _init()
    return stripe.billing_portal.Session.create(customer=customer_id, return_url=f"{settings.public_url}/billing").url


# ---------- синхронизация ----------

def fetch_subscription(subscription_id: str) -> dict:
    _init()
    return plain(stripe.Subscription.retrieve(
        subscription_id, expand=["default_payment_method", "customer.invoice_settings.default_payment_method"],
    ))


def _card(sub: dict) -> tuple[str | None, str | None]:
    customer = sub.get("customer")
    candidates = [sub.get("default_payment_method")]
    if isinstance(customer, dict):
        candidates.append((customer.get("invoice_settings") or {}).get("default_payment_method"))
    for pm in candidates:
        if isinstance(pm, dict) and pm.get("card"):
            return pm["card"].get("brand"), pm["card"].get("last4")
    return None, None


def _customer_id(sub: dict) -> str:
    c = sub["customer"]
    return c["id"] if isinstance(c, dict) else c


def sync_subscription(db: Session, user: UserProfile, sub: dict) -> None:
    """Приводит локальную подписку к состоянию в Stripe."""
    row = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
    if sub["status"] in ("canceled", "incomplete_expired"):
        if row is not None and row.stripe_subscription_id in (None, sub["id"]):
            db.delete(row)
        return
    if sub["status"] == "incomplete":  # первая оплата ещё не прошла
        return
    item = sub["items"]["data"][0]
    code = plan_code_from_lookup((item.get("price") or {}).get("lookup_key"))
    if code is None:
        log.warning("Подписка %s: неизвестный тариф", sub["id"])
        return
    # в новых версиях API период лежит в позиции подписки, в старых — в самой подписке
    end = item.get("current_period_end") or sub.get("current_period_end")
    period_end = datetime.fromtimestamp(end, tz=timezone.utc)
    brand, last4 = _card(sub)
    if row is None:
        row = Subscription(user_id=user.id, plan_code=code, current_period_end=period_end)
        db.add(row)
    row.plan_code, row.current_period_end, row.stripe_subscription_id = code, period_end, sub["id"]
    row.cancel_at_period_end = bool(sub.get("cancel_at_period_end"))
    if last4:
        row.card_brand, row.card_last4 = brand, last4
    db.flush()


# ---------- вебхуки ----------

def verify_signature(body: bytes, header: str) -> bool:
    try:
        stripe.WebhookSignature.verify_header(body.decode(), header, settings.stripe_webhook_secret, SIGNATURE_TOLERANCE)
        return True
    except (stripe.SignatureVerificationError, ValueError):
        return False


def _invoice_subscription_id(inv: dict) -> str | None:
    sid = inv.get("subscription")  # старые версии API
    if not sid:  # новые: invoice.parent.subscription_details.subscription
        sid = (((inv.get("parent") or {}).get("subscription_details")) or {}).get("subscription")
    return sid.get("id") if isinstance(sid, dict) else sid


def _close_replaced(db: Session, user: UserProfile, old_id: str) -> None:
    """Пользователь оформил другой тариф на странице Stripe: прежнюю подписку закрываем, чтобы не было двойных списаний."""
    try:
        _init()
        stripe.Subscription.cancel(old_id)
        db.add(AuditLog(user_id=user.id, action="subscription_replaced", payload={"old": old_id}))
    except stripe.StripeError:
        log.exception("Не удалось закрыть прежнюю подписку %s", old_id)


def _handle_invoice(db: Session, kind: str, inv: dict) -> str:
    user = db.scalar(select(UserProfile).where(UserProfile.stripe_customer_id == inv.get("customer")))
    sub_id = _invoice_subscription_id(inv)
    if user is None or not sub_id:
        return "ignored"
    reason = inv.get("billing_reason")
    pay_kind = {"subscription_create": "checkout", "subscription_cycle": "renewal"}.get(reason, "change")
    sub = fetch_subscription(sub_id)
    code = plan_code_from_lookup(((sub["items"]["data"][0]).get("price") or {}).get("lookup_key")) or "pro"
    brand, last4 = _card(sub)
    now = datetime.now(timezone.utc)

    if kind == "invoice.paid":
        if inv.get("amount_paid", 0) > 0 and db.scalar(select(Payment.id).where(Payment.external_id == inv["id"])) is None:
            pending = db.get(Payment, (sub.get("metadata") or {}).get("payment_id") or "") if reason == "subscription_create" else None
            if pending is None or pending.status != "pending" or pending.user_id != user.id:
                pending = Payment(id=billing.new_payment_id(), user_id=user.id, kind=pay_kind)
                db.add(pending)
            pending.plan_code, pending.amount, pending.currency = code, inv["amount_paid"], inv["currency"].upper()
            pending.status, pending.psp_status, pending.paid_at = "succeeded", "succeeded", now
            pending.card_brand, pending.card_last4, pending.external_id = brand, last4, inv["id"]
            db.add(AuditLog(user_id=user.id, action="payment_succeeded", payload={"invoice": inv["id"], "plan": code, "kind": pay_kind}))
        row = db.scalar(select(Subscription).where(Subscription.user_id == user.id))
        old_id = row.stripe_subscription_id if row is not None else None
        sync_subscription(db, user, sub)
        if reason == "subscription_create" and old_id and old_id != sub_id:
            _close_replaced(db, user, old_id)
        return "paid"

    # invoice.payment_failed. Первую оплату пользователь повторяет в самом Checkout, там запись не нужна.
    if reason != "subscription_create":
        attempt = inv.get("attempt_count", 1)
        ext = f"{inv['id']}:failed:{attempt}"
        if db.scalar(select(Payment.id).where(Payment.external_id == ext)) is None:
            db.add(Payment(
                id=billing.new_payment_id(), user_id=user.id, plan_code=code, kind=pay_kind, amount=inv.get("amount_due", 0),
                currency=(inv.get("currency") or billing.CURRENCY).upper(), status="failed", psp_status="failed",
                card_brand=brand, card_last4=last4, failure_reason="Банк отклонил списание", external_id=ext,
            ))
            db.add(AuditLog(user_id=user.id, action="payment_failed", payload={"invoice": inv["id"], "plan": code, "kind": pay_kind}))
    return "failed"


def handle_event(db: Session, event: dict) -> str:
    kind, obj = event["type"], event["data"]["object"]
    if kind in ("invoice.paid", "invoice.payment_failed"):
        return _handle_invoice(db, kind, obj)
    if kind in ("customer.subscription.updated", "customer.subscription.deleted"):
        user = db.scalar(select(UserProfile).where(UserProfile.stripe_customer_id == obj.get("customer")))
        if user is None:
            return "ignored"
        sync_subscription(db, user, fetch_subscription(obj["id"]))
        db.add(AuditLog(user_id=user.id, action="subscription_synced", payload={"event": kind, "status": obj.get("status")}))
        return "synced"
    return "ignored"
