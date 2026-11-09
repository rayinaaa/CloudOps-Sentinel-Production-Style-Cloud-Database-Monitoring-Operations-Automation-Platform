"""DatabaseInstance entity representing monitored database targets."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase


class DatabaseInstance(TimestampedBase):
    """Monitored database target (AWS RDS, Aurora, EC2 Postgres, or Containerized)."""

    __tablename__ = "database_instances"

    name: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
        index=True,
        doc="Human-readable identifier e.g. prod-us-east-1-orders",
    )
    engine: Mapped[str] = mapped_column(
        String(32),
        default="postgresql",
        nullable=False,
        doc="Database engine (postgresql, aurora_postgresql)",
    )
    host: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        doc="Hostname or RDS endpoint",
    )
    port: Mapped[int] = mapped_column(
        Integer,
        default=5432,
        nullable=False,
        doc="Database network port",
    )
    database_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Target catalog or database name",
    )
    username: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Service account with monitoring permissions",
    )
    environment: Mapped[str] = mapped_column(
        String(32),
        default="production",
        nullable=False,
        index=True,
        doc="Deployment tier: production, staging, development, dr",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        doc="Whether this target is actively polled by Sentinel",
    )
    health_status: Mapped[str] = mapped_column(
        String(32),
        default="UNKNOWN",
        nullable=False,
        index=True,
        doc="Calculated health: HEALTHY, DEGRADED, CRITICAL, UNKNOWN",
    )
    ssl_mode: Mapped[str] = mapped_column(
        String(32),
        default="require",
        nullable=False,
        doc="SSL connection mode (disable, require, verify-ca, verify-full)",
    )
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp of most recent health probe",
    )
    tags: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        doc="Cloud tags e.g. {'aws_region': 'us-east-1', 'owner': 'cloudops'}",
    )

    # Relationships
    metrics: Mapped[List["MetricSnapshot"]] = relationship(
        "MetricSnapshot",
        back_populates="database",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incidents: Mapped[List["AlertIncident"]] = relationship(
        "AlertIncident",
        back_populates="database",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    maintenance_tasks: Mapped[List["MaintenanceTask"]] = relationship(
        "MaintenanceTask",
        back_populates="database",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
