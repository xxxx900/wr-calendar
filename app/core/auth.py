from __future__ import annotations

import json
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.modules.chat.service import AuthenticatedUser

bearer = HTTPBearer(auto_error=False)
_jwks_cache: dict[str, Any] = {}


async def _decode_token(token: str, settings: Any) -> dict[str, Any]:
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    if algorithm == "HS256":
        return jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"], audience="authenticated")
    if algorithm not in {"ES256", "RS256"}:
        raise jwt.InvalidAlgorithmError("Unsupported token algorithm")

    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
    if jwks_url not in _jwks_cache:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(jwks_url)
            response.raise_for_status()
            _jwks_cache[jwks_url] = response.json().get("keys", [])
    key_data = next((key for key in _jwks_cache[jwks_url] if key.get("kid") == header.get("kid")), None)
    if key_data is None:
        raise jwt.InvalidKeyError("Signing key not found")
    algorithm_impl = jwt.algorithms.get_default_algorithms().get(algorithm)
    if algorithm_impl is None:
        raise jwt.InvalidAlgorithmError(
            f"Token algorithm {algorithm!r} is not available; install PyJWT with its crypto extra."
        )
    signing_key = algorithm_impl.from_jwk(json.dumps(key_data))
    return jwt.decode(token, signing_key, algorithms=[algorithm], audience="authenticated")


async def get_current_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthenticatedUser:
    settings = get_settings()
    if settings.local_development and credentials is None:
        return AuthenticatedUser(id="00000000-0000-0000-0000-000000000001", role="admin")

    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    try:
        claims = await _decode_token(credentials.credentials, settings)
    except (httpx.HTTPError, jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token.") from exc

    user_id = claims.get("sub")
    app_metadata = claims.get("app_metadata") or {}
    role = app_metadata.get("role", claims.get("role", "user"))
    email = claims.get("email", "")
    admin_emails = {value.strip().lower() for value in settings.admin_emails.split(",") if value.strip()}
    if isinstance(email, str) and email.lower() in admin_emails:
        role = "admin"

    # Also check if email is listed as admin in public.users table
    if role not in {"admin", "calendar_admin", "event_admin"} and email and request is not None:
        pools = getattr(request.app.state, "pools", None)
        if pools is not None and (pools.admin or pools.readonly):
            pool = pools.admin or pools.readonly
            try:
                async with pool.acquire() as connection:
                    db_role = await connection.fetchval(
                        "SELECT role::text FROM users WHERE LOWER(email) = LOWER($1)",
                        email.strip().lower(),
                    )
                    if db_role in {"admin", "calendar_admin", "event_admin"}:
                        role = db_role
            except Exception:
                pass

    if not isinstance(user_id, str) or not isinstance(role, str):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid identity claims.")
    return AuthenticatedUser(id=user_id, role=role)


async def get_optional_current_user(
    request: Request = None,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> AuthenticatedUser | None:
    if credentials is None:
        return None
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


async def verify_google_oauth_token(provider_token: str) -> dict[str, Any]:
    """Verify Google OAuth access token or ID token with Google's userinfo/tokeninfo endpoints."""
    headers = {"Authorization": f"Bearer {provider_token}"}
    async with httpx.AsyncClient(timeout=8) as client:
        # Try userinfo endpoint with bearer token
        response = await client.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
        if response.status_code != 200:
            # Fallback: tokeninfo with access_token or id_token parameter
            response = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"access_token": provider_token})
            if response.status_code != 200:
                response = await client.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": provider_token})
                if response.status_code != 200:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid Google provider token.",
                    )
        data = response.json()
        email = data.get("email")
        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not retrieve email from Google token.",
            )
        return data


async def check_user_is_admin_in_db(admin_pool: Any, email: str, settings: Any) -> bool:
    """Check if an email is listed as admin in the PostgreSQL users table or admin_emails setting."""
    email_clean = email.strip().lower()
    admin_emails = {value.strip().lower() for value in settings.admin_emails.split(",") if value.strip()}
    if email_clean in admin_emails:
        return True

    if admin_pool is not None:
        async with admin_pool.acquire() as connection:
            role = await connection.fetchval(
                "SELECT role::text FROM users WHERE LOWER(email) = $1",
                email_clean,
            )
            if role in {"admin", "calendar_admin", "event_admin"}:
                return True
    return False
