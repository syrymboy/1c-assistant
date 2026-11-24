from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    oidc_issuer: str
    oidc_jwks_url: str
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "mock"  # mock | anthropic | gemini
    llm_model: str = "claude-sonnet-5-5"
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    gemini_model: str = "gemini-4-hydrogen"
    payment_webhook_secret: str = "dev-webhook-secret"  # общий секрет приложения и платёжного провайдера
    payment_provider: str = "simulator"  # simulator | stripe
    stripe_secret_key: str = ""  # sk_test_...
    stripe_webhook_secret: str = ""  # whsec_... (из Stripe Dashboard или `stripe listen`)
    public_url: str = "http://localhost:3000"  # куда Stripe возвращает пользователя после оплаты
    internal_url: str = "http://localhost:8000"  # куда провайдер шлёт вебхуки


settings = Settings()
