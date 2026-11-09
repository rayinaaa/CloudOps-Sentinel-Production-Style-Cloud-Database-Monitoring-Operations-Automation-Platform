"""Unit tests for Sentinel health probe endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Test service info returned at root /."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OPERATIONAL"
    assert "CloudOps Sentinel" in data["service"]


@pytest.mark.asyncio
async def test_liveness_probe(client: AsyncClient):
    """Test Kubernetes/Docker liveness probe /api/v1/health/live."""
    response = await client.get("/api/v1/health/live")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "UP"
    assert "timestamp" in data

