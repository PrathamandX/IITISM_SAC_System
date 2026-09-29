import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from backend.auth.security import decode_token
from backend.database import get_db
from backend.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Roles whose data access is limited to their own hostel.
HOSTEL_SCOPED = {Role.warden, Role.clerk, Role.mess_manager}


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    unauthorized = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Invalid or expired token", headers={"WWW-Authenticate": "Bearer"}
    )
    try:
        user_id = int(decode_token(token)["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise unauthorized
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise unauthorized
    return user


def require_roles(*roles: Role):
    def checker(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "You are not allowed to perform this action")
        return user

    return checker


def check_hostel_access(user: User, hostel_id: int) -> None:
    """Wardens, clerks and mess managers may only touch their own hostel."""
    if user.role in HOSTEL_SCOPED and user.hostel_id != hostel_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can only access your own hostel")
