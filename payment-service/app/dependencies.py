from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from typing import AsyncGenerator, Optional
import logging

from app.config import settings
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

# Database dependency
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

# JWT dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    # 1. Check for internal service-to-service bypass
    if token == "internal-service-call":
        return {
            "user_id": "00000000-0000-0000-0000-000000000000",
            "role": "system",
            "email": "system@medstream.local",
        }

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        user_id: str = payload.get("sub") or payload.get("user_id")
        role: str = payload.get("role")
        email: str = payload.get("email")
        if user_id is None:
            raise credentials_exception
        
        return {
            "user_id": user_id, 
            "role": role, 
            "email": email, 
            "clinic_id": payload.get("clinic_id") # Optional clinic_id claim for clinic admins
        }
    except JWTError:
        raise credentials_exception

# Role-gating dependencies
async def require_patient(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "patient":
        raise HTTPException(status_code=403, detail="Only patients can perform this action")
    return user

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can perform this action")
    return user

async def require_clinic_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] not in ["clinic_admin", "admin"]: # Admin can also act as clinic admin
        raise HTTPException(status_code=403, detail="Access denied for this role")
    return user

async def require_doctor(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "doctor":
        raise HTTPException(status_code=403, detail="Only doctors can perform this action")
    return user

async def require_any_auth(user: dict = Depends(get_current_user)) -> dict:
    return user
