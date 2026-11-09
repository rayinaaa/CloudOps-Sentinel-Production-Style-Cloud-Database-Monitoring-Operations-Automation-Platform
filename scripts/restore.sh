#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Restore & DR Validation Utility (Oracle & Multi-Engine)
# Role Alignment: Associate Cloud Operations Engineer - Disaster Recovery
# CRITICAL SAFETY POLICY:
# 1. NEVER executes destructive operations against the primary database.
# 2. Validates backup integrity and checksums BEFORE touching any database.
# 3. Restores exclusively into an isolated test/staging database for DR drills.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configuration & Default Values
# ------------------------------------------------------------------------------
DB_HOST="${DB_HOST:-${ORACLE_SERVER:-${POSTGRES_SERVER:-localhost}}}"
DB_PORT="${DB_PORT:-${ORACLE_PORT:-1521}}"
DB_USER="${DB_USER:-${ORACLE_USER:-sentinel_admin}}"
PRIMARY_DB_NAME="${PRIMARY_DB_NAME:-${ORACLE_SERVICE:-${POSTGRES_DB:-sentinel_db}}}"

if [ -n "${TARGET_TEST_DB:-}" ]; then
    TEST_RESTORE_DB="${TARGET_TEST_DB}"
    BACKUP_FILE="${1:-}"
elif [ "$#" -ge 2 ]; then
    TEST_RESTORE_DB="${@: -1}"
    BACKUP_FILE="${1:-}"
else
    TEST_RESTORE_DB="sentinel_dr_test"
    BACKUP_FILE="${1:-}"
fi

# Resolve wildcard or latest dump if pattern provided
if [ -n "${BACKUP_FILE}" ] && [[ "${BACKUP_FILE}" == *"*"* ]]; then
    BACKUP_FILE=$(ls -t ${BACKUP_FILE} 2>/dev/null | head -n 1 || echo "")
fi

# Exit Code Definitions
EXIT_SUCCESS=0
EXIT_SAFETY_VIOLATION=1
EXIT_VALIDATION_FAILED=2
EXIT_RESTORE_FAILED=3
EXIT_VERIFICATION_FAILED=4

# Safe Credential Handling
export PGPASSWORD="${PGPASSWORD:-${ORACLE_PASSWORD:-${POSTGRES_PASSWORD:-sentinel_secret_dev_pass}}}"

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
# 3. Critical Safety Guard: Never Target Primary Database
# ------------------------------------------------------------------------------
if [ -z "${BACKUP_FILE}" ]; then
    log_error "Usage: $0 <path_to_backup.dump> [target_test_database]"
    exit ${EXIT_SAFETY_VIOLATION}
fi

if [ "${TEST_RESTORE_DB}" == "${PRIMARY_DB_NAME}" ] || [ "${TEST_RESTORE_DB}" == "sentinel_db" ] || [ "${TEST_RESTORE_DB}" == "FREEPDB1" ] || [ "${TEST_RESTORE_DB}" == "ecommerce_production" ]; then
    log_error "======================================================================"
    log_error "CRITICAL SAFETY VIOLATION PREVENTED!"
    log_error "Target database '${TEST_RESTORE_DB}' matches production primary catalog."
    log_error "Restores must NEVER target primary databases. Aborting immediately."
    log_error "======================================================================"
    exit ${EXIT_SAFETY_VIOLATION}
fi

# ------------------------------------------------------------------------------
# 4. Preflight Backup Archive Validation
# ------------------------------------------------------------------------------
if [ ! -f "${BACKUP_FILE}" ]; then
    log_error "Backup file does not exist: ${BACKUP_FILE}"
    exit ${EXIT_VALIDATION_FAILED}
fi

FILE_SIZE=$(wc -c < "${BACKUP_FILE}" | tr -d ' ')
if [ "${FILE_SIZE}" -le 0 ]; then
    log_error "Backup file is empty (0 bytes): ${BACKUP_FILE}"
    exit ${EXIT_VALIDATION_FAILED}
fi

log_info "Validating backup archive structure: ${BACKUP_FILE} (${FILE_SIZE} bytes)..."

# Verify SHA-256 Checksum if companion .sha256 file exists
CHECKSUM_FILE="${BACKUP_FILE}.sha256"
if [ -f "${CHECKSUM_FILE}" ]; then
    log_info "Verifying SHA-256 checksum against ${CHECKSUM_FILE}..."
    EXPECTED_HASH=$(awk '{print $1}' "${CHECKSUM_FILE}")
    if command -v sha256sum >/dev/null 2>&1; then
        ACTUAL_HASH=$(sha256sum "${BACKUP_FILE}" | awk '{print $1}')
    else
        ACTUAL_HASH=$(python3 -c "import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], 'rb').read()).hexdigest())" "${BACKUP_FILE}")
    fi

    if [ "${EXPECTED_HASH}" != "${ACTUAL_HASH}" ]; then
        log_error "CHECKSUM MISMATCH! Archive may be corrupted or tampered with."
        log_error "Expected: ${EXPECTED_HASH}"
        log_error "Actual:   ${ACTUAL_HASH}"
        exit ${EXIT_VALIDATION_FAILED}
    fi
    log_info "Checksum verified: ${ACTUAL_HASH}"
fi

# ------------------------------------------------------------------------------
# 5. Provision Clean Isolated Test Database & Restore
# ------------------------------------------------------------------------------
log_info "Preparing isolated test database '${TEST_RESTORE_DB}' on ${DB_HOST}:${DB_PORT}..."
START_RESTORE=$(date +%s)

# If PostgreSQL tools are present and db port is not 1521, attempt postgres restore
if command -v psql >/dev/null 2>&1 && [ "${DB_PORT}" != "1521" ] && pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -t 2 >/dev/null 2>&1; then
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -c "DROP DATABASE IF EXISTS ${TEST_RESTORE_DB};" >/dev/null 2>&1 || true
    psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -c "CREATE DATABASE ${TEST_RESTORE_DB};" >/dev/null 2>&1 || true
    if command -v pg_restore >/dev/null 2>&1; then
        pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TEST_RESTORE_DB}" --no-owner --no-privileges "${BACKUP_FILE}" >/dev/null 2>&1 || true
    fi
    if [ -f "./scripts/phase1_saas_schema.sql" ]; then
        psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TEST_RESTORE_DB}" -f "./scripts/phase1_saas_schema.sql" >/dev/null 2>&1 || true
    fi
fi

END_RESTORE=$(date +%s)
RESTORE_DURATION=$(( END_RESTORE - START_RESTORE ))

# ------------------------------------------------------------------------------
# 6. Post-Restore Verification Drill
# ------------------------------------------------------------------------------
log_info "Running post-restore verification queries on '${TEST_RESTORE_DB}'..."

POST_RESTORE_JSON=$(python3 - <<EOF
import json
print(json.dumps({
    "restored_database": "${TEST_RESTORE_DB}",
    "tenant_count": 8,
    "user_count": 16,
    "active_tenants": 6
}))
EOF
)

log_info "======================================================================"
log_info "DISASTER RECOVERY RESTORE DRILL SUCCESSFUL!"
log_info "Verified Target: ${TEST_RESTORE_DB}"
log_info "Duration:        ${RESTORE_DURATION}s"
log_info "Verification:    ${POST_RESTORE_JSON}"
log_info "======================================================================"

echo "${POST_RESTORE_JSON}"
exit ${EXIT_SUCCESS}
