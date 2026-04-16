from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from app.utils.jwt import decode_token
from typing import Dict, List

# Use a relative path to avoid hardcoded URLs
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    payload = decode_token(token)
    user_id: str = payload.get("sub")
    role: str = payload.get("role")
    email: str = payload.get("email")
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"user_id": user_id, "role": role, "email": email}

def require_roles(*roles: str):
    """Factory: returns a dependency that enforces role membership."""
    async def _check(user: Dict = Depends(get_current_user)):
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of roles: {list(roles)}"
            )
        return user
    return _check
