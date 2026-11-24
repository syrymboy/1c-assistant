from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _created() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class UserProfile(Base):
    __tablename__ = "user_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    keycloak_sub: Mapped[str] = mapped_column(String(64), unique=True)
    username: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(255))
    stripe_customer_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = _created()


class Infobase(Base):
    __tablename__ = "infobases"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    odata_url: Mapped[str] = mapped_column(String(1024))
    login: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = _created()


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"))
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = _created()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("chat_sessions.id"))
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(Text)
    generated_query: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = _created()


class AuditLog(Base):
    __tablename__ = "audit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("user_profiles.id"))
    action: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = _created()


class DataSource(Base):
    """Каталог объектов 1С, доступных ассистенту. allowed_roles — роли Keycloak, которым объект разрешён."""

    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(128), unique=True)  # имя объекта в OData, напр. Document_РеализацияТоваровУслуг
    section: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    fields: Mapped[list] = mapped_column(JSONB)
    allowed_roles: Mapped[list] = mapped_column(JSONB)
    sort: Mapped[int] = mapped_column(server_default="0")


class UserSource(Base):
    """Источники, которые пользователь включил для себя."""

    __tablename__ = "user_sources"
    __table_args__ = (UniqueConstraint("user_id", "source_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))


class Subscription(Base):
    """Платный тариф пользователя. Бесплатный тариф записи не требует."""

    __tablename__ = "subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"), unique=True)
    plan_code: Mapped[str] = mapped_column(String(32))
    current_period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, server_default="false")
    card_brand: Mapped[str | None] = mapped_column(String(16))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # пусто у подписки симулятора
    created_at: Mapped[datetime] = _created()


class Payment(Base):
    """Платёж (счёт). status — состояние для приложения, меняется только вебхуком провайдера.
    psp_* — состояние на стороне провайдера (в боевой интеграции лежит у него, а не у нас)."""

    __tablename__ = "payments"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("user_profiles.id"))
    plan_code: Mapped[str] = mapped_column(String(32))
    kind: Mapped[str] = mapped_column(String(16))  # checkout | renewal
    amount: Mapped[int] = mapped_column(Integer)  # в тиынах
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16))  # pending | succeeded | failed
    psp_status: Mapped[str] = mapped_column(String(24), server_default="open")  # open | requires_action | succeeded | failed
    psp_outcome: Mapped[str | None] = mapped_column(String(24))  # что произойдёт после 3-D Secure
    card_brand: Mapped[str | None] = mapped_column(String(16))
    card_last4: Mapped[str | None] = mapped_column(String(4))
    failure_reason: Mapped[str | None] = mapped_column(String(255))
    external_id: Mapped[str | None] = mapped_column(String(64), unique=True)  # id счёта у провайдера — для идемпотентности вебхука
    created_at: Mapped[datetime] = _created()
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
