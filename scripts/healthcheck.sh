#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Health & Latency Probe Utility
# Usage: ./scripts/healthcheck.sh [HOST] [PORT] [USER] [DB]
# ==============================================================================

set -euo pipefail

TARGET_HOST="${1:-localhost}"
TARGET_PORT="${2:-5432}"
TARGET_USER="${3:-sentinel_admin}"
TARGET_DB="${4:-sentinel_db}"

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Running Sentinel Health Probe on ${TARGET_USER}@${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}..."

# Check pg_isready
if ! pg_isready -h "${TARGET_HOST}" -p "${TARGET_PORT}" -U "${TARGET_USER}" -d "${TARGET_DB}" -t 5 > /dev/null 2>&1; then
    echo "{\"status\": \"UNHEALTHY\", \"error\": \"PostgreSQL socket not accepting connections\"}"
    exit 1
fi

# Measure query latency and active connection count
START_NS=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time() * 1e9))')

STATS_JSON=$(psql -h "${TARGET_HOST}" -p "${TARGET_PORT}" -U "${TARGET_USER}" -d "${TARGET_DB}" -At -c "
SELECT json_build_object(
    'status', 'HEALTHY',
    'active_connections', (SELECT count(*) FROM pg_stat_activity WHERE state = 'active'),
    'total_connections', (SELECT count(*) FROM pg_stat_activity),
    'max_connections', current_setting('max_connections')::int,
    'server_version', version()
);
" 2>/dev/null || echo "{}")

END_NS=$(date +%s%N 2>/dev/null || python3 -c 'import time; print(int(time.time() * 1e9))')
LATENCY_MS=$(( (END_NS - START_NS) / 1000000 ))

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Probe Complete. Latency: ${LATENCY_MS}ms"
echo "${STATS_JSON}"

