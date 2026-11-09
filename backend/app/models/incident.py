"""Incident and Incident History models for CloudOps Sentinel incident lifecycle."""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase, utc_now


class IncidentSeverity(str, Enum):
    """SRE Incident Severity classification."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class IncidentStatus(str, Enum):
    """Incident lifecycle workflow states."""

    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


class IncidentSource(str, Enum):
    """Originating trigger source for the incident."""

    ALERTMANAGER = "ALERTMANAGER"
    HEALTH_CHECK_PROBE = "HEALTH_CHECK_PROBE"
    DISK_MONITOR = "DISK_MONITOR"
    CONNECTION_MONITOR = "CONNECTION_MONITOR"
    MANUAL = "MANUAL"
    SIMULATION = "SIMULATION"


class Incident(TimestampedBase):
    """Production SRE incident record tracking outages, SLA timers, and escalation."""

    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    severity: Mapped[str] = mapped_column(
        String(32),
        default=IncidentSeverity.MEDIUM.value,
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default=IncidentStatus.OPEN.value,
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(
        String(64),
        default=IncidentSource.ALERTMANAGER.value,
        nullable=False,
    )
    component: Mapped[str] = mapped_column(
        String(64),
        default="DATABASE",
        nullable=False,
        index=True,
    )
    target_instance: Mapped[str] = mapped_column(
        String(128),
        default="primary-postgres",
        nullable=False,
    )
    fingerprint: Mapped[Optional[str]] = mapped_column(
        String(128),
        nullable=True,
        index=True,
    )
    escalation_level: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
    )
    assigned_to: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    acknowledged_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolved_by: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    # Lifecycle Timestamps
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relational Audit Trail
    history: Mapped[List["IncidentHistory"]] = relationship(
        "IncidentHistory",
        back_populates="incident",
        cascade="all, delete-orphan",
        order_by="IncidentHistory.created_at.desc()",
    )

    __table_args__ = (
        Index("idx_incidents_status_severity_comp", "status", "severity"),
    )

    @property
    def time_to_acknowledge_seconds(self) -> Optional[float]:
        """Calculates duration between incident creation and on-call acknowledgement."""
        if self.acknowledged_at and self.created_at:
            delta = (self.acknowledged_at - self.created_at).total_seconds()
            return round(max(0.0, delta), 2)
        return None

    @property
    def time_to_resolve_seconds(self) -> Optional[float]:
        """Calculates total Mean Time To Resolution (MTTR) duration in seconds."""
        if self.resolved_at and self.created_at:
            delta = (self.resolved_at - self.created_at).total_seconds()
            return round(max(0.0, delta), 2)
        return None


class IncidentHistory(TimestampedBase):
    """Immutable audit trail of transitions, notes, and actions for an incident."""

    __tablename__ = "incident_history"

    incident_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    to_status: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationship back to parent incident
    incident: Mapped["Incident"] = relationship("Incident", back_populates="history")

