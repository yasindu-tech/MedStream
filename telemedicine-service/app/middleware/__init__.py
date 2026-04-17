"""JWT middleware for telemedicine-service."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings

bearer_scheme = HTTPBearer()

ROLE_ALIASES = {
    "clinic_admin": "staff",
    "clinic_staff": "staff",
}


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        role = payload.get("role")
        if role in ROLE_ALIASES:
            payload["role"] = ROLE_ALIASES[role]

        user_roles = payload.get("roles") or []
        if isinstance(user_roles, str):
            user_roles = [user_roles]
        if payload.get("role") and payload["role"] not in user_roles:
            user_roles.append(payload["role"])
        payload["roles"] = user_roles

        return payload
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc


def require_roles(*roles: str):
    def _check(user: dict = Depends(get_current_user)):
        user_roles = user.get("roles") or []
        if not any(role in user_roles for role in roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}",
            )
        return user

    return _check
