from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.utils.jwt import decode_token
from app.database import get_db
from app.models import User

bearer_scheme = HTTPBearer()

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> dict:
    payload = decode_token(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.account_status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled or suspended",
        )

    return payload

def require_roles(*roles: str):
    """Factory: returns a dependency that enforces role membership."""
    def _check(user: dict = Depends(get_current_user)):
        user_roles = user.get("roles") or []
        if isinstance(user_roles, str):
            user_roles = [user_roles]
        if user.get("role"):
            user_roles.append(user["role"])
        if not any(role in roles for role in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}"
            )
        return user
    return _check
