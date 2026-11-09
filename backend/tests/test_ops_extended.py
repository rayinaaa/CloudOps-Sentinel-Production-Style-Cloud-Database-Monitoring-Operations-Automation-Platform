"""Extended integration test suite for CloudOps Sentinel Operations Endpoints.

Covers:
- GET /api/v1/ops/tenants
- GET /api/v1/ops/infra
- GET /api/v1/ops/backups
- POST /api/v1/ops/backups/trigger (success and security validation)
- GET /api/v1/ops/logs
"""

import pytest
from httpx import AsyncClient
from fastapi import status


@pytest.mark.asyncio
async def test_list_tenants_endpoint(client: AsyncClient):
    """Verifies listing tenants with live user allocations."""
    resp = await client.get("/api/v1/ops/tenants")
    assert resp.status_code == status.HTTP_200_OK
    tenants = resp.json()
    assert isinstance(tenants, list)
    assert len(tenants) >= 1

    first = tenants[0]
    assert "id" in first
    assert "name" in first
    assert "slug" in first
    assert "plan" in first
    assert "status" in first
    assert "current_users" in first
    assert "max_users" in first
    assert first["current_users"] >= 0


@pytest.mark.asyncio
async def test_infra_telemetry_endpoint(client: AsyncClient):
    """Verifies infrastructure container and process telemetry."""
    resp = await client.get("/api/v1/ops/infra")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()

    assert data["process_cpu_pct"] >= 0.0
    assert data["memory_rss_bytes"] > 0
    assert "MB" in data["memory_rss_human"]
    assert data["open_file_descriptors"] > 0
    assert data["uptime_seconds"] >= 0.0
    assert isinstance(data["services"], list)
    assert len(data["services"]) == 7

    service_names = [s["name"] for s in data["services"]]
    assert "sentinel-postgres" in service_names
    assert "sentinel-backend" in service_names
    assert "sentinel-prometheus" in service_names


@pytest.mark.asyncio
async def test_list_backups_endpoint(client: AsyncClient):
    """Verifies retrieval of recent disaster recovery backup catalog."""
    resp = await client.get("/api/v1/ops/backups")
    assert resp.status_code == status.HTTP_200_OK
    backups = resp.json()
    assert isinstance(backups, list)
    assert len(backups) >= 1

    bk = backups[0]
    assert "id" in bk
    assert "s3_url" in bk
    assert bk["s3_url"].startswith("s3://")
    assert "checksum_sha256" in bk
    assert len(bk["checksum_sha256"]) >= 32
    assert bk["status"] == "COMPLETED"


@pytest.mark.asyncio
async def test_trigger_backup_success(client: AsyncClient):
    """Verifies successful invocation of live S3 backup trigger."""
    resp = await client.post("/api/v1/ops/backups/trigger?database_name=sentinel_db")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()

    assert data["database_name"] == "sentinel_db"
    assert data["status"] == "COMPLETED"
    assert data["s3_url"].startswith("s3://")
    assert "sentinel_db" in data["s3_url"]
    assert len(data["checksum_sha256"]) >= 32


@pytest.mark.asyncio
async def test_trigger_backup_invalid_identifier_rejection(client: AsyncClient):
    """Verifies that malicious or path-traversal database names are rejected with HTTP 400."""
    malicious_inputs = [
        "../../../etc/passwd",
        "sentinel_db; DROP TABLE tenants; --",
        "db$(whoami)",
        "db name with spaces",
        "a" * 70,  # Exceeds max length
    ]

    for bad_name in malicious_inputs:
        resp = await client.post(f"/api/v1/ops/backups/trigger?database_name={bad_name}")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST, f"Expected 400 for input: {bad_name}"
        data = resp.json()
        assert "Invalid database name" in data["detail"]


@pytest.mark.asyncio
async def test_list_operational_logs(client: AsyncClient):
    """Verifies operational log stream retrieval and limit parameter enforcement."""
    resp = await client.get("/api/v1/ops/logs?limit=4")
    assert resp.status_code == status.HTTP_200_OK
    logs = resp.json()
    assert isinstance(logs, list)
    assert len(logs) == 4

    log_entry = logs[0]
    assert "id" in log_entry
    assert "timestamp" in log_entry
    assert "level" in log_entry
    assert log_entry["level"] in ["INFO", "WARN", "ERROR"]
    assert "component" in log_entry
    assert "message" in log_entry

