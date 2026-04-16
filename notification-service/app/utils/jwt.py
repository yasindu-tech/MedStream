from jose import jwt, JWTError
from app.config import settings
from fastapi import HTTPException, status

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
