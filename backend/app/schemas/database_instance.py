"""Pydantic schemas for DatabaseInstance entity."""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class DatabaseInstanceBase(BaseModel):
    name: str = Field(..., max_length=128, description="Target database identifier")
    engine: str = Field(default="postgresql", max_length=32)
    host: str = Field(..., max_length=255)
    port: int = Field(default=5432, ge=1, le=65535)
    database_name: str = Field(..., max_length=64)
    username: str = Field(..., max_length=64)
    environment: str = Field(default="production", max_length=32)
    is_active: bool = Field(default=True)
    ssl_mode: str = Field(default="require", max_length=32)
    tags: Optional[Dict[str, Any]] = None


class DatabaseInstanceCreate(DatabaseInstanceBase):
    pass


class DatabaseInstanceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=128)
    host: Optional[str] = Field(None, max_length=255)
    port: Optional[int] = Field(None, ge=1, le=65535)
    database_name: Optional[str] = Field(None, max_length=64)
    username: Optional[str] = Field(None, max_length=64)
    environment: Optional[str] = Field(None, max_length=32)
    is_active: Optional[bool] = None
    ssl_mode: Optional[str] = Field(None, max_length=32)
    tags: Optional[Dict[str, Any]] = None


class DatabaseInstanceRead(DatabaseInstanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    health_status: str
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

