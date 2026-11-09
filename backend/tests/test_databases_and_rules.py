"""Integration tests for Database Targets, Maintenance Tasks, Alert Rules, and Credential Redaction.

Covers:
- GET & POST /api/v1/databases
- GET /api/v1/operations/tasks (with and without database_id filter, verifying query construction)
- GET & POST /api/v1/alerts/rules
- Structlog sensitive credential redaction processor
"""

import uuid

import pytest
from fastapi import status
from httpx import AsyncClient

from app.core.logging import redact_sensitive_data


@pytest.mark.asyncio
async def test_list_and_register_database(client: AsyncClient):
    """Verifies listing database targets and registering a new instance."""
    # List targets
    list_resp = await client.get("/api/v1/databases")
    assert list_resp.status_code == status.HTTP_200_OK
    assert isinstance(list_resp.json(), list)

    # Register new target
    unique_name = f"test-rds-{uuid.uuid4().hex[:6]}"
    payload = {
        "name": unique_name,
        "engine": "postgresql",
        "host": "localhost",
        "port": 5433,
        "database_name": "ecommerce_production",
        "username": "monitor_agent",
        "environment": "staging",
        "is_active": True,
        "ssl_mode": "require",
    }
    create_resp = await client.post("/api/v1/databases", json=payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    assert data["name"] == unique_name
    assert data["environment"] == "staging"
    assert data["health_status"] == "UNKNOWN"

    # Verify duplicate name rejection (HTTP 409)
    dup_resp = await client.post("/api/v1/databases", json=payload)
    assert dup_resp.status_code == status.HTTP_409_CONFLICT


@pytest.mark.asyncio
async def test_maintenance_tasks_listing_and_filtering(client: AsyncClient):
    """Verifies maintenance task listing and ensures database_id filter behaves correctly."""
    # Unfiltered
    all_resp = await client.get("/api/v1/operations/tasks?limit=10")
    assert all_resp.status_code == status.HTTP_200_OK
    tasks = all_resp.json()
    assert isinstance(tasks, list)

    # Filter with non-existent database UUID (must return empty list, not crash)
    random_id = uuid.uuid4()
    filtered_resp = await client.get(
        f"/api/v1/operations/tasks?database_id={random_id}"
    )
    assert filtered_resp.status_code == status.HTTP_200_OK
    assert filtered_resp.json() == []


@pytest.mark.asyncio
async def test_alert_rules_lifecycle(client: AsyncClient):
    """Verifies listing and creating operational alert rules."""
    rules_resp = await client.get("/api/v1/alerts/rules")
    assert rules_resp.status_code == status.HTTP_200_OK
    rules = rules_resp.json()
    assert isinstance(rules, list)

    # Create new rule
    rule_name = f"ConnectionSatWarning_{uuid.uuid4().hex[:6]}"
    rule_payload = {
        "name": rule_name,
        "metric_name": "connection_pool_usage_pct",
        "operator": "GREATER_THAN",
        "threshold_value": 0.80,
        "severity": "WARNING",
        "is_enabled": True,
        "description": "Trigger warning when connection pool usage exceeds 80%",
    }
    create_resp = await client.post("/api/v1/alerts/rules", json=rule_payload)
    assert create_resp.status_code == status.HTTP_201_CREATED
    data = create_resp.json()
    assert data["name"] == rule_name
    assert data["threshold_value"] == 0.80
    assert data["severity"] == "WARNING"


def test_sensitive_credential_logging_redaction():
    """Unit test for the structlog sensitive data redaction processor."""
    event = {
        "event": "Database connection established",
        "password": "super_secret_password_123",
        "db_secret": "my_top_secret_token",
        "api_key": "xyz_api_key_value",
        "connection_url": "postgresql+asyncpg://admin:super_secret_pw@db.prod.internal:5432/mydb",
        "safe_metric": 42,
    }

    processed = redact_sensitive_data(None, "info", event)

    assert processed["password"] == "[REDACTED]"
    assert processed["db_secret"] == "[REDACTED]"
    assert processed["api_key"] == "[REDACTED]"
    assert "super_secret_pw" not in processed["connection_url"]
    assert "admin:***@db.prod.internal" in processed["connection_url"]
    assert processed["safe_metric"] == 42
