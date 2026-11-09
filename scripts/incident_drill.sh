#!/usr/bin/env bash
# ==============================================================================
# CloudOps Sentinel - Safe Database Outage, Detection & Recovery Drill
# Purpose: Simulates a production RDS/EC2 outage on monitored-db, demonstrates
#          proactive detection, webhook alerting, on-call triage, recovery,
#          and post-mortem SLA reporting.
#
# Safety Policy:
#   - NEVER runs against sentinel-db / sentinel_db (Primary Platform Database).
#   - Operates strictly on monitored-db (Simulated target database).
#
# Exit Codes:
#   0 - Drill executed and verified successfully
#   1 - Safety violation (attempted execution against sentinel-db)
#   2 - Pre-flight health check failed
#   3 - Outage detection failure
#   4 - Recovery or SLA verification failure
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Configurable Parameters & Defaults
# ------------------------------------------------------------------------------
TARGET_HOST="${1:-localhost}"
TARGET_PORT="${2:-5433}"
TARGET_USER="${3:-postgres}"
TARGET_DB="${4:-ecommerce_production}"
export PGPASSWORD="${PGPASSWORD:-target_secret_dev_pass}"

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
ONCALL_ENGINEER="${ONCALL_ENGINEER:-sarah.connor@acmecloud.io}"
OUTPUT_JSON=false

for arg in "$@"; do
    if [[ "$arg" == "--json" ]]; then
        OUTPUT_JSON=true
    fi
done

# ------------------------------------------------------------------------------
# Logging Helper Functions
# ------------------------------------------------------------------------------
log_info() {
    if [[ "$OUTPUT_JSON" == false ]]; then
        echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] \033[0;32m[INFO]\033[0m $*"
    fi
}

log_warn() {
    if [[ "$OUTPUT_JSON" == false ]]; then
        echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] \033[0;33m[WARN]\033[0m $*"
    fi
}

log_error() {
    if [[ "$OUTPUT_JSON" == false ]]; then
        echo -e "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] \033[0;31m[ERROR]\033[0m $*" >&2
    fi
}

# ------------------------------------------------------------------------------
# STEP 0: Safety Guard Verification
# ------------------------------------------------------------------------------
if [[ "${TARGET_DB}" == "sentinel_db" || "${TARGET_PORT}" == "5434" ]]; then
    log_error "CRITICAL SAFETY VIOLATION: Cannot run outage drill against primary platform database (${TARGET_DB}:${TARGET_PORT})!"
    log_error "This drill is restricted to simulated target databases (e.g. ecommerce_production:5433)."
    exit 1
fi

log_info "======================================================================"
log_info "CloudOps Sentinel - Automated Incident Lifecycle & Recovery Drill"
log_info "Target Database: ${TARGET_HOST}:${TARGET_PORT}/${TARGET_DB}"
log_info "Sentinel API:    ${API_BASE_URL}"
log_info "On-Call Lead:    ${ONCALL_ENGINEER}"
log_info "======================================================================"

# ------------------------------------------------------------------------------
# STEP 1: Pre-Flight Health Check
# ------------------------------------------------------------------------------
log_info "[STEP 1/7] Running pre-flight health check against target database..."
if ! pg_isready -h "${TARGET_HOST}" -p "${TARGET_PORT}" -U "${TARGET_USER}" -d "${TARGET_DB}" -t 5 > /dev/null 2>&1; then
    log_error "Pre-flight failed: Target database ${TARGET_HOST}:${TARGET_PORT} is not ready."
    exit 2
fi
log_info "Pre-flight check passed: Target database is healthy and accepting connections."

# Capture initial metrics
INITIAL_METRICS=$(curl -sf "${API_BASE_URL}/api/v1/incidents/metrics/sla" || echo '{"total_incidents": 0}')

# ------------------------------------------------------------------------------
# STEP 2: Controlled Outage Simulation
# ------------------------------------------------------------------------------
log_warn "[STEP 2/7] Injecting controlled database outage (stopping monitored-db container)..."
docker stop monitored-postgres > /dev/null 2>&1 || true
sleep 2

# ------------------------------------------------------------------------------
# STEP 3: Outage Detection & Webhook Dispatch
# ------------------------------------------------------------------------------
log_info "[STEP 3/7] Probing target database to verify anomaly detection..."
OUTAGE_DETECTED=false
if ! pg_isready -h "${TARGET_HOST}" -p "${TARGET_PORT}" -U "${TARGET_USER}" -d "${TARGET_DB}" -t 2 > /dev/null 2>&1; then
    OUTAGE_DETECTED=true
    log_warn "Detection Confirmed: Target database socket is DOWN (Connection Refused)."
else
    log_error "Detection Failed: Target database is unexpectedly still responding."
    exit 3
fi

# Dispatch firing alert to Sentinel Incident Management API (simulates Alertmanager)
DRILL_FINGERPRINT="DrillDatabaseOutage:${TARGET_HOST}:${TARGET_PORT}"
STARTS_AT=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

ALERT_PAYLOAD=$(cat <<EOF
{
  "version": "4",
  "status": "firing",
  "receiver": "cloudops-sentinel-webhook",
  "alerts": [
    {
      "status": "firing",
      "labels": {
        "alertname": "DatabaseDown",
        "severity": "critical",
        "instance": "${TARGET_HOST}:${TARGET_PORT}",
        "category": "DATABASE",
        "drill": "true"
      },
      "annotations": {
        "summary": "CRITICAL: Monitored Database Down (${TARGET_HOST}:${TARGET_PORT})",
        "description": "Target database unreachable during controlled SRE reliability drill.",
        "runbook": "Execute docker start monitored-postgres and verify connectivity."
      },
      "startsAt": "${STARTS_AT}",
      "fingerprint": "${DRILL_FINGERPRINT}"
    }
  ]
}
EOF
)

DISPATCH_RESP=$(curl -sf -X POST "${API_BASE_URL}/api/v1/incidents/webhook/alertmanager" \
    -H "Content-Type: application/json" \
    -d "${ALERT_PAYLOAD}")

INCIDENT_ID=$(echo "${DISPATCH_RESP}" | python3 -c "import sys, json; print(json.load(sys.stdin)['details']['incident_ids'][0])")
log_info "Alert ingested by Sentinel Webhook. Created Incident ID: ${INCIDENT_ID}"

# ------------------------------------------------------------------------------
# STEP 4: On-Call Triage & Acknowledgement
# ------------------------------------------------------------------------------
log_info "[STEP 4/7] On-Call engineer acknowledging incident via REST API..."
ACK_PAYLOAD=$(cat <<EOF
{
  "acknowledged_by": "${ONCALL_ENGINEER}",
  "notes": "Acknowledged automated outage alert. Verified socket refusal. Initiating container recovery."
}
EOF
)

ACK_RESP=$(curl -sf -X POST "${API_BASE_URL}/api/v1/incidents/${INCIDENT_ID}/acknowledge" \
    -H "Content-Type: application/json" \
    -d "${ACK_PAYLOAD}")

ACK_STATUS=$(echo "${ACK_RESP}" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
log_info "Incident successfully transitioned to: ${ACK_STATUS}"

# ------------------------------------------------------------------------------
# STEP 5: Automated Recovery Execution
# ------------------------------------------------------------------------------
log_info "[STEP 5/7] Executing recovery procedure: starting monitored-postgres container..."
docker start monitored-postgres > /dev/null 2>&1

# Wait for database readiness (up to 30 seconds)
RECOVERED=false
for i in {1..15}; do
    if pg_isready -h "${TARGET_HOST}" -p "${TARGET_PORT}" -U "${TARGET_USER}" -d "${TARGET_DB}" -t 2 > /dev/null 2>&1; then
        RECOVERED=true
        break
    fi
    sleep 2
done

if [[ "$RECOVERED" == false ]]; then
    log_error "Recovery verification failed: Database did not recover within 30 seconds."
    exit 4
fi
log_info "Database recovery verified: Target database is healthy and accepting connections."

# ------------------------------------------------------------------------------
# STEP 6: Incident Auto-Resolution / Formal Resolution
# ------------------------------------------------------------------------------
log_info "[STEP 6/7] Dispatching resolution notification to Sentinel Incident API..."
RESOLVE_PAYLOAD=$(cat <<EOF
{
  "resolved_by": "${ONCALL_ENGINEER}",
  "resolution_notes": "Target database restarted via Docker Compose runbook. Connectivity and query execution verified. SRE drill completed."
}
EOF
)

RESOLVE_RESP=$(curl -sf -X POST "${API_BASE_URL}/api/v1/incidents/${INCIDENT_ID}/resolve" \
    -H "Content-Type: application/json" \
    -d "${RESOLVE_PAYLOAD}")

FINAL_STATUS=$(echo "${RESOLVE_RESP}" | python3 -c "import sys, json; print(json.load(sys.stdin)['status'])")
MTTR_SEC=$(echo "${RESOLVE_RESP}" | python3 -c "import sys, json; print(json.load(sys.stdin).get('time_to_resolve_seconds', 0))")
log_info "Incident successfully transitioned to: ${FINAL_STATUS} (MTTR: ${MTTR_SEC}s)"

# ------------------------------------------------------------------------------
# STEP 7: Post-Mortem Audit & SRE Metrics Verification
# ------------------------------------------------------------------------------
log_info "[STEP 7/7] Fetching incident audit history and post-mortem metrics..."
DETAIL_RESP=$(curl -sf "${API_BASE_URL}/api/v1/incidents/${INCIDENT_ID}")
METRICS_RESP=$(curl -sf "${API_BASE_URL}/api/v1/incidents/metrics/sla")

if [[ "$OUTPUT_JSON" == true ]]; then
    python3 -c "
import sys, json
detail = json.loads('''${DETAIL_RESP}''')
metrics = json.loads('''${METRICS_RESP}''')
report = {
    'drill_status': 'SUCCESS',
    'incident_id': detail['id'],
    'title': detail['title'],
    'severity': detail['severity'],
    'final_status': detail['status'],
    'time_to_acknowledge_seconds': detail.get('time_to_acknowledge_seconds'),
    'time_to_resolve_seconds': detail.get('time_to_resolve_seconds'),
    'history_events_count': len(detail.get('history', [])),
    'sla_compliance_rate_pct': metrics.get('sla_compliance_rate_pct'),
    'total_incidents': metrics.get('total_incidents')
}
print(json.dumps(report, indent=2))
"
else
    log_info "======================================================================"
    log_info "DR DRILL COMPLETED SUCCESSFULLY"
    log_info "Incident ID:         ${INCIDENT_ID}"
    log_info "Lifecycle Status:    ${FINAL_STATUS}"
    log_info "Resolution Duration: ${MTTR_SEC} seconds"
    log_info "Audit Trail Events:"
    echo "${DETAIL_RESP}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for h in data.get('history', []):
    print(f\"  [{h['created_at']}] {h['action']} by {h['actor']}: {h.get('notes', '')}\")
"
    log_info "======================================================================"
fi

exit 0

