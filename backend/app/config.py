from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    oidc_issuer: str
    oidc_jwks_url: str
    cors_origins: str = "http://localhost:3000"
    llm_provider: str = "mock"  # mock | anthropic
    llm_model: str = "claude-sonnet-5-5"
    anthropic_api_key: str = ""
    payment_webhook_secret: str = "dev-webhook-secret"  # общий секрет приложения и платёжного провайдера
    internal_url: str = "http://localhost:8000"  # куда провайдер шлёт вебхуки


settings = Settings()
