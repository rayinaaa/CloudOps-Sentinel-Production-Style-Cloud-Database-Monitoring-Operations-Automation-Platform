"""Health check and database connectivity probes for CloudOps Sentinel."""

import time
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import check_database_connection, get_db
from app.core.logging import logger
from app.schemas.health import DatabaseHealthResponse, LivenessResponse

router = APIRouter(prefix="/health", tags=["Health & Probes"])


@router.get("/live", response_model=LivenessResponse, status_code=status.HTTP_200_OK)
async def liveness_probe() -> LivenessResponse:
    """Kubernetes/Docker liveness probe: indicates if the application server process is running."""
    return LivenessResponse(
        status="UP",
        service=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get(
    "/db",
    response_model=DatabaseHealthResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Database is reachable and responding to ping"},
        503: {"description": "Database connection failed or timed out"},
    },
)
async def database_health_probe(db: AsyncSession = Depends(get_db)):
    """Database connectivity probe: verifies roundtrip SQL execution and latency."""
    start_time = time.perf_counter()
    try:
        result = await db.execute(text("SELECT current_database(), version();"))
        row = result.fetchone()
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not row:
            raise RuntimeError("Database returned empty result for version probe")

        db_name = row[0]
        db_version = row[1]

        return DatabaseHealthResponse(
            status="HEALTHY",
            database=db_name,
            server_version=db_version,
            latency_ms=latency_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        # Log structured error safely internally - NEVER expose credentials to client
        logger.error(
            "Database health probe failed",
            error_type=type(exc).__name__,
            latency_ms=latency_ms,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "UNHEALTHY",
                "database": settings.POSTGRES_DB,
                "server_version": None,
                "latency_ms": latency_ms,
                "error": "Database connectivity check failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe() -> dict:
    """Readiness probe: validates Sentinel metadata database connection before accepting traffic."""
    db_healthy = await check_database_connection()
    if not db_healthy:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "DEGRADED",
                "database_connection": "UNHEALTHY",
                "message": "Failed to query database engine",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    return {
        "status": "READY",
        "database_connection": "HEALTHY",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
