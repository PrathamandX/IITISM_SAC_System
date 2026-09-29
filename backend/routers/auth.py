from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.auth import create_access_token, get_current_user, hash_password, require_roles, verify_password
from backend.auth.deps import HOSTEL_SCOPED
from backend.database import get_db
from backend.models import Hostel, Role, User
from backend.schemas.auth import PasswordChange, Token, UserCreate, UserOut

router = APIRouter(prefix="/api", tags=["Authentication & users"])


@router.post("/auth/login", response_model=Token)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.username == form.username))
    if not user or not user.is_active or not verify_password(form.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")
    return Token(access_token=create_access_token(user.id, user.role.value), role=user.role, full_name=user.full_name)


@router.get("/auth/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.post("/auth/change-password", status_code=204)
def change_password(data: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(data.old_password, user.password_hash):
        raise HTTPException(400, "Old password is incorrect")
    user.password_hash = hash_password(data.new_password)
    db.commit()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(data: UserCreate, db: Session = Depends(get_db), _: User = Depends(require_roles(Role.chairman))):
    """Chairman creates staff accounts (wardens, clerks, mess managers, dean). Students are created at admission."""
    if data.role == Role.student:
        raise HTTPException(400, "Student accounts are created through admission (POST /api/students)")
    if data.role in HOSTEL_SCOPED:
        if not data.hostel_id or not db.get(Hostel, data.hostel_id):
            raise HTTPException(400, "A valid hostel_id is required for this role")
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(409, "Username already exists")
    user = User(username=data.username, full_name=data.full_name, role=data.role,
                hostel_id=data.hostel_id if data.role in HOSTEL_SCOPED else None,
                password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_roles(Role.chairman))):
    return db.scalars(select(User).where(User.role != Role.student).order_by(User.id)).all()


@router.patch("/users/{user_id}/deactivate", response_model=UserOut)
def deactivate_user(user_id: int, db: Session = Depends(get_db), me: User = Depends(require_roles(Role.chairman))):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    if user.id == me.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    user.is_active = False
    db.commit()
    return user
