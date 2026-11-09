"""Pydantic schemas for database metrics and historical snapshots."""

import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MetricSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    database_id: uuid.UUID
    recorded_at: datetime
    active_connections: int
    idle_connections: int
    max_connections: int
    connection_pool_usage_pct: float
    cache_hit_ratio: float
    transactions_committed: int
    transactions_rolled_back: int
    deadlocks_count: int
    slow_queries_count: int
    replication_lag_seconds: float
    database_size_bytes: int


class MetricSummary(BaseModel):
    database_id: uuid.UUID
    database_name: str
    environment: str
    health_status: str
    active_connections: int
    max_connections: int
    connection_pool_usage_pct: float
    cache_hit_ratio: float
    database_size_mb: float
    slow_queries_last_hour: int
    last_polled_at: datetime

