"""Google OAuth helper utilities for one-time consent + refresh-token reuse."""
from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.config import settings
from app.models import GoogleOAuthIntegration

GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_PROVIDER_KEY = "google_meet"


def build_google_login_url() -> str:
    _assert_oauth_configured()
    state_token = _create_state_token()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.GOOGLE_OAUTH_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state_token,
    }
    return f"{GOOGLE_AUTH_ENDPOINT}?{urlencode(params)}"


def handle_google_callback(db: Session, *, code: str, state: str) -> dict:
    _assert_oauth_configured()
    _validate_state_token(state)

    token_response = _exchange_code_for_tokens(code)
    refresh_token = token_response.get("refresh_token")
    access_token = token_response.get("access_token")

    existing = _get_integration(db)
    if not refresh_token and not existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return a refresh token. Reconnect with prompt=consent.",
        )

    account_email = None
    if access_token:
        account_email = _fetch_google_account_email(access_token)

    if existing:
        if refresh_token:
            existing.refresh_token = refresh_token
        existing.scope = token_response.get("scope", existing.scope)
        existing.token_type = token_response.get("token_type", existing.token_type)
        existing.account_email = account_email or existing.account_email
        existing.is_active = 1
        db.commit()
        db.refresh(existing)
        return {
            "connected": True,
            "account_email": existing.account_email,
            "has_refresh_token": True,
            "scope": existing.scope,
            "updated": True,
        }

    integration = GoogleOAuthIntegration(
        provider=GOOGLE_PROVIDER_KEY,
        account_email=account_email,
        refresh_token=refresh_token,
        scope=token_response.get("scope"),
        token_type=token_response.get("token_type"),
        is_active=1,
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)

    return {
        "connected": True,
        "account_email": integration.account_email,
        "has_refresh_token": True,
        "scope": integration.scope,
        "updated": False,
    }


def get_google_integration_status(db: Session) -> dict:
    integration = _get_integration(db)
    if not integration or not integration.is_active:
        return {
            "connected": False,
            "provider": GOOGLE_PROVIDER_KEY,
        }
    return {
        "connected": True,
        "provider": GOOGLE_PROVIDER_KEY,
        "account_email": integration.account_email,
        "scope": integration.scope,
        "updated_at": integration.updated_at.isoformat() if integration.updated_at else None,
    }


def get_google_access_token_from_refresh(db: Session) -> str:
    _assert_oauth_configured()
    integration = _get_integration(db)
    if not integration or not integration.is_active or not integration.refresh_token:
        raise RuntimeError("Google OAuth integration is not connected.")

    payload = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "refresh_token": integration.refresh_token,
        "grant_type": "refresh_token",
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(GOOGLE_TOKEN_ENDPOINT, data=payload)

    if response.status_code >= 400:
        raise RuntimeError(f"Failed to refresh Google access token: {response.text}")

    data = response.json()
    access_token = data.get("access_token")
    if not access_token:
        raise RuntimeError("Google token refresh did not return access_token.")
    return access_token


def _exchange_code_for_tokens(code: str) -> dict:
    payload = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    with httpx.Client(timeout=10.0) as client:
        response = client.post(GOOGLE_TOKEN_ENDPOINT, data=payload)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to exchange Google authorization code: {response.text}",
        )

    return response.json()


def _fetch_google_account_email(access_token: str) -> str | None:
    headers = {"Authorization": f"Bearer {access_token}"}
    with httpx.Client(timeout=10.0) as client:
        response = client.get(GOOGLE_USERINFO_ENDPOINT, headers=headers)

    if response.status_code >= 400:
        return None

    return response.json().get("email")


def _get_integration(db: Session) -> GoogleOAuthIntegration | None:
    return (
        db.query(GoogleOAuthIntegration)
        .filter(GoogleOAuthIntegration.provider == GOOGLE_PROVIDER_KEY)
        .first()
    )


def _create_state_token() -> str:
    payload = {
        "type": "google_oauth_state",
        "exp": datetime.utcnow() + timedelta(minutes=15),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def _validate_state_token(state: str) -> None:
    try:
        payload = jwt.decode(state, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state.") from exc

    if payload.get("type") != "google_oauth_state":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state payload.")


def _assert_oauth_configured() -> None:
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Google OAuth is not configured. Missing client credentials.",
        )
