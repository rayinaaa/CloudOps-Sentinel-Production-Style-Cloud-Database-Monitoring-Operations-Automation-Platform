"""CloudOps Sentinel - Main FastAPI Application Entrypoint.

Provides production HTTP endpoints, Prometheus instrumentation, structured logging,
and comprehensive Swagger documentation for Cloud Database Operations.
"""

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.v1.endpoints import health, incidents, ops
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.database import engine
from app.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: logging initialization, telemetry, and graceful shutdown."""
    setup_logging()
    logger.info(
        "Initializing CloudOps Sentinel Platform",
        environment=settings.ENVIRONMENT,
        version=settings.APP_VERSION,
        api_prefix=settings.API_V1_PREFIX,
        db_host=settings.POSTGRES_SERVER,
        db_port=settings.POSTGRES_PORT,
    )

    yield

    logger.info("Gracefully shutting down CloudOps Sentinel Platform")
    # Release pooled database connections to prevent socket leaks on reload/shutdown
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Production-style Cloud Database Monitoring and Operations Automation Platform.\n\n"
        "Provides proactive database health telemetry, connection pool saturation tracking, "
        "storage footprint breakdown, and automated operations."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

# 1. CORS Policy
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 2. Structured Request Logging & Timing Middleware
@app.middleware("http")
async def structured_logging_middleware(request: Request, call_next):
    """Logs every HTTP transaction with execution duration, path, and response code."""
    start_time = time.perf_counter()
    client_ip = request.client.host if request.client else "unknown"

    try:
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Process-Time"] = f"{duration_ms}ms"

        # Exclude high-frequency health probes from noisy log output if in production
        if request.url.path not in ["/metrics"]:
            logger.info(
                "HTTP Request Completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
            )
        return response

    except Exception as exc:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.error(
            "Unhandled Exception during HTTP Request",
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            duration_ms=duration_ms,
            client_ip=client_ip,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "status": "ERROR",
                "message": "Internal server error. Incident has been logged.",
            },
        )


# 3. Prometheus Telemetry Exposition
if settings.PROMETHEUS_METRICS_ENABLED:
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/metrics", "/health/live"],
    )
    instrumentator.instrument(app).expose(app, endpoint="/metrics")

# 4. Mount Direct Top-Level Routes (/health/live, /health/db, /ops/db-summary, /incidents)
app.include_router(health.router)
app.include_router(ops.router)
app.include_router(incidents.router)

# 5. Mount API v1 Aggregator
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get("/", tags=["Root"])
async def root():
    """Service status, quick documentation links, and probe endpoints."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "OPERATIONAL",
        "docs": "/docs",
        "health_live": "/health/live",
        "health_db": "/health/db",
        "ops_db_summary": "/ops/db-summary",
        "incidents": "/incidents",
        "incident_metrics": "/incidents/metrics/sla",
        "metrics": "/metrics",
    }
