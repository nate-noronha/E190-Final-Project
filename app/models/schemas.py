from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr

from app.models.enums import RoleEnum


class UserCreate(BaseModel):
    name: str
    email: str
    role: RoleEnum = RoleEnum.STUDENT


class UserRead(BaseModel):
    id: int
    name: str
    email: str
    role: RoleEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class RoleUpdate(BaseModel):
    role: RoleEnum


class HealthResponse(BaseModel):
    status: str
    database: str
    detail: Optional[str] = None
