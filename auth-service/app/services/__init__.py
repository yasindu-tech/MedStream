from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models import Role, User, UserRole
from app.schemas import RegisterRequest, LoginRequest
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_token


def _resolve_primary_role(db: Session, user_id: str) -> str:
    row = (
        db.query(Role.role_name)
        .join(UserRole, UserRole.role_id == Role.role_id)
        .filter(UserRole.user_id == user_id)
        .order_by(UserRole.created_at.asc())
        .first()
    )
    if not row:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no assigned role",
        )
    return row[0]


def get_user_profile(user_id: str, db: Session) -> dict | None:
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        return None

    role_name = _resolve_primary_role(db, str(user.user_id))
    return {
        "id": user.user_id,
        "email": user.email,
        "role": role_name,
        "is_active": user.account_status == "ACTIVE",
    }

def register_user(data: RegisterRequest, db: Session):
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    role = db.query(Role).filter(Role.role_name == data.role.value).first()
    if not role:
        raise HTTPException(status_code=400, detail="Invalid role")

    user = User(
        email=data.email,
        password_hash=hash_password(data.password),
        account_status="ACTIVE",
    )
    db.add(user)
    db.flush()

    db.add(
        UserRole(
            user_id=user.user_id,
            role_id=role.role_id,
        )
    )

    db.commit()
    return {
        "id": user.user_id,
        "email": user.email,
        "role": role.role_name,
        "is_active": user.account_status == "ACTIVE",
    }

def login_user(data: LoginRequest, db: Session):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.account_status != "ACTIVE":
        raise HTTPException(status_code=403, detail="Account disabled")

    role_name = _resolve_primary_role(db, str(user.user_id))
    return {
        "access_token":  create_access_token(str(user.user_id), role_name),
        "refresh_token": create_refresh_token(str(user.user_id)),
        "token_type":    "bearer"
    }

def refresh_tokens(refresh_token: str, db: Session):
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    user = db.query(User).filter(User.user_id == payload["sub"]).first()
    if not user or user.account_status != "ACTIVE":
        raise HTTPException(status_code=401, detail="User not found or inactive")

    role_name = _resolve_primary_role(db, str(user.user_id))
    return {
        "access_token":  create_access_token(str(user.user_id), role_name),
        "refresh_token": create_refresh_token(str(user.user_id)),
        "token_type":    "bearer"
    }