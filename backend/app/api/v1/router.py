"""API v1 Aggregator Router."""

from fastapi import APIRouter
from app.api.v1.endpoints import (
    alerts,
    databases,
    health,
    incidents,
    metrics,
    operations,
    ops,
)

api_v1_router = APIRouter()

api_v1_router.include_router(health.router)
api_v1_router.include_router(ops.router)
api_v1_router.include_router(databases.router)
api_v1_router.include_router(metrics.router)
api_v1_router.include_router(alerts.router)
api_v1_router.include_router(incidents.router)
api_v1_router.include_router(operations.router)
