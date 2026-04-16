from datetime import datetime, timedelta
import secrets

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import User, Role, UserRole, AuthSession, OTPVerification
from app.schemas import RegisterRequest, LoginRequest, OtpPurpose
from app.utils.hashing import hash_password, verify_password
from app.utils.jwt import create_access_token, create_refresh_token, decode_token

REFRESH_TOKEN_EXPIRE_DAYS = 7
OTP_EXPIRE_MINUTES = 10


def _serialize_user(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "phone": user.phone,
        "is_verified": user.is_verified,
        "account_status": user.account_status,
        "roles": [role.role_name for role in user.roles],
    }


def _get_role(db: Session, role_name: str) -> Role:
    role = db.query(Role).filter(Role.role_name == role_name).first()
    if not role:
        raise HTTPException(status_code=400, detail=f"Unknown role: {role_name}")
    return role


def _primary_role(user: User) -> str:
    if user.roles:
        return user.roles[0].role_name
    return "patient"


def register_user(data: RegisterRequest, db: Session) -> dict:
    if db.query(User).filter(User.email == data.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    if data.phone and db.query(User).filter(User.phone == data.phone).first():
        raise HTTPException(status_code=400, detail="Phone already registered")

    role = _get_role(db, data.role.value)
    user = User(
        email=data.email,
        phone=data.phone,
        password_hash=hash_password(data.password),
        is_verified=False,
        account_status="ACTIVE",
    )
    db.add(user)
    db.flush()

    user_role = UserRole(user_id=user.id, role_id=role.role_id)
    db.add(user_role)
    db.commit()
    db.refresh(user)
    return _serialize_user(user)


def login_user(data: LoginRequest, db: Session) -> dict:
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account not verified")
    if user.account_status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account disabled")

    role_names = [role.role_name for role in user.roles]
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
    if not session or session.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked session")
    if session.expires_at < datetime.utcnow():
        session.is_revoked = True
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired")

    user = db.query(User).filter(User.id == payload["sub"]).first()
    if not user or user.account_status != "ACTIVE":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    role_names = [role.role_name for role in user.roles]
    primary_role = _primary_role(user)
    access_token = create_access_token(str(user.id), primary_role, role_names)
    new_refresh_token = create_refresh_token(str(user.id))

    session.refresh_token = new_refresh_token
    session.expires_at = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
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
    session.is_revoked = True
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

    otp.is_used = True

    if purpose == OtpPurpose.REGISTER:
        user.is_verified = True
    elif purpose == OtpPurpose.RESET_PASSWORD:
        if not new_password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="New password is required for password reset")
        user.password_hash = hash_password(new_password)
    db.commit()

    return {"success": True}


def get_all_roles(db: Session) -> list[str]:
    return [role.role_name for role in db.query(Role).order_by(Role.role_name).all()]
