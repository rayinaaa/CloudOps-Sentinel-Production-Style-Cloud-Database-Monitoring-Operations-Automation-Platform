"""CloudOps Sentinel Telemetry Scheduler & Background Polling Worker.

Periodically queries all active database targets, records MetricSnapshots,
evaluates AlertRules, updates Prometheus gauges, and logs operational telemetry.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.logging import logger
from app.core.telemetry import update_prometheus_metrics
from app.models.database_instance import DatabaseInstance
from app.models.metric_snapshot import MetricSnapshot
from app.services.alert_engine import AlertEngine
from app.services.db_inspector import DatabaseInspector

# Background task reference
_scheduler_task: Optional[asyncio.Task] = None
_stop_event = asyncio.Event()


async def poll_database_targets() -> int:
    """Executes a single telemetry collection pass across all active database targets."""
    targets_polled = 0
    async with AsyncSessionLocal() as db:
        try:
            result = await db.execute(
                select(DatabaseInstance).where(DatabaseInstance.is_active == True)  # noqa: E712
            )
            instances = result.scalars().all()

            for instance in instances:
                try:
                    # 1. Harvest telemetry from target PostgreSQL instance
                    # Determine appropriate credentials for target vs metadata DB
                    inst_password = (
                        settings.TARGET_POSTGRES_PASSWORD
                        if (
                            instance.port == settings.TARGET_POSTGRES_PORT
                            or instance.database_name != settings.POSTGRES_DB
                        )
                        else settings.POSTGRES_PASSWORD
                    )
                    telemetry = await DatabaseInspector.inspect(
                        host=instance.host,
                        port=instance.port,
                        user=instance.username,
                        password=inst_password,
                        database=instance.database_name,
                        ssl_mode=instance.ssl_mode,
                        slow_query_threshold_ms=settings.SLOW_QUERY_THRESHOLD_MS,
                    )

                    # 2. Record timeseries snapshot
                    snapshot = MetricSnapshot(
                        database_id=instance.id,
                        recorded_at=datetime.now(timezone.utc),
                        active_connections=telemetry.active_connections,
                        idle_connections=telemetry.idle_connections,
                        max_connections=telemetry.max_connections,
                        connection_pool_usage_pct=telemetry.connection_pool_usage_pct,
                        cache_hit_ratio=telemetry.cache_hit_ratio,
                        transactions_committed=telemetry.transactions_committed,
                        transactions_rolled_back=telemetry.transactions_rolled_back,
                        deadlocks_count=telemetry.deadlocks_count,
                        slow_queries_count=telemetry.slow_queries_count,
                        replication_lag_seconds=telemetry.replication_lag_seconds,
                        database_size_bytes=telemetry.database_size_bytes,
                    )
                    db.add(snapshot)

                    # 3. Update target instance health status & last checked timestamp
                    instance.health_status = telemetry.health_status
                    instance.last_checked_at = datetime.now(timezone.utc)

                    # 4. Evaluate Alert Rules & manage incidents
                    await AlertEngine.evaluate_target(db, instance, telemetry)

                    # 5. Update Prometheus Exporter Gauges
                    update_prometheus_metrics(
                        instance.name,
                        instance.environment,
                        {
                            "active_connections": telemetry.active_connections,
                            "idle_connections": telemetry.idle_connections,
                            "max_connections": telemetry.max_connections,
                            "connection_pool_usage_pct": telemetry.connection_pool_usage_pct,
                            "cache_hit_ratio": telemetry.cache_hit_ratio,
                            "slow_queries_count": telemetry.slow_queries_count,
                            "deadlocks_count": telemetry.deadlocks_count,
                            "database_size_bytes": telemetry.database_size_bytes,
                        },
                    )

                    targets_polled += 1

                except Exception as inst_err:
                    logger.warning(
                        "Error polling target database instance",
                        instance=instance.name,
                        error=str(inst_err),
                    )

            await db.commit()

        except Exception as exc:
            await db.rollback()
            logger.error("Telemetry polling batch failed", error=str(exc))

    return targets_polled


async def telemetry_background_loop() -> None:
    """Continuously runs telemetry polling at configured intervals until cancelled."""
    interval = max(5, settings.METRICS_SCRAPE_INTERVAL_SECONDS)
    logger.info(
        "Starting Sentinel Telemetry Background Worker", interval_seconds=interval
    )

    while not _stop_event.is_set():
        try:
            polled_count = await poll_database_targets()
            logger.debug(
                "Completed telemetry scrape cycle", targets_polled=polled_count
            )
        except Exception as loop_err:
            logger.error("Telemetry loop iteration error", error=str(loop_err))

        try:
            await asyncio.wait_for(_stop_event.wait(), timeout=interval)
        except asyncio.TimeoutError:
            pass  # Expected timeout to trigger next iteration


def start_telemetry_scheduler() -> None:
    """Starts the background telemetry collection worker in the active asyncio loop."""
    global _scheduler_task, _stop_event
    _stop_event.clear()
    if _scheduler_task is None or _scheduler_task.done():
        _scheduler_task = asyncio.create_task(telemetry_background_loop())
        logger.info("Sentinel Telemetry Scheduler spawned")


async def stop_telemetry_scheduler() -> None:
    """Gracefully requests cancellation of the background telemetry worker."""
    global _scheduler_task, _stop_event
    _stop_event.set()
    if _scheduler_task and not _scheduler_task.done():
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("Sentinel Telemetry Scheduler stopped")
