"""Integration tests for CloudOps Sentinel Incident Management, Alertmanager Webhook, and SLA Engine."""

import uuid

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_incident_success(client: AsyncClient):
    """Verifies incident creation via REST API, default status, and initial audit history."""
    payload = {
        "title": "PostgreSQL Connection Saturation Alert",
        "description": "Active connection pool utilization exceeded 85% on replica.",
        "severity": "HIGH",
        "source": "ALERTMANAGER",
        "component": "DATABASE",
        "target_instance": "monitored-postgres:5433",
        "fingerprint": f"test_pool_sat_{uuid.uuid4().hex[:8]}",
        "metadata_json": {"active_conns": 85, "max_conns": 100},
    }
    resp = await client.post("/api/v1/incidents/", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == payload["title"]
    assert data["severity"] == "HIGH"
    assert data["status"] == "OPEN"
    assert data["component"] == "DATABASE"
    assert data["target_instance"] == "monitored-postgres:5433"
    assert data["time_to_acknowledge_seconds"] is None
    assert data["time_to_resolve_seconds"] is None

    # Fetch incident detail to verify audit history
    incident_id = data["id"]
    detail_resp = await client.get(f"/api/v1/incidents/{incident_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert len(detail["history"]) >= 1
    assert detail["history"][0]["action"] == "CREATED"
    assert detail["history"][0]["to_status"] == "OPEN"


@pytest.mark.asyncio
async def test_list_incidents_with_filtering(client: AsyncClient):
    """Verifies listing incidents with status and severity filters."""
    # List all
    all_resp = await client.get("/api/v1/incidents/")
    assert all_resp.status_code == 200
    incidents = all_resp.json()
    assert isinstance(incidents, list)
    assert len(incidents) >= 1

    # Filter by status=OPEN
    open_resp = await client.get("/api/v1/incidents/?status=OPEN")
    assert open_resp.status_code == 200
    for inc in open_resp.json():
        assert inc["status"] == "OPEN"

    # Filter by severity=CRITICAL
    crit_resp = await client.get("/api/v1/incidents/?severity=CRITICAL")
    assert crit_resp.status_code == 200
    for inc in crit_resp.json():
        assert inc["severity"] == "CRITICAL"


@pytest.mark.asyncio
async def test_acknowledge_and_resolve_lifecycle(client: AsyncClient):
    """Verifies complete state machine transitions from OPEN to ACKNOWLEDGED to RESOLVED."""
    # 1. Create
    create_payload = {
        "title": "Buffer Cache Hit Ratio Degradation",
        "description": "Cache hit ratio dropped below 90% SLA.",
        "severity": "CRITICAL",
        "source": "HEALTH_CHECK_PROBE",
        "component": "DATABASE",
        "target_instance": "sentinel-postgres:5432",
    }
    create_resp = await client.post("/api/v1/incidents/", json=create_payload)
    assert create_resp.status_code == 201
    inc_id = create_resp.json()["id"]

    # 2. Acknowledge
    ack_payload = {
        "acknowledged_by": "oncall_sre",
        "notes": "Acknowledged page; auditing slow queries in pg_stat_statements.",
    }
    ack_resp = await client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge", json=ack_payload
    )
    assert ack_resp.status_code == 200
    ack_data = ack_resp.json()
    assert ack_data["status"] == "ACKNOWLEDGED"
    assert ack_data["acknowledged_by"] == "oncall_sre"
    assert ack_data["acknowledged_at"] is not None

    # 3. Resolve
    resolve_payload = {
        "resolved_by": "oncall_sre",
        "resolution_notes": "Created missing composite index on orders(tenant_id, created_at). Cache hit ratio restored to 99.1%.",
    }
    res_resp = await client.post(
        f"/api/v1/incidents/{inc_id}/resolve", json=resolve_payload
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()
    assert res_data["status"] == "RESOLVED"
    assert res_data["resolved_by"] == "oncall_sre"
    assert res_data["resolution_notes"] == resolve_payload["resolution_notes"]
    assert res_data["resolved_at"] is not None
    assert res_data["time_to_resolve_seconds"] is not None

    # 4. Verify full audit trail
    detail_resp = await client.get(f"/api/v1/incidents/{inc_id}")
    assert detail_resp.status_code == 200
    history = detail_resp.json()["history"]
    actions = [h["action"] for h in history]
    assert "CREATED" in actions
    assert "ACKNOWLEDGED" in actions
    assert "RESOLVED" in actions


@pytest.mark.asyncio
async def test_state_machine_guards(client: AsyncClient):
    """Verifies that invalid status transitions and missing resolution notes are rejected."""
    # Create incident
    create_resp = await client.post(
        "/api/v1/incidents/",
        json={"title": "Guard Validation Incident", "severity": "LOW"},
    )
    inc_id = create_resp.json()["id"]

    # Resolving without required resolution_notes should fail with 422
    invalid_resolve = await client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={"resolved_by": "engineer"},
    )
    assert invalid_resolve.status_code == 422

    # Resolve properly
    await client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={
            "resolved_by": "engineer",
            "resolution_notes": "Proper resolution notes.",
        },
    )

    # Attempting to acknowledge an already RESOLVED incident must return 400
    ack_after_resolve = await client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge",
        json={"acknowledged_by": "engineer"},
    )
    assert ack_after_resolve.status_code == 400
    assert "already RESOLVED" in ack_after_resolve.json()["detail"]

    # Attempting to resolve an already RESOLVED incident must return 400
    res_again = await client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={"resolved_by": "engineer", "resolution_notes": "Another note."},
    )
    assert res_again.status_code == 400


@pytest.mark.asyncio
async def test_alertmanager_webhook_deduplication_and_autoresolve(client: AsyncClient):
    """Verifies that Alertmanager dispatches create incidents, deduplicate firing alerts, and auto-resolve."""
    fingerprint = f"AMTestAlert_{uuid.uuid4().hex[:8]}"

    # 1. First firing dispatch -> creates incident
    payload_firing_1 = {
        "version": "4",
        "status": "firing",
        "receiver": "cloudops-sentinel-webhook",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "DatabaseDeadlocksDetected",
                    "severity": "warning",
                    "instance": "monitored-postgres:5433",
                    "category": "DATABASE",
                },
                "annotations": {
                    "summary": "Deadlocks detected on database ecommerce_production",
                    "description": "Transactions deadlocked in last 5m.",
                },
                "fingerprint": fingerprint,
            }
        ],
    }
    resp1 = await client.post(
        "/api/v1/incidents/webhook/alertmanager", json=payload_firing_1
    )
    assert resp1.status_code == 200
    res1_data = resp1.json()
    assert res1_data["details"]["firing_created"] == 1
    incident_id = res1_data["details"]["incident_ids"][0]

    # Verify created incident properties
    inc_resp = await client.get(f"/api/v1/incidents/{incident_id}")
    assert inc_resp.json()["status"] == "OPEN"
    assert inc_resp.json()["severity"] == "HIGH"  # 'warning' maps to HIGH

    # 2. Duplicate firing dispatch -> updates existing incident without duplicate ticket
    resp2 = await client.post(
        "/api/v1/incidents/webhook/alertmanager", json=payload_firing_1
    )
    assert resp2.status_code == 200
    res2_data = resp2.json()
    assert res2_data["details"]["firing_updated"] == 1
    assert res2_data["details"]["incident_ids"][0] == incident_id

    # 3. Resolved dispatch -> auto-resolves existing incident
    payload_resolved = {
        "version": "4",
        "status": "resolved",
        "receiver": "cloudops-sentinel-webhook",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": "DatabaseDeadlocksDetected",
                    "severity": "warning",
                    "instance": "monitored-postgres:5433",
                },
                "fingerprint": fingerprint,
            }
        ],
    }
    resp3 = await client.post(
        "/api/v1/incidents/webhook/alertmanager", json=payload_resolved
    )
    assert resp3.status_code == 200
    assert resp3.json()["details"]["auto_resolved"] == 1

    # Verify incident is now RESOLVED
    inc_after = await client.get(f"/api/v1/incidents/{incident_id}")
    assert inc_after.json()["status"] == "RESOLVED"
    assert inc_after.json()["resolved_by"] == "alertmanager_webhook"


@pytest.mark.asyncio
async def test_manual_and_automated_escalation(client: AsyncClient):
    """Verifies manual escalation and automated SLA evaluation runner."""
    # Create incident
    create_resp = await client.post(
        "/api/v1/incidents/",
        json={"title": "Escalation Candidate", "severity": "CRITICAL"},
    )
    inc_id = create_resp.json()["id"]

    # Manual escalation to Level 2
    esc_payload = {
        "actor": "sre_primary",
        "new_level": 2,
        "reason": "Outage uncontained after initial mitigation attempt; paging engineering lead.",
    }
    esc_resp = await client.post(
        f"/api/v1/incidents/{inc_id}/escalate", json=esc_payload
    )
    assert esc_resp.status_code == 200
    assert esc_resp.json()["escalation_level"] == 2
    assert esc_resp.json()["escalated_at"] is not None

    # Automated escalation evaluation sweep
    eval_resp = await client.post("/api/v1/incidents/escalate")
    assert eval_resp.status_code == 200
    assert isinstance(eval_resp.json(), list)


@pytest.mark.asyncio
async def test_incident_metrics_and_summary_report(client: AsyncClient):
    """Verifies MTTA, MTTR, SLA compliance calculation and executive reporting."""
    # SLA metrics endpoint
    metrics_resp = await client.get("/api/v1/incidents/metrics/sla")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()
    assert "total_incidents" in metrics
    assert "open_incidents" in metrics
    assert "resolved_incidents" in metrics
    assert "sla_compliance_rate_pct" in metrics
    assert "by_severity" in metrics
    assert metrics["by_severity"]["CRITICAL"] >= 1
    assert metrics["sla_compliance_rate_pct"] >= 0.0

    # Executive report endpoint
    report_resp = await client.get("/api/v1/incidents/reports/summary")
    assert report_resp.status_code == 200
    report = report_resp.json()
    assert report["report_title"] == "CloudOps Sentinel Incident & Reliability Report"
    assert "metrics" in report
    assert "recent_resolved_incidents" in report
