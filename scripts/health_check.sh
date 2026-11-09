#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Health Check Probe Utility
# Role Alignment: Associate Cloud Operations Engineer - Operational Monitoring
# Description: Validates network reachability, measures query roundtrip latency,
#              monitors connection saturation, and reports structured status.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configuration & Default Values
# ------------------------------------------------------------------------------
DB_HOST="${DB_HOST:-${POSTGRES_SERVER:-localhost}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5434}}"
DB_NAME="${DB_NAME:-${POSTGRES_DB:-sentinel_db}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-sentinel_admin}}"
TIMEOUT_SEC="${HEALTH_CHECK_TIMEOUT:-5}"
LATENCY_WARN_MS="${LATENCY_WARN_THRESHOLD_MS:-200}"

# Exit Code Standard Definitions
EXIT_HEALTHY=0
EXIT_CONFIG_ERROR=1
EXIT_CONNECTION_FAILED=2
EXIT_DEGRADED=3

# Safe Credential Handling: read from environment, never command line flags
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
# 3. Preflight Dependency Checks
# ------------------------------------------------------------------------------
if ! command -v psql >/dev/null 2>&1; then
    log_error "PostgreSQL client utility 'psql' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! command -v pg_isready >/dev/null 2>&1; then
    log_error "PostgreSQL client utility 'pg_isready' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

# ------------------------------------------------------------------------------
# 4. Socket & Service Liveness Check
# ------------------------------------------------------------------------------
log_info "Initiating CloudOps Sentinel database health probe on ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}..."

if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t "${TIMEOUT_SEC}" >/dev/null 2>&1; then
    log_error "PostgreSQL socket at ${DB_HOST}:${DB_PORT} is not accepting connections!"
    echo "{\"status\": \"UNREACHABLE\", \"host\": \"${DB_HOST}\", \"port\": ${DB_PORT}, \"database\": \"${DB_NAME}\", \"timestamp\": \"$(timestamp)\"}"
    exit ${EXIT_CONNECTION_FAILED}
fi

# ------------------------------------------------------------------------------
# 5. Measure Latency & Gather Deep Telemetry
# ------------------------------------------------------------------------------
START_TIME_MS=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time() * 1000))')

PROBE_SQL="
SELECT json_build_object(
    'status', 'HEALTHY',
    'database', current_database(),
    'server_version', version(),
    'active_connections', (SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND backend_type = 'client backend'),
    'idle_connections', (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle' AND backend_type = 'client backend'),
    'idle_in_transaction', (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle in transaction' AND backend_type = 'client backend'),
    'max_connections', current_setting('max_connections')::int,
    'cache_hit_ratio', (
        SELECT round(blks_hit::numeric / nullif(blks_hit + blks_read, 0), 4)
        FROM pg_stat_database WHERE datname = current_database()
    )
)::text;
"

RAW_OUTPUT=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "${PROBE_SQL}" 2>&1)
QUERY_STATUS=$?

END_TIME_MS=$(date +%s%3N 2>/dev/null || python3 -c 'import time; print(int(time.time() * 1000))')
ROUNDTRIP_LATENCY_MS=$(( END_TIME_MS - START_TIME_MS ))

if [ ${QUERY_STATUS} -ne 0 ]; then
    log_error "Database responded to socket but query execution failed: ${RAW_OUTPUT}"
    echo "{\"status\": \"DEGRADED\", \"error\": \"Query execution failed\", \"latency_ms\": ${ROUNDTRIP_LATENCY_MS}, \"timestamp\": \"$(timestamp)\"}"
    exit ${EXIT_DEGRADED}
fi

# ------------------------------------------------------------------------------
# 6. Evaluate Operational Thresholds & Status
# ------------------------------------------------------------------------------
log_info "Health probe succeeded in ${ROUNDTRIP_LATENCY_MS}ms."

if [ "${ROUNDTRIP_LATENCY_MS}" -gt "${LATENCY_WARN_MS}" ]; then
    log_warn "Latency threshold breached: ${ROUNDTRIP_LATENCY_MS}ms > ${LATENCY_WARN_MS}ms limit."
    echo "${RAW_OUTPUT}"
    exit ${EXIT_DEGRADED}
fi

# Output JSON telemetry payload
echo "${RAW_OUTPUT}"
exit ${EXIT_HEALTHY}

