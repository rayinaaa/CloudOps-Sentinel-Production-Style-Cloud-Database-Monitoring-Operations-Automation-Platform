"""Endpoints for managing monitored database instances."""

import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.models.database_instance import DatabaseInstance
from app.schemas.database_instance import (
    DatabaseInstanceCreate,
    DatabaseInstanceRead,
    DatabaseInstanceUpdate,
)

router = APIRouter(prefix="/databases", tags=["Database Targets"])


@router.get("", response_model=List[DatabaseInstanceRead])
async def list_databases(
    environment: Optional[str] = Query(None, description="Filter by environment (production, staging, etc.)"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    db: AsyncSession = Depends(get_db),
) -> List[DatabaseInstance]:
    """Retrieve all monitored database targets with optional environment filtering."""
    query = select(DatabaseInstance)
    if environment:
        query = query.where(DatabaseInstance.environment == environment)
    if is_active is not None:
        query = query.where(DatabaseInstance.is_active == is_active)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("", response_model=DatabaseInstanceRead, status_code=status.HTTP_201_CREATED)
async def register_database(
    payload: DatabaseInstanceCreate,
    db: AsyncSession = Depends(get_db),
) -> DatabaseInstance:
    """Register a new cloud database target for Sentinel telemetry and automation."""
    existing_res = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.name == payload.name)
    )
    if existing_res.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Database target with name '{payload.name}' already exists",
        )

    instance = DatabaseInstance(**payload.model_dump())
    db.add(instance)
    await db.flush()
    await db.refresh(instance)
    return instance


@router.get("/{instance_id}", response_model=DatabaseInstanceRead)
async def get_database(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> DatabaseInstance:
    """Fetch details of a specific database target."""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database target {instance_id} not found",
        )
    return instance


@router.patch("/{instance_id}", response_model=DatabaseInstanceRead)
async def update_database(
    instance_id: uuid.UUID,
    payload: DatabaseInstanceUpdate,
    db: AsyncSession = Depends(get_db),
) -> DatabaseInstance:
    """Update connection parameters or monitoring flags for a target."""
    result = await db.execute(
        select(DatabaseInstance).where(DatabaseInstance.id == instance_id)
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Database target {instance_id} not found",
        )

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        setattr(instance, field, val)

    await db.flush()
    await db.refresh(instance)
    return instance

