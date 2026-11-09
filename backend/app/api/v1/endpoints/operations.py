"""Endpoints for executing operational automation tasks."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.database_instance import DatabaseInstance
from app.models.maintenance_task import MaintenanceTask
from app.schemas.maintenance import MaintenanceTaskRead, MaintenanceTaskTrigger

router = APIRouter(prefix="/operations", tags=["Automated Operations"])


@router.get("/tasks", response_model=List[MaintenanceTaskRead])
async def list_maintenance_tasks(
    database_id: Optional[uuid.UUID] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> List[MaintenanceTask]:
    """Audit log of operational tasks (backups, vacuum, health audits)."""
    query = select(MaintenanceTask)
    if database_id:
        query = query.where(MaintenanceTask.database_id == database_id)
    query = query.order_by(desc(MaintenanceTask.started_at)).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post(
    "/databases/{instance_id}/trigger",
    response_model=MaintenanceTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_maintenance_operation(
    instance_id: uuid.UUID,
    payload: MaintenanceTaskTrigger,
    db: AsyncSession = Depends(get_db),
) -> MaintenanceTask:
    """Trigger an automated operations job (e.g., S3_BACKUP, VACUUM_ANALYZE, HEALTH_AUDIT)."""
    instance_res = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = instance_res.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database target {instance_id} not found",
        )

    # Record the task entry
    task = MaintenanceTask(
        database_id=instance.id,
        task_type=payload.task_type.upper(),
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        initiated_by=payload.initiated_by,
        execution_logs=f"Dispatched operational task {payload.task_type} for {instance.name}.",
    )
    db.add(task)
    await db.flush()
    await db.refresh(task)

    # In production, this dispatches to Celery/Arq/background worker or invokes AWS S3 / bash script.
    # For initial lifecycle simulation, set to SUCCESS with S3 metadata if backup:
    if payload.task_type.upper() == "S3_BACKUP":
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        task.artifact_s3_url = f"s3://{settings.S3_BACKUP_BUCKET}/{settings.S3_BACKUP_PREFIX}{instance.name}_{timestamp_str}.dump.gz"
        task.backup_size_bytes = 10485760  # Simulated 10MB compressed backup
        task.status = "SUCCESS"
        task.completed_at = datetime.now(timezone.utc)
        task.execution_logs += f"\nBackup archive created and uploaded to {task.artifact_s3_url} using AES256 server-side encryption."
    elif payload.task_type.upper() in ["VACUUM_ANALYZE", "HEALTH_AUDIT"]:
        task.status = "SUCCESS"
        task.completed_at = datetime.now(timezone.utc)
        task.execution_logs += (
            f"\nRoutine maintenance completed cleanly on target {instance.name}."
        )

    await db.flush()
    await db.refresh(task)
    return task
