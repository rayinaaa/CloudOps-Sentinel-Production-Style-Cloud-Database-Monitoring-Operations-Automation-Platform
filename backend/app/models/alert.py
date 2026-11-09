"""Alert Rule and Incident models for operational anomaly detection."""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import TimestampedBase, utc_now


class AlertRule(TimestampedBase):
    """Configurable threshold definition for database metrics."""

    __tablename__ = "alert_rules"

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    metric_name: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="Metric key (e.g. connection_pool_usage_pct, cache_hit_ratio)",
    )
    operator: Mapped[str] = mapped_column(
        String(16),
        default="GREATER_THAN",
        nullable=False,
        doc="Comparison operator: GREATER_THAN, LESS_THAN, EQUALS",
    )
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(
        String(32),
        default="WARNING",
        nullable=False,
        doc="Incident severity: INFO, WARNING, CRITICAL",
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AlertIncident(TimestampedBase):
    """Recorded operational incident when a threshold is breached."""

    __tablename__ = "alert_incidents"

    database_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("database_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("alert_rules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="OPEN",
        nullable=False,
        index=True,
        doc="Incident status: OPEN, ACKNOWLEDGED, RESOLVED",
    )
    severity: Mapped[str] = mapped_column(
        String(32),
        default="WARNING",
        nullable=False,
        doc="Incident severity: INFO, WARNING, CRITICAL",
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    current_value: Mapped[float] = mapped_column(Float, nullable=False)
    threshold_value: Mapped[float] = mapped_column(Float, nullable=False)
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledged_by: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        doc="Ops engineer identifier who acknowledged the alert",
    )

    # Relationships
    database: Mapped["DatabaseInstance"] = relationship(
        "DatabaseInstance", back_populates="incidents"
    )
    rule: Mapped[Optional["AlertRule"]] = relationship("AlertRule")

    __table_args__ = (
        Index("idx_incident_db_status", "database_id", "status"),
    )

