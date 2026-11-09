#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Connection Pool & Concurrency Monitor
# Role Alignment: Associate Cloud Operations Engineer - Operational Performance
# Description: Evaluates connection pool saturation, active queries, and detects
#              lingering idle-in-transaction connections holding locks.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configuration & Thresholds
# ------------------------------------------------------------------------------
DB_HOST="${DB_HOST:-${POSTGRES_SERVER:-localhost}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5434}}"
DB_NAME="${DB_NAME:-${POSTGRES_DB:-sentinel_db}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-sentinel_admin}}"
WARN_SATURATION_PCT="${CONN_WARN_SATURATION:-75}"
CRIT_SATURATION_PCT="${CONN_CRIT_SATURATION:-90}"
IDLE_IN_TRANS_WARN_SEC="${IDLE_TRANS_WARN_SEC:-60}"

# Exit Code Standard
EXIT_HEALTHY=0
EXIT_CONFIG_ERROR=1
EXIT_CONNECTION_FAILED=2
EXIT_WARN_THRESHOLD=3
EXIT_CRIT_THRESHOLD=4

# Safe Credential Handling
export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-sentinel_secret_dev_pass}}"

# ------------------------------------------------------------------------------
# 2. Logging Helpers
# ------------------------------------------------------------------------------
timestamp() {
    date -u +"%Y-%m-%dT%H:%M:%SZ"
}

log_info() {
    echo -e "[$(timestamp)] [INFO] $*"
}

log_warn() {
    echo -e "[$(timestamp)] [WARN] $*" >&2
}

log_error() {
    echo -e "[$(timestamp)] [ERROR] $*" >&2
}

# ------------------------------------------------------------------------------
# 3. Preflight Checks
# ------------------------------------------------------------------------------
if ! [[ "${IDLE_IN_TRANS_WARN_SEC}" =~ ^[0-9]+$ ]]; then
    log_error "Configuration error: IDLE_TRANS_WARN_SEC must be a positive integer."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! [[ "${WARN_SATURATION_PCT}" =~ ^[0-9]+$ ]] || ! [[ "${CRIT_SATURATION_PCT}" =~ ^[0-9]+$ ]]; then
    log_error "Configuration error: Saturation thresholds must be numeric integers."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! command -v psql >/dev/null 2>&1; then
    log_error "PostgreSQL client utility 'psql' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

log_info "Auditing connection pool on ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}..."

# ------------------------------------------------------------------------------
# 4. Connection Pool & Activity Telemetry Query
# ------------------------------------------------------------------------------
MONITOR_SQL="
WITH pool_stats AS (
    SELECT
        count(*) FILTER (WHERE state = 'active' AND backend_type = 'client backend') AS active_count,
        count(*) FILTER (WHERE state = 'idle' AND backend_type = 'client backend') AS idle_count,
        count(*) FILTER (WHERE state = 'idle in transaction' AND backend_type = 'client backend') AS idle_in_trans_count,
        count(*) FILTER (WHERE backend_type = 'client backend') AS total_client_connections,
        current_setting('max_connections')::int AS max_conn,
        current_setting('superuser_reserved_connections')::int AS superuser_reserved
    FROM pg_stat_activity
),
lingering_trans AS (
    SELECT
        pid,
        usename,
        client_addr,
        round(extract(epoch from (now() - state_change))::numeric, 1) AS idle_duration_sec,
        query
    FROM pg_stat_activity
    WHERE state = 'idle in transaction'
      AND state_change < now() - (${IDLE_IN_TRANS_WARN_SEC} || ' seconds')::interval
    LIMIT 5
)
SELECT json_build_object(
    'database_name', current_database(),
    'active_connections', p.active_count,
    'idle_connections', p.idle_count,
    'idle_in_transaction', p.idle_in_trans_count,
    'total_checked_out', p.total_client_connections,
    'max_connections', p.max_conn,
    'usable_limit', (p.max_conn - p.superuser_reserved),
    'saturation_pct', round((p.total_client_connections::numeric / p.max_conn) * 100, 2),
    'lingering_idle_in_transaction_count', (SELECT count(*) FROM lingering_trans),
    'lingering_transactions', (SELECT json_agg(lingering_trans) FROM lingering_trans)
)::text
FROM pool_stats p;
"

TELEMETRY_JSON=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "${MONITOR_SQL}" 2>&1)
QUERY_STATUS=$?

if [ ${QUERY_STATUS} -ne 0 ]; then
    log_error "Connection monitor query failed: ${TELEMETRY_JSON}"
    exit ${EXIT_CONNECTION_FAILED}
fi

echo "${TELEMETRY_JSON}"

# ------------------------------------------------------------------------------
# 5. Extract Metrics & Evaluate Thresholds
# ------------------------------------------------------------------------------
SATURATION_PCT=$(echo "${TELEMETRY_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('saturation_pct', 0.0))")
LINGERING_COUNT=$(echo "${TELEMETRY_JSON}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('lingering_idle_in_transaction_count', 0))")

log_info "Connection pool saturation: ${SATURATION_PCT}% (Lingering Idle-in-Transaction: ${LINGERING_COUNT})"

if (( $(echo "${SATURATION_PCT} >= ${CRIT_SATURATION_PCT}" | bc -l 2>/dev/null || python3 -c "print(1 if float('${SATURATION_PCT}') >= ${CRIT_SATURATION_PCT} else 0)") )); then
    log_error "CRITICAL: Connection pool saturation is ${SATURATION_PCT}% (Threshold: >= ${CRIT_SATURATION_PCT}%)!"
    exit ${EXIT_CRIT_THRESHOLD}
fi

if (( $(echo "${SATURATION_PCT} >= ${WARN_SATURATION_PCT}" | bc -l 2>/dev/null || python3 -c "print(1 if float('${SATURATION_PCT}') >= ${WARN_SATURATION_PCT} else 0)") )) || [ "${LINGERING_COUNT}" -gt 0 ]; then
    log_warn "WARNING: Elevated connection pool saturation or lingering transactions detected!"
    exit ${EXIT_WARN_THRESHOLD}
fi

log_info "Connection pool is healthy (${SATURATION_PCT}% saturation)."
exit ${EXIT_HEALTHY}

