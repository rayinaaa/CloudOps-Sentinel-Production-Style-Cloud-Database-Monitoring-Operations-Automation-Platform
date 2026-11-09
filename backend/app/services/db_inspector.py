"""CloudOps Database Inspector Service.

Connects to target PostgreSQL catalogs (AWS RDS, Aurora, EC2 Postgres, or Docker)
and gathers deep operational telemetry from system catalog views:
- pg_stat_activity: connection saturation, state breakdown
- pg_stat_database: buffer cache hit ratio, commits, rollbacks, disk usage
- pg_stat_statements: slow query detection and latency tracking
- pg_stat_replication: replication lag and replica health
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import asyncpg
from app.core.config import settings
from app.core.logging import logger


@dataclass
class TargetInspectionResult:
    """Standardized operational telemetry envelope for database instances."""

    is_reachable: bool
    health_status: str  # HEALTHY, DEGRADED, CRITICAL, UNREACHABLE
    active_connections: int = 0
    idle_connections: int = 0
    max_connections: int = 100
    connection_pool_usage_pct: float = 0.0
    cache_hit_ratio: float = 1.0
    transactions_committed: int = 0
    transactions_rolled_back: int = 0
    deadlocks_count: int = 0
    slow_queries_count: int = 0
    replication_lag_seconds: float = 0.0
    database_size_bytes: int = 0
    error_message: Optional[str] = None
    top_slow_queries: List[Dict[str, Any]] = field(default_factory=list)


class DatabaseInspector:
    """Asynchronous PostgreSQL telemetry harvester."""

    @staticmethod
    async def inspect(
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        ssl_mode: str = "prefer",
        slow_query_threshold_ms: int = None,
        timeout_seconds: float = 5.0,
    ) -> TargetInspectionResult:
        """Connects to a target PostgreSQL database and harvests system telemetry."""
        threshold_ms = (
            slow_query_threshold_ms
            if slow_query_threshold_ms is not None
            else settings.SLOW_QUERY_THRESHOLD_MS
        )
        ssl = ssl_mode if ssl_mode not in ["disable", "prefer"] else None

        conn = None
        try:
            conn = await asyncpg.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                ssl=ssl,
                timeout=timeout_seconds,
            )

            # 1. Connection Pool & Activity Statistics
            activity_sql = """
            SELECT
                count(*) FILTER (WHERE state = 'active') AS active_count,
                count(*) FILTER (WHERE state LIKE 'idle%') AS idle_count,
                current_setting('max_connections')::int AS max_conn
            FROM pg_stat_activity
            WHERE datname = current_database();
            """
            activity_row = await conn.fetchrow(activity_sql)
            active_conn = int(activity_row["active_count"] or 0)
            idle_conn = int(activity_row["idle_count"] or 0)
            max_conn = int(activity_row["max_conn"] or 100)
            total_conn = active_conn + idle_conn
            pool_usage = round(total_conn / max_conn, 4) if max_conn > 0 else 0.0

            # 2. Database Buffer Cache Hit Ratio & Storage Metrics
            db_stats_sql = """
            SELECT
                xact_commit,
                xact_rollback,
                deadlocks,
                blks_read,
                blks_hit,
                pg_database_size(current_database()) AS db_bytes
            FROM pg_stat_database
            WHERE datname = current_database();
            """
            db_row = await conn.fetchrow(db_stats_sql)
            blks_read = int(db_row["blks_read"] or 0) if db_row else 0
            blks_hit = int(db_row["blks_hit"] or 0) if db_row else 0
            total_reads = blks_read + blks_hit
            cache_hit_ratio = round(blks_hit / total_reads, 4) if total_reads > 0 else 1.0

            xact_commit = int(db_row["xact_commit"] or 0) if db_row else 0
            xact_rollback = int(db_row["xact_rollback"] or 0) if db_row else 0
            deadlocks = int(db_row["deadlocks"] or 0) if db_row else 0
            db_bytes = int(db_row["db_bytes"] or 0) if db_row else 0

            # 3. Slow Queries via pg_stat_statements (if extension is loaded)
            slow_queries_count = 0
            top_slow_queries: List[Dict[str, Any]] = []
            try:
                stat_statements_sql = """
                SELECT
                    query,
                    calls,
                    round(total_exec_time::numeric, 2) AS total_time_ms,
                    round(mean_exec_time::numeric, 2) AS avg_time_ms
                FROM pg_stat_statements
                WHERE mean_exec_time > $1
                ORDER BY mean_exec_time DESC
                LIMIT 5;
                """
                slow_rows = await conn.fetch(stat_statements_sql, float(threshold_ms))
                slow_queries_count = len(slow_rows)
                for r in slow_rows:
                    top_slow_queries.append(
                        {
                            "query": str(r["query"])[:200],  # Truncate for safety
                            "calls": int(r["calls"]),
                            "total_time_ms": float(r["total_time_ms"]),
                            "avg_time_ms": float(r["avg_time_ms"]),
                        }
                    )
            except Exception as ext_err:
                # Extension might not be installed or enabled in this database
                logger.debug(
                    "pg_stat_statements not available on target database",
                    error=str(ext_err),
                    database=database,
                )

            # 4. Replication Lag (if target is primary with replicas)
            replication_lag_seconds = 0.0
            try:
                rep_sql = """
                SELECT
                    COALESCE(
                        MAX(EXTRACT(EPOCH FROM (now() - replay_lag))),
                        0.0
                    ) AS max_lag_sec
                FROM pg_stat_replication;
                """
                rep_row = await conn.fetchrow(rep_sql)
                if rep_row and rep_row["max_lag_sec"] is not None:
                    replication_lag_seconds = float(rep_row["max_lag_sec"])
            except Exception:
                pass

            # 5. Evaluate Overall Health Status
            health_status = "HEALTHY"
            if (
                pool_usage >= settings.CONNECTION_POOL_CRITICAL_THRESHOLD
                or cache_hit_ratio < 0.70
            ):
                health_status = "CRITICAL"
            elif (
                pool_usage >= settings.CONNECTION_POOL_WARNING_THRESHOLD
                or cache_hit_ratio < settings.CACHE_HIT_RATIO_MIN_THRESHOLD
                or slow_queries_count > 0
                or deadlocks > 0
            ):
                health_status = "DEGRADED"

            return TargetInspectionResult(
                is_reachable=True,
                health_status=health_status,
                active_connections=active_conn,
                idle_connections=idle_conn,
                max_connections=max_conn,
                connection_pool_usage_pct=pool_usage,
                cache_hit_ratio=cache_hit_ratio,
                transactions_committed=xact_commit,
                transactions_rolled_back=xact_rollback,
                deadlocks_count=deadlocks,
                slow_queries_count=slow_queries_count,
                replication_lag_seconds=replication_lag_seconds,
                database_size_bytes=db_bytes,
                top_slow_queries=top_slow_queries,
            )

        except Exception as exc:
            logger.warning(
                "Failed to inspect target database",
                host=host,
                port=port,
                database=database,
                error=str(exc),
            )
            return TargetInspectionResult(
                is_reachable=False,
                health_status="UNREACHABLE",
                error_message=str(exc),
            )
        finally:
            if conn:
                try:
                    await conn.close(timeout=2.0)
                except Exception:
                    pass
