"""Pydantic schemas for health and database liveness probes."""

from typing import Optional
from pydantic import BaseModel, Field


class LivenessResponse(BaseModel):
    """Liveness probe response model."""

    status: str = Field(examples=["UP"], description="Application liveness status")
    service: str = Field(examples=["CloudOps Sentinel"], description="Service identifier")
    environment: str = Field(examples=["development"], description="Runtime environment")
    timestamp: str = Field(description="UTC timestamp")


class DatabaseHealthResponse(BaseModel):
    """Database connectivity health probe response."""

    status: str = Field(examples=["HEALTHY"], description="Database status: HEALTHY or UNHEALTHY")
    database: str = Field(examples=["sentinel_db"], description="Database catalog name")
    server_version: Optional[str] = Field(
        None, examples=["PostgreSQL 16.8 on x86_64-pc-linux-musl"], description="PostgreSQL engine version"
    )
    latency_ms: Optional[float] = Field(None, examples=[1.25], description="Ping roundtrip latency in milliseconds")
    error: Optional[str] = Field(None, description="Error summary without exposing internal credentials")
    timestamp: str = Field(description="UTC timestamp")
