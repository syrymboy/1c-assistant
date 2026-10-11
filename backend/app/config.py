from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    oidc_issuer: str
    oidc_jwks_url: str
    cors_origins: str = "http://localhost:3000"


settings = Settings()
