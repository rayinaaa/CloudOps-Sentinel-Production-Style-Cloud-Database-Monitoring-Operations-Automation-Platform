"""Endpoints for operational alert rules and incident management."""

import uuid
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.core.database import get_db
from app.models.alert import AlertRule, AlertIncident
from app.schemas.alert import AlertRuleCreate, AlertRuleRead, AlertIncidentRead

router = APIRouter(prefix="/alerts", tags=["Alerts & Incidents"])


@router.get("/rules", response_model=List[AlertRuleRead])
async def list_alert_rules(
    db: AsyncSession = Depends(get_db),
) -> List[AlertRule]:
    """List all configured anomaly detection rules."""
    result = await db.execute(select(AlertRule).order_by(AlertRule.name))
    return list(result.scalars().all())


@router.post("/rules", response_model=AlertRuleRead, status_code=status.HTTP_201_CREATED)
async def create_alert_rule(
    payload: AlertRuleCreate,
    db: AsyncSession = Depends(get_db),
) -> AlertRule:
    """Create a new threshold rule for database metrics."""
    rule = AlertRule(**payload.model_dump())
    db.add(rule)
    await db.flush()
    await db.refresh(rule)
    return rule


@router.get("/incidents", response_model=List[AlertIncidentRead])
async def list_incidents(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
) -> List[AlertIncident]:
    """List alert incidents with optional status filter (OPEN, ACKNOWLEDGED, RESOLVED)."""
    query = select(AlertIncident).order_by(desc(AlertIncident.triggered_at))
    if status:
        query = query.where(AlertIncident.status == status)
    if severity:
        query = query.where(AlertIncident.severity == severity)

    result = await db.execute(query)
    return list(result.scalars().all())


@router.post("/incidents/{incident_id}/acknowledge", response_model=AlertIncidentRead)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    acknowledged_by: str = "ops_engineer",
    db: AsyncSession = Depends(get_db),
) -> AlertIncident:
    """Acknowledge an open operational alert incident."""
    result = await db.execute(
        select(AlertIncident).where(AlertIncident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    incident.status = "ACKNOWLEDGED"
    incident.acknowledged_by = acknowledged_by
    await db.flush()
    await db.refresh(incident)
    return incident


@router.post("/incidents/{incident_id}/resolve", response_model=AlertIncidentRead)
async def resolve_incident(
    incident_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AlertIncident:
    """Mark an operational alert incident as resolved."""
    result = await db.execute(
        select(AlertIncident).where(AlertIncident.id == incident_id)
    )
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    incident.status = "RESOLVED"
    incident.resolved_at = datetime.now(timezone.utc)
    await db.flush()
    await db.refresh(incident)
    return incident

