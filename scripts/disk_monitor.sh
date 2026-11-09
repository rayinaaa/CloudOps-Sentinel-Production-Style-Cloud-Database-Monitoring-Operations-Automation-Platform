#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Storage & Disk Capacity Monitor
# Role Alignment: Associate Cloud Operations Engineer - Capacity Planning
# Description: Evaluates filesystem usage, PostgreSQL database catalog size,
#              detects table/index disk consumption, and triggers capacity alerts.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configuration & Thresholds
# ------------------------------------------------------------------------------
DB_HOST="${DB_HOST:-${POSTGRES_SERVER:-localhost}}"
DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5434}}"
DB_NAME="${DB_NAME:-${POSTGRES_DB:-sentinel_db}}"
DB_USER="${DB_USER:-${POSTGRES_USER:-sentinel_admin}}"
DATA_DIR="${PGDATA_DIR:-/}"
WARN_THRESHOLD_PCT="${DISK_WARN_THRESHOLD:-75}"
CRIT_THRESHOLD_PCT="${DISK_CRIT_THRESHOLD:-85}"

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
if ! command -v psql >/dev/null 2>&1; then
    log_error "PostgreSQL client utility 'psql' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! command -v df >/dev/null 2>&1; then
    log_error "Utility 'df' is not available."
    exit ${EXIT_CONFIG_ERROR}
fi

log_info "Initiating disk capacity audit for ${DB_NAME} on ${DB_HOST}:${DB_PORT}..."

# ------------------------------------------------------------------------------
# 4. Filesystem Storage Audit
# ------------------------------------------------------------------------------
DF_LINE=$(df -Pk "${DATA_DIR}" | tail -1)
FS_TOTAL_KB=$(echo "${DF_LINE}" | awk '{print $2}')
FS_USED_KB=$(echo "${DF_LINE}" | awk '{print $3}')
FS_AVAIL_KB=$(echo "${DF_LINE}" | awk '{print $4}')
FS_PERCENT=$(echo "${DF_LINE}" | awk '{print $5}' | tr -d '%')
MOUNT_POINT=$(echo "${DF_LINE}" | awk '{print $6}')

# Ensure numeric values to prevent malformed SQL interpolation
if ! [[ "${FS_PERCENT}" =~ ^[0-9]+$ ]]; then
    FS_PERCENT=0
fi
if ! [[ "${FS_AVAIL_KB}" =~ ^[0-9]+$ ]]; then
    FS_AVAIL_KB=0
fi

log_info "Filesystem (${MOUNT_POINT}): ${FS_PERCENT}% used (Available: $(( FS_AVAIL_KB / 1024 )) MB of $(( FS_TOTAL_KB / 1024 )) MB)"

# ------------------------------------------------------------------------------
# 5. Database Catalog & Relation Size Audit
# ------------------------------------------------------------------------------
DB_QUERY="
WITH relation_data AS (
    SELECT
        c.relname AS relation_name,
        pg_total_relation_size(c.oid) AS total_bytes,
        pg_size_pretty(pg_total_relation_size(c.oid)) AS total_human
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind = 'r'
    ORDER BY total_bytes DESC
    LIMIT 5
)
SELECT json_build_object(
    'database_name', current_database(),
    'catalog_size_bytes', pg_database_size(current_database()),
    'catalog_size_human', pg_size_pretty(pg_database_size(current_database())),
    'filesystem_percent_used', ${FS_PERCENT},
    'filesystem_available_mb', $(( FS_AVAIL_KB / 1024 )),
    'top_relations', (SELECT json_agg(relation_data) FROM relation_data)
)::text;
"

TELEMETRY_JSON=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t -A -c "${DB_QUERY}" 2>&1 | tr '\r\n' ' ')
QUERY_STATUS=$?

if [ ${QUERY_STATUS} -ne 0 ]; then
    log_error "Failed to query database catalog size: ${TELEMETRY_JSON}"
    exit ${EXIT_CONNECTION_FAILED}
fi

# Print Telemetry Payload
echo "${TELEMETRY_JSON}"

# ------------------------------------------------------------------------------
# 6. Evaluate Operational Thresholds
# ------------------------------------------------------------------------------
if [ "${FS_PERCENT}" -ge "${CRIT_THRESHOLD_PCT}" ]; then
    log_error "CRITICAL: Disk usage on ${MOUNT_POINT} is at ${FS_PERCENT}% (Threshold: >= ${CRIT_THRESHOLD_PCT}%)!"
    exit ${EXIT_CRIT_THRESHOLD}
elif [ "${FS_PERCENT}" -ge "${WARN_THRESHOLD_PCT}" ]; then
    log_warn "WARNING: Disk usage on ${MOUNT_POINT} is at ${FS_PERCENT}% (Threshold: >= ${WARN_THRESHOLD_PCT}%)!"
    exit ${EXIT_WARN_THRESHOLD}
fi

log_info "Storage capacity within nominal bounds (${FS_PERCENT}% < ${WARN_THRESHOLD_PCT}%)."
exit ${EXIT_HEALTHY}
