from pydantic import BaseModel, Field

from backend.models import Role
from backend.schemas.common import ORM, Name


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: Role
    full_name: str


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9_.\-]+$")
    full_name: Name
    password: str = Field(min_length=8, max_length=72)
    role: Role
    hostel_id: int | None = None


class UserOut(ORM):
    id: int
    username: str
    full_name: str
    role: Role
    hostel_id: int | None
    student_id: int | None
    is_active: bool


class PasswordChange(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)
