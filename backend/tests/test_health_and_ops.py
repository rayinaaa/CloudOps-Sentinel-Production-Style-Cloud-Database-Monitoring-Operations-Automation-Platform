"""Test suite for CloudOps Sentinel Health and Operational Telemetry Endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock, patch
from fastapi import status
from sqlalchemy.exc import OperationalError
from app.main import app
from app.core.database import get_db


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test service landing route /."""
    response = await client.get("/")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "CloudOps Sentinel" in data["service"]
    assert "health_live" in data
    assert "health_db" in data
    assert "ops_db_summary" in data


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    """Test GET /health/live liveness probe."""
    response = await client.get("/health/live")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "UP"
    assert data["service"] == "CloudOps Sentinel"
    assert "timestamp" in data
    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_database_health_probe_success(client: AsyncClient):
    """Test GET /health/db when PostgreSQL is reachable."""
    response = await client.get("/health/db")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert data["database"] == "sentinel_db"
    assert "PostgreSQL" in data["server_version"]
    assert data["latency_ms"] is not None
    assert data["latency_ms"] >= 0.0
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_database_health_probe_failure_handling(client: AsyncClient):
    """Test GET /health/db failure mode: must return HTTP 503 and never expose credentials."""
    async def mock_failing_db():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError("connection failure", None, None)
        yield mock_session

    app.dependency_overrides[get_db] = mock_failing_db
    try:
        response = await client.get("/health/db")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "UNHEALTHY"
        assert data["error"] == "Database connectivity check failed"
        # Security Verification: Ensure no password or sensitive connection strings are leaked
        assert "password" not in str(data).lower()
        assert "secret" not in str(data).lower()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_ops_database_summary_success(client: AsyncClient):
    """Test GET /ops/db-summary returns comprehensive operational metrics."""
    response = await client.get("/ops/db-summary")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # 1. Identification
    assert data["database_name"] == "sentinel_db"
    assert "PostgreSQL" in data["server_version"]

    # 2. Connection Metrics
    conn = data["connection_metrics"]
    assert conn["active_connections"] >= 0
    assert conn["idle_connections"] >= 0
    assert conn["total_connections"] >= 0
    assert conn["max_connections"] > 0
    assert conn["pool_saturation_pct"] >= 0.0
    assert conn["connection_status"] in ["HEALTHY", "WARNING", "CRITICAL"]

    # 3. Storage Metrics
    storage = data["storage_metrics"]
    assert storage["total_database_size_bytes"] > 0
    assert "total_database_size_human" in storage
    assert isinstance(storage["tables"], list)
    table_names = [t["table_name"] for t in storage["tables"]]
    assert "tenants" in table_names
    assert "app_users" in table_names

    # 4. Tenancy Summary
    tenancy = data["tenancy_summary"]
    assert tenancy["total_tenants"] >= 8
    assert tenancy["active_tenants"] >= 1
    assert tenancy["total_users"] >= 16

    # 5. Metadata
    assert "timestamp" in data
    assert "X-Process-Time" in response.headers


@pytest.mark.asyncio
async def test_ops_database_summary_failure_handling(client: AsyncClient):
    """Test GET /ops/db-summary failure mode: must return HTTP 503 and mask internal errors."""
    async def mock_failing_db():
        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError("catalog corrupt or locked", None, None)
        yield mock_session

    app.dependency_overrides[get_db] = mock_failing_db
    try:
        response = await client.get("/ops/db-summary")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "ERROR"
        assert "password" not in str(data).lower()
        assert "traceback" not in str(data).lower()
    finally:
        app.dependency_overrides.clear()

