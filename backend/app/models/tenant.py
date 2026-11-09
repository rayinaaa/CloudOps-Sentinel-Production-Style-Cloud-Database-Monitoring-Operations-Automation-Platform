"""SQLAlchemy model for Tenant entity."""

import uuid
from datetime import datetime
from typing import List

from sqlalchemy import BigInteger, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utc_now


class Tenant(Base):
    """Multi-tenant organization entity."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )
    plan: Mapped[str] = mapped_column(
        String(32), default="FREE", nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="ACTIVE", nullable=False, index=True
    )
    max_users: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    max_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, default=1073741824, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )

    # Relationships
    users: Mapped[List["AppUser"]] = relationship(
        "AppUser",
        back_populates="tenant",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
