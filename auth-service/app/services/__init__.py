from datetime import datetime, timedelta
import secrets
from typing import cast
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User, Role, UserRole, AuthSession, OTPVerification, AccountStatusEnum
from app.schemas import RegisterRequest, LoginRequest, OtpPurpose, RoleEnum
from app.services.patient_client import create_patient_profile
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_token

REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 10


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
        "is_verified": user.is_verified,
        "account_status": user.account_status,
        "roles": [cast(str, role.role_name) for role in user.roles],
    }


def _get_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role_name}")
    return role


def _primary_role(user: User) -> str:
    if user.roles:
        return cast(str, user.roles[0].role_name)
    return "patient"


def _create_patient_profile(user: User) -> None:
    payload = {
        "user_id": str(user.id),
        "full_name": user.full_name,
        "email": user.email,
        "phone": user.phone,
    }
    create_patient_profile(payload)


def register_user(data: RegisterRequest, db: Session) -> dict:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if data.phone and db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    role = _get_role(db, data.role.value)
    user = User(
        full_name=data.full_name.strip(),
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        is_verified=True,
        account_status="ACTIVE",
    )
    db.add(user)
    db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.role_id)
    db.add(user_role)
    db.commit()
    db.refresh(user)

    if role.role_name == RoleEnum.patient.value:
        try:
            _create_patient_profile(user)
        except HTTPException:
            db.delete(user)
            db.commit()
            raise

    return _serialize_user(user)

def create_verified_user(
    email: str,
    password: str,
    role_name: str,
    db: Session,
    phone: str | None = None,
    full_name: str | None = None,
) -> dict:
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="Email already registered")
    if phone and db.query(User).filter(User.phone == phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    role = _get_role(db, role_name)
    user = User(
        full_name=full_name.strip() if full_name else None,
        email=email,
        phone=phone,
        password_hash=hash_password(password),
        is_verified=True,
        account_status="ACTIVE",
    )
    db.add(user)
    db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.role_id)
    db.add(user_role)
    db.commit()
    db.refresh(user)

    if role.role_name == RoleEnum.patient.value:
        try:
            _create_patient_profile(user)
        except HTTPException:
            db.delete(user)
            db.commit()
            raise

    return _serialize_user(user)


def login_user(data: LoginRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, cast(str, user.password_hash)):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not cast(bool, user.is_verified):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified")
    if cast(str, user.account_status) != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    role_names = [cast(str, role.role_name) for role in user.roles]
    primary_role = _primary_role(user)
    access_token = create_access_token(str(user.id), primary_role, role_names)
    refresh_token = create_refresh_token(str(user.id))

    expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    session = AuthSession(
        user_id=user.id,
        refresh_token=refresh_token,
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


def refresh_tokens(refresh_token: str, db: Session) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    session = db.query(AuthSession).filter(AuthSession.refresh_token == refresh_token).first()
    if not session or cast(bool, session.is_revoked):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked session")
    if cast(datetime, session.expires_at) < datetime.utcnow():
        setattr(session, "is_revoked", True)
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or cast(str, user.account_status) != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    role_names = [cast(str, role.role_name) for role in user.roles]
    primary_role = _primary_role(user)
    access_token = create_access_token(str(user.id), primary_role, role_names)
    new_refresh_token = create_refresh_token(str(user.id))

    setattr(session, "refresh_token", new_refresh_token)
    setattr(session, "expires_at", datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_refresh_token,
        "token_type": "bearer",
    }


def logout_user(refresh_token: str, db: Session) -> None:
    session = db.query(AuthSession).filter(AuthSession.refresh_token == refresh_token).first()
    if not session:
        return
    setattr(session, "is_revoked", True)
    db.commit()


def request_otp_code(email: str, purpose: OtpPurpose, db: Session) -> dict:
    if purpose not in (OtpPurpose.REGISTER, OtpPurpose.RESET_PASSWORD):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP purpose not supported")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    code = f"{secrets.randbelow(10**6):06d}"
    expires_at = datetime.utcnow() + timedelta(minutes=OTP_EXPIRE_MINUTES)
    otp = OTPVerification(
        user_id=user.id,
        otp_code=code,
        purpose=purpose.value,
        expires_at=expires_at,
    )
    db.add(otp)
    db.commit()

    return {"otp_code": code}


def verify_otp_code(email: str, otp_code: str, purpose: OtpPurpose, new_password: str | None, db: Session) -> dict:
    if purpose not in (OtpPurpose.REGISTER, OtpPurpose.RESET_PASSWORD):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP purpose not supported")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    otp = (
        db.query(OTPVerification)
        .filter(
            OTPVerification.user_id == user.id,
            OTPVerification.otp_code == otp_code,
            OTPVerification.purpose == purpose.value,
            OTPVerification.is_used == False,
            OTPVerification.expires_at >= datetime.utcnow(),
        )
        .order_by(OTPVerification.created_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    setattr(otp, "is_used", True)

    if purpose == OtpPurpose.REGISTER:
        setattr(user, "is_verified", True)
    elif purpose == OtpPurpose.RESET_PASSWORD:
        if not new_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password is required for password reset")
        setattr(user, "password_hash", hash_password(new_password))
    db.commit()

    return {"success": True}


def deactivate_user(user_id: UUID, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if cast(str, user.account_status) == "INACTIVE":
        return {"success": True}

    setattr(user, "account_status", "INACTIVE")
    db.commit()
    return {"success": True}


def suspend_user(user_id: UUID, reason: str | None, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if cast(str, user.account_status) == AccountStatusEnum.SUSPENDED.value:
        return {"success": True}

    setattr(user, "account_status", AccountStatusEnum.SUSPENDED.value)
    setattr(user, "suspension_reason", reason)
    db.commit()
    return {"success": True}


def get_all_roles(db: Session) -> list[str]:
    return [cast(str, role.role_name) for role in db.query(Role).order_by(Role.role_name).all()]
