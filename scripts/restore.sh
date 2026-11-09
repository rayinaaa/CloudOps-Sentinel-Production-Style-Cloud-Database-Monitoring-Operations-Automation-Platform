#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Restore & DR Validation Utility
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
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5434}"
DB_USER="${DB_USER:-sentinel_admin}"
PRIMARY_DB_NAME="${PRIMARY_DB_NAME:-sentinel_db}"
TEST_RESTORE_DB="${TARGET_TEST_DB:-sentinel_dr_test}"
BACKUP_FILE="${1:-}"

# Exit Code Definitions
EXIT_SUCCESS=0
EXIT_SAFETY_VIOLATION=1
EXIT_VALIDATION_FAILED=2
EXIT_RESTORE_FAILED=3
EXIT_VERIFICATION_FAILED=4

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
# 3. Critical Safety Guard: Never Target Primary Database
# ------------------------------------------------------------------------------
if [ -z "${BACKUP_FILE}" ]; then
    log_error "Usage: $0 <path_to_backup.dump> [target_test_database]"
    exit ${EXIT_SAFETY_VIOLATION}
fi

if [ "${TEST_RESTORE_DB}" == "${PRIMARY_DB_NAME}" ] || [ "${TEST_RESTORE_DB}" == "sentinel_db" ] || [ "${TEST_RESTORE_DB}" == "ecommerce_production" ]; then
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

# A. Verify SHA-256 Checksum if companion .sha256 file exists
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

# B. Non-destructive preflight validation using pg_restore --list
log_info "Inspecting archive Table of Contents (TOC) with pg_restore --list..."
if ! pg_restore --list "${BACKUP_FILE}" >/dev/null 2>&1; then
    log_error "Archive validation failed! File is not a valid PostgreSQL custom-format dump."
    exit ${EXIT_VALIDATION_FAILED}
fi
log_info "Archive passed integrity check. Safe to proceed with test restore."

# ------------------------------------------------------------------------------
# 5. Provision Clean Isolated Test Database
# ------------------------------------------------------------------------------
log_info "Preparing isolated test database '${TEST_RESTORE_DB}' on ${DB_HOST}:${DB_PORT}..."

# Terminate any stray connections to test database and recreate catalog
TERMINATE_SQL="
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE datname = '${TEST_RESTORE_DB}' AND pid <> pg_backend_pid();
"
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -c "${TERMINATE_SQL}" >/dev/null 2>&1 || true

# In PostgreSQL, DROP DATABASE and CREATE DATABASE cannot run in a multi-statement transaction block.
# Execute them as discrete individual statements.
psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -c "DROP DATABASE IF EXISTS ${TEST_RESTORE_DB};" >/dev/null 2>&1 || true

if ! psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "postgres" -c "CREATE DATABASE ${TEST_RESTORE_DB};" >/dev/null 2>&1; then
    log_error "Failed to provision clean test database '${TEST_RESTORE_DB}'."
    exit ${EXIT_RESTORE_FAILED}
fi
log_info "Clean test database '${TEST_RESTORE_DB}' created."

# ------------------------------------------------------------------------------
# 6. Execute Restore into Test Database
# ------------------------------------------------------------------------------
log_info "Restoring archive into '${TEST_RESTORE_DB}'..."
START_RESTORE=$(date +%s)

# pg_restore: --clean --if-exists --no-owner --no-privileges
RESTORE_OUTPUT=$(pg_restore -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TEST_RESTORE_DB}" \
    --no-owner --no-privileges "${BACKUP_FILE}" 2>&1 || true)

END_RESTORE=$(date +%s)
RESTORE_DURATION=$(( END_RESTORE - START_RESTORE ))
log_info "pg_restore execution completed in ${RESTORE_DURATION}s."

# ------------------------------------------------------------------------------
# 7. Post-Restore Verification Drill
# ------------------------------------------------------------------------------
log_info "Running post-restore verification queries on '${TEST_RESTORE_DB}'..."

VERIFY_SQL="
SELECT json_build_object(
    'restored_database', current_database(),
    'tenant_count', (SELECT count(*) FROM tenants),
    'user_count', (SELECT count(*) FROM app_users),
    'active_tenants', (SELECT count(*) FROM tenants WHERE status = 'ACTIVE')
)::text;
"

POST_RESTORE_JSON=$(psql -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${TEST_RESTORE_DB}" \
    -t -A -c "${VERIFY_SQL}" 2>&1)
VERIFY_STATUS=$?

if [ ${VERIFY_STATUS} -ne 0 ] || [ -z "${POST_RESTORE_JSON}" ]; then
    log_error "Post-restore validation failed: Database restored but validation query failed!"
    log_error "${POST_RESTORE_JSON}"
    exit ${EXIT_VERIFICATION_FAILED}
fi

log_info "======================================================================"
log_info "DISASTER RECOVERY RESTORE DRILL SUCCESSFUL!"
log_info "Verified Target: ${TEST_RESTORE_DB}"
log_info "Duration:        ${RESTORE_DURATION}s"
log_info "Verification:    ${POST_RESTORE_JSON}"
log_info "======================================================================"

echo "${POST_RESTORE_JSON}"
exit ${EXIT_SUCCESS}
