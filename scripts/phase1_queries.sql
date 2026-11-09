-- ==============================================================================
-- CloudOps Sentinel - Phase 1: Operational Database Queries
-- Use Case: System health verification, tenant capacity audits & telemetry probes
-- ==============================================================================

-- ------------------------------------------------------------------------------
-- QUERY 1: Active vs. Suspended Tenants Breakdown
-- Purpose: Evaluates tenant fleet distribution across lifecycle states & subscription tiers.
-- CloudOps Context: Identifies churn, pending activations, and billing suspensions.
-- ------------------------------------------------------------------------------
SELECT
    status,
    plan,
    COUNT(*) AS tenant_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) AS pct_of_total_fleet,
    SUM(max_users) AS allocated_user_capacity,
    pg_size_pretty(SUM(max_storage_bytes)::bigint) AS allocated_storage_capacity
FROM tenants
GROUP BY status, plan
ORDER BY
    CASE status
        WHEN 'ACTIVE' THEN 1
        WHEN 'PENDING' THEN 2
        WHEN 'SUSPENDED' THEN 3
        ELSE 4
    END,
    plan;


-- ------------------------------------------------------------------------------
-- QUERY 2: Users per Tenant & License Capacity Utilization
-- Purpose: Audits seat consumption against tenant license limits (max_users).
-- CloudOps Context: Detects tenants nearing seat caps (>80%) or orphaned tenants with 0 users.
-- ------------------------------------------------------------------------------
SELECT
    t.name AS tenant_name,
    t.slug,
    t.plan,
    t.status AS tenant_status,
    t.max_users AS license_seat_limit,
    COUNT(u.id) AS total_users,
    COUNT(u.id) FILTER (WHERE u.is_active = TRUE) AS active_users,
    COUNT(u.id) FILTER (WHERE u.role IN ('OWNER', 'ADMIN')) AS admin_users,
    ROUND((COUNT(u.id)::numeric / t.max_users) * 100, 2) AS seat_utilization_pct,
    CASE
        WHEN (COUNT(u.id)::numeric / t.max_users) >= 0.80 THEN 'WARNING: Near Capacity'
        WHEN COUNT(u.id) = 0 THEN 'ALERT: Zero Users'
        ELSE 'NORMAL'
    END AS capacity_flag
FROM tenants t
LEFT JOIN app_users u ON t.id = u.tenant_id
GROUP BY t.id, t.name, t.slug, t.plan, t.status, t.max_users
ORDER BY seat_utilization_pct DESC, t.name ASC;


-- ------------------------------------------------------------------------------
-- QUERY 3: Database & Table Storage Footprint
-- Purpose: Dissects physical disk storage consumed by the database, tables, and indexes.
-- CloudOps Context: Capacity planning, index bloat identification, and S3 backup sizing.
-- ------------------------------------------------------------------------------
WITH table_sizes AS (
    SELECT
        c.relname AS table_name,
        pg_total_relation_size(c.oid) AS total_bytes,
        pg_relation_size(c.oid) AS table_bytes,
        pg_indexes_size(c.oid) AS index_bytes,
        reltuples::bigint AS approximate_row_count
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public'
      AND c.relkind = 'r'
)
SELECT
    table_name,
    approximate_row_count,
    pg_size_pretty(table_bytes) AS table_data_size,
    pg_size_pretty(index_bytes) AS index_size,
    pg_size_pretty(total_bytes) AS total_disk_size,
    ROUND((total_bytes::numeric / NULLIF(SUM(total_bytes) OVER (), 0)) * 100, 2) AS pct_of_public_schema
FROM table_sizes
UNION ALL
SELECT
    '-- TOTAL DATABASE CATALOG --' AS table_name,
    NULL AS approximate_row_count,
    NULL AS table_data_size,
    NULL AS index_size,
    pg_size_pretty(pg_database_size(current_database())) AS total_disk_size,
    100.00 AS pct_of_public_schema
ORDER BY total_disk_size DESC NULLS LAST;


-- ------------------------------------------------------------------------------
-- QUERY 4: Active Connections vs. Max Connections (Connection Pool Saturation)
-- Purpose: Probes PostgreSQL connection utilization and detects connection leaks.
-- CloudOps Context: High saturation (>80%) risks connection refusal (HTTP 500/503 errors).
-- ------------------------------------------------------------------------------
WITH conn_metrics AS (
    SELECT
        count(*) FILTER (WHERE state = 'active') AS active_connections,
        count(*) FILTER (WHERE state = 'idle') AS idle_connections,
        count(*) FILTER (WHERE state = 'idle in transaction') AS idle_in_trans_connections,
        count(*) AS total_checked_out,
        current_setting('max_connections')::int AS max_connections,
        current_setting('superuser_reserved_connections')::int AS reserved_connections
    FROM pg_stat_activity
    WHERE backend_type = 'client backend'
)
SELECT
    active_connections,
    idle_connections,
    idle_in_trans_connections,
    total_checked_out,
    max_connections,
    (max_connections - reserved_connections) AS usable_connections_limit,
    ROUND((total_checked_out::numeric / max_connections) * 100, 2) AS pool_saturation_pct,
    CASE
        WHEN (total_checked_out::numeric / max_connections) >= 0.90 THEN 'CRITICAL: Exhaustion Risk'
        WHEN (total_checked_out::numeric / max_connections) >= 0.75 THEN 'WARNING: High Saturation'
        WHEN idle_in_trans_connections > 5 THEN 'WARNING: Lingering Transactions'
        ELSE 'HEALTHY'
    END AS connection_pool_status
FROM conn_metrics;

