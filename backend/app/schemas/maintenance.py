"""Pydantic schemas for operational maintenance tasks."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MaintenanceTaskTrigger(BaseModel):
    task_type: str = Field(
        ..., description="S3_BACKUP, VACUUM_ANALYZE, HEALTH_AUDIT, FAILOVER_TEST"
    )
    initiated_by: str = Field(default="user:ops_engineer")


class MaintenanceTaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    database_id: uuid.UUID
    task_type: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    artifact_s3_url: Optional[str] = None
    backup_size_bytes: Optional[int] = None
    execution_logs: Optional[str] = None
    initiated_by: str
    created_at: datetime
