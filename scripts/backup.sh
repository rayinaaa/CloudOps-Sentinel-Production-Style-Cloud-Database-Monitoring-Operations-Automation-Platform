#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Backup Automation Utility
# Role Alignment: Associate Cloud Operations Engineer - Disaster Recovery
# Description: Generates compressed PostgreSQL custom-format backups, computes
#              SHA256 checksums, validates archive integrity, and applies retention.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configuration & Default Values
# ------------------------------------------------------------------------------
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5434}"
DB_NAME="${DB_NAME:-sentinel_db}"
DB_USER="${DB_USER:-sentinel_admin}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

# Exit Code Definitions
EXIT_SUCCESS=0
EXIT_CONFIG_ERROR=1
EXIT_CONNECTION_FAILED=2
EXIT_DUMP_FAILED=3
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
# 3. Preflight Validation
# ------------------------------------------------------------------------------
if ! command -v pg_dump >/dev/null 2>&1; then
    log_error "Required tool 'pg_dump' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! command -v pg_restore >/dev/null 2>&1; then
    log_error "Required tool 'pg_restore' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

if ! command -v pg_isready >/dev/null 2>&1; then
    log_error "Required tool 'pg_isready' is not installed or not in PATH."
    exit ${EXIT_CONFIG_ERROR}
fi

mkdir -p "${BACKUP_DIR}"

# Validate database connection before dumping
if ! pg_isready -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -t 5 >/dev/null 2>&1; then
    log_error "Database ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME} is unreachable."
    exit ${EXIT_CONNECTION_FAILED}
fi

# ------------------------------------------------------------------------------
# 4. Execute Custom-Format Compressed Backup
# ------------------------------------------------------------------------------
BACKUP_TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_FILENAME="${DB_NAME}_${BACKUP_TIMESTAMP}.dump"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILENAME}"
CHECKSUM_PATH="${BACKUP_PATH}.sha256"
METADATA_PATH="${BACKUP_PATH}.meta.json"

log_info "Starting database dump for '${DB_NAME}' from ${DB_HOST}:${DB_PORT}..."
START_TIME=$(date +%s)

# Execute pg_dump in Custom Format (-F c) with zlib compression (-Z 6)
if ! pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    -F c -Z 6 -f "${BACKUP_PATH}"; then
    log_error "pg_dump failed to extract catalog!"
    rm -f "${BACKUP_PATH}"
    exit ${EXIT_DUMP_FAILED}
fi

END_TIME=$(date +%s)
DURATION=$(( END_TIME - START_TIME ))

# ------------------------------------------------------------------------------
# 5. Checksum Generation & Archive Integrity Verification
# ------------------------------------------------------------------------------
log_info "Calculating SHA-256 checksum for backup artifact..."
if command -v sha256sum >/dev/null 2>&1; then
    SHA256_HASH=$(sha256sum "${BACKUP_PATH}" | awk '{print $1}')
elif command -v shasum >/dev/null 2>&1; then
    SHA256_HASH=$(shasum -a 256 "${BACKUP_PATH}" | awk '{print $1}')
else
    SHA256_HASH=$(python3 -c "import hashlib; print(hashlib.sha256(open('${BACKUP_PATH}', 'rb').read()).hexdigest())")
fi

echo "${SHA256_HASH}  ${BACKUP_FILENAME}" > "${CHECKSUM_PATH}"
FILE_SIZE_BYTES=$(wc -c < "${BACKUP_PATH}" | tr -d ' ')

# Critical: Validate archive integrity before accepting
log_info "Validating dump archive structure with pg_restore --list..."
if ! pg_restore --list "${BACKUP_PATH}" >/dev/null 2>&1; then
    log_error "Integrity check failed: Dump archive is corrupted or unreadable!"
    rm -f "${BACKUP_PATH}" "${CHECKSUM_PATH}"
    exit ${EXIT_VERIFICATION_FAILED}
fi

# ------------------------------------------------------------------------------
# 6. Generate Metadata Manifest
# ------------------------------------------------------------------------------
cat <<EOF > "${METADATA_PATH}"
{
    "database": "${DB_NAME}",
    "host": "${DB_HOST}",
    "port": ${DB_PORT},
    "backup_file": "${BACKUP_FILENAME}",
    "file_size_bytes": ${FILE_SIZE_BYTES},
    "duration_seconds": ${DURATION},
    "sha256_checksum": "${SHA256_HASH}",
    "format": "PostgreSQL Custom Format (pg_dump -F c)",
    "compression": "zlib-level-6",
    "created_at": "$(timestamp)",
    "integrity_verified": true
}
EOF

log_info "Backup completed successfully in ${DURATION}s."
log_info "Artifact: ${BACKUP_PATH} (${FILE_SIZE_BYTES} bytes)"
log_info "SHA256:   ${SHA256_HASH}"
log_info "Manifest: ${METADATA_PATH}"

# ------------------------------------------------------------------------------
# 7. Retention Policy Enforcement
# ------------------------------------------------------------------------------
log_info "Pruning backups older than ${RETENTION_DAYS} days in ${BACKUP_DIR}..."
find "${BACKUP_DIR}" -name "${DB_NAME}_*.dump*" -type f -mtime +"${RETENTION_DAYS}" -delete 2>/dev/null || true

exit ${EXIT_SUCCESS}

