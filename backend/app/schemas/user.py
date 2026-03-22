from typing import Literal
from pydantic import BaseModel
from uuid import UUID

UserRole = Literal["reviewer", "admin", "super_admin"]


class UserOut(BaseModel):
    id: UUID
    username: str
    full_name: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    password: str
    full_name: str
    role: UserRole = "reviewer"


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    is_active: bool | None = None
