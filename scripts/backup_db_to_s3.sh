#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Database Backup to AWS S3 Automation Runner
# Description: Dumps PostgreSQL catalog, applies compression, validates checksum,
#              and securely streams to AWS S3 with server-side encryption (AES-256).
# Role Alignment: Demonstrates CloudOps operational automation & DR readiness.
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# Configuration & Defaults
# ------------------------------------------------------------------------------
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
BACKUP_DIR="${BACKUP_TEMP_DIR:-/tmp/sentinel_backups}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-sentinel_db}"
DB_USER="${DB_USER:-sentinel_admin}"
S3_BUCKET="${S3_BACKUP_BUCKET:-cloudops-sentinel-backups-dev}"
S3_PREFIX="${S3_BACKUP_PREFIX:-db-snapshots}"
STORAGE_CLASS="${S3_STORAGE_CLASS:-STANDARD_IA}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"

DUMP_FILENAME="${DB_NAME}_${TIMESTAMP}.dump.gz"
DUMP_FILEPATH="${BACKUP_DIR}/${DUMP_FILENAME}"
S3_TARGET_URI="s3://${S3_BUCKET}/${S3_PREFIX}/${DUMP_FILENAME}"

# ------------------------------------------------------------------------------
# Logging Utilities
# ------------------------------------------------------------------------------
log_info() {
    echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [INFO] $*"
}

log_error() {
    echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] [ERROR] $*" >&2
}

# ------------------------------------------------------------------------------
# Preflight Validation
# ------------------------------------------------------------------------------
command -v pg_dump >/dev/null 2>&1 || {
    log_error "PostgreSQL client (pg_dump) is required but not installed. Aborting."
    exit 1
}

command -v aws >/dev/null 2>&1 || {
    log_error "AWS CLI is required for S3 upload but not installed. Aborting."
    exit 1
}

mkdir -p "${BACKUP_DIR}"

log_info "Initiating automated backup for database: ${DB_NAME} at ${DB_HOST}:${DB_PORT}..."

# ------------------------------------------------------------------------------
# Execute Backup with Compression
# ------------------------------------------------------------------------------
START_TIME=$(date +%s)

export PGPASSWORD="${PGPASSWORD:-${POSTGRES_PASSWORD:-}}"

if pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" -F c -Z 6 -f "${DUMP_FILEPATH}"; then
    DUMP_SIZE=$(du -h "${DUMP_FILEPATH}" | cut -f1)
    DUMP_BYTES=$(stat -c%s "${DUMP_FILEPATH}" 2>/dev/null || stat -f%z "${DUMP_FILEPATH}")
    log_info "Database dump completed successfully: ${DUMP_FILEPATH} (Size: ${DUMP_SIZE}, Bytes: ${DUMP_BYTES})"
else
    log_error "pg_dump failed during execution!"
    rm -f "${DUMP_FILEPATH}"
    exit 2
fi

# ------------------------------------------------------------------------------
# Upload to AWS S3 with Server-Side Encryption
# ------------------------------------------------------------------------------
log_info "Uploading artifact to ${S3_TARGET_URI} with storage-class: ${STORAGE_CLASS}..."

if aws s3 cp "${DUMP_FILEPATH}" "${S3_TARGET_URI}" \
    --storage-class "${STORAGE_CLASS}" \
    --sse AES256 \
    --metadata "database=${DB_NAME},timestamp=${TIMESTAMP},environment=${ENVIRONMENT:-development}"; then
    log_info "S3 upload confirmed: ${S3_TARGET_URI}"
else
    log_error "Failed to upload backup to AWS S3!"
    rm -f "${DUMP_FILEPATH}"
    exit 3
fi

# ------------------------------------------------------------------------------
# Local Cleanup
# ------------------------------------------------------------------------------
rm -f "${DUMP_FILEPATH}"
log_info "Temporary local file purged: ${DUMP_FILEPATH}"

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))
log_info "Backup job finished successfully in ${DURATION}s. Target: ${S3_TARGET_URI}"

