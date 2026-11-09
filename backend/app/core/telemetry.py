"""Custom Prometheus Telemetry Gauges and Metrics Collector for CloudOps Sentinel."""

from prometheus_client import Gauge, Counter

# Connection Metrics
DB_ACTIVE_CONNECTIONS = Gauge(
    "sentinel_db_connections_active",
    "Current active executing connections on the target database",
    ["database_name", "environment"],
)
DB_IDLE_CONNECTIONS = Gauge(
    "sentinel_db_connections_idle",
    "Current idle connections in the pool",
    ["database_name", "environment"],
)
DB_MAX_CONNECTIONS = Gauge(
    "sentinel_db_connections_max",
    "Configured maximum client connection limit",
    ["database_name", "environment"],
)
DB_POOL_SATURATION_RATIO = Gauge(
    "sentinel_db_pool_saturation_ratio",
    "Connection pool usage percentage (total connections / max connections)",
    ["database_name", "environment"],
)

# Performance & Throughput Metrics
DB_CACHE_HIT_RATIO = Gauge(
    "sentinel_db_cache_hit_ratio",
    "Buffer pool cache hit ratio (0.0 to 1.0)",
    ["database_name", "environment"],
)
DB_SLOW_QUERIES_COUNT = Gauge(
    "sentinel_db_slow_queries_count",
    "Number of queries exceeding the slow query threshold in sample interval",
    ["database_name", "environment"],
)
DB_DEADLOCKS_COUNT = Gauge(
    "sentinel_db_deadlocks_count",
    "Total deadlock events detected",
    ["database_name", "environment"],
)
DB_SIZE_BYTES = Gauge(
    "sentinel_db_size_bytes",
    "Physical database catalog storage consumption in bytes",
    ["database_name", "environment"],
)

# Incident & Automation Counters
INCIDENTS_TRIGGERED_TOTAL = Counter(
    "sentinel_incidents_triggered_total",
    "Total number of operational alert incidents triggered",
    ["database_name", "severity"],
)
MAINTENANCE_JOBS_TOTAL = Counter(
    "sentinel_maintenance_jobs_total",
    "Total operational maintenance jobs executed (backups, vacuum, etc.)",
    ["task_type", "status"],
)


def update_prometheus_metrics(instance_name: str, environment: str, metrics: dict) -> None:
    """Updates Prometheus gauges with fresh telemetry snapshot data."""
    labels = {"database_name": instance_name, "environment": environment}

    if "active_connections" in metrics:
        DB_ACTIVE_CONNECTIONS.labels(**labels).set(metrics["active_connections"])
    if "idle_connections" in metrics:
        DB_IDLE_CONNECTIONS.labels(**labels).set(metrics["idle_connections"])
    if "max_connections" in metrics:
        DB_MAX_CONNECTIONS.labels(**labels).set(metrics["max_connections"])
    if "connection_pool_usage_pct" in metrics:
        DB_POOL_SATURATION_RATIO.labels(**labels).set(metrics["connection_pool_usage_pct"])
    if "cache_hit_ratio" in metrics:
        DB_CACHE_HIT_RATIO.labels(**labels).set(metrics["cache_hit_ratio"])
    if "slow_queries_count" in metrics:
        DB_SLOW_QUERIES_COUNT.labels(**labels).set(metrics["slow_queries_count"])
    if "deadlocks_count" in metrics:
        DB_DEADLOCKS_COUNT.labels(**labels).set(metrics["deadlocks_count"])
    if "database_size_bytes" in metrics:
        DB_SIZE_BYTES.labels(**labels).set(metrics["database_size_bytes"])

