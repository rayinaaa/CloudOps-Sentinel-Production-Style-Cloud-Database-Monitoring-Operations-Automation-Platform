"""Pydantic schemas for operational database metrics and summary."""

from typing import List, Optional
from pydantic import BaseModel, Field


class ConnectionMetrics(BaseModel):
    """PostgreSQL connection pool and activity metrics."""

    active_connections: int = Field(..., description="Connections actively executing a query")
    idle_connections: int = Field(..., description="Connections idle and awaiting commands")
    idle_in_transaction: int = Field(..., description="Connections idling inside open transactions")
    total_connections: int = Field(..., description="Total connections currently open")
    max_connections: int = Field(..., description="Configured maximum connections limit")
    usable_connections_limit: int = Field(..., description="Max connections minus reserved superuser slots")
    pool_saturation_pct: float = Field(..., description="Percentage of connection pool utilized")
    connection_status: str = Field(..., description="Status evaluation: HEALTHY, WARNING, CRITICAL")


class TableStorageMetric(BaseModel):
    """Storage footprint breakdown for an individual database table."""

    table_name: str
    approximate_row_count: Optional[int] = None
    table_data_size: str
    index_size: str
    total_disk_size: str
    pct_of_public_schema: Optional[float] = None


class StorageMetrics(BaseModel):
    """Database catalog and table-level disk usage."""

    total_database_size_bytes: int
    total_database_size_human: str
    tables: List[TableStorageMetric]


class TenancySummary(BaseModel):
    """Summary of multi-tenant SaaS fleet."""

    total_tenants: int
    active_tenants: int
    suspended_tenants: int
    total_users: int


class DatabaseOperationalSummary(BaseModel):
    """Comprehensive operational database status response."""

    database_name: str
    server_version: str
    connection_metrics: ConnectionMetrics
    storage_metrics: StorageMetrics
    tenancy_summary: TenancySummary
    timestamp: str


class TenantDetail(BaseModel):
    """Detailed tenant overview with live user allocation."""

    id: str
    name: str
    slug: str
    plan: str
    status: str
    max_users: int
    max_storage_bytes: int
    current_users: int
    created_at: str


class InfraServiceStatus(BaseModel):
    """Health status of an infrastructure container / process."""

    name: str
    component: str
    status: str
    port: int
    latency_ms: Optional[float] = None


class InfraMetrics(BaseModel):
    """Host and container infrastructure telemetry."""

    process_cpu_pct: float
    memory_rss_bytes: int
    memory_rss_human: str
    memory_vms_bytes: int
    memory_vms_human: str
    open_file_descriptors: int
    uptime_seconds: float
    python_version: str
    services: List[InfraServiceStatus]
    timestamp: str


class OperationalLogItem(BaseModel):
    """Structured operational log entry for auditing."""

    id: str
    timestamp: str
    level: str
    component: str
    message: str
    details: Optional[str] = None


class BackupItem(BaseModel):
    """Backup execution history and S3 disaster recovery snapshot."""

    id: str
    task_id: str
    database_name: str
    task_type: str
    status: str
    size_bytes: int
    size_human: str
    s3_url: str
    checksum_sha256: str
    started_at: str
    completed_at: Optional[str] = None
    duration_seconds: Optional[float] = None

