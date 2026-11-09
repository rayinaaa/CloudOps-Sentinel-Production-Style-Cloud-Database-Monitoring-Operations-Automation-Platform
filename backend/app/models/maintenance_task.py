"""MaintenanceTask entity for operational task automation and audit trails."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase, utc_now


class MaintenanceTask(TimestampedBase):
    """Audit record and execution tracking for database maintenance operations."""

    __tablename__ = "maintenance_tasks"

    database_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("database_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    task_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
        doc="Task operation: S3_BACKUP, VACUUM_ANALYZE, REINDEX, HEALTH_AUDIT, FAILOVER_TEST",
    )
    status: Mapped[str] = mapped_column(
        String(32),
        default="PENDING",
        nullable=False,
        index=True,
        doc="Execution status: PENDING, RUNNING, SUCCESS, FAILED",
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    artifact_s3_url: Mapped[Optional[str]] = mapped_column(
        String(512),
        nullable=True,
        doc="S3 bucket URI for generated backup archive (e.g. s3://bucket/path/backup.dump.gz)",
    )
    backup_size_bytes: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        nullable=True,
        doc="Size of generated backup file in bytes",
    )
    execution_logs: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        doc="Output logs, stdout, or stderr captured during operational task execution",
    )
    initiated_by: Mapped[str] = mapped_column(
        String(128),
        default="system_scheduler",
        nullable=False,
        doc="Originator: system_scheduler, github_action, user:cloudops_admin",
    )

    # Relationship
    database: Mapped["DatabaseInstance"] = relationship(
        "DatabaseInstance", back_populates="maintenance_tasks"
    )

    __table_args__ = (Index("idx_maintenance_db_status", "database_id", "status"),)
