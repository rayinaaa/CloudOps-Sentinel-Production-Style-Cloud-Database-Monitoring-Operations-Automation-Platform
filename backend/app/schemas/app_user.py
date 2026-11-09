"""Pydantic schemas for AppUser entity."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AppUserBase(BaseModel):
    email: EmailStr = Field(..., max_length=255)
    full_name: str = Field(..., max_length=128)
    role: str = Field(default="MEMBER", max_length=32)
    is_active: bool = True


class AppUserCreate(AppUserBase):
    pass


class AppUserRead(AppUserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: uuid.UUID
    last_login_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
