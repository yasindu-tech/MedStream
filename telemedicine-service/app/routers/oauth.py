"""Google OAuth connect endpoints for telemedicine provider integration."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.middleware import require_roles
from app.services.google_oauth import (
    build_google_login_url,
    get_google_integration_status,
    handle_google_callback,
)

router = APIRouter(tags=["google-oauth"])


@router.get("/auth/google/login")
def google_login() -> RedirectResponse:
    return RedirectResponse(build_google_login_url())


@router.get("/auth/google/callback")
def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    return handle_google_callback(db, code=code, state=state)


@router.get("/auth/google/status")
def google_status(
    _: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
) -> dict:
    return get_google_integration_status(db)
