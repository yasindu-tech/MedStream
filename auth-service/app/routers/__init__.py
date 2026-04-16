from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import (
    RegisterRequest,
    LoginRequest,
    RefreshRequest,
    LogoutRequest,
    OTPRequest,
    OTPVerifyRequest,
    TokenResponse,
    OTPResponse,
    UserResponse,
)
from app.services import (
    register_user,
    login_user,
    refresh_tokens,
    logout_user,
    request_otp_code,
    verify_otp_code,
    get_all_roles,
)
from app.middleware import get_current_user, require_roles

router = APIRouter(tags=["Auth"])

@router.post("/register", response_model=UserResponse, status_code=201)
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    return register_user(data, db)

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    return login_user(data, db)

@router.post("/refresh", response_model=TokenResponse)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    return refresh_tokens(data.refresh_token, db)

@router.post("/logout", status_code=204)
def logout(data: LogoutRequest, db: Session = Depends(get_db)):
    logout_user(data.refresh_token, db)

@router.post("/otp/request", response_model=OTPResponse)
def request_otp(data: OTPRequest, db: Session = Depends(get_db)):
    return request_otp_code(data.email, data.purpose, db)

@router.post("/otp/verify")
def verify_otp(data: OTPVerifyRequest, db: Session = Depends(get_db)):
    return verify_otp_code(data.email, data.otp_code, data.purpose, data.new_password, db)

@router.get("/me", response_model=UserResponse)
def me(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    from app.models import User

    db_user = db.query(User).filter(User.id == user["sub"]).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "email": db_user.email,
        "phone": db_user.phone,
        "is_verified": db_user.is_verified,
        "account_status": db_user.account_status,
        "roles": [role.role_name for role in db_user.roles],
    }

@router.get("/roles", response_model=list[str])
def list_roles(db: Session = Depends(get_db)):
    return get_all_roles(db)

# --- Role-gated example endpoints (consumed by other services via gateway) ---
@router.get("/admin-only")
def admin_only(user=Depends(require_roles("admin"))):
    return {"message": f"Hello admin {user['sub']}"}

@router.get("/doctor-or-admin")
def doctor_or_admin(user=Depends(require_roles("admin", "doctor"))):
    return {"message": f"Hello {user['role']} {user['sub']}"}
