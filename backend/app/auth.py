from dataclasses import dataclass

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

bearer = HTTPBearer(auto_error=False)
jwks_client = jwt.PyJWKClient(settings.oidc_jwks_url, cache_keys=True)


@dataclass
class CurrentUser:
    sub: str
    username: str
    email: str | None
    name: str | None
    roles: list[str]
    sid: str | None


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> CurrentUser:
    if creds is None:
        raise HTTPException(401, "Требуется авторизация", headers={"WWW-Authenticate": "Bearer"})
    try:
        key = jwks_client.get_signing_key_from_jwt(creds.credentials).key
        claims = jwt.decode(
            creds.credentials,
            key,
            algorithms=["RS256"],
            issuer=settings.oidc_issuer,
            options={"verify_aud": False, "require": ["exp", "iss", "sub"]},
        )
    except jwt.PyJWTError as e:
        raise HTTPException(401, f"Недействительный токен: {e}", headers={"WWW-Authenticate": "Bearer"})
    return CurrentUser(
        sub=claims["sub"],
        username=claims.get("preferred_username", claims["sub"]),
        email=claims.get("email"),
        name=claims.get("name"),
        roles=claims.get("realm_access", {}).get("roles", []),
        sid=claims.get("sid"),
    )


def require_role(role: str):
    def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if role not in user.roles:
            raise HTTPException(403, "Недостаточно прав")
        return user

    return checker
