"""Endpoints for database performance telemetry and historical metric trends."""

import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.database_instance import DatabaseInstance
from app.models.metric_snapshot import MetricSnapshot
from app.schemas.metric import MetricSnapshotRead, MetricSummary

router = APIRouter(prefix="/metrics", tags=["Performance Telemetry"])


@router.get("/{instance_id}/history", response_model=List[MetricSnapshotRead])
async def get_metric_history(
    instance_id: uuid.UUID,
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
) -> List[MetricSnapshot]:
    """Retrieve timeseries snapshots for connections, cache hit ratio, and queries."""
    query = (
        select(MetricSnapshot)
        .where(MetricSnapshot.database_id == instance_id)
        .order_by(desc(MetricSnapshot.recorded_at))
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


@router.get("/{instance_id}/summary", response_model=MetricSummary)
async def get_metric_summary(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> MetricSummary:
    """Retrieve the latest operational KPI summary for a given database target."""
    instance_res = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = instance_res.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database target {instance_id} not found",
        )

    latest_snapshot_res = await db.execute(
        select(MetricSnapshot)
        .where(MetricSnapshot.database_id == instance_id)
        .order_by(desc(MetricSnapshot.recorded_at))
        .limit(1)
    )
    latest = latest_snapshot_res.scalar_one_or_none()

    if not latest:
        # Return sensible baseline if polling hasn't completed yet
        return MetricSummary(
            database_id=instance.id,
            database_name=instance.name,
            environment=instance.environment,
            health_status=instance.health_status,
            active_connections=0,
            max_connections=100,
            connection_pool_usage_pct=0.0,
            cache_hit_ratio=1.0,
            database_size_mb=0.0,
            slow_queries_last_hour=0,
            last_polled_at=instance.created_at,
        )

    return MetricSummary(
        database_id=instance.id,
        database_name=instance.name,
        environment=instance.environment,
        health_status=instance.health_status,
        active_connections=latest.active_connections,
        max_connections=latest.max_connections,
        connection_pool_usage_pct=latest.connection_pool_usage_pct,
        cache_hit_ratio=latest.cache_hit_ratio,
        database_size_mb=round(latest.database_size_bytes / (1024 * 1024), 2),
        slow_queries_last_hour=latest.slow_queries_count,
        last_polled_at=latest.recorded_at,
    )
