#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - AWS EC2 Production Deployment Automation
# Workflow: Preflight Probes -> Safety Backup -> Migrations -> Zero-Downtime Rollout -> Verification
# ==============================================================================

set -euo pipefail

APP_DIR="/opt/cloudops-sentinel"
COMPOSE_FILE="${APP_DIR}/aws/config/docker-compose.aws.yml"
CONFIG_FILE="/etc/cloudops-sentinel/.env.production"
BACKUP_SCRIPT="${APP_DIR}/aws/scripts/aws_backup_to_s3.sh"
ROLLBACK_SCRIPT="${APP_DIR}/aws/scripts/rollback.sh"
LOG_PREFIX="[$(date -u +%FT%TZ)]"

echo "${LOG_PREFIX} [INFO] Initiating CloudOps Sentinel production deployment..."

cd "${APP_DIR}"

# ------------------------------------------------------------------------------
# 1. Preflight Validations
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] [1/5] Running preflight system checks..."
if [ ! -f "${CONFIG_FILE}" ]; then
    echo "${LOG_PREFIX} [FATAL] Configuration file ${CONFIG_FILE} does not exist!" >&2
    exit 1
fi

if ! docker info &>/dev/null; then
    echo "${LOG_PREFIX} [FATAL] Docker daemon is not running!" >&2
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Automated Pre-Deployment Safety Backup
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] [2/5] Taking pre-deployment safety snapshot to S3..."
if [ -x "${BACKUP_SCRIPT}" ]; then
    "${BACKUP_SCRIPT}" || {
        echo "${LOG_PREFIX} [ERROR] Safety backup failed. Aborting deployment before modifying database." >&2
        exit 2
    }
else
    echo "${LOG_PREFIX} [WARN] Backup script not found or not executable. Proceeding with caution."
fi

# ------------------------------------------------------------------------------
# 3. Pull / Build Images
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] [3/5] Building & packaging production container images..."
docker compose -f "${COMPOSE_FILE}" build --no-cache frontend backend

# ------------------------------------------------------------------------------
# 4. Apply Database Migrations
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] [4/5] Executing database schema migrations (Alembic)..."
docker compose -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head || {
    echo "${LOG_PREFIX} [FATAL] Database migration failed! Triggering emergency rollback..." >&2
    if [ -x "${ROLLBACK_SCRIPT}" ]; then
        "${ROLLBACK_SCRIPT}"
    fi
    exit 3
}

# ------------------------------------------------------------------------------
# 5. Service Rollout & Health Probing
# ------------------------------------------------------------------------------
echo "${LOG_PREFIX} [INFO] [5/5] Launching updated containers..."
docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans

echo "${LOG_PREFIX} [INFO] Waiting for service health checks..."
HEALTHY=0
for i in {1..12}; do
    echo "${LOG_PREFIX} [INFO] Health probe attempt ${i}/12..."
    if curl -s -f http://localhost:8000/api/v1/health/live >/dev/null && \
       curl -s -f http://localhost:8000/api/v1/health/db >/dev/null && \
       curl -s -f -I http://localhost:80 >/dev/null; then
        HEALTHY=1
        break
    fi
    sleep 5
done

if [ "${HEALTHY}" -eq 1 ]; then
    echo "${LOG_PREFIX} [INFO] Deployment SUCCESSFUL! All services healthy and accepting ingress."
    exit 0
else
    echo "${LOG_PREFIX} [FATAL] Health probe timed out! Initiating automated rollback..." >&2
    if [ -x "${ROLLBACK_SCRIPT}" ]; then
        "${ROLLBACK_SCRIPT}"
    fi
    exit 4
fi

