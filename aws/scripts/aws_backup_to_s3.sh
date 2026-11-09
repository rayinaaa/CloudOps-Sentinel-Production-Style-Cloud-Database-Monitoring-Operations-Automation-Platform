#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - AWS S3 Production Database Backup Automation
# Operating System: Linux (EC2)
# Dependencies: postgresql-client (pg_dump), awscli, sha256sum, curl
# IAM Authentication: EC2 IAM Instance Profile (Zero hardcoded credentials)
# Encryption: AWS S3 Server-Side Encryption (AES256 or AWS KMS)
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Source Environment Settings
# ------------------------------------------------------------------------------
CONFIG_FILE="/etc/cloudops-sentinel/.env.production"
if [ -f "${CONFIG_FILE}" ]; then
    # shellcheck disable=SC1090
    set -a
    source "${CONFIG_FILE}"
    set +a
fi

DB_HOST="${POSTGRES_SERVER:-localhost}"
DB_PORT="${POSTGRES_PORT:-5432}"
DB_NAME="${POSTGRES_DB:-sentinel_db}"
DB_USER="${POSTGRES_USER:-sentinel_admin}"
export PGPASSWORD="${POSTGRES_PASSWORD}"
export PGSSLMODE="${PGSSLMODE:-require}"

AWS_REGION="${AWS_REGION:-us-east-1}"
S3_BUCKET="${S3_BACKUP_BUCKET:-cloudops-sentinel-backups}"
S3_PREFIX="${S3_BACKUP_PREFIX:-db-snapshots/}"
STORAGE_CLASS="${S3_STORAGE_CLASS:-STANDARD_IA}"
CLOUDWATCH_NAMESPACE="${CLOUDWATCH_NAMESPACE:-CloudOpsSentinel/Databases}"

BACKUP_DIR="/tmp/cloudops-backups"
TIMESTAMP=$(date -u +"%Y%m%d_%H%M%SZ")
SNAPSHOT_FILENAME="${DB_NAME}_${TIMESTAMP}.dump.gz"
SNAPSHOT_PATH="${BACKUP_DIR}/${SNAPSHOT_FILENAME}"
CHECKSUM_PATH="${SNAPSHOT_PATH}.sha256"
LOG_PREFIX="[$(date -u +%FT%TZ)]"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

echo "${LOG_PREFIX} [INFO] Starting automated RDS backup for database: ${DB_NAME} on ${DB_HOST}:${DB_PORT}..."
START_TIME=$(date +%s)

# ------------------------------------------------------------------------------
# 2. Execute pg_dump with Gzip Compression
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] Dumping database via pg_dump stream (SSL enforced)..."
if ! pg_dump -h "${DB_HOST}" -p "${DB_PORT}" -U "${DB_USER}" -d "${DB_NAME}" \
    --format=custom \
    --compress=6 \
    --no-owner \
    --no-privileges \
    --file="${SNAPSHOT_PATH}"; then
    echo "${LOG_PREFIX} [ERROR] Database pg_dump failed!" >&2
    
    # Emit CloudWatch Metric: Backup Failure
    aws cloudwatch put-metric-data \
        --region "${AWS_REGION}" \
        --namespace "${CLOUDWATCH_NAMESPACE}" \
        --metric-name "BackupSuccess" \
        --value 0 \
        --unit Count \
        --dimensions DatabaseName="${DB_NAME}" 2>/dev/null || true
    exit 1
fi

FILE_SIZE_BYTES=$(stat -c%s "${SNAPSHOT_PATH}" 2>/dev/null || stat -f%z "${SNAPSHOT_PATH}")
echo "${LOG_PREFIX} [INFO] pg_dump completed successfully. Local size: ${FILE_SIZE_BYTES} bytes."

# ------------------------------------------------------------------------------
# 3. Compute SHA256 Integrity Checksum
# ------------------------------------------------------------------------------
sha256sum "${SNAPSHOT_PATH}" | awk '{print $1}' > "${CHECKSUM_PATH}"
CHECKSUM=$(cat "${CHECKSUM_PATH}")
echo "${LOG_PREFIX} [INFO] SHA256 Checksum: ${CHECKSUM}"

# ------------------------------------------------------------------------------
# 4. Upload to AWS S3 with SSE-S3 Encryption & Metadata Tags
# ------------------------------------------------------------------------------
S3_TARGET_URI="s3://${S3_BUCKET}/${S3_PREFIX}${SNAPSHOT_FILENAME}"
echo "${LOG_PREFIX} [INFO] Uploading snapshot to ${S3_TARGET_URI} (Storage Class: ${STORAGE_CLASS})..."

aws s3 cp "${SNAPSHOT_PATH}" "${S3_TARGET_URI}" \
    --region "${AWS_REGION}" \
    --storage-class "${STORAGE_CLASS}" \
    --sse AES256 \
    --metadata "database=${DB_NAME},timestamp=${TIMESTAMP},sha256=${CHECKSUM}"

# Also upload checksum sidecar
aws s3 cp "${CHECKSUM_PATH}" "${S3_TARGET_URI}.sha256" \
    --region "${AWS_REGION}" \
    --sse AES256

# ------------------------------------------------------------------------------
# 5. Verify Remote S3 Object Existence
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] Verifying remote S3 upload integrity..."
REMOTE_SIZE=$(aws s3api head-object \
    --region "${AWS_REGION}" \
    --bucket "${S3_BUCKET}" \
    --key "${S3_PREFIX}${SNAPSHOT_FILENAME}" \
    --query ContentLength \
    --output text)

if [ "${REMOTE_SIZE}" -ne "${FILE_SIZE_BYTES}" ]; then
    echo "${LOG_PREFIX} [ERROR] S3 size mismatch! Local: ${FILE_SIZE_BYTES}, S3: ${REMOTE_SIZE}" >&2
    exit 2
fi

END_TIME=$(date +%s)
DURATION_SECONDS=$((END_TIME - START_TIME))
echo "${LOG_PREFIX} [INFO] S3 Backup verified. Elapsed duration: ${DURATION_SECONDS}s."

# ------------------------------------------------------------------------------
# 6. Publish Telemetry to CloudWatch Custom Metrics
# ------------------------------------------------------------------------------
aws cloudwatch put-metric-data \
    --region "${AWS_REGION}" \
    --namespace "${CLOUDWATCH_NAMESPACE}" \
    --metric-data \
    "MetricName=BackupSuccess,Value=1,Unit=Count,Dimensions=[{Name=DatabaseName,Value=${DB_NAME}}]" \
    "MetricName=BackupDurationSeconds,Value=${DURATION_SECONDS},Unit=Seconds,Dimensions=[{Name=DatabaseName,Value=${DB_NAME}}]" \
    "MetricName=BackupSizeBytes,Value=${FILE_SIZE_BYTES},Unit=Bytes,Dimensions=[{Name=DatabaseName,Value=${DB_NAME}}]" 2>/dev/null || true

# ------------------------------------------------------------------------------
# 7. Safe Cleanup of Local Artifacts
# ------------------------------------------------------------------------------
rm -f "${SNAPSHOT_PATH}" "${CHECKSUM_PATH}"
echo "${LOG_PREFIX} [INFO] Local scratch files cleaned. Backup routine completed successfully."

