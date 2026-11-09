"""Integration tests for Prometheus, Grafana, and FastAPI metrics telemetry.

Validates:
1. FastAPI /metrics endpoint exposition and formatting
2. Metric increments on route execution
3. PostgreSQL exporter metric collection (pg_up, connection counts, storage)
4. Prometheus scraping target health and alert rule loading
5. Grafana datasource and dashboard provisioning
"""

import base64
import os

import httpx
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_fastapi_metrics_endpoint_format(client: AsyncClient):
    """Verifies that FastAPI /metrics endpoint exposes valid Prometheus metrics."""
    # First invoke a couple endpoints to generate HTTP request metrics
    live_resp = await client.get("/health/live")
    assert live_resp.status_code == 200

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert "text/plain" in metrics_resp.headers.get("content-type", "")

    content = metrics_resp.text
    # Verify core Prometheus metrics are exposed
    assert "http_requests_total" in content
    assert (
        "http_request_duration_seconds" in content
        or "http_request_duration_highr_seconds" in content
    )
    assert "python_info" in content or "python_gc_objects_collected_total" in content


@pytest.mark.asyncio
async def test_fastapi_metrics_counter_increments(client: AsyncClient):
    """Verifies that calling /ops/db-summary increments http_requests_total counter."""
    # Invoke /ops/db-summary
    summary_resp = await client.get("/ops/db-summary")
    assert summary_resp.status_code == 200

    metrics_resp = await client.get("/metrics")
    assert metrics_resp.status_code == 200
    assert 'handler="/ops/db-summary"' in metrics_resp.text


@pytest.mark.asyncio
async def test_database_exporter_live_metrics():
    """Verifies that database exporter (Oracle on 9161 or PostgreSQL on 9187) collects metrics."""
    default_port = "9161" if os.getenv("ORACLE_SERVER") else "9187"
    exporter_url = os.getenv("EXPORTER_URL", f"http://localhost:{default_port}/metrics")
    async with httpx.AsyncClient(timeout=10.0) as ac:
        try:
            resp = await ac.get(exporter_url)
            assert resp.status_code == 200
            content = resp.text
            # Verify exporter metric headers and values
            if "oracledb" in content or "9161" in exporter_url:
                assert "oracledb_up" in content
            else:
                assert "pg_up 1" in content
                assert "pg_stat_activity_count" in content
                assert "pg_database_size_bytes" in content
                assert "pg_stat_database_xact_commit" in content
        except (httpx.ConnectError, httpx.TimeoutException):
            pytest.skip(
                f"Database exporter not reachable at {exporter_url} in current test environment"
            )


@pytest.mark.asyncio
async def test_prometheus_targets_up():
    """Verifies that Prometheus on port 9090 has all monitored scrape targets in UP state."""
    prom_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090/api/v1/targets")
    async with httpx.AsyncClient(timeout=10.0) as ac:
        try:
            resp = await ac.get(prom_url)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "success"

            targets = data.get("data", {}).get("activeTargets", [])
            assert len(targets) >= 3, (
                f"Expected at least 3 scrape targets, found {len(targets)}"
            )

            jobs = {t["labels"]["job"]: t["health"] for t in targets}
            assert "oracle-exporter" in jobs or "postgres-exporter" in jobs
            assert "prometheus" in jobs
            assert jobs["prometheus"] == "up"
            assert "sentinel-backend" in jobs
            assert jobs["sentinel-backend"] == "up"
        except httpx.ConnectError:
            pytest.skip(
                f"Prometheus not reachable at {prom_url} in current test environment"
            )


@pytest.mark.asyncio
async def test_prometheus_alert_rules_loaded():
    """Verifies that Prometheus has loaded all CloudOps Sentinel alert rules."""
    prom_rules_url = os.getenv(
        "PROMETHEUS_RULES_URL", "http://localhost:9090/api/v1/rules"
    )
    async with httpx.AsyncClient(timeout=10.0) as ac:
        try:
            resp = await ac.get(prom_rules_url)
            assert resp.status_code == 200
            data = resp.json()
            assert data.get("status") == "success"

            groups = data.get("data", {}).get("groups", [])
            group_names = [g["name"] for g in groups]
            assert "cloudops_database_alerts" in group_names
            assert "cloudops_api_alerts" in group_names

            all_rules = []
            for g in groups:
                for r in g.get("rules", []):
                    all_rules.append(r["name"])

            expected_rules = [
                "DatabaseDown",
                "DatabaseConnectionPoolCritical",
                "DatabaseConnectionPoolWarning",
                "LowBufferCacheHitRatio",
                "DatabaseDeadlocksDetected",
                "HighApiErrorRate5xx",
                "HighApiLatencyP95",
            ]
            for rule in expected_rules:
                assert rule in all_rules, f"Missing expected alert rule: {rule}"
        except httpx.ConnectError:
            pytest.skip(
                f"Prometheus not reachable at {prom_rules_url} in current test environment"
            )


@pytest.mark.asyncio
async def test_grafana_datasource_provisioning():
    """Verifies that Grafana on port 3001 has provisioned Prometheus datasource."""
    grafana_ds_url = os.getenv("GRAFANA_URL", "http://localhost:3001/api/datasources")
    auth_header = "Basic " + base64.b64encode(b"admin:admin").decode("utf-8")

    async with httpx.AsyncClient(
        timeout=10.0, headers={"Authorization": auth_header}
    ) as ac:
        try:
            resp = await ac.get(grafana_ds_url)
            assert resp.status_code == 200
            datasources = resp.json()
            prom_ds = next(
                (ds for ds in datasources if ds.get("type") == "prometheus"), None
            )
            assert prom_ds is not None, "Prometheus datasource not found in Grafana"
            assert prom_ds.get("isDefault") is True
            assert prom_ds.get("url") == "http://prometheus:9090"
        except httpx.ConnectError:
            pytest.skip(
                f"Grafana not reachable at {grafana_ds_url} in current test environment"
            )


@pytest.mark.asyncio
async def test_grafana_dashboard_provisioning():
    """Verifies that the CloudOps Sentinel dashboard is provisioned with 14 panels."""
    grafana_dash_url = (
        "http://localhost:3001/api/dashboards/uid/cloudops-sentinel-overview"
    )
    auth_header = "Basic " + base64.b64encode(b"admin:admin").decode("utf-8")

    async with httpx.AsyncClient(
        timeout=10.0, headers={"Authorization": auth_header}
    ) as ac:
        try:
            resp = await ac.get(grafana_dash_url)
            assert resp.status_code == 200
            dashboard_data = resp.json().get("dashboard", {})
            assert (
                dashboard_data.get("title")
                == "CloudOps Sentinel - Database & Operations Platform"
            )

            panels = dashboard_data.get("panels", [])
            # Filter non-row visualization panels
            visual_panels = [p for p in panels if p.get("type") != "row"]
            assert len(visual_panels) == 14, (
                f"Expected 14 visualization panels, found {len(visual_panels)}"
            )

            panel_titles = [p.get("title") for p in visual_panels]
            assert "Database Availability" in panel_titles
            assert "Connection Pool Saturation" in panel_titles
            assert "Buffer Cache Hit Ratio" in panel_titles
            assert "Catalog Storage Footprint" in panel_titles
            assert "Throughput (Trans/sec)" in panel_titles
            assert "API p95 Response Latency" in panel_titles
            assert "Connection States Breakdown" in panel_titles
            assert "Connection Saturation % Trend" in panel_titles
            assert "Database Transaction Rate (Commit vs. Rollback)" in panel_titles
            assert "Buffer Pool Cache Activity (Hits vs. Disk Reads)" in panel_titles
            assert "HTTP Traffic Rate by Status Code" in panel_titles
            assert "API Latency Percentiles (p50, p90, p95, p99)" in panel_titles
            assert "Process CPU Usage %" in panel_titles
            assert "Process Resident Memory Footprint (RSS)" in panel_titles
        except httpx.ConnectError:
            pytest.skip(
                f"Grafana not reachable at {grafana_dash_url} in current test environment"
            )
