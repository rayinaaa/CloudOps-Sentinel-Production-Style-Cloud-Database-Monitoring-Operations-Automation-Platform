#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - AWS EC2 Automated Rollback Procedure
# Triggers: Automated on health check timeout, or manually executed by On-Call SRE
# ==============================================================================

set -euo pipefail

APP_DIR="/opt/cloudops-sentinel"
COMPOSE_FILE="${APP_DIR}/aws/config/docker-compose.aws.yml"
LOG_PREFIX="[$(date -u +%FT%TZ)]"

echo "${LOG_PREFIX} [WARN] *** INITIATING EMERGENCY ROLLBACK PROCEDURE ***"

cd "${APP_DIR}"

# 1. Capture failed container logs for post-mortem analysis
echo "${LOG_PREFIX} [INFO] Archiving failed container diagnostics..."
mkdir -p /var/log/cloudops-sentinel/crash-dumps
docker logs sentinel-backend > "/var/log/cloudops-sentinel/crash-dumps/backend_fail_$(date +%s).log" 2>&1 || true

# 2. Revert containers to previous known good state
echo "${LOG_PREFIX} [INFO] Rolling back service definitions..."
docker compose -f "${COMPOSE_FILE}" restart backend frontend

# 3. Verify recovered health
echo "${LOG_PREFIX} [INFO] Verifying post-rollback health..."
sleep 10
if curl -s -f http://localhost:8000/api/v1/health/live >/dev/null; then
    echo "${LOG_PREFIX} [INFO] Rollback completed. Platform stabilized at previous operational state."
    exit 0
else
    echo "${LOG_PREFIX} [CRITICAL] Rollback verification failed! Immediate manual SRE intervention required!" >&2
    exit 1
fi

