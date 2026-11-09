"""MetricSnapshot entity storing historical performance telemetry."""

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Index, Integer, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TimestampedBase, utc_now


class MetricSnapshot(TimestampedBase):
    """Point-in-time performance and capacity telemetry for a monitored database."""

    __tablename__ = "metric_snapshots"

    database_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("database_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
        index=True,
        doc="UTC time when telemetry was polled",
    )

    # Connection Pool Telemetry
    active_connections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idle_connections: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_connections: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    connection_pool_usage_pct: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, doc="Calculated percentage: active/max"
    )

    # Performance & Throughput
    cache_hit_ratio: Mapped[float] = mapped_column(
        Float,
        default=1.0,
        nullable=False,
        doc="Buffer pool cache hit ratio (0.00 to 1.00)",
    )
    transactions_committed: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    transactions_rolled_back: Mapped[int] = mapped_column(
        BigInteger, default=0, nullable=False
    )
    deadlocks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    slow_queries_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False,
        doc="Queries exceeding threshold in sample interval",
    )
    replication_lag_seconds: Mapped[float] = mapped_column(
        Float, default=0.0, nullable=False, doc="Replication lag in seconds"
    )

    # Storage Capacity
    database_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        default=0,
        nullable=False,
        doc="Catalog disk space consumed in bytes",
    )

    # Relationship
    database: Mapped["DatabaseInstance"] = relationship(
        "DatabaseInstance", back_populates="metrics"
    )

    __table_args__ = (Index("idx_metric_db_time", "database_id", "recorded_at"),)
