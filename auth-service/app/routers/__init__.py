from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, UserResponse
from app.services import register_user, login_user, refresh_tokens
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

@router.get("/me", response_model=UserResponse)
def me(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    from app.models import User
    return db.query(User).filter(User.id == user["sub"]).first()

# --- Role-gated example endpoints (consumed by other services via gateway) ---
@router.get("/admin-only")
def admin_only(user=Depends(require_roles("admin"))):
    return {"message": f"Hello admin {user['sub']}"}

@router.get("/doctor-or-admin")
def doctor_or_admin(user=Depends(require_roles("admin", "doctor"))):
    return {"message": f"Hello {user['role']} {user['sub']}"}